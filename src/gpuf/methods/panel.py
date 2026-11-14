"""panel: forecast the daily median by simulating the offer panel behind it (gpuf.panel).

Every input comes from gpuf.panel.offers / panel_offers truncated at the origin day.

params
  variant   "v0": no fitted parameters; median under single/double removals of current offers and returns of
            offers seen in the last `window` days but absent at the origin (same distribution at every h).
            "v1": Monte Carlo of per-offer reprice / exit / return hazards and entrants, estimated from rows on
            or before the origin, pooled by collector x instrument class.
  base      fallback forecaster [name, params] for series without a panel (afhubbard) or without history
  n_paths   Monte Carlo paths (v1)
  a         prior strength (in offer-days) shrinking each offer's own reprice rate to the pool
  ka        prior strength (in reprices) shrinking each offer's own reprice sizes to the pooled sizes
  hl        half-life in days for recency weights on pooled events (0 = equal)
  window    days an absent offer stays eligible to return
  entrants  simulate new offers (v1): True = independent per-offer entry rate, "batch" = entry days with
            batch sizes drawn from past entry days, False = none
  seed      base seed; the run seed is crc32(sid, origin) + seed
  width     optional [name, params]: keep the panel's q50 and take q10/q90 offsets (log, from its q50) from it
"""
from __future__ import annotations

import zlib
from itertools import combinations

import numpy as np

from gpuf import panel as P
from gpuf.methods import get, register

DEFAULT_BASE = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]


def _pivot(o):
    """days (consecutive calendar range of observed days), keys, price matrix [day, key] with NaN = absent."""
    days = np.sort(o["day"].unique())
    keys = np.array(sorted(o["key"].unique()))
    di = np.searchsorted(days, o["day"].to_numpy())
    ki = np.searchsorted(keys, o["key"].to_numpy())
    M = np.full((len(days), len(keys)), np.nan)
    M[di, ki] = o["price"].to_numpy()
    return days, keys, M


def events(o, window):
    """Transitions between consecutive calendar days of one panel (rows already truncated)."""
    days, keys, M = _pivot(o)
    seen = ~np.isnan(M)
    ev = {"rep_day": [], "rep_size": [], "stay_day": [], "stay_rep": [], "stay_key": [],
          "exit_day": [], "exit": [], "ret_day": [], "ret": [], "ret_size": [],
          "ent_day": [], "ent_n": [], "ent_pres": [], "ent_rel": [], "ent_rel_day": []}
    ever = np.zeros(len(keys), bool)
    last_seen = np.full(len(keys), -10 ** 9)
    last_px = np.full(len(keys), np.nan)
    for t in range(len(days)):
        if t and days[t] - days[t - 1] == 1:
            a, b, d = seen[t - 1], seen[t], days[t]
            both = a & b
            rep = both & ~np.isclose(np.nan_to_num(M[t - 1]), np.nan_to_num(M[t]))
            ev["stay_day"] += [d] * int(both.sum()); ev["stay_rep"] += list(rep[both]); ev["stay_key"] += list(keys[both])
            ev["rep_day"] += [d] * int(rep.sum()); ev["rep_size"] += list(np.log(M[t, rep] / M[t - 1, rep]))
            ev["exit_day"] += [d] * int(a.sum()); ev["exit"] += list(~b[a])
            rec = ~a & ever & (days[t - 1] - last_seen <= window)
            ev["ret_day"] += [d] * int(rec.sum()); ev["ret"] += list(b[rec])
            rb = rec & b
            ev["ret_size"] += list(np.log(M[t, rb] / last_px[rb]))
            new = b & ~ever
            ev["ent_day"].append(d); ev["ent_n"].append(int(new.sum())); ev["ent_pres"].append(int(a.sum()))
            if new.any():
                med = np.nanmedian(M[t - 1])
                ev["ent_rel"] += list(np.log(M[t, new] / med)); ev["ent_rel_day"] += [d] * int(new.sum())
        ever |= seen[t]
        last_seen[seen[t]] = days[t]
        last_px[seen[t]] = M[t, seen[t]]
    return {k: np.asarray(v) for k, v in ev.items()}, (days, keys, M)


@register("panel")
def make(variant="v1", base=None, n_paths=2000, a=10.0, ka=5.0, hl=0.0, window=7, entrants=True, seed=0, width=None):
    base_spec = base or DEFAULT_BASE
    base_f = get(base_spec[0], **base_spec[1])
    width_f = get(width[0], **width[1]) if width else None
    ev_cache, pool_cache = {}, {}

    def panel_events(key, o):
        k = (key, o)
        if k not in ev_cache:
            if len(ev_cache) > 20000:
                ev_cache.clear()
            ev_cache[k] = events(P.panel_offers(key, o), window)
        return ev_cache[k]

    def pooled(sid, o):
        g = P.parse_sid(sid)[:2]
        if (g, o) not in pool_cache:
            evs = [panel_events(k, o)[0] for k in P.group_series(sid)]
            cat = {f: np.concatenate([e[f] for e in evs]) for f in evs[0]}
            w = (lambda d: np.ones(len(d)) if not hl else 0.5 ** ((o - d) / hl))

            def rate(flag, day):
                return float((w(day) * flag).sum() / max(w(day).sum(), 1e-9)) if len(flag) else 0.0
            pool_cache[(g, o)] = {
                "p_rep": rate(cat["stay_rep"].astype(float), cat["stay_day"]),
                "p_exit": rate(cat["exit"].astype(float), cat["exit_day"]),
                "p_ret": rate(cat["ret"].astype(float), cat["ret_day"]),
                "p_day": rate((cat["ent_n"] > 0).astype(float), cat["ent_day"]),
                "batch": cat["ent_n"][cat["ent_n"] > 0] if (cat["ent_n"] > 0).any() else np.ones(1, int),
                "lam": float((w(cat["ent_day"]) * cat["ent_n"]).sum() / max((w(cat["ent_day"]) * cat["ent_pres"]).sum(), 1e-9)),
                "rep_size": cat["rep_size"], "rep_w": w(cat["rep_day"]),
                "ret_size": cat["ret_size"] if len(cat["ret_size"]) else np.zeros(1),
                "ent_rel": cat["ent_rel"] if len(cat["ent_rel"]) else np.zeros(1),
            }
        return pool_cache[(g, o)]

    def v0(cur, recent):
        meds = [np.median(cur)]
        groups = []
        n = len(cur)
        if n > 1:
            groups.append([np.median(np.delete(cur, i)) for i in range(n)])
        if n > 2:
            groups.append([np.median(np.delete(cur, list(ij))) for ij in combinations(range(n), 2)])
        if len(recent):
            groups.append([np.median(np.r_[cur, r]) for r in recent])
        if len(recent) > 1:
            groups.append([np.median(np.r_[cur, recent[list(ij)]]) for ij in combinations(range(len(recent)), 2)])
        x = [np.array(meds)] + [np.array(g) for g in groups]
        w = [np.full(len(g), 1.0 / len(g)) for g in x]
        x, w = np.concatenate(x), np.concatenate(w)
        o = np.argsort(x, kind="stable")
        x, w = x[o], w[o]
        cw = np.cumsum(w) / w.sum()
        return [float(x[np.searchsorted(cw, q - 1e-12)]) for q in (0.1, 0.5, 0.9)]

    def v1(sid, o, ev, days, keys, M, hmax, rng):
        pool = pooled(sid, o)
        cur = ~np.isnan(M[-1])
        cidx = np.nonzero(cur)[0]
        last_seen = np.full(len(keys), -10 ** 9)
        for t in range(len(days)):
            last_seen[~np.isnan(M[t])] = days[t]
        last_px = np.array([M[~np.isnan(M[:, j]), j][-1] for j in range(len(keys))])
        ridx = np.nonzero(~cur & (days[-1] - last_seen <= window))[0]
        idx = np.r_[cidx, ridx]
        m0 = len(idx)
        S = (8 if entrants == "batch" else 4) if entrants else 0
        N = n_paths
        price = np.tile(np.r_[last_px[idx], np.zeros(S)], (N, 1))
        present = np.zeros((N, m0 + S), bool)
        present[:, :len(cidx)] = True
        eligible = np.zeros((N, m0 + S), bool)  # absent but may return
        eligible[:, len(cidx):m0] = True
        # per-offer reprice rate and own sizes
        sk, sr = ev["stay_key"], ev["stay_rep"].astype(bool)
        p_rep = np.full(m0 + S, pool["p_rep"])
        own_sizes = [np.zeros(0)] * (m0 + S)
        rep_keys = ev["stay_key"][sr] if len(sk) else np.zeros(0)
        for c, j in enumerate(idx):
            mk = sk == keys[j] if len(sk) else np.zeros(0, bool)
            n_i, r_i = int(mk.sum()), int((sr & mk).sum()) if len(sk) else 0
            p_rep[c] = (r_i + a * pool["p_rep"]) / (n_i + a)
        # own reprice sizes, in key order of stay events
        if len(rep_keys):
            for c, j in enumerate(idx):
                own_sizes[c] = ev["rep_size"][rep_keys == keys[j]]
        rs, rw = pool["rep_size"], pool["rep_w"]
        rcdf = np.cumsum(rw) / rw.sum() if len(rs) else None
        out = {}
        for step in range(1, hmax + 1):
            U = rng.random((N, m0 + S, 3))
            # reprices
            rep = present & (U[:, :, 0] < p_rep[None, :])
            for c in np.nonzero(rep.any(0))[0]:
                r = rep[:, c]
                k = int(r.sum())
                own = own_sizes[c]
                if len(rs):
                    draw = rs[np.searchsorted(rcdf, rng.random(k))] if rcdf is not None else np.zeros(k)
                else:
                    draw = np.zeros(k)
                if len(own):
                    use = rng.random(k) < len(own) / (len(own) + ka)
                    draw[use] = own[rng.integers(0, len(own), int(use.sum()))]
                price[r, c] *= np.exp(draw)
            # exits and returns
            ex = present & (U[:, :, 1] < pool["p_exit"])
            rt = eligible & (U[:, :, 1] < pool["p_ret"])
            if rt.any():
                price[rt] *= np.exp(pool["ret_size"][rng.integers(0, len(pool["ret_size"]), int(rt.sum()))])
            present = (present & ~ex) | rt
            eligible = (eligible & ~rt) | ex
            # entrants
            if S:
                med = np.nanmedian(np.where(present, price, np.nan), axis=1)
                n_pres = present.sum(1)
                free = ~present[:, m0:] & ~eligible[:, m0:]
                if entrants == "batch":  # an entry day brings a batch of offers (size drawn from past batches)
                    k = np.where(U[:, m0, 2] < pool["p_day"], pool["batch"][rng.integers(0, len(pool["batch"]), N)], 0)
                    new = free & (np.cumsum(free, axis=1) <= k[:, None])
                else:
                    p_ent = np.clip(pool["lam"] * n_pres / S, 0, 1)
                    new = free & (U[:, m0:, 2] < p_ent[:, None])
                if new.any():
                    rows, cols = np.nonzero(new)
                    rel = pool["ent_rel"][rng.integers(0, len(pool["ent_rel"]), len(rows))]
                    price[rows, m0 + cols] = med[rows] * np.exp(rel)
                    present[rows, m0 + cols] = True
            out[step] = present.copy(), price.copy()
        return out

    def f(sid, days, vals, origin_day, horizons, ctx):
        last = float(vals[-1])
        if not P.supported(sid):
            return base_f(sid, days, vals, origin_day, horizons, ctx)
        o = P.offers(sid, origin_day)
        if len(o) == 0:
            return base_f(sid, days, vals, origin_day, horizons, ctx)
        ev, (pd_, keys, M) = panel_events(P.parse_sid(sid), origin_day)
        cur = M[-1][~np.isnan(M[-1])]
        med0 = float(np.median(cur))
        scale = last / med0
        gap = int(origin_day - pd_[-1])
        if variant == "v0":
            ls = np.full(len(keys), -10 ** 9)
            for t in range(len(pd_)):
                ls[~np.isnan(M[t])] = pd_[t]
            lp = np.array([M[~np.isnan(M[:, j]), j][-1] for j in range(len(keys))])
            rmask = np.isnan(M[-1]) & (pd_[-1] - ls <= window)
            q = [x * scale for x in v0(cur, lp[rmask])]
            return {h: tuple(q) for h in horizons}
        rng = np.random.default_rng(zlib.crc32(f"{sid}|{origin_day}".encode()) + int(seed))
        sim = v1(sid, origin_day, ev, pd_, keys, M, max(horizons) + gap, rng)
        res = {}
        for h in horizons:
            pr, px = sim[h + gap]
            med = np.nanmedian(np.where(pr, px, np.nan), axis=1)
            med = np.where(np.isnan(med), med0, med)
            res[h] = tuple(float(x) * scale for x in np.quantile(med, [0.1, 0.5, 0.9]))
        if width_f is not None:  # panel centre, width (log offsets of q10, q90 from q50) from another method
            w = width_f(sid, days, vals, origin_day, horizons, ctx)
            res = {h: (res[h][1] * w[h][0] / w[h][1], res[h][1], res[h][1] * w[h][2] / w[h][1]) for h in horizons}
        return res

    return f
