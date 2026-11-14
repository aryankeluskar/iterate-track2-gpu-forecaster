"""hazard: hurdle model for posted rental medians (slug: hazard).

Stage 1: pooled multinomial classifier per horizon for the h-day outcome {no change, up, down}, fit at refit
origins on every daily_statistics series (rental_all) using pairs (t, t+h) with t+h <= origin; features use
rows <= t only. Stage 2: recency-weighted pooled distributions of non-zero h-day log changes by sign, pooled
by collector x class with the series' own samples mixed in (prior strength k, as in mix), optionally rescaled
by the series' volatility state. q10/q50/q90 are read from P(down) G_down + P(0) delta_0 + P(up) G_up.

The offer-panel table daily_statistics.csv is read directly and filtered to rows dated <= origin inside the
forecaster (tests/test_hazard.py checks that perturbing later rows leaves the forecast unchanged).

params
  clf       "lr" | "lgbm" | "base" (collector x horizon base rate only)
  refit     refit the classifier every this many origins (days)
  hl        half-life (days) of recency weights on stage-2 samples
  k         stage-2 prior strength of the pooled samples (own samples weigh 1 each)
  volscale  rescale stage-2 samples by (series EWMA |change| now) / (EWMA |change| at sample start)
  pmult     multiply P(move) by this before reading quantiles (diagnostic; 1 = as fitted)
  train     "all" (every daily_statistics series) | "active" (series that changed on >= 10% of days up to origin)
  dirsrc    "clf" (P(up | move) from the classifier) | "pool" (recency-weighted up share of the stage-2 samples)
  collapse  "mixture" (exact mixture quantiles) | "none" (ignore p0: quantiles of the signed move mixture)
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from gpuf.data import PACK
from gpuf.methods import register

NUM = ["ltsl", "n3", "n7", "n14", "ewm", "peer_ewm", "last_sign", "last_size", "pos30", "lnprov", "dprov7",
       "provchg3", "p25rel", "p75rel", "spread", "frac30", "frac_all"]
CAT = ["collector", "iclass", "family"]
_PANEL: dict | None = None


def load_panel(path=None) -> dict:
    """sid -> (days, n_providers, p25/median, p75/median) sorted by day. Full table; callers filter by origin."""
    df = pd.read_csv(path or PACK / "daily_statistics.csv",
                     usecols=["date", "source_id", "gpu_model", "pricing_tier", "instrument_class", "n_providers",
                              "median_usd_per_gpu_hour", "p25_usd_per_gpu_hour", "p75_usd_per_gpu_hour"])
    df["sid"] = (df.source_id + "." + df.instrument_class + "." + df.gpu_model.str.replace(" ", "_") + "."
                 + df.pricing_tier + ".median")
    df["day"] = [dt.date.fromisoformat(s[:10]).toordinal() for s in df["date"]]
    med = df.median_usd_per_gpu_hour.where(df.median_usd_per_gpu_hour > 0)
    df["p25r"] = np.log(df.p25_usd_per_gpu_hour.clip(lower=1e-6) / med)
    df["p75r"] = np.log(df.p75_usd_per_gpu_hour.clip(lower=1e-6) / med)
    out = {}
    for sid, g in df.sort_values("day").groupby("sid"):
        out[sid] = (g.day.to_numpy(np.int64), g.n_providers.to_numpy(float), g.p25r.fillna(0).to_numpy(),
                    g.p75r.fillna(0).to_numpy())
    return out


def panel():
    global _PANEL
    if _PANEL is None:
        _PANEL = load_panel()
    return _PANEL


def _family(gm: str) -> str:
    import re
    m = re.search(r"[A-Za-z]+\d+[A-Za-z]*", gm or "")
    return (m.group(0) if m else (gm or "?")).upper()


def series_frame(days, vals, pan, origin):
    """Per-calendar-day features from rows <= each day (and <= origin). Returns (d0, lg, obs, DataFrame)."""
    days = np.asarray(days, np.int64)
    keep = days <= origin
    days, vals = days[keep], np.asarray(vals, float)[keep]
    d0 = int(days[0]); n = int(days[-1]) - d0 + 1
    g = np.full(n, np.nan); g[days - d0] = vals
    obs = np.zeros(n, bool); obs[days - d0] = True
    g = pd.Series(g).ffill().to_numpy()
    lg = np.log(np.maximum(g, 1e-9))
    dl = np.r_[0.0, np.diff(lg)]
    ch = np.abs(dl) > 1e-9
    idx = np.arange(n)
    lastc = pd.Series(np.where(ch, idx, np.nan)).ffill().to_numpy()
    tsl = np.where(np.isnan(lastc), idx + 30, idx - lastc)
    cs = np.cumsum(ch)
    f = {"ltsl": np.log1p(np.minimum(tsl, 90))}
    for w in (3, 7, 14):
        f["n%d" % w] = cs - np.r_[np.zeros(w), cs[:-w]] if n > w else cs.astype(float)
    f["frac30"] = pd.Series(ch.astype(float)).rolling(30, min_periods=1).mean().to_numpy()
    f["frac_all"] = cs / (idx + 1.0)
    f["ewm"] = pd.Series(np.abs(dl)).ewm(halflife=7).mean().to_numpy()
    lsz = pd.Series(np.where(ch, dl, np.nan)).ffill().fillna(0).to_numpy()
    f["last_sign"] = np.sign(lsz); f["last_size"] = np.abs(lsz)
    s = pd.Series(lg)
    lo, hi = s.rolling(30, min_periods=1).min().to_numpy(), s.rolling(30, min_periods=1).max().to_numpy()
    f["pos30"] = np.where(hi - lo > 1e-9, (lg - lo) / np.maximum(hi - lo, 1e-9), 0.5)
    if pan is not None:
        pd_, npv, p25, p75 = pan
        m = pd_ <= origin
        P = pd.DataFrame({"np": npv[m], "p25": p25[m], "p75": p75[m]}, index=pd_[m] - d0)
        P = P[~P.index.duplicated()].reindex(np.arange(n)).ffill()
        lnp = np.log(P["np"].fillna(1).clip(lower=1).to_numpy())
        f["lnprov"] = lnp
        f["dprov7"] = lnp - np.r_[np.full(7, lnp[0]), lnp[:-7]] if n > 7 else np.zeros(n)
        dch = np.r_[0, np.abs(np.diff(lnp)) > 1e-9].astype(float)
        f["provchg3"] = pd.Series(dch).rolling(3, min_periods=1).max().to_numpy()
        f["p25rel"] = P["p25"].fillna(0).to_numpy(); f["p75rel"] = P["p75"].fillna(0).to_numpy()
    else:
        for c in ("lnprov", "dprov7", "provchg3", "p25rel", "p75rel"):
            f[c] = np.zeros(n)
    f["spread"] = f["p75rel"] - f["p25rel"]
    return d0, lg, obs, pd.DataFrame(f)


def origin_frames(ctx, origin):
    """Features for every daily_statistics series in ctx at this origin, with peer EWMA by collector x class."""
    pan = panel()
    fr = {}
    for sid in ctx.ids():
        m = ctx.meta(sid)
        if m.get("table") != "daily_statistics":
            continue
        days, vals = ctx.history(sid)
        if len(days) < 5 or not (np.asarray(vals) > 0).all():
            continue
        d0, lg, obs, df = series_frame(days, vals, pan.get(sid), origin)
        df["day"] = d0 + np.arange(len(df))
        df["grp"] = m.get("source_id", "") + "|" + m.get("instrument_class", "")
        df["collector"] = m.get("source_id", ""); df["iclass"] = m.get("instrument_class", "")
        df["family"] = _family(m.get("gpu_model", ""))
        fr[sid] = (d0, lg, obs, df)
    allf = pd.concat([v[3][["grp", "day", "ewm"]] for v in fr.values()], ignore_index=True)
    peer = allf.groupby(["grp", "day"])["ewm"].mean()
    for sid, (d0, lg, obs, df) in fr.items():
        df["peer_ewm"] = peer.reindex(pd.MultiIndex.from_arrays([df.grp, df.day])).to_numpy()
    return fr


def pairs_table(fr, h, warm=7):
    """Training pairs (t, t+h) with t+h observed (<= origin by construction)."""
    out = []
    for sid, (d0, lg, obs, df) in fr.items():
        n = len(lg)
        t = np.arange(warm, n - h)
        if not len(t):
            continue
        t = t[obs[t + h]]
        if not len(t):
            continue
        r = lg[t + h] - lg[t]
        X = df.iloc[t].copy()
        X["sid"] = sid; X["r"] = r; X["end"] = d0 + t + h
        X["y"] = np.where(r > 1e-9, 1, np.where(r < -1e-9, 2, 0))
        out.append(X)
    return pd.concat(out, ignore_index=True)


def fit_clf(kind, T, hl_w=0.0, origin=None):
    y = T["y"].to_numpy()
    w = np.ones(len(T)) if not hl_w else 0.5 ** ((origin - T["end"].to_numpy()) / hl_w)
    if kind == "lr":
        from sklearn.compose import ColumnTransformer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
        ct = ColumnTransformer([("n", StandardScaler(), NUM), ("c", OneHotEncoder(handle_unknown="ignore"), CAT)])
        m = make_pipeline(ct, LogisticRegression(C=1.0, max_iter=500))
        m.fit(T[NUM + CAT], y, logisticregression__sample_weight=w)
        cls = list(m.classes_)
        return lambda X: _full(m.predict_proba(X[NUM + CAT]), cls)
    if kind == "lgbm":
        import lightgbm as lgb
        cats = {c: sorted(T[c].unique()) for c in CAT}

        def enc(X):
            Z = X[NUM].copy()
            for c in CAT:
                Z[c] = pd.Categorical(X[c], categories=cats[c]).codes
            return Z
        m = lgb.LGBMClassifier(objective="multiclass", n_estimators=200, learning_rate=0.05, num_leaves=15,
                               min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                               reg_lambda=1.0, num_threads=2, verbose=-1, random_state=0)
        m.fit(enc(T), y, sample_weight=w, categorical_feature=CAT)
        cls = list(m.classes_)
        return lambda X: _full(m.predict_proba(enc(X)), cls)
    # base rate by collector
    br = T.assign(w=w).groupby("collector").apply(lambda g: np.bincount(g.y, weights=g.w, minlength=3) / g.w.sum())
    glob = np.bincount(y, weights=w, minlength=3) / w.sum()
    return lambda X: np.vstack([br.get(c, glob) for c in X["collector"]])


def _full(p, cls):
    out = np.zeros((len(p), 3))
    for i, c in enumerate(cls):
        out[:, c] = p[:, i]
    return out


def wquantile(x, w, q):
    o = np.argsort(x, kind="stable")
    x, w = x[o], w[o]
    cw = np.cumsum(w)
    return float(np.interp(q, (cw - 0.5 * w) / cw[-1], x))


@register("hazard")
def make(clf="lr", refit=7, train="all", dirsrc="clf", hl=30.0, k=20.0, volscale=False, pmult=1.0, collapse="mixture", clf_hl=0.0,
         horizons_fit=(1, 3, 7)):
    st = {"origin": None, "fr": None, "T": {}, "clf": {}, "base": {}, "fit_at": None}
    log = []

    def prepare(ctx, origin):
        st["origin"] = origin
        st["fr"] = origin_frames(ctx, origin)
        st["T"] = {h: pairs_table(st["fr"], h) for h in horizons_fit}
        if st["fit_at"] is None or origin - st["fit_at"] >= refit:
            st["fit_at"] = origin
            for h, T in st["T"].items():
                if train == "active":
                    act = T.groupby("sid")["frac_all"].transform("last") >= 0.10
                    T = T[act]
                st["clf"][h] = fit_clf(clf, T, clf_hl, origin)
                st["base"][h] = fit_clf("base", T)

    def size_samples(T, sid, grp, sign, origin, ewm_now):
        m = (T["grp"].to_numpy() == grp) & (T["y"].to_numpy() == sign)
        if not m.any():
            m = T["y"].to_numpy() == sign
        S = T.loc[m]
        r = S["r"].to_numpy()
        w = 0.5 ** ((origin - S["end"].to_numpy()) / hl) if hl else np.ones(len(S))
        if volscale:
            e0 = S["ewm"].to_numpy()
            fl = max(float(np.median(e0)), 1e-4)
            r = r * np.clip(max(ewm_now, fl) / np.maximum(e0, fl), 0.33, 3.0)
        own = S["sid"].to_numpy() == sid
        if (~own).any() and k > 0:
            w = w.copy()
            w[~own] *= k / w[~own].sum()
        return r, w

    def f(sid, days, vals, origin_day, horizons, ctx):
        if st["origin"] != origin_day:
            prepare(ctx, origin_day)
        if sid not in st["fr"]:
            return {}
        d0, lg, obs, df = st["fr"][sid]
        row = df.iloc[[len(df) - 1]]
        last = float(vals[-1])
        out = {}
        for h in horizons:
            if h not in st["T"]:
                continue
            T = st["T"][h]
            p = st["clf"][h](row)[0]
            pb = st["base"][h](row)[0]
            ewm_now = float(row["ewm"].iloc[0])
            ru, wu = size_samples(T, sid, row["grp"].iloc[0], 1, origin_day, ewm_now)
            rd, wd = size_samples(T, sid, row["grp"].iloc[0], 2, origin_day, ewm_now)
            own = np.bincount(T.loc[T["sid"].to_numpy() == sid, "y"], minlength=3) + 1.0
            log.append((sid, origin_day, h, *p, *pb, *(own / own.sum())))
            pm = min(1.0, (p[1] + p[2]) * pmult)
            tot = max(p[1] + p[2], 1e-9)
            fu = p[1] / tot if dirsrc == "clf" else wu.sum() / max(wu.sum() + wd.sum(), 1e-12)
            pu, pdn = pm * fu, pm * (1 - fu)
            p0 = 1 - pu - pdn
            if collapse == "none":
                p0, pu, pdn = 0.0, fu, 1 - fu

            def q(a):
                if a < pdn and len(rd):
                    return wquantile(rd, wd, a / pdn)
                if a <= pdn + p0 or not len(ru):
                    return 0.0
                return wquantile(ru, wu, (a - pdn - p0) / max(pu, 1e-9))
            out[h] = tuple(last * float(np.exp(q(a))) for a in (0.1, 0.5, 0.9))
        return out

    f.log = log
    return f
