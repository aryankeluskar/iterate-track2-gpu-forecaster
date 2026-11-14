"""mix: empirical h-day log-change quantiles from a weighted mixture of the series' own changes and the
pooled changes of a peer group, optionally conditioned on the series' state at the origin.

Every sample is a pair (t, t+h) with t+h <= origin, taken from arrays the harness already truncated.

params
  pool      peer group: "cc" (collector, class), "collector", "class", "all", or "none"
  k         prior strength: the pooled samples together weigh as much as k own samples
  min_own   below this many own samples the own part is dropped (drift uses 20 and falls back to flat)
  state     "none" | "chg1" (did the value change on the origin day) | "chgk" (any change in the last sk days)
  sk        window for "chgk"; also "dirk" (sign of net change over sk days) and "dirchg" (changed within sk days x sign of latest change)
  hl        half-life in days for recency weights on samples (0 = equal weights)
  centre    "median" (drift-like), "last", or a float c in [0,1]: q50 = last * exp(c * mixture median)
  scale     multiplier on the log offsets of q10 and q90 from the centre
  norm      scale pooled changes by (own mean |1-day change|) / (donor mean |1-day change|), clipped
  lo, hi    tail levels (default 0.1 and 0.9)
"""
from __future__ import annotations

import numpy as np

from gpuf.methods import register


def pairs(days, vals, h):
    """(i, j) index arrays with days[j] == days[i] + h."""
    j = np.searchsorted(days, days + h)
    ok = j < len(days)
    i = np.nonzero(ok)[0]
    j = j[ok]
    m = days[j] == days[i] + h
    return i[m], j[m]


def changed_within(days, vals, k):
    """c[i] = 1 if the value changed between any two consecutive rows in the last k calendar days up to row i."""
    n = len(vals)
    c = np.zeros(n, dtype=np.int8)
    if n < 2:
        return c
    ch = np.r_[False, vals[1:] != vals[:-1]]
    last = -10 ** 9
    for i in range(n):
        if ch[i]:
            last = days[i]
        c[i] = 1 if days[i] - last < k else 0
    return c


def wquantile(x, w, qs):
    o = np.argsort(x, kind="stable")
    x, w = x[o], w[o]
    cw = np.cumsum(w)
    p = (cw - 0.5 * w) / cw[-1]
    return np.interp(qs, p, x)


def series_samples(days, vals, h, state, sk):
    """(log changes, sample end day, state at sample start, current state, mean abs 1-day log change)."""
    if len(days) < 2 or not (vals > 0).all():
        return None
    lv = np.log(vals)
    i, j = pairs(days, vals, h)
    if state == "none":
        st = np.zeros(len(vals), dtype=np.int8)
    elif state == "dirk":  # sign of the net log change over the last sk calendar days (0 flat, 1 up, 2 down)
        p = np.searchsorted(days, days - sk, side="left")
        d = lv - lv[p]
        st = np.where(d > 1e-12, 1, np.where(d < -1e-12, 2, 0)).astype(np.int8)
    elif state == "dirchg":  # changed within sk days (0/1) x sign of the latest change (up/down)
        c = changed_within(days, vals, sk)
        sg = np.zeros(len(vals), dtype=np.int8)
        cur = 0
        for q in range(1, len(vals)):
            if vals[q] > vals[q - 1]:
                cur = 1
            elif vals[q] < vals[q - 1]:
                cur = 2
            sg[q] = cur
        st = (c * sg).astype(np.int8)
    else:
        st = changed_within(days, vals, 1 if state == "chg1" else sk)
    i1, j1 = pairs(days, vals, 1)
    vol = float(np.mean(np.abs(lv[j1] - lv[i1]))) if len(i1) else 0.0
    return lv[j] - lv[i], days[j], st[i], int(st[-1]), vol


@register("mix")
def make(pool="cc", k=20.0, min_own=1, state="none", sk=3, hl=0.0, centre="median", scale=1.0, norm=False,
         lo=0.1, hi=0.9, scale_by_h=None, k_by_h=None, centre_by_h=None):
    cache = {}

    def grp(ctx, sid):
        m = ctx.meta(sid)
        if pool == "cc":
            return (m.get("source_id"), m.get("instrument_class"))
        if pool == "collector":
            return (m.get("source_id"),)
        if pool == "class":
            return (m.get("instrument_class"),)
        return ("all",)

    def donors(ctx, g, o, h):
        key = (g, o, h)
        if key not in cache:
            if len(cache) > 4000:
                cache.clear()
            out = []
            for s in ctx.ids():
                if ctx.meta(s).get("table", "daily_statistics") != "daily_statistics" or grp(ctx, s) != g:
                    continue
                r = series_samples(*ctx.history(s), h, state, sk)
                if r is not None and len(r[0]):
                    out.append((s, r))
            cache[key] = out
        return cache[key]

    def f(sid, days, vals, origin_day, horizons, ctx):
        last = float(vals[-1])
        out = {}
        for h in horizons:
            kk = float((k_by_h or {}).get(str(h), k))
            sc = float((scale_by_h or {}).get(str(h), scale))
            ce = (centre_by_h or {}).get(str(h), centre)
            own = series_samples(days, vals, h, state, sk)
            if own is None:
                out[h] = (last, last, last)
                continue
            ch, end, st, cur, vol = own
            xs, ws = [], []

            def add(c, e, s, total):
                m = s == cur
                if not m.any():
                    return
                c, e = c[m], e[m]
                w = np.ones(len(c)) if not hl else 0.5 ** ((origin_day - e) / hl)
                if total is not None:
                    w = w * (total / w.sum())
                xs.append(c)
                ws.append(w)

            if len(ch) >= min_own:
                add(ch, end, st, None)
            if pool != "none" and kk > 0:
                px, pe, ps = [], [], []
                for s, (c2, e2, s2, _, v2) in donors(ctx, grp(ctx, sid), origin_day, h):
                    if s == sid:
                        continue
                    if norm and v2 > 0 and vol > 0:
                        c2 = c2 * float(np.clip(vol / v2, 0.25, 4.0))
                    px.append(c2); pe.append(e2); ps.append(s2)
                if px:
                    add(np.concatenate(px), np.concatenate(pe), np.concatenate(ps), kk)
            if not xs:
                out[h] = (last, last, last)
                continue
            x, w = np.concatenate(xs), np.concatenate(ws)
            a, b, c = wquantile(x, w, [lo, 0.5, hi])
            if ce == "median":
                mid = b
            elif ce == "last":
                mid = 0.0
            else:
                mid = float(ce) * b
            out[h] = (last * np.exp(mid + sc * (a - b)), last * np.exp(mid), last * np.exp(mid + sc * (c - b)))
        return out

    return f
