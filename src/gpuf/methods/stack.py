"""stack: online-learned combination of a bank of experts' quantile forecasts, in log-price space.

The bank is a list of parquet files written by experiments/dump.py (the same files `replay` reads). At origin d the
combiner sees only cells (series, origin o, horizon h) whose target day o+h <= d: their truth is read from the
history the harness already truncated at d, and the expert forecasts for them were made at o <= d by causal methods.

params
  bank     list of parquet paths (experts, in a fixed order)
  comb     "equal" | "ewa" | "fs" (fixed share) | "ftl" (follow the leader) | "stack" (rolling pinball LP)
  key      "h" (one weight vector per horizon) or "grp" (per horizon x collector x class)
  tsep     True: separate weights for q10, q50, q90; False: one vector shared by the three quantiles
  eta      learning rate on the relative excess loss (ewa, fs)
  gamma    per-day forgetting factor on past losses (ewa, ftl)
  alpha    share rate (fs)
  window   rolling window in target days (stack)
  lam      shrink toward equal weights (stack), 0..1
  nmin     fewer known cells than this in a key: equal weights
"""
from __future__ import annotations

import numpy as np

from gpuf.methods import register

TAUS = np.array([0.1, 0.5, 0.9])


def pin(y, q, tau):
    d = y - q
    return np.maximum(tau * d, (tau - 1.0) * d)


def _softmax(z):
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def _lp(x, ly, p, tau, E):
    from scipy.optimize import linprog
    n = x.shape[1]
    c = np.r_[np.zeros(E), tau * p, (1 - tau) * p]
    A = np.hstack([x.T, np.eye(n), -np.eye(n)])
    A = np.vstack([A, np.r_[np.ones(E), np.zeros(2 * n)]])
    b = np.r_[ly, 1.0]
    r = linprog(c, A_eq=A, b_eq=b, bounds=[(0, None)] * (E + 2 * n), method="highs")
    if r.status != 0:
        return np.full(E, 1.0 / E)
    w = np.clip(r.x[:E], 0, None)
    return w / w.sum()


def weights(d, C, comb="ewa", key="h", tsep=False, eta=20.0, gamma=1.0, alpha=0.05, window=28, lam=0.0, nmin=20):
    """Weight tables at origin d: {(h, g): array (3, E)}. C: dict of arrays tday, h, g, y, logq (E, n, 3)."""
    E = C["logq"].shape[0]
    eq = np.full((3, E), 1.0 / E)
    keys = {}
    if comb == "equal":
        return keys, eq
    known = C["tday"] <= d
    if not known.any():
        return keys, eq
    tday, hh, gg, y, lq = C["tday"][known], C["h"][known], C["g"][known], C["y"][known], C["logq"][:, known, :]
    L = pin(y[None, :, None], np.exp(lq), TAUS[None, None, :])
    gkey = gg if key == "grp" else np.full(len(gg), "*")
    for h in np.unique(hh):
        for g in np.unique(gkey[hh == h]):
            m = (hh == h) & (gkey == g)
            if m.sum() < nmin:
                continue
            Lm = L[:, m, :]
            td = tday[m]
            if comb in ("ewa", "ftl"):
                gw = gamma ** (d - td)
                S = np.einsum("enk,n->ek", Lm, gw)
                S = S if tsep else np.repeat(S.sum(1, keepdims=True), 3, axis=1)
                W = np.zeros((3, E))
                for t in range(3):
                    s = S[:, t]
                    if s.mean() <= 0:
                        W[t] = 1.0 / E
                    elif comb == "ewa":
                        W[t] = _softmax(-eta * (s / s.mean() - 1.0))
                    else:
                        top = s <= s.min() + 1e-12
                        W[t] = top / top.sum()
            elif comb == "fs":
                days = np.unique(td)
                W = np.zeros((3, E))
                w = np.full((3, E), 1.0 / E)
                for t0 in days:
                    ld = Lm[:, td == t0, :].sum(1)
                    ld = ld if tsep else np.repeat(ld.sum(1, keepdims=True), 3, axis=1)
                    for t in range(3):
                        s = ld[:, t]
                        if s.mean() > 0:
                            w[t] = w[t] * np.exp(-eta * (s / s.mean() - 1.0))
                            w[t] /= w[t].sum()
                        w[t] = (1 - alpha) * w[t] + alpha / E
                W = w
            elif comb == "stack":
                win = td > d - window
                if win.sum() < nmin:
                    continue
                x = np.log(np.clip(np.exp(lq[:, m, :][:, win, :]), 1e-9, None))
                ly = np.log(y[m][win])
                p = y[m][win]
                W = np.zeros((3, E))
                if tsep:
                    for t in range(3):
                        W[t] = _lp(x[:, :, t], ly, p, TAUS[t], E)
                else:
                    xs = np.concatenate([x[:, :, t] for t in range(3)], axis=1)
                    lys = np.tile(ly, 3)
                    ps = np.concatenate([p * w3 for w3 in (1.0, 1.0, 1.0)])
                    # shared weights: sum of the three pinball losses, one LP with stacked cells and tau-specific costs
                    W[:] = _lp3(x, ly, p, E)
                W = (1 - lam) * W + lam / E
            else:
                raise ValueError(comb)
            keys[(int(h), g)] = W
    return keys, eq


def _lp3(x, ly, p, E):
    from scipy.optimize import linprog
    n = x.shape[1]
    nv = E + 6 * n
    c = np.zeros(nv)
    rows, b = [], []
    A = np.zeros((3 * n + 1, nv))
    for t, tau in enumerate(TAUS):
        sl = slice(E + 2 * n * t, E + 2 * n * (t + 1))
        c[E + 2 * n * t: E + 2 * n * t + n] = tau * p
        c[E + 2 * n * t + n: E + 2 * n * (t + 1)] = (1 - tau) * p
        A[t * n:(t + 1) * n, :E] = x[:, :, t].T
        A[t * n:(t + 1) * n, E + 2 * n * t: E + 2 * n * t + n] = np.eye(n)
        A[t * n:(t + 1) * n, E + 2 * n * t + n: E + 2 * n * (t + 1)] = -np.eye(n)
    A[3 * n, :E] = 1.0
    bb = np.r_[ly, ly, ly, 1.0]
    r = linprog(c, A_eq=A, b_eq=bb, bounds=[(0, None)] * nv, method="highs")
    if r.status != 0:
        return np.full((3, E), 1.0 / E)
    w = np.clip(r.x[:E], 0, None)
    return np.tile(w / w.sum(), (3, 1))


def blend(W, lq):
    """lq (E, 3) log quantiles of one cell, W (3, E) -> sorted price quantiles."""
    q = np.exp(np.einsum("te,et->t", W, lq))
    return np.sort(q)


def lookup(keys, eq, h, g, key):
    return keys.get((int(h), g if key == "grp" else "*"), eq)


@register("stack")
def make(bank=(), comb="ewa", key="h", tsep=False, eta=20.0, gamma=1.0, alpha=0.05, window=28, lam=0.0, nmin=20):
    import pandas as pd
    tabs = []
    for p in bank:
        df = pd.read_parquet(p)
        tabs.append({(s, int(o), int(h)): np.log(np.maximum([a, b, c], 1e-9))
                     for s, o, h, a, b, c in df[["series_id", "origin_day", "horizon_days", "q10", "q50", "q90"]].itertuples(index=False)})
    E = len(tabs)
    cellkeys = list(tabs[0])
    by_origin = {}
    for k in cellkeys:
        by_origin.setdefault(k[1], []).append(k)
    cache = {}

    def prep(d, ctx):
        if d in cache:
            return cache[d]
        cache.clear()
        ys, ks = [], []
        hist = {}
        for o, lst in by_origin.items():
            for (s, _, h) in lst:
                if o + h > d:
                    continue
                if s not in hist:
                    hist[s] = ctx.history(s)
                days, vals = hist[s]
                i = np.searchsorted(days, o + h)
                if i < len(days) and days[i] == o + h:
                    ks.append((s, o, h))
                    ys.append(vals[i])
        if ks:
            C = {"tday": np.array([o + h for _, o, h in ks]), "h": np.array([h for _, _, h in ks]),
                 "g": np.array([_grp(ctx, s) for s, _, _ in ks]), "y": np.array(ys),
                 "logq": np.stack([[t[k] for k in ks] for t in tabs])}
        else:
            C = {"tday": np.zeros(0, int), "h": np.zeros(0, int), "g": np.zeros(0, object), "y": np.zeros(0),
                 "logq": np.zeros((E, 0, 3))}
        cache[d] = weights(d, C, comb, key, tsep, eta, gamma, alpha, window, lam, nmin)
        return cache[d]

    def _grp(ctx, s):
        m = ctx.meta(s)
        return f"{m.get('source_id')}|{m.get('instrument_class')}"

    def f(sid, days, vals, origin_day, horizons, ctx):
        keys, eq = prep(int(origin_day), ctx)
        out = {}
        for h in horizons:
            if (sid, int(origin_day), int(h)) not in tabs[0]:
                continue
            lq = np.stack([t[(sid, int(origin_day), int(h))] for t in tabs])
            W = lookup(keys, eq, h, _grp(ctx, sid), key)
            out[h] = tuple(float(x) for x in blend(W, lq))
        return out

    return f
