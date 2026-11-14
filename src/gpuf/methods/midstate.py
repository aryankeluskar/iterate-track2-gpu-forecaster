"""midstate: pooled empirical h-day log changes of the panel median, conditioned on the repricing state of the
provider(s) holding the middle offer(s) at the origin.

All panel features at day t use rows dated on or before t, and a training case (t, t+h) needs t+h <= origin;
the panel is read only through gpuf.panel.panel_offers(key, origin_day), which drops later rows.

params
  state    "mid" | "midchg" (crossed with mix's own changed-in-last-sk-days state) | "chgk" (mix state only)
  w        trailing window (days) for the middle provider's reprice rate and signed mean change
  bounds   reprice-rate bucket edges
  min_n    minimum offer-day pairs in the window for the rate to be known
  nmin     minimum matching pooled cases; thinner buckets absorb neighbouring buckets, then fall back to all cases
  k, hl, sk  as in mix (pooled mass relative to one own case, recency half-life, own-state window)
  centre   "median" | "last"
  tailsign condition q90 on sign of the middle provider's signed mean change (when >= nmin cases match)
  gapclip  if > 0, cap the q90 (q10) log offset at gapclip * log-gap to the next offer above (below) + gapfloor
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from gpuf import panel
from gpuf.methods import get, register

MIXP = {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}


def wquantile(x, w, qs):
    o = np.argsort(x, kind="stable")
    x, w = x[o], w[o]
    cw = np.cumsum(w)
    return np.interp(qs, (cw - 0.5 * w) / cw[-1], x)


def changed_within(days, vals, k):
    c = np.zeros(len(vals), dtype=np.int8)
    last = -10 ** 9
    for i in range(len(vals)):
        if i and vals[i] != vals[i - 1]:
            last = days[i]
        c[i] = 1 if days[i] - last < k else 0
    return c


def provider_tables(src, origin, w):
    """Per (src, origin): provider -> arrays of trailing-w reprice count, pair count, signed log change sum, by day."""
    keys = [k for k in panel._index() if k[0] == src]
    parts = []
    for key in keys:
        o = panel.panel_offers(key, origin)
        o = o.sort_values(["key", "day"], kind="stable")
        pdday = o.groupby("key")["day"].shift(1)
        pp = o.groupby("key")["price"].shift(1)
        m = (o["day"] - pdday) == 1
        r = np.log(o["price"][m] / pp[m])
        parts.append(pd.DataFrame({"provider": o["provider"][m], "day": o["day"][m], "ch": (r != 0).astype(int), "r": r}))
    c = pd.concat(parts, ignore_index=True)
    if not len(c):
        return None
    g = c.groupby(["provider", "day"]).agg(k=("ch", "sum"), n=("ch", "size"), s=("r", "sum")).reset_index()
    d0, d1 = int(g["day"].min()), int(origin)
    provs = sorted(g["provider"].unique())
    pi = {p: i for i, p in enumerate(provs)}
    D = d1 - d0 + 1
    A = np.zeros((3, len(provs), D))
    A[0][g["provider"].map(pi).to_numpy(), g["day"].to_numpy() - d0] = g["k"]
    A[1][g["provider"].map(pi).to_numpy(), g["day"].to_numpy() - d0] = g["n"]
    A[2][g["provider"].map(pi).to_numpy(), g["day"].to_numpy() - d0] = g["s"]
    C = np.concatenate([np.zeros((3, len(provs), 1)), np.cumsum(A, axis=2)], axis=2)
    return pi, d0, C


def panel_cases(key, origin, pi, d0, C, w):
    """Daily table for one panel: day, med, n, rate, nn, drift, gapup, gapdn (all causal)."""
    o = panel.panel_offers(key, origin).sort_values(["day", "price"], kind="stable")
    day = o["day"].to_numpy()
    price = o["price"].to_numpy()
    prov = np.array([pi.get(p, -1) for p in o["provider"]], dtype=np.int64)
    ud, st, cnt = np.unique(day, return_index=True, return_counts=True)
    lo, hi = st + (cnt - 1) // 2, st + cnt // 2
    med = (price[lo] + price[hi]) / 2
    up = np.where(hi + 1 < st + cnt, price[np.minimum(hi + 1, len(price) - 1)], np.nan)
    dn = np.where(lo - 1 >= st, price[np.maximum(lo - 1, 0)], np.nan)
    gapup = np.log(up / med)
    gapdn = np.log(med / dn)
    idx = ud - d0 + 1
    i0 = np.clip(idx - w, 0, None)

    def tw(a, p):
        return np.where(p >= 0, C[a][np.maximum(p, 0), idx] - C[a][np.maximum(p, 0), i0], 0.0)

    plo, phi = prov[lo], prov[hi]
    dup = (phi != plo)
    k_ = tw(0, plo) + np.where(dup, tw(0, phi), 0)
    n_ = tw(1, plo) + np.where(dup, tw(1, phi), 0)
    s_ = tw(2, plo) + np.where(dup, tw(2, phi), 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        rate = np.where(n_ > 0, k_ / n_, np.nan)
        drift = np.where(n_ > 0, s_ / n_, np.nan)
    return {"day": ud, "med": med, "n": cnt, "rate": rate, "nn": n_, "drift": drift, "gapup": gapup, "gapdn": gapdn,
            "chg": None}


@register("midstate")
def make(state="mid", w=14, bounds=(0.02, 0.15, 0.5), min_n=5, nmin=40, k=20.0, hl=30.0, sk=3, centre="median",
         tailsign=False, gapclip=0.0, gapfloor=0.01, drift_eps=0.002):
    bounds = np.asarray(bounds, float)
    base = get("mix", **MIXP)
    cache = {}

    def tables(src, cls, origin):
        key = (src, cls, origin, w)
        if key not in cache:
            if len(cache) > 6:
                cache.clear()
            pt = provider_tables(src, origin, w)
            if pt is None:
                cache[key] = None
                return None
            pi, d0, C = pt
            out = {}
            for pk in panel.group_series(f"{src}.{cls}.X.Y.median"):
                t = panel_cases(pk, origin, pi, d0, C, w)
                t["chg"] = changed_within(t["day"], t["med"], sk)
                t["bk"] = np.where((t["nn"] >= min_n) & ~np.isnan(t["rate"]), np.searchsorted(bounds, t["rate"], side="right"), -1)
                t["sg"] = np.where(np.isnan(t["drift"]), 0, np.where(t["drift"] > drift_eps, 1, np.where(t["drift"] < -drift_eps, -1, 0)))
                out[pk] = t
            cache[key] = out
        return cache[key]

    def cases(tabs, h, origin):
        """concatenated cases for each panel key: y, end day, bucket, own state, sign, panel key index."""
        res = {}
        for pk, t in tabs.items():
            j = np.searchsorted(t["day"], t["day"] + h)
            ok = j < len(t["day"])
            i = np.nonzero(ok)[0]
            j = j[ok]
            m = t["day"][j] == t["day"][i] + h
            i, j = i[m], j[m]
            res[pk] = (np.log(t["med"][j] / t["med"][i]), t["day"][j], t["bk"][i], t["chg"][i], t["sg"][i])
        return res

    def pick(bk, cur, nmin_):
        """boolean mask of cases matching bucket cur, merged with neighbouring buckets until >= nmin_ cases."""
        if cur < 0:
            return np.ones(len(bk), bool)
        lo = hi = cur
        known = bk >= 0
        while True:
            m = known & (bk >= lo) & (bk <= hi)
            if m.sum() >= nmin_ or (lo == 0 and hi == len(bounds)):
                return m if m.sum() >= nmin_ else np.ones(len(bk), bool)
            cl = known & (bk == lo - 1) if lo > 0 else None
            ch = known & (bk == hi + 1) if hi < len(bounds) else None
            if ch is None or (cl is not None and cl.sum() >= ch.sum()):
                lo -= 1
            else:
                hi += 1

    def f(sid, days, vals, origin_day, horizons, ctx):
        last = float(vals[-1])
        if not panel.supported(sid):
            return base(sid, days, vals, origin_day, horizons, ctx)
        src, cls, gpu, tier = panel.parse_sid(sid)
        tabs = tables(src, cls, origin_day)
        if tabs is None or len(tabs.get((src, cls, gpu, tier), {"day": []})["day"]) == 0:
            return base(sid, days, vals, origin_day, horizons, ctx)
        me = (src, cls, gpu, tier)
        t = tabs[me]
        i = len(t["day"]) - 1
        cur_b, cur_c, cur_s = int(t["bk"][i]), int(t["chg"][i]), int(t["sg"][i])
        gu, gd = float(t["gapup"][i]), float(t["gapdn"][i])
        out = {}
        for h in horizons:
            cs = cases(tabs, h, origin_day)
            ys, es, bs, cc, sg, own = [], [], [], [], [], []
            for pk, (y, e, b, c, s) in cs.items():
                ys.append(y); es.append(e); bs.append(b); cc.append(c); sg.append(s)
                own.append(np.full(len(y), pk == me))
            y, e, b, c, s, ow = map(np.concatenate, (ys, es, bs, cc, sg, own))
            if not len(y):
                out[h] = (last, last, last)
                continue
            rw = 0.5 ** ((origin_day - e) / hl) if hl else np.ones(len(y))

            def qs(extra=None):
                if state == "chgk":
                    m = c == cur_c
                else:
                    m = pick(b, cur_b, nmin)
                    if state == "midchg":
                        m2 = m & (c == cur_c)
                        m = m2 if (m2 & ~ow).sum() >= nmin else m
                if extra is not None:
                    m3 = m & extra
                    m = m3 if (m3 & ~ow).sum() >= nmin else m
                if not m.any():
                    m = np.ones(len(y), bool)
                wo = np.where(m & ow, rw, 0.0)
                wp = np.where(m & ~ow, rw, 0.0)
                tot = wp.sum()
                wt = wo + (wp * (k / tot) if tot > 0 and k > 0 else wp * 0)
                if wt.sum() <= 0:
                    wt = np.where(m, rw, 0.0)
                return wquantile(y[m], wt[m], [0.1, 0.5, 0.9])

            a, mdn, c9 = qs()
            if tailsign:
                c9 = qs(extra=(s == cur_s))[2]
            mid = 0.0 if centre == "last" else mdn
            lo_off, hi_off = a - mdn, c9 - mdn
            if gapclip > 0:
                if np.isfinite(gu):
                    hi_off = min(hi_off, gapclip * gu + gapfloor)
                if np.isfinite(gd):
                    lo_off = max(lo_off, -(gapclip * gd + gapfloor))
            out[h] = (last * np.exp(mid + lo_off), last * np.exp(mid), last * np.exp(mid + hi_off))
        return out

    return f
