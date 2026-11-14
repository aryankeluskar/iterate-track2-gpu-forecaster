"""Member store for the scientist (practice dates only): one row per (series, origin, horizon) of the 357 posted rental
series, with the truth, the last value, the last-value loss, every `final` member's quantiles and drift's
(runs/maturity/cells.parquet, built by experiments/maturity/dump.py), joined to origin-time facts computed here.

Every fact of an origin is computed only from rows dated on or before it:
  series rows  through SeriesStore-style truncation (np.searchsorted on the sorted days, side="right")
  offer panel  through gpuf.panel.offers(sid, origin), which returns rows dated on or before the origin
  catalog      static definitions of the series (collector, instrument class, GPU model, pricing tier)
tests/test_scientist.py deletes and corrupts every later row (series table and offer panel) and checks the facts
are bit-identical. `in37` is the fixed scored set, chosen as of 6 November (hindsight), kept because the submitted
system's gate uses it.

The store refuses any origin outside split dev (the held-back weeks are never read here).
Facts are cached in runs/scientist/facts.parquet (about a minute to rebuild): `python -m gpuf.store --rebuild`.
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "2")

import datetime as dt
import sys
import time

import numpy as np
import pandas as pd

from . import data, panel, splits

CELLS = data.ROOT / "runs/maturity/cells.parquet"
FACTS_PATH = data.ROOT / "runs/scientist/facts.parquet"
CAUSES = data.ROOT / "experiments/loop/cause_labels.parquet"
MEMBERS = ("mix", "gbm", "chronos", "analog", "prov", "fm2", "fragility")
ALL_MEMBERS = MEMBERS + ("drift",)
KEY = ["series_id", "origin_day", "horizon_days"]
DEV = set(splits.DEV)

# name: (kind, description). kind: num, bool or cat. Categories of cat facts are read from the store.
FACTS = {
    "horizon": ("num", "forecast horizon in days (1, 3 or 7)"),
    "rows": ("num", "rows of the series dated on or before the origin"),
    "span": ("num", "days from the first row to the origin"),
    "stale": ("num", "days from the last row to the origin (0 = a row on the origin day)"),
    "chg3": ("num", "value changes between consecutive rows whose later row is in the last 3 days"),
    "chg7": ("num", "the same over the last 7 days"),
    "chg14": ("num", "the same over the last 14 days"),
    "chg30": ("num", "the same over the last 30 days"),
    "days_since_change": ("num", "days since the last value change (= span if it never changed)"),
    "last_change": ("num", "signed log size of the last value change (0 if none)"),
    "last_change_abs": ("num", "absolute log size of the last value change (0 if none)"),
    "zero_share": ("num", "share of consecutive-row pairs with no change, whole history"),
    "vol30": ("num", "standard deviation of log changes between consecutive rows in the last 30 days"),
    "ret7": ("num", "log change from the last row on or before origin-7 to the last value"),
    "ret30": ("num", "log change from the last row on or before origin-30 to the last value"),
    "last": ("num", "last value, USD per GPU-hour"),
    "gate14": ("bool", "the series has 14+ days of history and did not change in the last 14 days"),
    "mature": ("bool", "met the organisers' headline rule at the origin (60+ rows, fresh, 5+ distinct values in 90 days, median providers 3+)"),
    "in37": ("bool", "one of the 37 scored headline series (fixed set chosen as of 6 November: hindsight)"),
    "collector": ("cat", "data collector (source id)"),
    "cls": ("cat", "instrument class"),
    "gpu": ("cat", "GPU model"),
    "pricing_tier": ("cat", "pricing tier"),
    "has_panel": ("bool", "an offer panel is available (fastgpu_daily or gpurentalprices) with rows on or before the origin"),
    "p_offers": ("num", "offers in the panel on its last day on or before the origin"),
    "p_providers": ("num", "distinct providers among those offers"),
    "gap_below": ("num", "log gap from the median down to the offer just below the middle"),
    "gap_above": ("num", "log gap from the median up to the offer just above the middle"),
    "mid_gap": ("num", "gap_below + gap_above"),
    "mid_prov_reprice21": ("num", "share of the last 21 days on which the provider of the middle offer repriced any of its offers in this panel"),
    "joined7": ("num", "offers on the last panel day that were absent on the last panel day at least 7 days earlier"),
    "left7": ("num", "offers present on that earlier day and absent on the last panel day"),
    "panel_stale": ("num", "days from the last panel day to the origin"),
}
SERIES_FACTS = [k for k, v in FACTS.items() if k not in ("horizon", "in37", "collector", "cls", "gpu", "pricing_tier", "has_panel", "p_offers",
                                                         "p_providers", "gap_below", "gap_above", "mid_gap", "mid_prov_reprice21", "joined7",
                                                         "left7", "panel_stale")]
PANEL_FACTS = ["has_panel", "p_offers", "p_providers", "gap_below", "gap_above", "mid_gap", "mid_prov_reprice21", "joined7", "left7", "panel_stale"]


class HeldBack(PermissionError):
    pass


def check_origins(origins, allow_any: bool = False) -> None:
    bad = sorted(set(int(o) for o in origins) - DEV)
    if bad and not allow_any:
        raise HeldBack(f"REFUSED: the scientist store serves practice dates only; {len(bad)} origin(s) outside split dev, "
                       f"first {dt.date.fromordinal(bad[0])}")


# ----------------------------------------------------------------------------- series facts
def series_frame(path: str | None = None) -> pd.DataFrame:
    """series_id, day, value, n_providers of the daily_statistics series, sorted by series and day."""
    cat = data.load_catalog()
    S = pd.read_csv(path or data.series_path(), dtype={"series_id": str}, low_memory=False,
                    usecols=["series_id", "date", "value", "n_providers"])
    S = S[S["series_id"].isin(set(cat.loc[cat["table"] == "daily_statistics", "series_id"]))].dropna(subset=["value"]).copy()
    S["day"] = pd.to_datetime(S["date"]).map(pd.Timestamp.toordinal).astype(np.int64)
    S["n_providers"] = pd.to_numeric(S["n_providers"], errors="coerce")
    return S[["series_id", "day", "value", "n_providers"]].sort_values(["series_id", "day"], kind="stable").reset_index(drop=True)


def _nchg(days, vals, o, n):   # = gpuf.methods.allrental.n_changes
    lo = max(int(np.searchsorted(days, o - n, side="right")), 1)
    return int((vals[lo:] != vals[lo - 1:-1]).sum()) if lo < len(vals) else 0


def _ret(days, vals, o, k):
    j = int(np.searchsorted(days, o - k, side="right")) - 1
    return float(np.log(vals[-1] / vals[j])) if j >= 0 and vals[j] > 0 and vals[-1] > 0 else np.nan


def series_facts(days: np.ndarray, vals: np.ndarray, nprov: np.ndarray, o: int) -> dict:
    """Facts of one series at origin o from its rows; rows dated after o are cut off here."""
    k = int(np.searchsorted(days, o, side="right"))
    d, v, p = days[:k], vals[:k], nprov[:k]
    n = len(v)
    if n == 0:
        return {f: np.nan for f in SERIES_FACTS} | {"gate14": False, "mature": False}
    lv = np.log(np.maximum(v, 1e-12))
    dl = np.diff(lv)
    ch = np.nonzero(v[1:] != v[:-1])[0]
    span = int(o - d[0])
    w = d[1:] > o - 30
    rec = dl[w] if n > 1 else dl
    h90 = v[d > o - 90]
    pp = p[~np.isnan(p)]
    return {
        "rows": n, "span": span, "stale": int(o - d[-1]),
        "chg3": _nchg(d, v, o, 3), "chg7": _nchg(d, v, o, 7), "chg14": _nchg(d, v, o, 14), "chg30": _nchg(d, v, o, 30),
        "days_since_change": int(o - d[ch[-1] + 1]) if len(ch) else span,
        "last_change": float(dl[ch[-1]]) if len(ch) else 0.0, "last_change_abs": float(abs(dl[ch[-1]])) if len(ch) else 0.0,
        "zero_share": float((dl == 0).mean()) if n > 1 else np.nan,
        "vol30": float(rec.std()) if len(rec) >= 2 else np.nan,
        "ret7": _ret(d, v, o, 7), "ret30": _ret(d, v, o, 30), "last": float(v[-1]),
        "gate14": bool(span >= 14 and _nchg(d, v, o, 14) < 1),
        "mature": bool(n >= 60 and o - int(d[-1]) <= 3 and len(np.unique(np.round(h90, 6))) >= 5 and len(pp) and np.median(pp) >= 3),
    }


# ----------------------------------------------------------------------------- panel facts
def panel_facts(sid: str, o: int) -> dict:
    """Facts of the offer panel behind the series at origin o, read through panel.offers (rows on or before o)."""
    out = {"has_panel": False} | {k: np.nan for k in PANEL_FACTS[1:]}
    if not panel.supported(sid):
        return out
    g = panel.offers(sid, o)
    if g.empty:
        return out
    days = g["day"].to_numpy(np.int64)
    L = int(days.max())
    cur = g[g["day"] == L].sort_values(["price", "key"], kind="stable")
    p = cur["price"].to_numpy(float)
    n = len(p)
    med = float(np.median(p))
    if n % 2:
        m = (n - 1) // 2
        below, above = (p[m - 1] if m >= 1 else np.nan), (p[m + 1] if m + 1 < n else np.nan)
    else:
        below, above = (p[n // 2 - 2] if n >= 4 else np.nan), (p[n // 2 + 1] if n // 2 + 1 < n else np.nan)
    gb = float(np.log(med / below)) if below == below and below > 0 and med > 0 else np.nan
    ga = float(np.log(above / med)) if above == above and med > 0 else np.nan
    pv = cur["provider"].iloc[(n - 1) // 2]
    h = g[g["provider"] == pv].sort_values(["key", "day"], kind="stable")
    dp = h.groupby("key")["price"].diff()
    hh = h.assign(rep=dp.abs() > 1e-9)[dp.notna().to_numpy() & (h["day"] > o - 21).to_numpy()]
    rate = float(hh.groupby("day")["rep"].any().mean()) if len(hh) else 0.0
    earlier = days[days <= L - 7]
    if len(earlier):
        E = int(earlier.max())
        kl, ke = set(cur["key"]), set(g.loc[g["day"] == E, "key"])
        j7, l7 = float(len(kl - ke)), float(len(ke - kl))
    else:
        j7 = l7 = np.nan
    return {"has_panel": True, "p_offers": float(n), "p_providers": float(cur["provider"].nunique()), "gap_below": gb, "gap_above": ga,
            "mid_gap": gb + ga, "mid_prov_reprice21": rate, "joined7": j7, "left7": l7, "panel_stale": float(o - L)}


def catalog_facts() -> dict[str, dict]:
    cat = data.load_catalog()
    cat = cat[cat["table"] == "daily_statistics"]
    return {r.series_id: {"collector": r.source_id, "cls": r.instrument_class, "gpu": r.gpu_model, "pricing_tier": r.pricing_tier}
            for r in cat.itertuples()}


def build_facts(S: pd.DataFrame, pairs, allow_any: bool = False) -> pd.DataFrame:
    """One row per (series_id, origin_day) in `pairs`, every fact computed from rows dated on or before the origin."""
    pairs = sorted({(str(s), int(o)) for s, o in pairs})
    check_origins([o for _, o in pairs], allow_any)
    head = set(data.universe("rental_headline"))
    cf = catalog_facts()
    G = {s: (g["day"].to_numpy(np.int64), g["value"].to_numpy(float), g["n_providers"].to_numpy(float)) for s, g in S.groupby("series_id", sort=False)}
    empty = (np.empty(0, np.int64), np.empty(0), np.empty(0))
    rows = []
    for s, o in pairs:
        rows.append({"series_id": s, "origin_day": o, **series_facts(*G.get(s, empty), o), "in37": s in head,
                     **cf.get(s, {"collector": "", "cls": "", "gpu": "", "pricing_tier": ""}), **panel_facts(s, o)})
    F = pd.DataFrame(rows)
    for k, (kind, _) in FACTS.items():
        if k == "horizon":
            continue
        F[k] = F[k].astype(bool) if kind == "bool" else F[k].astype(str) if kind == "cat" else F[k].astype(float)
    return F


# ----------------------------------------------------------------------------- the store
class Store:
    """Arrays over the cells of the member store, in a fixed order (series, origin, horizon)."""

    def __init__(self, df: pd.DataFrame):
        check_origins(df["origin_day"].unique())
        df = df.sort_values(KEY, kind="stable").reset_index(drop=True)
        self.df = df
        self.n = len(df)
        Q = np.stack([np.stack([df[f"{m}_{q}"].to_numpy(float) for q in ("q10", "q50", "q90")], 1) for m in ALL_MEMBERS], 1)  # n x M x 3
        self.avail = np.isfinite(Q).all(2) & (Q > 0).all(2)
        self.Lq = np.where(self.avail[:, :, None], np.log(np.where(Q > 0, Q, 1.0)), 0.0)
        self.y = df["y"].to_numpy(float)
        self.lastv = df["last"].to_numpy(float)
        self.bl = df["baseline_loss"].to_numpy(float)
        self.origin = df["origin_day"].to_numpy(np.int64)
        self.h = df["horizon_days"].to_numpy(np.int64)
        self.sid = df["series_id"].to_numpy(object)
        self.week = np.array(["%d-W%02d" % dt.date.fromordinal(int(o)).isocalendar()[:2] for o in self.origin], dtype=object)
        self.facts = {k: (self.h.astype(float) if k == "horizon" else df[k].to_numpy(bool if v[0] == "bool" else object if v[0] == "cat" else float))
                      for k, v in FACTS.items()}
        self.cats = {k: sorted(set(self.facts[k])) for k, v in FACTS.items() if v[0] == "cat"}
        self.cause = df["cause"].to_numpy(object) if "cause" in df else np.full(self.n, None, object)

    def subset(self, idx: np.ndarray) -> "Store":
        return Store(self.df.iloc[idx].reset_index(drop=True))


def cells_frame(path=CELLS) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"error: {path} is missing; build it (dev only, about 90 s):\n  PYTHONPATH=src .venv/bin/python experiments/maturity/dump.py")
    D = pd.read_parquet(path).rename(columns={"last": "last_dump", "gate14": "gate14_dump", "tier": "tier_dump"})
    return D.drop(columns=[c for c in ("rows", "span", "in37", "chg14", "chg30", "cls") if c in D])


def load(rebuild: bool = False) -> Store:
    D = cells_frame()
    check_origins(D["origin_day"].unique())
    if rebuild or not FACTS_PATH.exists():
        t0 = time.time()
        F = build_facts(series_frame(), D[["series_id", "origin_day"]].drop_duplicates().itertuples(index=False))
        FACTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        F.to_parquet(FACTS_PATH, index=False)
        print(f"store: facts for {len(F)} (series, origin) pairs in {time.time() - t0:.0f}s -> {FACTS_PATH}", file=sys.stderr)
    F = pd.read_parquet(FACTS_PATH)
    df = D.merge(F, on=["series_id", "origin_day"], how="left", validate="many_to_one")
    assert df["rows"].notna().all(), "facts missing for some cells: rebuild with python -m gpuf.store --rebuild"
    assert np.allclose(df["last"], df["last_dump"]), "store: last value differs from the dump"
    if CAUSES.exists():
        c = pd.read_parquet(CAUSES, columns=KEY + ["cause2"]).rename(columns={"cause2": "cause"})
        df = df.merge(c, on=KEY, how="left", validate="one_to_one")
    return Store(df)


if __name__ == "__main__":
    st = load(rebuild="--rebuild" in sys.argv)
    d = st.df
    print(f"{st.n} cells, {d.series_id.nunique()} series, {d.origin_day.nunique()} origins "
          f"({dt.date.fromordinal(int(d.origin_day.min()))}..{dt.date.fromordinal(int(d.origin_day.max()))})")
    print("gate14 equal to the dump's:", bool((d.gate14 == d.gate14_dump).all()), " mature equal to the dump's tier:", bool((d.mature == d.tier_dump).all()))
