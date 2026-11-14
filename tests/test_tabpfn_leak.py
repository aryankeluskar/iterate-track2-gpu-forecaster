"""tabpfn forecasts at origin d must not change when rows dated after d are perturbed or appended to the context."""
import os

import numpy as np

from gpuf import data, harness, methods, splits
from gpuf.harness import OriginContext


def test_perturbing_future_rows_changes_nothing():
    os.environ["OMP_NUM_THREADS"] = "2"
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    o = splits.DEV[10]
    sids = data.universe("rental_headline")[:3]
    rows = {}
    for s in store.ids():
        d, v = store.history(s, o + 20)
        if len(d):
            rows[s] = (d, v)
    bumped = {s: (d, np.where(d > o, v * 3.0, v)) for s, (d, v) in rows.items()}
    hist_t = {s: (d[d <= o], v[d <= o]) for s, (d, v) in rows.items() if (d <= o).any()}
    ctx_a = OriginContext(o, hist_t, meta)
    ctx_b = OriginContext(o, {s: (d, v) for s, (d, v) in bumped.items()}, meta)  # future rows present and perturbed
    out = []
    for ctx in (ctx_a, ctx_b):
        f = methods.get("tabpfn", n=300, est=1, cache=False, post="raw")
        d, v = ctx.history(sids[0])
        keep = d <= o
        out.append(f(sids[0], d[keep], v[keep], o, (1, 3, 7), ctx))
    assert out[0] and out[0] == out[1]
