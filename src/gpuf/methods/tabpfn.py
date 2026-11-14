"""In-context tabular regression (TabPFN v2 checkpoint) on gbm's features (slug: tabpfn).

Target: log(v[t+h] / v[t]). At a refit origin o the context is a recency- and class-weighted subsample of rows
(series, t, h) with target date t+h <= o. The context is frozen for `refit` days; queries are the features of each
series at the forecast origin. Raw predictive quantile grids are cached on disk (runs/tabpfn/raw_<hash>.pkl) so
post-processing variants re-score in seconds.

cfg (keys the raw cache): kind full|move, mode hfeat|perh, scope pref|cc|all, n, hl, refit, est.
post: raw | off | offclip | twopart (twopart needs kind=move: size-given-move model x empirical move frequency).
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
from pathlib import Path

import numpy as np

from gpuf.methods import register
from gpuf.methods.gbm import FEATS, _features, _static

RUNS = Path(__file__).resolve().parents[3] / "runs" / "tabpfn"
QL = np.array([0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8,
               0.85, 0.9, 0.95, 0.98, 0.99])
I10, I50, I90 = (int(np.argmin(abs(QL - a))) for a in (0.1, 0.5, 0.9))
CATS = [FEATS.index(c) for c in ("collector", "iclass", "family")]
ANCHOR = 739846
HOR = FEATS.index("horizon")


def _bucket(s):
    return np.minimum(np.asarray(s, float), 7.0).astype(int) if np.ndim(s) else int(min(s, 7))


def mixture_q(grid, p, taus):
    """Quantiles of (1-p) delta_0 + p F_move, F_move given by its quantile grid over QL."""
    g = np.maximum.accumulate(np.asarray(grid, float))
    a = float(np.interp(0.0, g, QL, left=0.0, right=1.0))
    out = []
    for t in taus:
        if t < p * a:
            x = np.interp(t / p, QL, g)
        elif t <= p * a + (1 - p):
            x = 0.0
        else:
            x = np.interp((t - (1 - p)) / p, QL, g)
        out.append(float(x))
    return out


@register("tabpfn")
def make(kind="full", mode="hfeat", scope="pref", n=1500, hl=30.0, refit=7, est=4, post="raw", horizons_train=(1, 3, 7),
         device="cpu", seed=0, cache=True):
    os.environ.setdefault("TABPFN_ALLOW_CPU_LARGE_DATASET", "1")
    import torch
    torch.set_num_threads(2)
    import pandas as pd
    from tabpfn import TabPFNRegressor
    from tabpfn.constants import ModelVersion
    from gpuf import data

    cfg = dict(kind=kind, mode=mode, scope=scope, n=n, hl=hl, refit=refit, est=est, ht=list(horizons_train), seed=seed)
    key = hashlib.md5(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:10]
    RUNS.mkdir(parents=True, exist_ok=True)
    path = RUNS / f"raw_{key}.pkl"
    raw = pickle.load(open(path, "rb")) if cache and path.exists() else {}
    done_origins = {k[1] for k in raw}
    state = {"fit": None, "rows": None, "models": {}, "dirty": 0}
    headline = set(data.universe("rental_headline"))

    def build(ctx, o):
        Xs, ys, ag, col, cls, sidx = [], [], [], [], [], []
        for sid in ctx.ids():
            m = ctx.meta(sid)
            if m.get("table") != "daily_statistics":
                continue
            days, vals = ctx.history(sid)
            keep = days <= o
            days, vals = days[keep], vals[keep]
            if len(days) < 12:
                continue
            d0, lg, obs, df = _features(days, vals, _static(m))
            nn = len(lg)
            for h in horizons_train:
                t = np.arange(0, nn - h)
                t = t[obs[t + h] & (t >= 8)]
                if len(t) == 0:
                    continue
                X = df.iloc[t].copy()
                X["horizon"] = float(h)
                Xs.append(X[list(FEATS)])
                ys.append(lg[t + h] - lg[t])
                ag.append(np.full(len(t), 0.0) + (nn - 1 - (t + h)))
                col.append(np.full(len(t), X["collector"].iloc[0]))
                cls.append(np.full(len(t), X["iclass"].iloc[0]))
        X = pd.concat(Xs, ignore_index=True)
        return dict(X=X, y=np.concatenate(ys), age=np.concatenate(ag), col=np.concatenate(col),
                    cls=np.concatenate(cls), h=X["horizon"].to_numpy())

    def sample(rows, qcol, qcls, h, o):
        mask = np.ones(len(rows["y"]), bool)
        if h is not None:
            mask &= rows["h"] == h
        if kind == "move":
            mask &= np.abs(rows["y"]) > 1e-9
        if scope == "cc":
            mask &= (rows["col"] == qcol) & (rows["cls"] == qcls)
        idx = np.flatnonzero(mask)
        w = np.exp(-rows["age"][idx] / hl)
        if scope == "pref":
            w = w * np.where(rows["cls"][idx] == qcls, 4.0, 1.0) * np.where(rows["col"][idx] == qcol, 2.0, 1.0)
        if len(idx) > n:
            r = np.random.default_rng(seed + o)
            idx = r.choice(idx, n, replace=False, p=w / w.sum())
        return idx

    def model_for(o, qcol, qcls, h):
        k = (state["fit"], qcol, qcls, h)
        if k not in state["models"]:
            rows = state["rows"]
            idx = sample(rows, qcol, qcls, h, state["fit"])
            X = rows["X"].iloc[idx]
            if h is not None:
                X = X.drop(columns=["horizon"])
            cats = [list(X.columns).index(c) for c in ("collector", "iclass", "family")]
            m = TabPFNRegressor.create_default_for_version(
                ModelVersion.V2, device=device, n_estimators=est, random_state=seed, fit_mode="fit_with_cache",
                categorical_features_indices=cats)
            m.fit(X.to_numpy(float), rows["y"][idx])
            state["models"][k] = m
        return state["models"][k]

    def move_p(rows, qcol, h, since):
        """Empirical chance of a change from context rows, by (collector, h, since_chg bucket), shrunk to (h, bucket)."""
        sc = rows["X"]["since_chg"].to_numpy()
        b = _bucket(sc)
        mv = np.abs(rows["y"]) > 1e-9
        w = np.exp(-rows["age"] / hl)
        mh = rows["h"] == h
        bk = _bucket(since)
        base = mh & (b == bk)
        p0 = (w[base] * mv[base]).sum() / max(w[base].sum(), 1e-9) if base.any() else mv[mh].mean()
        sel = base & (rows["col"] == qcol)
        ws, k = w[sel].sum(), 10.0
        return float((w[sel] @ mv[sel] + k * p0) / (ws + k))

    def predict_origin(ctx, o, sids):
        fo = ANCHOR + ((o - ANCHOR) // refit) * refit
        if state["fit"] != fo:
            state["rows"], state["fit"], state["models"] = build(ctx, fo), fo, {}
        qrows = {}
        for sid in sids:
            days, vals = ctx.history(sid)
            keep = days <= o
            days, vals = days[keep], vals[keep]
            if len(days) < 9:
                continue
            m = ctx.meta(sid)
            _, lg, obs, df = _features(days, vals, _static(m))
            r = df.iloc[len(df) - 1]
            qrows[sid] = r
        groups = {}
        for sid, r in qrows.items():
            groups.setdefault((r["collector"], r["iclass"]), []).append(sid)
        for (qcol, qcls), ss in groups.items():
            for h in (None,) if mode == "hfeat" else horizons_train:
                hs = horizons_train if h is None else (h,)
                Xq, keys = [], []
                for sid in ss:
                    for hh in hs:
                        r = qrows[sid].copy()
                        r["horizon"] = float(hh)
                        Xq.append(r[list(FEATS)].to_numpy(float))
                        keys.append((sid, hh))
                Xq = np.array(Xq)
                if h is not None:
                    Xq = np.delete(Xq, HOR, axis=1)
                mdl = model_for(o, qcol, qcls, h)
                q = np.asarray(mdl.predict(Xq, output_type="quantiles", quantiles=QL.tolist()))
                for i, (sid, hh) in enumerate(keys):
                    g = np.sort(q[:, i])
                    pm = move_p(state["rows"], qcol, hh, qrows[sid]["since_chg"]) if kind == "move" else None
                    raw[(sid, o, hh)] = (g, pm)
        state["dirty"] += 1
        if cache:
            pickle.dump(raw, open(path, "wb"))

    def f(sid, days, vals, origin_day, horizons, ctx):
        o = int(origin_day)
        if o not in done_origins and (sid, o, horizons[0]) not in raw:
            predict_origin(ctx, o, sorted(headline | {sid}))
            done_origins.add(o)
        last = float(vals[-1])
        out = {}
        for h in horizons:
            if (sid, o, h) not in raw:
                if o in done_origins and (sid not in headline) and len(days) >= 9:
                    predict_origin(ctx, o, [sid])
                if (sid, o, h) not in raw:
                    continue
            g, pm = raw[(sid, o, h)]
            if post == "twopart":
                q10, q50, q90 = mixture_q(g, pm, (0.1, 0.5, 0.9))
            elif post == "raw":
                q10, q50, q90 = g[I10], g[I50], g[I90]
            elif post == "off":
                q10, q50, q90 = g[I10] - g[I50], 0.0, g[I90] - g[I50]
            else:
                q10, q50, q90 = min(g[I10], 0.0), 0.0, max(g[I90], 0.0)
            out[h] = tuple(last * float(np.exp(x)) for x in (q10, q50, q90))
        return out

    f.flush = lambda: cache and pickle.dump(raw, open(path, "wb"))
    f.raw = raw
    return f
