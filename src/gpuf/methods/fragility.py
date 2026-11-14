"""fragility: wrap a base method and put mixture mass where the daily median can jump by panel composition.

At the origin the panel behind the last value is known (gpuf.panel). Reachable values: the median after removing
one offer, after removing one provider's offers, and after adding one offer below the minimum, above the maximum
or at the typical relative price of past entrants. Probability p of at least one composition event within h days
comes from per-offer exit and entry rates pooled by collector and class (recency weighted, rows <= origin only).

params
  base, base_params  wrapped method (default mix with the reference params)
  mode     "mix" (mixture of base and reachable atoms), "soft" (pull q10/q90 toward the reachable value), "off"
  hl       half-life of rate recency weights in days
  boost    multiplier on exit hazard of offers whose provider had an event on another series in the last `bdays`
  bdays    window of the cluster flag
  bkind    "comp" (enter/exit events) or "any" (also repricings)
  c        soft: tail shift fraction = min(1, c * p_side)
  pw       share of a multi-offer provider's exit mass given to removing all its offers together
  pscale   multiplier on p
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from gpuf import panel
from gpuf.methods import get, register
from gpuf.methods.mix import wquantile

REF = {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}
_C: dict = {}


def build_events(df: pd.DataFrame) -> dict:
    """Event tables from a panel frame (all dates; consumers filter by day <= origin)."""
    trans, ent, prov = [], [], []
    for (src, cls, gpu, tier), g in df.groupby(["src", "cls", "gpu", "tier"], sort=False):
        sid = (src, cls, gpu, tier)
        days = {d: x for d, x in g.groupby("day")}
        for d in sorted(days):
            a, b = days.get(d - 1), days[d]
            if a is None:
                continue
            ka, kb = set(a["key"]), set(b["key"])
            exits, enters = ka - kb, kb - ka
            pa, pb = a.set_index("key")["price"], b.set_index("key")["price"]
            mprev, lo, hi = float(np.median(a["price"])), float(a["price"].min()), float(a["price"].max())
            trans.append((src, cls, sid, d, len(ka), len(exits), len(enters)))
            for k in enters:
                p = float(pb[k])
                ent.append((src, cls, d, p / mprev, 0 if p < lo else (2 if p > hi else 1)))
            pr_a = dict(zip(a["key"], a["provider"]))
            pr_b = dict(zip(b["key"], b["provider"]))
            ev = {}
            for k in exits:
                ev.setdefault(pr_a[k], [0, 0])[0] += 1
            for k in enters:
                ev.setdefault(pr_b[k], [0, 0])[0] += 1
            for k in ka & kb:
                if abs(pa[k] - pb[k]) > 1e-9:
                    ev.setdefault(pr_b[k], [0, 0])[1] += 1
            for p, (c, r) in ev.items():
                prov.append((src, sid, d, p, c, r))
    T = pd.DataFrame(trans, columns=["src", "cls", "sid", "day", "n_risk", "n_exit", "n_enter"])
    E = pd.DataFrame(ent, columns=["src", "cls", "day", "rel", "pos"])
    P = pd.DataFrame(prov, columns=["src", "sid", "day", "provider", "comp", "rep"])
    return {"T": T, "E": E, "P": P}


def events() -> dict:
    idx = panel._index()
    if _C.get("idx") is not idx:
        _C.clear()
        _C["idx"] = idx
        _C["ev"] = build_events(panel.load())
        _C["rate"] = {}
    return _C["ev"]


def rates(src, cls, origin_day, hl):
    ev = events()
    key = (src, cls, origin_day, hl)
    if key in _C["rate"]:
        return _C["rate"][key]
    T, E = ev["T"], ev["E"]
    t = T[(T.src == src) & (T.day <= origin_day)]
    tc = t[t.cls == cls]
    if len(tc) >= 100:
        t = tc
    e = E[(E.src == src) & (E.day <= origin_day)]
    ecl = e[e.cls == cls]
    if len(ecl) >= 15:
        e = ecl
    w = 0.5 ** ((origin_day - t.day.to_numpy()) / hl)
    risk = (w * t.n_risk.to_numpy()).sum()
    rx = (w * t.n_exit.to_numpy()).sum() / max(risk, 1e-9)
    re = (w * t.n_enter.to_numpy()).sum() / max(risk, 1e-9)
    if len(e):
        we = 0.5 ** ((origin_day - e.day.to_numpy()) / hl)
        sh = np.array([we[e.pos.to_numpy() == k].sum() for k in range(3)]) + 0.1
        sh = sh / sh.sum()
        typ = e[e.pos == 1]
        rel = wquantile(typ.rel.to_numpy(), 0.5 ** ((origin_day - typ.day.to_numpy()) / hl), [0.5])[0] if len(typ) else 1.0
    else:
        sh, rel = np.array([1 / 3] * 3), 1.0
    out = (float(rx), float(re), sh, float(rel))
    _C["rate"][key] = out
    return out


def flagged(src, sid, origin_day, bdays, bkind):
    P = events()["P"]
    p = P[(P.src == src) & (P.day <= origin_day) & (P.day > origin_day - bdays) & (P.sid != sid)]
    col = p.comp if bkind == "comp" else p.comp + p.rep
    return set(p.provider[col > 0])


def reach(sid, origin_day, last_day, h, rt, boost, bdays, bkind, pw):
    """(p, atom log-ratios to the current median, atom weights summing to 1) or None."""
    src = panel.parse_sid(sid)[0]
    o = panel.offers(sid, origin_day)
    o = o[o["day"] == last_day]
    n = len(o)
    if n < 2:
        return None
    pr = o["price"].to_numpy(float)
    prov = o["provider"].to_numpy()
    m0 = float(np.median(pr))
    if m0 <= 0:
        return None
    rx, re, sh, rel = rt
    fl = flagged(src, panel.parse_sid(sid), origin_day, bdays, bkind) if boost != 1 else set()
    hz = np.array([rx * (boost if p in fl else 1.0) for p in prov])
    atoms, wts = [], []
    for p in np.unique(prov):
        mask = prov == p
        if mask.sum() == 1:
            atoms.append(np.median(pr[~mask])); wts.append(hz[mask][0])
        else:
            atoms.append(np.median(pr[~mask]) if (~mask).any() else m0); wts.append(pw * hz[mask].sum())
            for i in np.nonzero(mask)[0]:
                atoms.append(np.median(np.delete(pr, i))); wts.append((1 - pw) * hz[i])
    lam_e = re * n
    for v, s in ((pr.min() * 0.9, sh[0]), (pr.max() * 1.1, sh[2]), (rel * m0, sh[1])):
        atoms.append(float(np.median(np.append(pr, v)))); wts.append(lam_e * s)
    wts = np.array(wts)
    lam = wts.sum()
    if lam <= 0:
        return None
    return float(1.0 - np.exp(-h * lam)), np.log(np.array(atoms) / m0), wts / lam


def base_atoms(q, K=100):
    """K quantile atoms (log space) of the base forecast: linear in log between q10, q50, q90, tails extrapolated."""
    lq = np.log(np.maximum(np.asarray(q, float), 1e-9))
    u = (np.arange(K) + 0.5) / K
    return np.interp(u, [0.0, 0.1, 0.5, 0.9, 1.0],
                     [lq[0] - (lq[1] - lq[0]) * 0.25, lq[0], lq[1], lq[2], lq[2] + (lq[2] - lq[1]) * 0.25])


@register("fragility")
def make(base="mix", base_params=None, mode="mix", hl=30.0, boost=1.0, bdays=3, bkind="comp", c=1.0, pw=0.5,
         pscale=1.0, K=100):
    bf = get(base, **(REF if base_params is None else base_params))

    def f(sid, days, vals, origin_day, horizons, ctx):
        out = bf(sid, days, vals, origin_day, horizons, ctx)
        if mode == "off" or not panel.supported(sid) or origin_day - int(days[-1]) > 3:
            return out
        src, cls, _, _ = panel.parse_sid(sid)
        lg = np.log(float(vals[-1]))
        rt = rates(src, cls, origin_day, hl)
        res = {}
        for h in horizons:
            q = out[h]
            r = reach(sid, origin_day, int(days[-1]), h, rt, boost, bdays, bkind, pw)
            if r is None:
                res[h] = q
                continue
            p, lr, w = r
            p = min(1.0, p * pscale)
            x = lr + lg
            if mode == "mix":
                wt = np.concatenate([np.full(K, (1 - p) / K), p * w])
                a, _, cc = wquantile(np.concatenate([base_atoms(q, K), x]), wt, [0.1, 0.5, 0.9])
                res[h] = (float(np.exp(a)), q[1], float(np.exp(cc)))
            else:
                lq = np.log(np.maximum(np.array(q), 1e-9))
                q10, q90 = lq[0], lq[2]
                for side, sel in ((2, x > lq[2]), (0, x < lq[0])):
                    if sel.any():
                        t = float(np.average(x[sel], weights=w[sel]))
                        s = min(1.0, c * p * w[sel].sum()) * (t - lq[side])
                        if side == 2:
                            q90 = lq[2] + s
                        else:
                            q10 = lq[0] + s
                res[h] = (float(np.exp(q10)), q[1], float(np.exp(q90)))
        return res

    return f
