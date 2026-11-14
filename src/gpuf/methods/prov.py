"""prov: simulate the offer panel behind each median with every offer driven by its provider's own recent
signed repricing (gpuf.panel rows, all truncated at the origin).

A provider reprices its whole card with one policy (experiments/prov/results/provider_policy.txt), so the
dynamics are estimated per (collector, provider) across all its offers on that collector: for each
provider-day in the trailing `W` days (rows on or before the origin) the share of its offers that repriced
and their mean nonzero log change. Paths are built from blocks of `L` consecutive provider-days (circular
within the window, block starts recency-weighted with half-life `hl`), so trend and autocorrelation are kept.
Offers whose provider did not reprice in the window stay fixed. A provider with few observed days is shrunk
toward static: per path it is dynamic with probability nd / (nd + a). The median of each simulated panel
is taken and q10/q50/q90 are read from the simulated medians.

params
  W        trailing window in days (7, 14, 21)
  L        block length in provider-days (1 = iid days)
  hl       half-life (days) of recency weights on block starts (0 = equal)
  a        prior strength in provider-days toward static
  sizes    "signed" (resample signed provider-days) or "sym" (provider rate, iid days, random sign)
  comp     simulate exits, returns of offers seen in the last 7 days and entrants (pooled by collector x class)
  centre   "sim" or "last" (q50 forced to the last value, q10/q90 kept on either side of it)
  gate     "none": prov on every panel series; "dyn": prov only where an offer within `nb` ranks of the middle
           belongs to a provider whose trailing reprice rate exceeds `dthr`, base elsewhere
  w        weight of prov in a log-quantile blend with base where prov applies (1 = prov only)
  base     [name, params] fallback (afhubbard, no panel, gated-off cells)
  n_paths, seed
"""
from __future__ import annotations

import warnings
import zlib

import numpy as np

from gpuf import panel as P
from gpuf.methods import get, register

DEFAULT_BASE = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
RET_WINDOW = 7


def _pivot(o):
    days = np.sort(o["day"].unique())
    keys = np.array(sorted(o["key"].unique()))
    M = np.full((len(days), len(keys)), np.nan)
    M[np.searchsorted(days, o["day"].to_numpy()), np.searchsorted(keys, o["key"].to_numpy())] = o["price"].to_numpy()
    return days, keys, M


def _prep():
    """Provider-day repricing stats and pooled composition events, each labelled with the day it is observed
    (a change on day d uses the rows of d-1 and d). Filtering by day <= origin at query time keeps it causal."""
    df = P.load().sort_values(["src", "cls", "gpu", "tier", "key", "day"], kind="stable")
    g = df.groupby(["src", "cls", "gpu", "tier", "key"], sort=False)
    pdy, pp = g["day"].shift(1), g["price"].shift(1)
    m = ((df["day"] - pdy) == 1).to_numpy()
    t = df.loc[m, ["src", "provider", "day"]].assign(r=np.log(df["price"].to_numpy()[m] / pp.to_numpy()[m]))
    t["k"] = (t["r"] != 0).astype(float)
    a = t.groupby(["src", "provider", "day"]).agg(n=("k", "size"), k=("k", "sum"), s=("r", "sum")).reset_index()
    prov = {}
    for (src, pv), x in a.groupby(["src", "provider"]):
        k = x["k"].to_numpy()
        prov[(src, pv)] = (x["day"].to_numpy(), x["n"].to_numpy(float), k, np.where(k > 0, x["s"].to_numpy() / np.maximum(k, 1), 0.0))
    comp = {}
    for (src, cls, gpu, tier), x in df.groupby(["src", "cls", "gpu", "tier"], sort=False):
        days, keys, M = _pivot(x)
        seen = ~np.isnan(M)
        ever = np.zeros(len(keys), bool)
        last_seen = np.full(len(keys), -10 ** 9)
        e = comp.setdefault((src, cls), {f: [] for f in ("ex_d", "ex", "rt_d", "rt", "en_d", "en_n", "en_p", "rel_d", "rel")})
        for i in range(len(days)):
            if i and days[i] - days[i - 1] == 1:
                b0, b1, d = seen[i - 1], seen[i], days[i]
                e["ex_d"] += [d] * int(b0.sum()); e["ex"] += list(~b1[b0])
                rec = ~b0 & ever & (days[i - 1] - last_seen <= RET_WINDOW)
                e["rt_d"] += [d] * int(rec.sum()); e["rt"] += list(b1[rec])
                new = b1 & ~ever
                e["en_d"].append(d); e["en_n"].append(int(new.sum())); e["en_p"].append(int(b0.sum()))
                if new.any():
                    e["rel"] += list(np.log(M[i, new] / np.nanmedian(M[i - 1]))); e["rel_d"] += [d] * int(new.sum())
            ever |= seen[i]
            last_seen[seen[i]] = days[i]
    comp = {k: {f: np.asarray(v, float) for f, v in e.items()} for k, e in comp.items()}
    return prov, comp


@register("prov")
def make(W=14, L=7, hl=7.0, a=3.0, sizes="signed", comp=True, centre="sim", gate="none", nb=1, dthr=0.15,
         w=1.0, base=None, n_paths=1000, seed=0):
    base_spec = base or DEFAULT_BASE
    base_f = get(base_spec[0], **base_spec[1])
    st = {}

    def window(src, pv, o):
        x = st["prov"].get((src, pv))
        if x is None:
            return None
        d, n, k, mr = x
        sel = (d <= o) & (d > o - W)
        return (d[sel], n[sel], k[sel], mr[sel]) if sel.any() else None

    def pooled(src, cls, o):
        e = st["comp"].get((src, cls))
        if e is None:
            return None
        def rate(f, fd):
            s = e[fd] <= o
            return float(e[f][s].mean()) if s.any() else 0.0
        s = e["en_d"] <= o
        rel = e["rel"][e["rel_d"] <= o]
        return {"p_exit": rate("ex", "ex_d"), "p_ret": rate("rt", "rt_d"),
                "lam": float(e["en_n"][s].sum() / max(e["en_p"][s].sum(), 1.0)), "rel": rel if len(rel) else np.zeros(1)}

    def simulate(src, cls, o, keys, M, provs, H, rng):
        last_seen_i = np.array([np.nonzero(~np.isnan(M[:, j]))[0][-1] for j in range(len(keys))])
        last_px = M[last_seen_i, np.arange(len(keys))]
        cur = ~np.isnan(M[-1])
        pool = pooled(src, cls, o) if comp else None
        ret = np.nonzero(~cur & (len(M) - 1 - last_seen_i <= RET_WINDOW))[0] if comp else np.zeros(0, int)
        idx = np.r_[np.nonzero(cur)[0], ret]
        m0, S, N = len(idx), (3 if comp else 0), n_paths
        R = np.zeros((N, m0, H))
        for pv in set(provs[idx]):
            x = window(src, pv, o)
            if x is None or x[2].sum() == 0:
                continue
            d, n, k, mr = x
            nd = len(d)
            share = k / n
            dyn = rng.random(N) < nd / (nd + a)
            if sizes == "sym":
                pi = rng.integers(0, nd, (N, H))
                sgn = np.where(rng.random((N, H)) < 0.5, -1.0, 1.0)
                step = np.abs(mr[pi]) * sgn
            else:
                rw = 0.5 ** ((o - d) / hl) if hl else np.ones(nd)
                nbk = -(-H // L)
                starts = rng.choice(nd, size=(N, nbk), p=rw / rw.sum())
                pi = ((starts[:, :, None] + np.arange(L)[None, None, :]) % nd).reshape(N, -1)[:, :H]
                step = mr[pi]
            for c in np.nonzero(provs[idx] == pv)[0]:
                mv = rng.random((N, H)) < share[pi]
                R[:, c, :] = np.where(mv & dyn[:, None], step, 0.0)
        px0 = last_px[idx]
        cum = px0[None, :, None] * np.exp(np.cumsum(R, axis=2))
        present = np.zeros((N, m0 + S), bool)
        present[:, :int(cur.sum())] = True
        eligible = np.zeros((N, m0 + S), bool)
        eligible[:, int(cur.sum()):m0] = True
        ent_px = np.zeros((N, S))
        meds = {}
        for t in range(H):
            price = np.concatenate([cum[:, :, t], ent_px], axis=1)
            if comp:
                U = rng.random((N, m0 + S))
                ex = present & (U < pool["p_exit"])
                rt = eligible & (U < pool["p_ret"])
                present = (present & ~ex) | rt
                eligible = (eligible & ~rt) | ex
                if S:
                    med = np.nanmedian(np.where(present, price, np.nan), axis=1)
                    free = ~present[:, m0:] & ~eligible[:, m0:]
                    new = free & (rng.random((N, S)) < np.clip(pool["lam"] * present.sum(1) / S, 0, 1)[:, None])
                    if new.any():
                        r_, c_ = np.nonzero(new)
                        ent_px[r_, c_] = med[r_] * np.exp(pool["rel"][rng.integers(0, len(pool["rel"]), len(r_))])
                        present[r_, m0 + c_] = True
                        price = np.concatenate([cum[:, :, t], ent_px], axis=1)
            med = np.nanmedian(np.where(present, price, np.nan), axis=1)
            meds[t + 1] = np.where(np.isnan(med), np.median(px0[:int(cur.sum())]), med)
        return meds

    def mid_state(src, o, cur_px, cur_prov):
        n = len(cur_px)
        order = np.argsort(cur_px, kind="stable")
        lo, hi = max((n - 1) // 2 - nb, 0), min(n // 2 + nb, n - 1)
        near = set(cur_prov[order[lo:hi + 1]])
        mids = set(cur_prov[order[[(n - 1) // 2, n // 2]]])
        def rate(ps):
            xs = [window(src, p, o) for p in ps]
            xs = [x for x in xs if x is not None]
            if not xs:
                return 0.0, 0.0
            n_ = sum(x[1].sum() for x in xs)
            return sum(x[2].sum() for x in xs) / n_, sum((x[2] * x[3]).sum() for x in xs) / n_
        r_near = max(rate([p])[0] for p in near)
        r_mid, d_mid = rate(mids)
        return {"dyn_near": r_near > dthr, "mid_rate": r_mid, "mid_drift": d_mid}

    def f(sid, days, vals, origin_day, horizons, ctx):
        if not st:
            st["prov"], st["comp"] = _prep()
        if not P.supported(sid):
            return base_f(sid, days, vals, origin_day, horizons, ctx)
        o_rows = P.offers(sid, origin_day)
        if len(o_rows) == 0:
            return base_f(sid, days, vals, origin_day, horizons, ctx)
        last = float(vals[-1])
        src, cls, _, _ = P.parse_sid(sid)
        pdays, keys, M = _pivot(o_rows)
        kp = o_rows.drop_duplicates("key").set_index("key")["provider"]
        provs = kp.reindex(keys).to_numpy()
        cur = ~np.isnan(M[-1])
        ms = mid_state(src, origin_day, M[-1][cur], provs[cur])
        f.state[(sid, origin_day)] = ms
        if gate == "dyn" and not ms["dyn_near"]:
            return base_f(sid, days, vals, origin_day, horizons, ctx)
        gap = int(origin_day - pdays[-1])
        rng = np.random.default_rng(zlib.crc32(f"{sid}|{origin_day}".encode()) + int(seed))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            meds = simulate(src, cls, origin_day, keys, M, provs, max(horizons) + gap, rng)
        scale = last / float(np.median(M[-1][cur]))
        res = {}
        for h in horizons:
            q10, q50, q90 = (float(x) * scale for x in np.quantile(meds[h + gap], [0.1, 0.5, 0.9]))
            if centre == "last":
                q10, q50, q90 = min(q10, last), last, max(q90, last)
            res[h] = (q10, q50, q90)
        if w < 1.0:
            b = base_f(sid, days, vals, origin_day, horizons, ctx)
            res = {h: tuple(float(np.exp(w * np.log(res[h][i]) + (1 - w) * np.log(b[h][i]))) for i in range(3))
                   for h in horizons}
        return res

    f.state = {}
    return f
