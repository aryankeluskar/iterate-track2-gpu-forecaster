"""allrental: activity-gated forecaster for every posted rental series.

A series that has at least `gate_n` days of history and changed fewer than `gate_m` times in the last `gate_n`
calendar days (rows dated in (origin - gate_n, origin]) gets the last value with a zero-width interval, which
scores exactly the last-value baseline. Every other series gets the log-space average of `members` (as `ens`),
with the q10/q90 log offsets from q50 multiplied by `scale`. Uses only the harness's origin-truncated arrays.

params
  members   [[method, params], ...] blended like `ens` (default: the reference mix)
  gate_n    window in calendar days (0 disables the gate)
  gate_m    minimum number of changes in the window to count as active
  scale     width multiplier on the blended interval
"""
from __future__ import annotations

import numpy as np

from gpuf.methods import get, register

REF_MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]


def n_changes(days, vals, origin_day, n):
    """Value changes between consecutive rows whose later row is dated in (origin_day - n, origin_day]."""
    lo = int(np.searchsorted(days, origin_day - n, side="right"))
    lo = max(lo, 1)
    return int((vals[lo:] != vals[lo - 1:-1]).sum()) if lo < len(vals) else 0


def gated(days, vals, origin_day, n, m):
    return n > 0 and origin_day - int(days[0]) >= n and n_changes(days, vals, origin_day, n) < m


@register("allrental")
def make(members=(REF_MIX,), gate_n=14, gate_m=1, scale=1.0):
    fs = [get(name, **p) for name, p in members]

    def f(sid, days, vals, origin_day, horizons, ctx):
        last = float(vals[-1])
        if gated(days, vals, origin_day, gate_n, gate_m):
            return {h: (last, last, last) for h in horizons}
        outs = [g(sid, days, vals, origin_day, horizons, ctx) for g in fs]
        res = {}
        for h in horizons:
            q = np.log([[max(float(x), 1e-9) for x in o.get(h, (last, last, last))] for o in outs]).mean(0)
            res[h] = (float(np.exp(q[1] + scale * (q[0] - q[1]))), float(np.exp(q[1])),
                      float(np.exp(q[1] + scale * (q[2] - q[1]))))
        return res

    return f
