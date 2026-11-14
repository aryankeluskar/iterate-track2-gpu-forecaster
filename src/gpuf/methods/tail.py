"""tail: online, leak-free recalibration of a base method's q10 and q90, separately per horizon.

For each past cell (series s, origin o, horizon h) with o+h <= current origin d, the base method's forecast at o
is recomputed from history truncated at o (memoised) and compared with the realised value y at o+h.
  mode conf : q90' = q90*exp(Q_{.9}(log y/q90)), q10' = q10*exp(Q_{.1}(log y/q10)), pooled over series
  mode aci  : adaptive conformal inference, level of each tail adapted with step gamma from delayed feedback
  mode scale: multiplicative scale on each tail's log offset from q50, fitted by minimising past pinball loss
params
  base     [method, params]
  mode     conf | aci | scale
  pool     all | cc (collector x class; falls back to all when the group has < gmin cells)
  hl       half-life (days of target date) for recency weights, 0 = equal
  gamma    ACI step
  nmin,gmin  minimum cells before any correction
  n0       shrinkage: correction * n/(n+n0)
  pw       weight cells by base q50 ** pw (1 = in proportion to price, as the pooled score is)
  tails    both | hi | lo
  scope    headline | all : which series feed the error pool
"""
from __future__ import annotations

import numpy as np

from gpuf.methods import get, register
from gpuf.scoring import pinball

HS = (1, 3, 7)
GRID = np.array([0.4, 0.55, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0, 2.5])


class TCtx:
    """Context at a past origin o, built from a context that is itself truncated at d >= o."""

    def __init__(self, full, o):
        self.origin_day = int(o)
        self._full, self._c = full, {}
        self._ids = [s for s in full.ids() if full.history(s)[0][0] <= o]

    def ids(self):
        return list(self._ids)

    def history(self, sid):
        if sid not in self._c:
            d, v = self._full.history(sid)
            k = int(np.searchsorted(d, self.origin_day, side="right"))
            self._c[sid] = (d[:k], v[:k])
        return self._c[sid]

    def meta(self, sid):
        return self._full.meta(sid)


def wq(x, w, q):
    o = np.argsort(x, kind="stable")
    x, w = x[o], w[o]
    cw = np.cumsum(w)
    return float(np.interp(q * cw[-1], cw - 0.5 * w, x))


@register("tail")
def make(base=("mix", {}), mode="conf", pool="all", hl=0.0, gamma=0.02, nmin=40, gmin=80, n0=0.0, pw=0.0,
         tails="both", scope="headline", min_a=0.01, max_a=0.5):
    bf = get(base[0], **base[1])
    st = {"day": None}
    memo, tcs = {}, {}

    def reset():
        st.update(day=None, cells={h: [] for h in HS}, grp={}, ver=0, alpha={}, issued={}, cache={}, arr={})

    reset()
    sc_ids = {}

    def scope_ids(ctx):
        if "s" not in sc_ids:
            if scope == "all":
                sc_ids["s"] = None
            else:
                from gpuf import data
                sc_ids["s"] = set(data.universe("rental_headline"))
        return sc_ids["s"]

    def tc(full, o):
        if o not in tcs:
            tcs[o] = TCtx(full, o)
        return tcs[o]

    def base_at(full, sid, o):
        k = (sid, o)
        if k not in memo:
            t = tc(full, o)
            d, v = t.history(sid)
            memo[k] = bf(sid, d, v, o, HS, t)
        return memo[k]

    def key_of(ctx, sid):
        if pool == "all":
            return ("all",)
        m = ctx.meta(sid)
        return (m.get("source_id"), m.get("instrument_class"))

    def arrays(h, key):
        ck = (h, key, st["ver"])
        if ck not in st["arr"]:
            rows = [c for c in st["cells"][h] if key is None or c[0] == key]
            st["arr"][ck] = np.array([c[1:] for c in rows], float).reshape(-1, 6)
        return st["arr"][ck]

    def pick(h, key, t):
        a = arrays(h, key)
        if pool != "all" and len(a) < gmin:
            a = arrays(h, None)
        return a if len(a) >= nmin else None

    def weights(a, t):
        w = np.ones(len(a))
        if hl:
            w = w * 0.5 ** ((t - a[:, 0]) / hl)
        if pw:
            w = w * a[:, 3] ** pw
        return w

    def offsets(h, key, t, a_lo, a_hi):
        """(lo, hi): additive log shifts (conf, aci) or multiplicative scales (scale)."""
        ck = (t, h, key, round(a_lo, 6), round(a_hi, 6), st["ver"])
        if ck in st["cache"]:
            return st["cache"][ck]
        a = pick(h, key, t)
        neutral = 1.0 if mode == "scale" else 0.0
        if a is None:
            res = (neutral, neutral)
        else:
            y, q10, q50, q90, w = a[:, 1], a[:, 2], a[:, 3], a[:, 4], weights(a, t)
            n = len(a)
            sh = n / (n + n0) if n0 else 1.0
            if mode == "scale":
                u_hi, u_lo = np.log(q90 / q50), np.log(q50 / q10)
                lhi = [(pinball(y, q50 * np.exp(s * u_hi), .9) * w).sum() for s in GRID]
                llo = [(pinball(y, q50 * np.exp(-s * u_lo), .1) * w).sum() for s in GRID]
                res = tuple(neutral + sh * (GRID[int(np.argmin(l))] - neutral) for l in (llo, lhi))
            else:
                res = (sh * wq(np.log(y / q10), w, a_lo), sh * wq(np.log(y / q90), w, 1 - a_hi))
        st["cache"][ck] = res
        return res

    def alphas(h, key):
        return st["alpha"].setdefault((h, key), [0.1, 0.1])

    def adjust(h, key, t, q):
        q10, q50, q90 = q
        a_lo, a_hi = (0.1, 0.1)
        if mode == "aci":
            a_lo, a_hi = (float(np.clip(x, min_a, max_a)) for x in alphas(h, key))
        use = None if pool == "all" else key
        lo, hi = offsets(h, use, t, a_lo, a_hi)
        if mode == "scale":
            n10 = q50 * np.exp(-lo * np.log(q50 / q10)) if q10 > 0 and q50 > 0 else q10
            n90 = q50 * np.exp(hi * np.log(q90 / q50)) if q90 > 0 and q50 > 0 else q90
        else:
            n10, n90 = q10 * np.exp(lo), q90 * np.exp(hi)
        if tails == "hi":
            n10 = q10
        if tails == "lo":
            n90 = q90
        return min(n10, q50), q50, max(n90, q50)

    def advance(full, d):
        if st["day"] is not None and d < st["day"]:
            reset()
        ids = scope_ids(full)
        ids = [s for s in full.ids() if ids is None or s in ids]
        if not ids:
            return
        t0 = st["day"] + 1 if st["day"] is not None else min(int(full.history(s)[0][0]) for s in ids)
        for t in range(t0, d + 1):
            new = False
            for sid in ids:
                sd, sv = full.history(sid)
                k = int(np.searchsorted(sd, t))
                if k >= len(sd) or sd[k] != t:
                    continue
                y = float(sv[k])
                for h in HS:
                    j = int(np.searchsorted(sd, t - h))
                    if j >= len(sd) or sd[j] != t - h or t - h < sd[0]:
                        continue
                    q = base_at(full, sid, t - h)[h]
                    q10, q50, q90 = (max(float(x), 1e-9) for x in q)
                    key = key_of(full, sid)
                    st["cells"][h].append((key, t, y, q10, q50, q90, 0.0))
                    new = True
                    rec = st["issued"].pop((sid, t - h, h), None)
                    if rec is not None:
                        al = alphas(h, rec[2])
                        al[0] += gamma * (0.1 - float(y < rec[0]))
                        al[1] += gamma * (0.1 - float(y > rec[1]))
            if new:
                st["ver"] += 1
            if mode == "aci":
                for sid in ids:
                    sd, _ = full.history(sid)
                    k = int(np.searchsorted(sd, t))
                    if k >= len(sd) or sd[k] != t:
                        continue
                    b = base_at(full, sid, t)
                    key = key_of(full, sid)
                    for h in HS:
                        r = adjust(h, key, t, tuple(max(float(x), 1e-9) for x in b[h]))
                        st["issued"][(sid, t, h)] = (r[0], r[2], key)
            st["day"] = t

    def f(sid, days, vals, origin_day, horizons, ctx):
        if st["day"] != origin_day:
            advance(ctx, origin_day)
        b = bf(sid, days, vals, origin_day, horizons, ctx)
        last = float(vals[-1])
        out, key = {}, key_of(ctx, sid)
        for h in horizons:
            q = tuple(max(float(x), 1e-9) for x in b.get(h, (last, last, last)))
            out[h] = adjust(h, key, origin_day, q) if h in HS else q
        return out

    f.state, f.offsets, f.adjust = st, offsets, adjust
    return f
