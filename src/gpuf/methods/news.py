"""news: wrap a base method and widen a tail when Exa finds a burst of dated price-change news before the origin.

z_up = (hits with an increase word in the title, last `w` days up to the origin) / (median of the same count over the
`ref` origins before that window). q90's log offset from q50 is multiplied by 1 + g * clip(z_up - 1, 0, zmax); with
both=True, q10 gets the same treatment from decrease titles. `shift` moves all quantiles up by shift * that factor's
excess * (q90 offset). Reads the scout's cache only: run `python -m gpuf.scout fetch A B` first. A day missing from the
cache raises rather than counting as zero news.
"""
from __future__ import annotations

import datetime as dt

import numpy as np

from gpuf import scout
from gpuf.methods import get, register


@register("news")
def make(base=("drift", {}), g=0.5, w=7, ref=42, zmax=3.0, both=False, shift=0.0, hs=(7,), field="title"):
    f0 = get(base[0], **base[1])
    memo = {}

    def counts(o):
        if o not in memo:
            d = dt.date.fromordinal(int(o))
            hits = scout.day_hits(d, fetch=False)
            if not any(scout.CACHE.glob(f"{d}_*.json")):
                raise RuntimeError(f"news: {d} not in the Exa cache")
            k = ("title_up", "title_down") if field == "title" else ("up", "down")
            memo[o] = (sum(h[k[0]] for h in hits), sum(h[k[1]] for h in hits))
        return memo[o]

    def z(o):
        key = ("z", o)
        if key not in memo:
            cur = np.array([counts(o - i) for i in range(w)]).sum(axis=0)
            hist = np.array([[sum(counts(o - j - i)[s] for i in range(w)) for s in (0, 1)] for j in range(w, w + ref)])
            med = np.maximum(np.median(hist, axis=0), 1.0)
            memo[key] = tuple(float(x) for x in cur / med)
        return memo[key]

    def f(sid, days, vals, origin_day, horizons, ctx):
        out = f0(sid, days, vals, origin_day, horizons, ctx) or {}
        zu, zd = z(int(origin_day))
        eu = float(np.clip(zu - 1.0, 0.0, zmax)); ed = float(np.clip(zd - 1.0, 0.0, zmax)) if both else 0.0
        res = {}
        for h, (q10, q50, q90) in out.items():
            if h not in hs or (eu == 0 and ed == 0):
                res[h] = (q10, q50, q90); continue
            l10, l50, l90 = np.log(max(q10, 1e-9)), np.log(max(q50, 1e-9)), np.log(max(q90, 1e-9))
            s = shift * g * eu * (l90 - l50)
            res[h] = (float(np.exp(l50 + (1 + g * ed) * (l10 - l50) + s)), float(np.exp(l50 + s)),
                      float(np.exp(l50 + (1 + g * eu) * (l90 - l50) + s)))
        return res

    return f
