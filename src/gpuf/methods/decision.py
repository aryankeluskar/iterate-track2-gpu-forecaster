"""decision: quantiles from a classifier's P(down), P(unchanged), P(up), read from a cache.

q10/q50/q90 invert the mixture  P(down) * D + P(flat) * point mass at 0 + P(up) * U  of h-day log changes,
where D and U are the pooled negative and positive h-day log changes of every series of the same collector
and instrument class, over sample pairs whose end day is on or before the origin (from ctx.history, so
already truncated). Cells missing from the cache, or with fewer than `min_moves` pooled moves on a side,
fall back to drift.

params
  path       parquet with series_id, origin_day, horizon_days, p_down, p_flat, p_up
  min_moves  minimum pooled moves per side (default 20)
"""
from __future__ import annotations

import numpy as np

from gpuf.methods import register


@register("decision")
def make(path: str = "runs/decision/lgbm_probs.parquet", min_moves: int = 20):
    import pandas as pd
    from gpuf.baselines import starter_method
    from gpuf.methods.mix import pairs

    cache = pd.read_parquet(path).set_index(["series_id", "origin_day", "horizon_days"])[["p_down", "p_flat", "p_up"]]
    probs = {k: v for k, v in zip(cache.index, cache.to_numpy())}
    drift = starter_method("drift")
    pools: dict = {}

    def pool(ctx, src, cls, origin_day, h):
        key = (src, cls, origin_day, h)
        if key not in pools:
            xs = []
            for s in ctx.ids():
                m = ctx.meta(s)
                if m.get("source_id") != src or m.get("instrument_class") != cls:
                    continue
                d, v = ctx.history(s)
                if len(d) < 2 or not (v > 0).all():
                    continue
                i, j = pairs(d, v, h)
                xs.append(np.log(v[j] / v[i]))
            x = np.concatenate(xs) if xs else np.zeros(0)
            pools[key] = (np.sort(x[x < -1e-9]), np.sort(x[x > 1e-9]))
        return pools[key]

    def f(sid, days, vals, origin_day, horizons, ctx):
        base = drift(sid, days, vals, origin_day, horizons, ctx)
        m = ctx.meta(sid)
        last = float(vals[-1])
        out = dict(base)
        for h in horizons:
            p = probs.get((sid, origin_day, h))
            if p is None:
                continue
            dn, up = pool(ctx, m.get("source_id"), m.get("instrument_class"), origin_day, h)
            if len(dn) < min_moves or len(up) < min_moves:
                continue
            pd_, pf, pu = p / p.sum()
            qs = []
            for q in (0.1, 0.5, 0.9):
                if q < pd_:
                    x = np.quantile(dn, q / pd_)
                elif q <= pd_ + pf:
                    x = 0.0
                else:
                    x = np.quantile(up, min(1.0, (q - pd_ - pf) / pu))
                qs.append(last * float(np.exp(x)))
            out[h] = tuple(qs)
        return out

    return f
