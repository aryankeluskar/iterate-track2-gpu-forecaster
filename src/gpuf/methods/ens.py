"""ens: average the members' quantiles in log-price space (equal weights unless given).

params: members = [[method, params], ...], weights = optional list
"""
from __future__ import annotations

import numpy as np

from gpuf.methods import get, register


@register("ens")
def make(members=(), weights=None):
    fs = [get(m, **p) for m, p in members]
    w = np.ones(len(fs)) if weights is None else np.asarray(weights, float)
    w = w / w.sum()

    def f(sid, days, vals, origin_day, horizons, ctx):
        outs = [g(sid, days, vals, origin_day, horizons, ctx) for g in fs]
        last = float(vals[-1])
        res = {}
        for h in horizons:
            q = np.array([[max(float(x), 1e-9) for x in o.get(h, (last, last, last))] for o in outs])
            res[h] = tuple(float(v) for v in np.exp(w @ np.log(q)))
        return res

    return f
