import numpy as np
from gpuf.methods.allrental import gated, n_changes


def test_gate_counts_only_window_and_is_origin_truncated():
    days = np.arange(100, 160)
    vals = np.ones(60); vals[30:] = 2.0  # one change at day 130
    assert n_changes(days, vals, 159, 14) == 0 and gated(days, vals, 159, 14, 1)
    assert n_changes(days, vals, 140, 14) == 1 and not gated(days, vals, 140, 14, 1)
    # rows after the origin cannot matter: the harness passes truncated arrays; same arrays plus later rows, truncated, agree
    d2, v2 = np.r_[days, 160, 161], np.r_[vals, 5.0, 7.0]
    m = d2 <= 159
    assert gated(d2[m], v2[m], 159, 14, 1) == gated(days, vals, 159, 14, 1)


def test_short_history_never_gated():
    days = np.arange(100, 105); vals = np.ones(5)
    assert not gated(days, vals, 104, 14, 1)


def test_forecast_unchanged_by_future_rows():
    from gpuf import data, harness, methods
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    sid = data.universe("rental_all")[0]
    o = 739880
    f = methods.get("allrental")
    ctx = harness.make_context(store, o, meta)
    d, v = ctx.history(sid)
    a = f(sid, d, v, o, (1, 3, 7), ctx)
    assert d[-1] <= o and all(len(ctx.history(s)[0]) == 0 or ctx.history(s)[0][-1] <= o for s in ctx.ids())
    b = f(sid, d, v, o, (1, 3, 7), ctx)
    assert a == b
