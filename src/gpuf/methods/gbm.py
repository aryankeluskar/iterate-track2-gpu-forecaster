"""Pooled LightGBM quantile model over all rental series (slug: gbm).

Target: log(v[t+h] / v[t]). Fitted at a refit origin o on pairs (series, t, h) with t + h <= o (target date
on or before o), features from rows <= t. A model fitted at o is used only for origins >= o.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from gpuf.methods import register

OUT = Path(__file__).resolve().parents[3] / "experiments" / "gbm"
FEATS = (["lc%d" % k for k in range(1, 8)] + ["vol7", "vol14", "vol30", "frac7", "frac14", "frac30", "since_chg",
         "gap7", "gap14", "horizon", "collector", "iclass", "family", "logp", "nhist"])
ALPHAS = (0.1, 0.5, 0.9)
_CODES: dict = {}


def _code(kind, val):
    d = _CODES.setdefault(kind, {})
    return d.setdefault(val, len(d))


def _family(gm: str) -> str:
    m = re.search(r"[A-Za-z]+\d+[A-Za-z]*", gm or "")
    return (m.group(0) if m else (gm or "?")).upper()


def _grid(days, vals):
    """Calendar grid with forward fill; observed mask marks rows actually present."""
    d0, d1 = int(days[0]), int(days[-1])
    n = d1 - d0 + 1
    g = np.full(n, np.nan)
    obs = np.zeros(n, bool)
    g[days - d0] = vals
    obs[days - d0] = True
    s = pd.Series(g).ffill().to_numpy()
    return d0, s, obs


def _features(days, vals, static):
    """Per-day feature frame (index = calendar position) using only rows up to each day."""
    d0, g, obs = _grid(np.asarray(days), np.asarray(vals, float))
    lg = np.log(np.maximum(g, 1e-9))
    n = len(g)
    lc = np.concatenate([[np.nan], np.diff(lg)])
    s = pd.Series(lc)
    f = {}
    for k in range(1, 8):
        f["lc%d" % k] = s.shift(k - 1).to_numpy()
    chg = (s.abs() > 1e-9).astype(float).where(s.notna())
    for w in (7, 14, 30):
        f["vol%d" % w] = s.rolling(w, min_periods=3).std().to_numpy()
        f["frac%d" % w] = chg.rolling(w, min_periods=3).mean().to_numpy()
    idx = np.arange(n)
    last_chg = pd.Series(np.where(chg.fillna(0).to_numpy() > 0, idx, np.nan)).ffill().to_numpy()
    f["since_chg"] = np.where(np.isnan(last_chg), idx, idx - last_chg)
    ls = pd.Series(lg)
    for w in (7, 14):
        f["gap%d" % w] = (ls - ls.rolling(w, min_periods=3).median()).to_numpy()
    f["logp"] = lg
    f["nhist"] = idx + 1.0
    f["collector"] = float(static[0]); f["iclass"] = float(static[1]); f["family"] = float(static[2])
    df = pd.DataFrame(f)
    return d0, lg, obs, df


def _static(meta):
    return (_code("src", meta.get("source_id", "")), _code("cls", meta.get("instrument_class", "")),
            _code("fam", _family(meta.get("gpu_model", ""))))


def _train_set(ctx, origin, horizons, headline_like):
    Xs, ys, ws = [], [], []
    for sid in ctx.ids():
        m = ctx.meta(sid)
        if m.get("table") != "daily_statistics":
            continue
        days, vals = ctx.history(sid)
        if len(days) < 12:
            continue
        d0, lg, obs, df = _features(days, vals, _static(m))
        if headline_like:
            lc = np.diff(lg)
            if len(lc) < 5 or (np.abs(lc) > 1e-9).mean() <= 0.10:
                continue
        n = len(lg)
        for h in horizons:
            t = np.arange(0, n - h)
            ok = obs[t + h] & (t >= 8)  # target day actually observed, a week of lags
            t = t[ok]
            if len(t) == 0:
                continue
            X = df.iloc[t].copy()
            X["horizon"] = float(h)
            Xs.append(X[list(FEATS)])
            ys.append(lg[t + h] - lg[t])
    X = pd.concat(Xs, ignore_index=True)
    return X, np.concatenate(ys)


@register("gbm")
def make(horizons_train=(1, 3, 7), refit_days=7, mode="full", train="all", n_est=200, lr=0.05, leaves=15,
         min_leaf=40, tag=None, save_importance=True):
    import lightgbm as lgb
    state = {"fit": None, "models": None}
    imp = {}
    tag = tag or f"{mode}_{train}"

    def fit(ctx, origin):
        X, y = _train_set(ctx, origin, horizons_train, train == "headline_like")
        models = {}
        for a in ALPHAS:
            if mode == "interval_only" and a == 0.5:
                continue
            params = dict(objective="quantile", alpha=a, learning_rate=lr, num_leaves=leaves, min_data_in_leaf=min_leaf,
                          bagging_fraction=0.8, bagging_freq=1, feature_fraction=0.8, lambda_l2=1.0, verbose=-1,
                          num_threads=4, seed=0)
            ds = lgb.Dataset(X, y, categorical_feature=["collector", "iclass", "family"], free_raw_data=False)
            m = lgb.train(params, ds, num_boost_round=n_est)
            models[a] = m
            if save_importance and a in (0.1, 0.9):
                g = m.feature_importance("gain")
                imp.setdefault(f"q{int(a*100)}", {})[str(origin)] = dict(zip(FEATS, map(float, g)))
        state["fit"], state["models"], state["n"] = origin, models, len(y)
        if save_importance:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / f"importance_{tag}.json").write_text(json.dumps(imp))

    def f(sid, days, vals, origin_day, horizons, ctx):
        if state["fit"] is None or origin_day - state["fit"] >= refit_days:
            fit(ctx, origin_day)
        assert state["fit"] <= origin_day
        if len(days) < 9:
            return {}
        m = ctx.meta(sid)
        d0, lg, obs, df = _features(days, vals, _static(m))
        row = df.iloc[[len(df) - 1]]
        last = float(vals[-1])
        out = {}
        for h in horizons:
            X = row.copy()
            X["horizon"] = float(h)
            X = X[list(FEATS)]
            p = {a: float(mod.predict(X)[0]) for a, mod in state["models"].items()}
            if mode == "interval_only":
                p[0.5] = 0.0
                p[0.1] = min(p[0.1], 0.0)
                p[0.9] = max(p[0.9], 0.0)
            out[h] = tuple(last * float(np.exp(p[a])) for a in ALPHAS)
        return out

    return f
