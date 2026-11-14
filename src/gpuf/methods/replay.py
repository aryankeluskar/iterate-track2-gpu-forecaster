"""replay: return forecasts saved by experiments/dump.py, so torch and LightGBM members can be blended without sharing a process.

The saved forecasts were produced by the harness under origin truncation, so replaying them adds no leakage.
params: path = parquet with series_id, origin_day, horizon_days, q10, q50, q90. A missing cell raises.
"""
from __future__ import annotations

import pandas as pd

from gpuf.methods import register


@register("replay")
def make(path=""):
    df = pd.read_parquet(path)
    tab = {(s, int(o), int(h)): (a, b, c) for s, o, h, a, b, c in
           df[["series_id", "origin_day", "horizon_days", "q10", "q50", "q90"]].itertuples(index=False)}
    seen_o = {k[1] for k in tab}

    def f(sid, days, vals, origin_day, horizons, ctx):
        if int(origin_day) not in seen_o:
            raise KeyError(f"replay: origin {origin_day} not in {path}")
        # cells exist only where truth exists; a series/horizon with no truth is never scored
        return {h: tab[(sid, int(origin_day), int(h))] for h in horizons if (sid, int(origin_day), int(h)) in tab}

    return f
