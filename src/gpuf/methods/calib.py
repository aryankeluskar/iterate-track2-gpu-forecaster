"""calib: drift's centre, recalibrated intervals.

Tails are quantiles of the series' own h-day log changes (drift) or, when it has too few samples,
of the pooled changes of its (collector, class) group. Optional online corrections learned only from
forecasts whose target date is on or before the origin:
  mult: per (collector, class, h) multipliers on the lower and upper offsets from q50 (grid, shrunk to 1)
  aci : adaptive conformal inference on the tail levels with delayed updates
Every quantity at a past origin o is recomputed from history truncated at o, so nothing after the
current origin is read.
"""
from __future__ import annotations

import numpy as np

from gpuf.data import starter_common
from gpuf.methods import register
from gpuf.scoring import pinball

h_step_changes = starter_common.h_step_changes
GRID = np.array([0, .25, .5, .75, 1, 1.25, 1.5, 2.0])


def _hist_at(days, vals, o):
    k = int(np.searchsorted(days, o, side="right"))
    return days[:k], vals[:k]


@register("calib")
def make(min_samples=20, pool=False, pool_min=20, mult=False, n0=100.0, window=0, aci=False, gamma=0.02,
         aci_by="class", min_cells=0):
    cache_own, cache_pool, cache_c, aci_state = {}, {}, {}, {}

    def own_changes(sid, days, vals, o, h):
        key = (sid, o, h)
        if key not in cache_own:
            d, v = _hist_at(days, vals, o)
            cache_own[key] = (np.sort(h_step_changes(d, v, h, True)) if len(d) and (v > 0).all() else np.empty(0),
                              float(v[-1]) if len(d) else np.nan)
        return cache_own[key]

    def grp_of(ctx, sid):
        m = ctx.meta(sid)
        return (m.get("source_id", ""), m.get("instrument_class", ""))

    def pooled(ctx, g, o, h):
        key = (g, o, h)
        if key not in cache_pool:
            arrs = [own_changes(s, *ctx.history(s), o, h)[0] for s in ctx.ids() if grp_of(ctx, s) == g]
            cache_pool[key] = np.sort(np.concatenate(arrs)) if arrs else np.empty(0)
        return cache_pool[key]

    def dist(ctx, sid, days, vals, o, h):
        ch, last = own_changes(sid, days, vals, o, h)
        if len(ch) >= min_samples:
            return ch, last, True
        if pool:
            pc = pooled(ctx, grp_of(ctx, sid), o, h)
            if len(pc) >= pool_min:
                return pc, last, False
        return None, last, False

    def tails(ch, last, a_lo, a_hi):
        """price-space (q10, q50, q90) with q50 = drift's centre (own median, else last)."""
        if ch is None:
            return last, last, last
        lo, hi = np.quantile(ch, [a_lo, 1 - a_hi])
        return last * np.exp(lo), last, last * np.exp(hi)

    def centre(ch, last, own_ok):
        return last * float(np.exp(np.quantile(ch, 0.5))) if (ch is not None and own_ok) else last

    def base_q(ctx, sid, days, vals, o, h, a_lo=0.1, a_hi=0.1):
        ch, last, own_ok = dist(ctx, sid, days, vals, o, h)
        q10, _, q90 = tails(ch, last, a_lo, a_hi)
        q50 = centre(ch, last, own_ok)
        return q10, q50, q90

    def realised(days, vals, day):
        k = int(np.searchsorted(days, day))
        return float(vals[k]) if k < len(days) and days[k] == day else None

    def learned_c(ctx, g, h, d):
        key = (g, h, d)
        if key in cache_c:
            return cache_c[key]
        rows = []
        for s in ctx.ids():
            if grp_of(ctx, s) != g:
                continue
            sd, sv = ctx.history(s)
            lo_o = sd[0] if len(sd) else d
            for o in range(max(int(lo_o), d - window - h if window else int(lo_o)), d - h + 1):
                y = realised(sd, sv, o + h)
                if y is None or o > sd[-1]:
                    continue
                d_o, v_o = _hist_at(sd, sv, o)
                if len(d_o) == 0:
                    continue
                q10, q50, q90 = base_q(ctx, s, sd, sv, o, h)
                rows.append((y, q10, q50, q90))
        if len(rows) < max(min_cells, 1):
            cache_c[key] = (1.0, 1.0)
            return cache_c[key]
        y, q10, q50, q90 = (np.array(c) for c in zip(*rows))
        lo, hi = q50 - q10, q90 - q50
        cl = [pinball(y, q50 - c * lo, .1).sum() for c in GRID]
        ch_ = [pinball(y, q50 + c * hi, .9).sum() for c in GRID]
        n = len(y)
        w = n / (n + n0)
        out = tuple(w * GRID[int(np.argmin(l))] + (1 - w) for l in (cl, ch_))
        cache_c[key] = out
        return out

    # ---- ACI: sequential replay with delayed errors, state per (group, h) ----
    def aci_key(g, h):
        return (g if aci_by == "class" else (g[0],), h)

    def aci_advance(ctx, d):
        st = aci_state.setdefault("s", {"day": None, "alpha": {}, "pending": {}})
        if st["day"] is not None and d < st["day"]:
            st.update(day=None, alpha={}, pending={})
        ids = ctx.ids()
        starts = [int(ctx.history(s)[0][0]) for s in ids]
        t = (st["day"] + 1) if st["day"] is not None else min(starts)
        for o in range(t, d + 1):
            # 1. delayed updates: cells issued at o-h now have a known outcome
            for (sid, h, issued), (qlo, qhi, g) in list(st["pending"].items()):
                if issued + h == o:
                    sd, sv = ctx.history(sid)
                    y = realised(sd, sv, o)
                    if y is not None:
                        k = aci_key(g, h)
                        a = st["alpha"].setdefault(k, [0.1, 0.1])
                        a[0] += gamma * (0.1 - float(y < qlo))
                        a[1] += gamma * (0.1 - float(y > qhi))
                    del st["pending"][(sid, h, issued)]
            # 2. issue forecasts at o with current alphas
            if o == d:
                break
            for sid in ids:
                sd, sv = ctx.history(sid)
                dd, _ = _hist_at(sd, sv, o)
                if len(dd) == 0:
                    continue
                g = grp_of(ctx, sid)
                for h in (1, 3, 7):
                    a = st["alpha"].setdefault(aci_key(g, h), [0.1, 0.1])
                    ch, last, _ = dist(ctx, sid, sd, sv, o, h)
                    q10, _, q90 = tails(ch, last, float(np.clip(a[0], 0.01, 0.45)), float(np.clip(a[1], 0.01, 0.45)))
                    st["pending"][(sid, h, o)] = (q10, q90, g)
        st["day"] = d - 1 if False else d
        return st

    def f(sid, days, vals, origin_day, horizons, ctx):
        out = {}
        g = grp_of(ctx, sid)
        if aci:
            st = aci_state.get("s")
            if st is None or st["day"] != origin_day:
                st = aci_advance(ctx, origin_day)
        for h in horizons:
            if aci:
                a = st["alpha"].setdefault(aci_key(g, h), [0.1, 0.1])
                a_lo, a_hi = float(np.clip(a[0], 0.01, 0.45)), float(np.clip(a[1], 0.01, 0.45))
            else:
                a_lo = a_hi = 0.1
            ch, last, own_ok = dist(ctx, sid, days, vals, origin_day, h)
            q10, _, q90 = tails(ch, last, a_lo, a_hi)
            q50 = centre(ch, last, own_ok)
            if mult:
                cl, chh = learned_c(ctx, g, h, origin_day)
                q10, q90 = q50 - cl * (q50 - q10), q50 + chh * (q90 - q50)
            out[h] = (q10, q50, q90)
        return out

    return f
