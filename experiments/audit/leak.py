"""Audit item 1: future-data leak test, stronger than tests/.

For each origin O and each method, forecasts for origin O are computed three times, each in a fresh forecaster
with every module cache cleared:
  base   the real input tables
  del    every row dated after O deleted from every input table the method can reach
  wild   every row dated after O replaced by wild values (series values and n_providers, panel prices and providers,
         plus fake entrant offers added after O)
Input tables perturbed: runs/series/series_daily.csv (harness store and analog's direct read) and the offer panel
built from rental_observations (prov, fragility), perturbed on the RAW rows before panel.load's key construction.
Forecasts go through harness.forecast (no scoring, no val log). Compare q10/q50/q90 bit for bit.

Order test: one forecaster instance run origin by origin in forward order and another in reverse order, compared
with the fresh-per-origin base forecasts.

Usage: PYTHONPATH=src OMP_NUM_THREADS=2 .venv/bin/python experiments/audit/leak.py METHOD [--origins a,b,..]
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from gpuf import data, harness, methods, panel

OUT = Path(__file__).resolve().parent / "results"
RUNS = data.ROOT / "runs" / "audit"
OUT.mkdir(parents=True, exist_ok=True)
RUNS.mkdir(parents=True, exist_ok=True)

SPECS = {
    "drift": ("drift", {}),
    "mix": ("mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}),
    "analog": ("analog", {"pool": "all", "k": 600, "drop": ["n14", "sign"], "cap": "2026-11-06"}),
    "prov": ("prov", {"L": 1, "W": 21, "gate": "dyn"}),
    "prov_cal": ("prov", {"L": 1, "W": 21, "gate": "dyn", "cal": True, "ret_mkt": False}),
    "fragility": ("fragility", {"mode": "mix", "boost": 20, "bkind": "any"}),
    "gbm": ("gbm", {"mode": "full", "train": "all", "save_importance": False}),
    "fm2_live": ("fm2_live", {"ctx_len": 16, "lo": 0.15}),
    "chronos": ("chronos", {"centre": "last"}),
}
D = lambda s: dt.date.fromisoformat(s).toordinal()
ORIGINS = ["2026-08-20", "2026-08-31", "2026-09-10", "2026-09-21", "2026-09-30", "2026-10-06",
           "2026-10-13", "2026-10-21", "2026-10-30"]

SERIES = pd.read_csv(data.series_path(), dtype={"series_id": str}, low_memory=False)
SERIES_DAY = pd.to_datetime(SERIES["date"]).map(pd.Timestamp.toordinal).astype(np.int64).to_numpy()
CAT = data.load_catalog()
META = harness.static_meta(CAT)
HEAD = data.universe("rental_headline")
_all = [s for s in data.universe("rental_all") if s not in HEAD]
SIDS = HEAD + list(np.random.default_rng(2026).choice(_all, 60, replace=False))


def raw_panel() -> pd.DataFrame:
    import duckdb
    frames = []
    for s in panel.SOURCES:
        q = f"""select source_id src, instrument_class cls, gpu_model gpu, pricing_tier tier, cast(dt as date) d,
                       provider, coalesce(region_raw,'') region, coalesce(sku_raw,'') sku,
                       coalesce(cast(gpu_count as varchar),'') gc, usd_per_gpu_hour price
                from read_parquet('{panel.OBS}/source_id={s}/*/*.parquet', hive_partitioning=true)
                where usd_per_gpu_hour is not null"""
        frames.append(duckdb.sql(q).df())
    df = pd.concat(frames, ignore_index=True)
    df["day"] = pd.to_datetime(df["d"]).map(lambda x: x.date().toordinal()).astype(np.int64)
    return df


RAW = raw_panel()


def build_panel(df: pd.DataFrame) -> pd.DataFrame:
    """panel.load()'s key construction, applied to a (possibly perturbed) raw frame."""
    base = df["provider"] + "|" + df["region"] + "|" + df["sku"] + "|" + df["gc"]
    df = df.assign(base=base).sort_values(["src", "cls", "gpu", "tier", "day", "base", "price"], kind="stable")
    occ = df.groupby(["src", "cls", "gpu", "tier", "day", "base"]).cumcount()
    df["key"] = df["base"] + "#" + occ.astype(str)
    return df[["src", "cls", "gpu", "tier", "day", "key", "provider", "price"]].reset_index(drop=True)


def perturb(o: int, kind: str, seed: int):
    rng = np.random.default_rng(seed)
    s, r = SERIES.copy(), RAW.copy()
    late_s, late_r = SERIES_DAY > o, r["day"].to_numpy() > o
    if kind == "del":
        s, r = s[~late_s], r[~late_r]
    elif kind == "wild":
        s.loc[late_s, "value"] = s.loc[late_s, "value"] * np.exp(rng.uniform(-3, 3, late_s.sum()))
        s.loc[late_s, "n_providers"] = rng.integers(1, 500, late_s.sum())
        s.loc[late_s, "n_obs"] = rng.integers(1, 5000, late_s.sum())
        r.loc[late_r, "price"] = r.loc[late_r, "price"].to_numpy() * np.exp(rng.uniform(-3, 3, late_r.sum()))
        flip = late_r & (rng.random(len(r)) < 0.2)
        r.loc[flip, "provider"] = rng.choice(r["provider"].unique(), flip.sum())
        fake = r[late_r].sample(frac=0.2, random_state=seed).copy()
        fake["region"] = "audit_fake"
        fake["provider"] = "audit_fake_provider"
        fake["price"] = fake["price"] * np.exp(rng.uniform(-2, 2, len(fake)))
        r = pd.concat([r, fake], ignore_index=True)
    return s, r


def install(series_df: pd.DataFrame, raw_df: pd.DataFrame, tag: str):
    """Point every input path at the given tables and clear every module-level cache."""
    path = RUNS / f"series_{sys.argv[1]}_{tag}.csv"
    series_df.to_csv(path, index=False)
    data.series_path = lambda p=str(path): p
    data.load_store.cache_clear()
    pnl = build_panel(raw_df)
    panel.load = functools.lru_cache(maxsize=1)(lambda p=pnl: p)
    panel._index.cache_clear()
    from gpuf.methods import analog, fragility
    analog._TABLES.clear()
    fragility._C.clear()
    try:
        from gpuf.methods import gbm
        gbm._CODES.clear()
    except Exception:
        pass
    return data.load_store(str(path))


def _cheat_factory():
    """Positive control: reads the series file from disk (as analog does) and peeks at the day after the origin."""
    def f(sid, days, vals, origin_day, horizons, ctx):
        df = _cheat_factory.cache.get(data.series_path())
        if df is None:
            df = pd.read_csv(data.series_path(), usecols=["series_id", "date", "value"])
            df["day"] = pd.to_datetime(df["date"]).map(pd.Timestamp.toordinal)
            _cheat_factory.cache = {data.series_path(): df}
        nxt = df[(df.series_id == sid) & (df.day == origin_day + 1)]["value"]
        v = float(nxt.iloc[0]) if len(nxt) else float(vals[-1])
        return {h: (v, v, v) for h in horizons}
    return f


_cheat_factory.cache = {}
SPECS["cheat"] = ("cheat", {})


def _cheat_panel():
    """Positive control for the panel: median of the series' offers on the last panel day, whatever its date."""
    def f(sid, days, vals, origin_day, horizons, ctx):
        if not panel.supported(sid):
            return None
        g = panel._index()[panel.parse_sid(sid)]
        v = float(g.loc[g["day"] == g["day"].max(), "price"].median())
        return {h: (v, v, v) for h in horizons}
    return f


SPECS["cheat_panel"] = ("cheat_panel", {})


def run(method, origins, store, inst=None):
    m, p = SPECS[method]
    f = inst or ({"cheat": _cheat_factory, "cheat_panel": _cheat_panel}[m]() if m.startswith("cheat")
                 else methods.get(m, **p))
    fc, _ = harness.forecast(f, origins, SIDS, (1, 3, 7), store, META)
    return fc.sort_values(["series_id", "origin_day", "horizon_days"]).reset_index(drop=True), f


def compare(a, b):
    k = ["series_id", "origin_day", "horizon_days"]
    m = a.merge(b, on=k, how="outer", suffixes=("_a", "_b"), indicator=True)
    rows_diff = int((m["_merge"] != "both").sum())
    mm = m[m["_merge"] == "both"]
    q = ["q10", "q50", "q90"]
    neq = np.zeros(len(mm), bool)
    for c in q:
        neq |= mm[c + "_a"].to_numpy() != mm[c + "_b"].to_numpy()
    mx = max(float(np.max(np.abs(np.log(mm[c + "_a"].to_numpy() / mm[c + "_b"].to_numpy())))) if len(mm) else 0.0 for c in q)
    return {"rows": int(len(mm)), "rows_only_one_side": rows_diff, "cells_not_bit_identical": int(neq.sum()),
            "max_abs_log_diff": mx, "series_differing": sorted(mm.loc[neq, "series_id"].unique().tolist())[:10]}


def main():
    method = sys.argv[1]
    origins = [D(x) for x in (sys.argv[sys.argv.index("--origins") + 1].split(",") if "--origins" in sys.argv else ORIGINS)]
    res = {"method": method, "spec": SPECS[method], "n_sids": len(SIDS), "origins": [dt.date.fromordinal(o).isoformat() for o in origins],
           "perturbation": {}, "order": {}}
    t0 = time.time()
    base = {}
    store0 = install(SERIES, RAW, "real")
    for o in origins:
        base[o], _ = run(method, [o], store0)
        install(SERIES, RAW, "real")
    for o in origins:
        for kind in ("del", "wild"):
            s, r = perturb(o, kind, seed=o % 10007)
            st = install(s, r, f"{kind}")
            fc, _ = run(method, [o], st)
            res["perturbation"][f"{dt.date.fromordinal(o)}|{kind}"] = compare(base[o], fc)
            print(method, dt.date.fromordinal(o), kind, res["perturbation"][f"{dt.date.fromordinal(o)}|{kind}"], f"{time.time()-t0:.0f}s", flush=True)
    store0 = install(SERIES, RAW, "real")
    for label, seq in (("forward", sorted(origins)), ("reverse", sorted(origins, reverse=True))):
        inst = None
        out = []
        try:
            for o in seq:
                fc, inst = run(method, [o], store0, inst)
                out.append(fc)
            got = pd.concat(out)
            res["order"][label] = compare(pd.concat([base[o] for o in seq]), got)
        except AssertionError as e:
            res["order"][label] = {"error": f"AssertionError {e}"}
        print(method, label, res["order"][label], flush=True)
        store0 = install(SERIES, RAW, "real")
    res["wall_s"] = round(time.time() - t0)
    (OUT / f"leak_{method}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
