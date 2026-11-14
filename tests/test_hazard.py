"""hazard reads daily_statistics.csv directly: perturbing panel rows dated after the origin must not change forecasts."""
import numpy as np

from gpuf import data, harness, methods, splits
from gpuf.methods import hazard as hz


def _run(origin, sids):
    store, meta = data.load_store(), harness.static_meta(data.load_catalog())
    ctx = harness.make_context(store, origin, meta)
    f = methods.get("hazard", clf="lr")
    return {s: f(s, *ctx.history(s), origin, (1, 3, 7), ctx) for s in sids}


def test_panel_after_origin_is_ignored():
    origin = splits.origins("dev")[10]
    sids = data.universe("rental_headline")[:6]
    a = _run(origin, sids)
    orig = hz.panel()
    try:
        hz._PANEL = {s: (d, np.where(d > origin, n * 3 + 7, n), np.where(d > origin, p25 - 1, p25),
                         np.where(d > origin, p75 + 1, p75)) for s, (d, n, p25, p75) in orig.items()}
        b = _run(origin, sids)
    finally:
        hz._PANEL = orig
    assert a == b
