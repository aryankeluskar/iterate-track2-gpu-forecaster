"""Provider-balanced matched-offer change index for one (collector, class, GPU model, tier) panel.

Rules are frozen in experiments/index/protocol.yaml. For each observed day t, take the offers (gpuf.panel keys)
present on t and on the previous observed day, collapse them to one log change per provider (median over that
provider's matched offers), and average providers with equal weights. With fewer than MIN_PROVIDERS matched
providers the level is carried and the day is flagged invalid. Changes are chained from an anchor equal to the
posted median on the panel's first observed day. Every value for day t uses only rows dated on or before t.

CLI: PYTHONPATH=src .venv/bin/python -m gpuf.index --gpu H100 --source gpurentalprices --to 2026-10-06
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

import numpy as np
import pandas as pd

from . import panel

MIN_PROVIDERS = 3
ALIASES = {"paperspace": "digitalocean"}
CLS, TIER = "neocloud_rate_card", "on_demand"
SOURCES = {"fastgpu": "fastgpu_daily", "fastgpu_daily": "fastgpu_daily", "gpurentalprices": "gpurentalprices", "grp": "gpurentalprices"}

iso = lambda d: dt.date.fromordinal(int(d)).isoformat()
ordinal = lambda s: dt.date.fromisoformat(s).toordinal()


def rows(src: str, gpu: str, cls: str = CLS, tier: str = TIER, to_day: int | None = None) -> pd.DataFrame:
    """Offer rows (day, key, provider, price) of one panel dated on or before to_day, providers alias-mapped."""
    df = panel.load()
    m = (df["src"] == src) & (df["cls"] == cls) & (df["gpu"] == gpu) & (df["tier"] == tier)
    if to_day is not None:
        m &= df["day"] <= to_day
    r = df.loc[m, ["day", "key", "provider", "price"]].copy()
    r["provider"] = r["provider"].replace(ALIASES)
    return r.reset_index(drop=True)


def _core(r: pd.DataFrame, exclude: str | None = None) -> pd.DataFrame:
    """Per observed day: index change, validity, coverage, provider changes, posted and balanced medians (log)."""
    if exclude is not None:
        r = r[r["provider"] != exclude]
    if r.empty:
        return pd.DataFrame(columns=["change", "valid", "anchor", "providers", "providers_present", "offers",
                                     "offers_present", "r", "posted", "balanced"])
    W = r.pivot_table(index="day", columns="key", values="price", aggfunc="first").sort_index()
    prov = r.drop_duplicates("key").set_index("key")["provider"].reindex(W.columns).to_numpy()
    LW = np.log(W.to_numpy(dtype=float))
    out = []
    for i in range(len(W)):
        b = LW[i]
        pres = ~np.isnan(b)
        rec = dict(change=0.0, valid=False, anchor=i == 0, providers=0, providers_present=len(set(prov[pres])),
                   offers=0, offers_present=int(pres.sum()), r={}, posted=float(np.median(b[pres])), balanced=0.0)
        if i > 0:
            a = LW[i - 1]
            m = pres & ~np.isnan(a)
            if m.any():
                d = b[m] - a[m]
                rp = pd.Series(d).groupby(prov[m]).median()
                rec.update(providers=len(rp), offers=int(m.sum()), r=rp.to_dict(),
                           balanced=float(np.median(b[m]) - np.median(a[m])))
                if len(rp) >= MIN_PROVIDERS:
                    rec.update(change=float(rp.mean()), valid=True)
        out.append(rec)
    return pd.DataFrame(out, index=W.index)


def _calendar(core: pd.DataFrame, to_day: int | None) -> pd.DataFrame:
    """Expand observed days to calendar days: changes 0 and level carried on days without rows."""
    last = core.index.max() if to_day is None else min(int(to_day), int(core.index.max()))
    days = np.arange(int(core.index.min()), last + 1)
    c = core.reindex(days)
    c["observed"] = c["providers_present"].notna()
    c["change"] = c["change"].fillna(0.0)
    c["balanced"] = c["balanced"].fillna(0.0)
    c["valid"] = c["valid"].fillna(False).astype(bool)
    c["anchor"] = c["anchor"].fillna(False).astype(bool)
    c["posted"] = c["posted"].ffill()
    c["index_log"] = c["change"].cumsum()
    c["balanced_log"] = c["balanced"].cumsum()
    c["posted_log"] = c["posted"] - c["posted"].iloc[0]
    return c


def paths(src: str, gpu: str, cls: str = CLS, tier: str = TIER, to_day: int | None = None,
          exclude: str | None = None) -> pd.DataFrame:
    """Calendar-day log paths since the anchor of the index, the posted median and the balanced median."""
    r = rows(src, gpu, cls, tier, to_day)
    core = _core(r, exclude)
    if core.empty:
        return pd.DataFrame(columns=["index_log", "posted_log", "balanced_log", "valid", "observed"])
    return _calendar(core, to_day)[["index_log", "posted_log", "balanced_log", "change", "valid", "observed"]]


def compute(src: str, gpu: str, cls: str = CLS, tier: str = TIER, to_day: int | None = None) -> pd.DataFrame:
    """Published table, one row per calendar day: level, daily change, coverage and concentration warnings."""
    r = rows(src, gpu, cls, tier, to_day)
    core = _core(r)
    if core.empty:
        return pd.DataFrame()
    cal = _calendar(core, to_day)
    removal = pd.Series(0.0, index=cal.index)
    for p in sorted(r["provider"].unique()):
        alt = _core(r, exclude=p)
        c_alt = alt["change"].reindex(cal.index).fillna(0.0) if not alt.empty else pd.Series(0.0, index=cal.index)
        removal = np.maximum(removal, (c_alt - cal["change"]).abs())

    def share(d):
        if not isinstance(d, dict) or not d:
            return np.nan
        v = np.abs(np.array(list(d.values())))
        return float(v.max() / v.sum()) if v.sum() > 0 else np.nan

    def top(d):
        if not isinstance(d, dict) or not d or not any(d.values()):
            return ""
        return max(d, key=lambda k: abs(d[k]))

    anchor = float(np.exp(cal["posted"].iloc[0]))
    return pd.DataFrame({
        "date": [iso(d) for d in cal.index], "day": cal.index.astype(int), "collector": src, "instrument_class": cls,
        "pricing_tier": tier, "gpu_model": gpu,
        "index_level": anchor * np.exp(cal["index_log"].to_numpy()), "daily_change": cal["change"].to_numpy(),
        "posted_median": np.exp(cal["posted"].to_numpy()),
        "providers": cal["providers"].fillna(0).astype(int).to_numpy(),
        "providers_present": cal["providers_present"].fillna(0).astype(int).to_numpy(),
        "offers": cal["offers"].fillna(0).astype(int).to_numpy(),
        "offers_present": cal["offers_present"].fillna(0).astype(int).to_numpy(),
        "largest_provider_share": [share(d) for d in cal["r"]], "largest_provider": [top(d) for d in cal["r"]],
        "one_provider_removal": removal.to_numpy(), "valid": cal["valid"].to_numpy(),
        "anchor": cal["anchor"].to_numpy(), "observed": cal["observed"].to_numpy(),
    })


def resolve_gpu(name: str, src: str, cls: str = CLS, tier: str = TIER) -> list[str]:
    df = panel.load()
    models = sorted(df.loc[(df["src"] == src) & (df["cls"] == cls) & (df["tier"] == tier), "gpu"].unique())
    q = name.replace("_", " ").strip().lower()
    exact = [m for m in models if m.lower() == q]
    if exact:
        return exact
    pref = [m for m in models if m.lower().startswith(q + " ")]
    if not pref:
        raise SystemExit(f"no GPU model matching {name!r} in {src}/{cls}/{tier}; available: {', '.join(models)}")
    return pref


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m gpuf.index", description=__doc__.split("\n\n")[0],
                                 epilog="example: python -m gpuf.index --gpu H100 --source gpurentalprices --to 2026-10-06")
    ap.add_argument("--gpu", required=True, help="pack gpu_model (e.g. 'H100 SXM 80GB' or H100_SXM_80GB); a prefix such as H100 lists every matching model")
    ap.add_argument("--source", required=True, choices=sorted(SOURCES), help="collector")
    ap.add_argument("--to", default="2026-11-06", help="last date (YYYY-MM-DD); only rows dated on or before it are read")
    ap.add_argument("--from", dest="start", default=None, help="first date to print (the index is still anchored at the panel's first day)")
    ap.add_argument("--cls", default=CLS, help=f"instrument_class (default {CLS})")
    ap.add_argument("--tier", default=TIER, help=f"pricing_tier (default {TIER})")
    ap.add_argument("--csv", default=None, help="write the full table(s) to this CSV path")
    a = ap.parse_args(argv)
    src = SOURCES[a.source]
    tables = []
    for gpu in resolve_gpu(a.gpu, src, a.cls, a.tier):
        t = compute(src, gpu, a.cls, a.tier, ordinal(a.to))
        if t.empty:
            continue
        tables.append(t)
        show = t if a.start is None else t[t["date"] >= a.start]
        cols = ["date", "index_level", "daily_change", "posted_median", "providers", "offers",
                "largest_provider_share", "largest_provider", "one_provider_removal", "valid"]
        print(f"\n== {src} / {a.cls} / {gpu} / {a.tier}  (anchor {t['date'].iloc[0]}, min providers {MIN_PROVIDERS}) ==")
        print(show[cols].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    if a.csv and tables:
        pd.concat(tables).to_csv(a.csv, index=False)
        print(f"\nwrote {a.csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
