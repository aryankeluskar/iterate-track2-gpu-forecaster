"""entry: prov {"L":1,"W":21,"gate":"dyn"} plus simulated membership events in the tails.

Candidate events at origin o (rows dated on or before o only, via gpuf.panel and a once-built table of
panel/provider run boundaries filtered at query time):
  entry : provider listing the same GPU and class on the other collector on day o that has never been in this
          panel; enters at its other-collector price. Daily probability `pe` per candidate (measured 0.0034).
  exit  : provider in this panel that left or newly entered another panel of the same collector on days
          o-2..o; all its offers leave. Daily probability `px` per candidate (measured about 0.06).
Each event is applied to the origin-day panel (median recomputed, rescaled to the last value) and mixed as a
point mass with weight 1-(1-p)^h (total capped at `cap`) into prov's distribution, which is rebuilt from its
three quantiles by log-linear interpolation (tails extended `ext` times the outer slope). The gate opens (full
prov) for a series whenever a candidate exists.
"""
from __future__ import annotations

import numpy as np

from gpuf import panel as P
from gpuf.methods import get, register

OTHER = {"fastgpu_daily": "gpurentalprices", "gpurentalprices": "fastgpu_daily"}
U = (np.arange(2000) + 0.5) / 2000


def _runs():
    """Per (src, panel key, provider): sorted day arrays present; plus event tables labelled by event day."""
    df = P.load()
    ev = {"en": [], "ex": []}  # (src, panel, provider, day)
    first = {}
    obsdays = {s: set(df.loc[df.src == s, "day"].unique().tolist()) for s in P.SOURCES}
    for (src, cls, gpu, tier, pv), x in df.groupby(["src", "cls", "gpu", "tier", "provider"], sort=False):
        d = np.unique(x["day"].to_numpy())
        pk = (src, cls, gpu, tier)
        first[(pk, pv)] = int(d[0])
        ev["en"].append((src, pk, pv, int(d[0])))
        for i in np.nonzero(np.r_[d[1:] - d[:-1] > 1, True])[0]:
            t = int(d[i]) + 1
            if t in obsdays[src]:
                ev["ex"].append((src, pk, pv, t))
    return first, ev


@register("entry")
def make(pe=0.0034, px=0.06, cap=0.5, ext=1.5, win=3, prov_params=None, cal=False):
    pp = {"L": 1, "W": 21, "gate": "dyn"}
    pp.update(prov_params or {})
    dyn = get("prov", **pp)
    full = get("prov", **{**pp, "gate": "none"})
    st = {}

    def pdist(q):
        l = np.log(np.maximum(q, 1e-9))
        lo = l[0] - ext * (l[1] - l[0]) / 0.4 * 0.08
        hi = l[2] + ext * (l[2] - l[1]) / 0.4 * 0.08
        return np.exp(np.interp(U, [0.02, 0.1, 0.5, 0.9, 0.98], [lo, l[0], l[1], l[2], hi]))

    def candidates(sid, o):
        src, cls, gpu, tier = P.parse_sid(sid)
        pk = (src, cls, gpu, tier)
        rows = P.offers(sid, o)
        dmax = int(rows["day"].max())
        cur = rows[rows["day"] == dmax]
        ever = set(rows["provider"])
        ents = []
        oth = OTHER[src]
        refs = {}
        for k in P._index():
            if k[0] == oth and k[1] == cls and k[2] == gpu:
                r = P.panel_offers(k, o)
                r = r[r["day"] == o]
                for pv, g in r.groupby("provider"):
                    if pv not in ever:
                        refs.setdefault(pv, []).append((k[3] == tier, float(g["price"].median())))
        for pv, l in refs.items():
            same = [p for s, p in l if s]
            ents.append((pv, float(np.median(same or [p for _, p in l]))))
        flagged = set()
        for kind in ("en", "ex"):
            for s_, k_, pv, t in st["ev"][kind]:
                if s_ == src and k_ != pk and o - win + 1 <= t <= o:
                    flagged.add(pv)
        exits = [pv for pv in set(cur["provider"]) if pv in flagged]
        return cur, ents, exits

    def f(sid, days, vals, origin_day, horizons, ctx):
        if not st:
            st["first"], st["ev"] = _runs()
        res = dyn(sid, days, vals, origin_day, horizons, ctx)
        if not P.supported(sid) or len(P.offers(sid, origin_day)) == 0:
            return res
        cur, ents, exits = candidates(sid, origin_day)
        if not ents and not exits:
            return res
        if not dyn.state.get((sid, origin_day), {}).get("dyn_near", False):
            res = full(sid, days, vals, origin_day, horizons, ctx)
        last = float(vals[-1])
        px0 = cur["price"].to_numpy()
        m0 = float(np.median(px0))
        vals_ev, p_ev = [], []
        for pv, price in ents:
            vals_ev.append(float(np.median(np.r_[px0, price]))); p_ev.append(pe)
        for pv in exits:
            keep = px0[cur["provider"].to_numpy() != pv]
            if len(keep):
                vals_ev.append(float(np.median(keep))); p_ev.append(px)
        vals_ev = np.array(vals_ev) / m0 * last
        p_ev = np.array(p_ev)
        out = {}
        for h in horizons:
            w = 1 - (1 - p_ev) ** h
            if w.sum() > cap:
                w = w * cap / w.sum()
            x = np.r_[pdist(np.array(res[h])), vals_ev]
            wt = np.r_[np.full(len(U), (1 - w.sum()) / len(U)), w]
            o = np.argsort(x)
            c = np.cumsum(wt[o]) / wt.sum()
            q = [float(x[o][min(np.searchsorted(c, t), len(x) - 1)]) for t in (0.1, 0.5, 0.9)]
            out[h] = tuple(q)
        return out

    f.state = dyn.state
    return f
