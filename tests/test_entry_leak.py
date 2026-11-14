"""entry forecasts for origin o must not change when panel rows dated after o are perturbed."""
import datetime as dt

import numpy as np

from gpuf import data, harness, panel as P
from gpuf.methods import get


def _forecast(df, index, sids, o, store, meta):
    old_load, old_index = P.load, P._index
    P.load, P._index = (lambda: df), (lambda: index)
    try:
        ctx = harness.make_context(store, o, meta)
        f = get("entry", pe=0.012, prov_params={"n_paths": 200})
        out = {}
        for sid in sids:
            days, vals = ctx.history(sid)
            out[sid] = f(sid, days, vals, o, (1, 3, 7), ctx)
        return out
    finally:
        P.load, P._index = old_load, old_index


def test_rows_after_origin_do_not_change_forecast():
    o = dt.date(2026, 9, 25).toordinal()
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    sids = [s for s in data.universe("rental_headline") if P.supported(s)]
    sids = [sids[0], sids[len(sids) // 3], sids[len(sids) // 2], sids[-1]]
    df = P.load()
    base_index = P._index()
    bad = df.copy()
    late = bad["day"] > o
    bad.loc[late, "price"] = bad.loc[late, "price"] * 7.3 + 1.0
    bad.loc[late, "provider"] = "zzz"
    bad_index = {k: g.reset_index(drop=True) for k, g in bad.groupby(["src", "cls", "gpu", "tier"], sort=False)}
    a = _forecast(df, base_index, sids, o, store, meta)
    b = _forecast(bad, bad_index, sids, o, store, meta)
    for sid in sids:
        for h in (1, 3, 7):
            np.testing.assert_array_equal(a[sid][h], b[sid][h])
