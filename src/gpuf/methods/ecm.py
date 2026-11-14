"""ecm: error-correction wrapper around a base method.

Features, all built per origin from rows dated on or before the origin:
  dev   log median today minus the median of the series' own medians over the previous `win` days (level gap)
  pos   log(p75/med) - log(med/p25) from daily_statistics (read here, filtered to dates <= origin; see tests/test_ecm_leak.py)
  gap   pair gap z-score (same gpu, class, tier on fastgpu_daily and gpurentalprices): -z for the fastgpu side, +z for the other
Per origin, collector and horizon, a through-origin least-squares slope of the h-day log change on the features is fitted on pairs
(t, t+h) with t+h <= origin, t in the last `fit_days` days, pooled over the collector's series. Predicted change p = x . b.
  kappa  shift all three log quantiles by kappa * p
  skew   g = clip(p / half-width of the base interval, -1, 1); upper offset *= (1 + skew g), lower offset *= (1 - skew g)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from gpuf.methods import get, register

REF = ("mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30})
_DS = {}


def _ds():
    """daily_statistics rows with series id and integer day. Callers must filter to day <= origin."""
    if "df" not in _DS:
        from gpuf import data
        sc = data.starter_common
        df = pd.read_csv(data.PACK / "daily_statistics.csv", usecols=["date", "source_id", "gpu_model", "pricing_tier",
                         "instrument_class", "p25_usd_per_gpu_hour", "p75_usd_per_gpu_hour"])
        df["sid"] = (df.source_id + "." + df.instrument_class + "." + df.gpu_model.str.replace(" ", "_") + "." + df.pricing_tier + ".median")
        dm = {d: sc.day_of(sc.parse_date(d)) for d in df["date"].unique()}
        df["day"] = df["date"].map(dm)
        _DS["df"] = df[["sid", "day", "p25_usd_per_gpu_hour", "p75_usd_per_gpu_hour"]]
    return _DS["df"]


def _grid(d, v, o, n):
    g = np.full(n + 1, np.nan)
    m = d >= o - n
    if m.sum() == 0:
        return g
    g[d[m] - (o - n)] = np.log(v[m])
    s = pd.Series(g).ffill().to_numpy()
    return s


def _roll(g, win, minper, stat):
    r = pd.Series(g).shift(1).rolling(win, min_periods=minper)
    return (r.median() if stat == "median" else r.mean()).to_numpy(), r.std().to_numpy()


@register("ecm")
def make(base=REF, feats=("dev",), kappa=0.0, skew=0.0, win=30, minper=10, fit_days=45, min_pairs=200, clip=1.0, sd_floor=0.01):
    f0 = get(base[0], **base[1])
    feats = tuple(feats)
    cache = {"o": None}
    alias = {"A100 SXM 80GB": "A100 80GB"}

    def build(ctx, o):
        n = fit_days + max(win, 7) + 10
        G, X = {}, {k: {} for k in feats}
        for sid in ctx.ids():
            d, v = ctx.history(sid)
            if len(d) >= minper + 1:
                G[sid] = _grid(d, v, o, n)
        if "dev" in feats:
            for sid, g in G.items():
                med, _ = _roll(g, win, minper, "median")
                X["dev"][sid] = g - med
        if "pos" in feats:
            ds = _ds()
            sub = ds[(ds.day <= o) & (ds.day >= o - n)]
            for sid, t in sub.groupby("sid"):
                if sid not in G:
                    continue
                lo = np.full(n + 1, np.nan); hi = np.full(n + 1, np.nan)
                lo[t.day.to_numpy() - (o - n)] = t.p25_usd_per_gpu_hour.to_numpy()
                hi[t.day.to_numpy() - (o - n)] = t.p75_usd_per_gpu_hour.to_numpy()
                lo = pd.Series(lo).ffill().to_numpy(); hi = pd.Series(hi).ffill().to_numpy()
                lm = G[sid]
                ok = (lo > 0) & (hi > lo) & (np.exp(lm) >= lo) & (np.exp(lm) <= hi)
                with np.errstate(all="ignore"):
                    X["pos"][sid] = np.where(ok, np.log(hi / np.exp(lm)) - np.log(np.exp(lm) / lo), np.nan)
        if "gap" in feats:
            fk, gk = {}, {}
            for sid in G:
                m = ctx.meta(sid)
                key = (m.get("instrument_class"), alias.get(m.get("gpu_model"), m.get("gpu_model")), m.get("pricing_tier"))
                if m.get("source_id") == "fastgpu_daily":
                    fk[key] = sid
                elif m.get("source_id") == "gpurentalprices":
                    if m.get("gpu_model") == "A100 SXM 80GB" or m.get("gpu_model") != "A100 80GB":
                        gk[key] = sid
            for key, a in fk.items():
                b = gk.get(key)
                if b is None or key[1] == "A100 80GB":
                    continue
                gap = G[a] - G[b]
                mu, sd = _roll(gap, win, minper, "mean")
                z = (gap - mu) / np.maximum(sd, sd_floor)
                X["gap"][a] = -z
                X["gap"][b] = z
        src = {sid: ctx.meta(sid).get("source_id") for sid in G}
        fits = {}
        for h in (1, 3, 7):
            rows = {}
            for sid, g in G.items():
                t = np.arange(n - fit_days, n - h + 1)
                y = g[t + h] - g[t]
                xs = [X[k][sid][t] if sid in X[k] else np.full(len(t), np.nan) for k in feats]
                A = np.column_stack(xs + [y])
                A = A[np.isfinite(A).all(axis=1)]
                if len(A):
                    rows.setdefault(src[sid], []).append(A)
            for c, lst in rows.items():
                A = np.vstack(lst)
                if len(A) < min_pairs:
                    continue
                x, y = A[:, :-1], A[:, -1]
                b = np.linalg.lstsq(x.T @ x + 1e-9 * np.eye(x.shape[1]), x.T @ y, rcond=None)[0]
                fits[(c, h)] = np.clip(b, -clip, clip)
        cache.update(o=o, G=G, X=X, src=src, fits=fits, n=n)

    def f(sid, days, vals, origin_day, horizons, ctx):
        out = f0(sid, days, vals, origin_day, horizons, ctx) or {}
        if not (kappa or skew):
            return out
        if cache["o"] != origin_day:
            build(ctx, origin_day)
        n = cache["n"]
        c = cache["src"].get(sid)
        res = {}
        for h, (q10, q50, q90) in out.items():
            b = cache["fits"].get((c, h))
            if b is None:
                res[h] = (q10, q50, q90)
                continue
            x = np.array([cache["X"][k].get(sid, np.full(n + 1, np.nan))[n] for k in feats])
            p = float(np.nan_to_num(x) @ b)
            l10, l50, l90 = (np.log(max(q, 1e-9)) for q in (q10, q50, q90))
            u, dn = l90 - l50, l50 - l10
            hw = 0.5 * (u + dn)
            gg = float(np.clip(p / hw, -1, 1)) if hw > 1e-9 else 0.0
            c50 = l50 + kappa * p
            res[h] = (float(np.exp(c50 - dn * (1 - skew * gg))), float(np.exp(c50)), float(np.exp(c50 + u * (1 + skew * gg))))
        return res

    return f
