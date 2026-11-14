import datetime as dt

import numpy as np

from gpuf import data, panel
from gpuf.methods import get


def _forecast(index, sid, origin, **params):
    panel._index.cache_clear = getattr(panel._index, "cache_clear")
    orig = panel._index
    panel._index = lambda: index
    try:
        days_s = panel.daily_median(sid, origin)
        days, vals = days_s.index.to_numpy(), days_s.to_numpy()
        f = get("midstate", **params)
        return f(sid, days, vals, origin, (1, 3, 7), None)
    finally:
        panel._index = orig


def test_rows_after_origin_do_not_change_forecast():
    origin = dt.date(2026, 9, 25).toordinal()
    sids = [s for s in data.universe("rental_headline") if panel.supported(s)]
    base_index = panel._index()
    pert = {}
    for k, g in base_index.items():
        g = g.copy()
        late = g["day"] > origin
        g.loc[late, "price"] = g.loc[late, "price"] * 7.3 + 1.0
        g.loc[late, "provider"] = "zzz"
        pert[k] = g
    for sid in (sids[0], sids[len(sids) // 2], sids[-1]):
        for params in ({"state": "mid"}, {"state": "midchg", "tailsign": True, "gapclip": 3.0}):
            a = _forecast(base_index, sid, origin, **params)
            b = _forecast(pert, sid, origin, **params)
            for h in (1, 3, 7):
                np.testing.assert_array_equal(a[h], b[h])
