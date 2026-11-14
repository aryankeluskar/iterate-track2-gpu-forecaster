"""sig: wrap a base method with three signals found in the dev-period failure analysis.

  alpha, b   width: multiply the log offsets of q10/q90 from q50 by (recent breadth / long-run breadth) ** alpha, where
             breadth is the share of the series' collector (daily_statistics) that changed per day; recent = last b days.
  beta, lead centre: add beta * (partner's latest 1-day log change) to all quantiles; the partner is the series with the same
             gpu_model and instrument_class on the other collector. lead="g2f" shifts only fastgpu_daily series
             (partner gpurentalprices); "both" shifts either. Used only if the partner has a row on the origin day.
  rev, big   centre at h=7: subtract rev * (own latest 1-day log change) when it exceeds `big` in size and is dated at the origin.
Every input comes from ctx, which the harness truncated at the origin.
"""
from __future__ import annotations

import numpy as np

from gpuf.methods import get, register


@register("sig")
def make(base=("drift", {}), alpha=0.0, b=3, clip=(0.5, 2.5), beta=0.0, lead="g2f", rev=0.0, big=0.05, min_days=14):
    f0 = get(base[0], **base[1])
    cache = {}

    def breadth(ctx, src, o):
        key = ("b", src, o)
        if key not in cache:
            if len(cache) > 3000:
                cache.clear()
            ch, ob = {}, {}
            for s in ctx.ids():
                m = ctx.meta(s)
                if m.get("source_id") != src or m.get("table", "daily_statistics") != "daily_statistics":
                    continue
                d, v = ctx.history(s)
                if len(d) < 2:
                    continue
                c = v[1:] != v[:-1]
                for day, cc in zip(d[1:][np.diff(d) == 1], c[np.diff(d) == 1]):
                    ob[day] = ob.get(day, 0) + 1
                    ch[day] = ch.get(day, 0) + int(cc)
            days = sorted(ob)
            if len(days) < min_days:
                cache[key] = 1.0
            else:
                fr = np.array([ch[x] / ob[x] for x in days])
                rec = fr[np.array(days) > o - b]
                long = fr.mean()
                cache[key] = float(np.clip((rec.mean() / long) if len(rec) and long > 0 else 1.0, 1e-3, 1e3))
        return cache[key]

    def partner(ctx, sid, o):
        key = ("p", sid, o)
        if key not in cache:
            m = ctx.meta(sid)
            x = None
            want = {"fastgpu_daily": "gpurentalprices", "gpurentalprices": "fastgpu_daily"}.get(m.get("source_id"))
            if want and (lead == "both" or m.get("source_id") == "fastgpu_daily"):
                for s in ctx.ids():
                    ms = ctx.meta(s)
                    if (ms.get("source_id") == want and ms.get("gpu_model") == m.get("gpu_model")
                            and ms.get("instrument_class") == m.get("instrument_class")
                            and ms.get("pricing_tier") == m.get("pricing_tier") and ms.get("statistic") == m.get("statistic")):
                        d, v = ctx.history(s)
                        if len(d) >= 2 and d[-1] == o and d[-2] == o - 1 and v[-1] > 0 and v[-2] > 0:
                            x = float(np.log(v[-1] / v[-2]))
                        break
            cache[key] = x
        return cache[key]

    def f(sid, days, vals, origin_day, horizons, ctx):
        out = f0(sid, days, vals, origin_day, horizons, ctx) or {}
        m = ctx.meta(sid)
        w = 1.0
        if alpha:
            w = float(np.clip(breadth(ctx, m.get("source_id"), origin_day) ** alpha, clip[0], clip[1]))
        sh = 0.0
        if beta:
            x = partner(ctx, sid, origin_day)
            if x is not None:
                sh = beta * x
        own = 0.0
        if rev and len(days) >= 2 and days[-1] == origin_day and days[-2] == origin_day - 1 and vals[-2] > 0:
            r = float(np.log(vals[-1] / vals[-2]))
            if abs(r) > big:
                own = -rev * r
        res = {}
        for h, (q10, q50, q90) in out.items():
            l10, l50, l90 = np.log(max(q10, 1e-9)), np.log(max(q50, 1e-9)), np.log(max(q90, 1e-9))
            s = sh + (own if h == 7 else 0.0)
            res[h] = (float(np.exp(l50 + w * (l10 - l50) + s)), float(np.exp(l50 + s)), float(np.exp(l50 + w * (l90 - l50) + s)))
        return res

    return f
