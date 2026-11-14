"""Shared helpers: score dumped forecasts on rental_all dev, series activity features (all leak-safe: <= origin)."""
import numpy as np
import pandas as pd
from gpuf import data, splits
from gpuf.harness import static_meta
from gpuf.scoring import score_fast

H = (1, 3, 7)
SPLIT_DAY = data.starter_common.day_of(data.starter_common.parse_date("2026-09-11"))  # early half: origin <= this


def ctx():
    store = data.load_store(data.series_path())
    meta = static_meta(data.load_catalog())
    sids = data.universe("rental_all")
    head = set(data.universe("rental_headline"))
    return store, meta, sids, head


def score(fc, store, meta, sids, head):
    fc = fc[["series_id", "origin_day", "horizon_days", "q10", "q50", "q90"]].copy()
    if "baseline" not in fc:
        base = {}
        for sid in fc["series_id"].unique():
            d, v = store.arrays(sid)
            base[sid] = (d, v)
        b = np.empty(len(fc))
        for sid, idx in fc.groupby("series_id").indices.items():
            d, v = base[sid]
            o = fc["origin_day"].to_numpy()[idx]
            j = np.searchsorted(d, o, side="right") - 1
            b[idx] = v[j]
        fc["baseline"] = b
    cells, _ = score_fast(fc, store, sids, H)
    cells["cls"] = cells["series_id"].map(lambda s: meta[s]["instrument_class"])
    cells["src"] = cells["series_id"].map(lambda s: meta[s]["source_id"])
    cells["head"] = cells["series_id"].isin(head)
    cells["half"] = np.where(cells["origin_day"] <= SPLIT_DAY, "early", "late")
    return cells


def activity(days, vals, origin_day, n):
    """Number of value changes between consecutive rows dated in (origin-n, origin]; days since last change; staleness."""
    m = days > origin_day - n
    d, v = days[m], vals[m]
    i0 = np.searchsorted(days, origin_day - n, side="right")
    prev = vals[i0 - 1] if i0 > 0 else None
    ch = int((v[1:] != v[:-1]).sum()) + (int(prev is not None and len(v) and v[0] != prev))
    return ch
