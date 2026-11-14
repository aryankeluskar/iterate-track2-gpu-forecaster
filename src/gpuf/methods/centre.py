"""Centre dynamics (slug: centre): shift drift's q10/q50/q90 by a predicted h-day log change.

Predictor: ridge (no intercept, standardised features) of y = log v[t+h]/v[t] on the latest 1/3/7-day log
changes and the gap between the last value and its trailing 7/14-day median, fitted per group on pairs
whose target date t+h <= origin (features use rows <= t only). Modes: full, sign, cap, big, undo.
"""
from __future__ import annotations

import numpy as np

from gpuf.methods import register

NF = 5
_FIT_CACHE: dict = {}


def _grid(days, vals):
    d0 = int(days[0])
    n = int(days[-1]) - d0 + 1
    g = np.full(n, np.nan)
    g[days - d0] = vals
    obs = ~np.isnan(g)
    idx = np.where(obs, np.arange(n), 0)
    np.maximum.accumulate(idx, out=idx)
    return d0, np.log(np.maximum(g[idx], 1e-12)), obs


def _feats(lg):
    """Feature matrix (n, 5) for every calendar position; NaN where unavailable."""
    n = len(lg)
    X = np.full((n, NF), np.nan)
    def sh(k):
        a = np.full(n, np.nan)
        a[k:] = lg[:n - k]
        return a
    X[:, 0] = lg - sh(1)
    X[:, 1] = lg - sh(3)
    X[:, 2] = lg - sh(7)
    for j, w in ((3, 7), (4, 14)):
        if n >= w:
            win = np.lib.stride_tricks.sliding_window_view(lg, w)
            med = np.full(n, np.nan)
            med[w - 1:] = np.median(win, axis=1)
            X[:, j] = lg - med
    return X


def _collector(ctx, sid):
    return ctx.meta(sid).get("source_id", "")


def _group_key(ctx, sid, group):
    m = ctx.meta(sid)
    if group == "collector":
        return (m.get("source_id", ""),)
    if group == "collector_class":
        return (m.get("source_id", ""), m.get("instrument_class", ""))
    return ("all",)


def _fit(ctx, origin, key, group, horizons, lam, min_pairs, train_scope):
    ck = (origin, key, group, tuple(horizons), lam, train_scope)
    if ck in _FIT_CACHE:
        return _FIT_CACHE[ck]
    Xs = {h: [] for h in horizons}
    ys = {h: [] for h in horizons}
    for sid in ctx.ids():
        if _group_key(ctx, sid, group) != key:
            continue
        if train_scope == "headline_tier" and False:
            continue
        d, v = ctx.history(sid)
        if len(d) < 12:
            continue
        d0, lg, obs = _grid(np.asarray(d), np.asarray(v, float))
        F = _feats(lg)
        n = len(lg)
        for h in horizons:
            if n <= h:
                continue
            t = np.arange(0, n - h)
            ok = obs[t] & obs[t + h] & ~np.isnan(F[t]).any(axis=1)
            if ok.any():
                Xs[h].append(F[t][ok])
                ys[h].append((lg[t + h] - lg[t])[ok])
    out = {}
    for h in horizons:
        if not Xs[h]:
            out[h] = None
            continue
        X = np.vstack(Xs[h]); y = np.concatenate(ys[h])
        if len(y) < min_pairs:
            out[h] = None
            continue
        sd = X.std(axis=0) + 1e-9
        Z = X / sd
        lo, hi = np.quantile(y, [0.01, 0.99])
        yc = np.clip(y, lo, hi)
        A = Z.T @ Z + lam * len(y) * np.eye(NF)
        beta = np.linalg.solve(A, Z.T @ yc)
        out[h] = (beta / sd, len(y))
    _FIT_CACHE[ck] = out
    if len(_FIT_CACHE) > 400:
        _FIT_CACHE.pop(next(iter(_FIT_CACHE)))
    return out


def _drift_q(days, vals, h, min_samples=20):
    from gpuf.data import starter_common
    last = float(vals[-1])
    ch = starter_common.h_step_changes(days, vals, h, True)
    if len(ch) < min_samples:
        return None
    return np.quantile(ch, [0.1, 0.5, 0.9])


@register("centre")
def make(mode: str = "full", group: str = "collector", lam: float = 0.5, feats=(0, 1, 2, 3, 4), cap_frac: float = 0.5,
         big_q: float = 0.75, w: float = 0.5, w_by_h=None, flat_k: int = 3, min_pairs: int = 60,
         scale: float = 1.0, only_collectors=None, hs=(1, 3, 7), train_scope: str = "all"):
    feats = tuple(feats)
    mask = np.zeros(NF); mask[list(feats)] = 1.0

    def f(sid, days, vals, origin_day, horizons, ctx):
        days = np.asarray(days); vals = np.asarray(vals, float)
        last = float(vals[-1])
        res = {}
        coll = _collector(ctx, sid)
        enabled = only_collectors is None or coll in only_collectors
        d0, lg, obs = _grid(days, vals)
        F = _feats(lg)
        x = F[-1]
        key = _group_key(ctx, sid, group)
        fits = None
        if mode != "undo" and enabled and obs[-1]:
            fits = _fit(ctx, origin_day, key, group, tuple(horizons), lam, min_pairs, train_scope)
        # big-move threshold from the series' own history
        d1 = np.diff(lg)
        a1 = np.abs(d1[np.isfinite(d1)])
        thr = np.quantile(a1[a1 > 1e-9], big_q) if (a1 > 1e-9).sum() >= 4 else np.inf
        for h in horizons:
            q = _drift_q(days, vals, h)
            if q is None:
                continue  # filled from last value, as drift does
            lq = np.array(q, float)
            hw = max((lq[2] - lq[0]) / 2.0, 1e-9)
            shift = 0.0
            if enabled and h in hs:
                if mode == "undo":
                    ww = (w_by_h or {}).get(str(h), w)
                    n = len(lg)
                    if n > flat_k + 1 and obs[-1] and abs(x[0]) > 1e-9:
                        prev = np.abs(np.diff(lg[-(flat_k + 2):-1]))
                        if np.all(prev < 1e-9):
                            shift = -ww * x[0]
                elif fits is not None and fits.get(h) is not None and not np.isnan(x).any():
                    pred = float((fits[h][0] * mask) @ x) * scale
                    if mode == "full":
                        shift = pred
                    elif mode == "sign":
                        shift = np.sign(pred) * cap_frac * hw
                    elif mode == "cap":
                        shift = float(np.clip(pred, -cap_frac * hw, cap_frac * hw))
                    elif mode == "big":
                        shift = float(np.clip(pred, -cap_frac * hw, cap_frac * hw)) if abs(x[0]) >= thr else 0.0
                    elif mode == "big_full":
                        shift = pred if abs(x[0]) >= thr else 0.0
            lq = lq + shift
            res[h] = tuple(float(last * np.exp(z)) for z in lq)
        return res
    return f
