"""fm2: pretrained time-series model widths (Chronos-Bolt small/base, TimesFM 2.5, Chronos-2) around the last value.

Two methods.
  fm2_live  loads one model and forecasts every series of a universe at each origin in one batch, from the
            harness-truncated histories in ctx. It keeps the model's full quantile grid (h = 1..7) and, with
            dump=path, writes it to parquet when the last origin is done (experiments/fm2/collect.py).
  fm2       rebuilds q10/q50/q90 from one or more saved grids without loading a model.

Grid parquet columns: series_id, origin_day, horizon_days, last, space ("lin" | "log"), and one column per
quantile level named "q0.05" etc. In log space the model saw log prices.

fm2 params
  grids   list of grid paths (several = average their log offsets from their own median, equal weights)
  lo, hi  quantile levels for the lower and upper end (must be in every grid, or are linearly interpolated)
  centre  "last" (q50 = last value, width = model offsets from the model median) or "model" (raw quantiles)
  scale   multiplier on the log offsets
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from gpuf.methods import register

_MODEL = {}
LV_BOLT = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
LV_C2 = [0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.975, 0.99]
H = 7


def grid_values(days, vals, ctx_len):
    full = np.arange(days[0], days[-1] + 1)
    idx = np.searchsorted(days, full, side="right") - 1
    return full[-ctx_len:], vals[idx][-ctx_len:]


def covariates(ds, src, cls, gpu, tier, gdays, origin_day):
    """Panel covariates (n_providers, p25, p75 in log ratio to median) on the target's daily grid, forward-filled.
    Only daily_statistics rows dated on or before origin_day are used."""
    g = ds[(ds["day"] <= origin_day) & (ds["source_id"] == src) & (ds["instrument_class"] == cls)
           & (ds["gpu_model"] == gpu) & (ds["pricing_tier"] == tier)].sort_values("day")
    out = {}
    for c in ("n_providers", "lp25", "lp75"):
        if len(g) == 0:
            out[c] = np.zeros(len(gdays), np.float32)
            continue
        d, v = g["day"].to_numpy(), g[c].to_numpy(float)
        j = np.searchsorted(d, gdays, side="right") - 1
        out[c] = np.where(j >= 0, v[np.clip(j, 0, None)], v[0]).astype(np.float32)
    return out


def load_daily_statistics():
    from gpuf import data
    ds = pd.read_csv(data.PACK / "daily_statistics.csv")
    ds["day"] = pd.to_datetime(ds["date"]).map(lambda t: t.date().toordinal())
    ds["lp25"] = np.log(ds["p25_usd_per_gpu_hour"] / ds["median_usd_per_gpu_hour"])
    ds["lp75"] = np.log(ds["p75_usd_per_gpu_hour"] / ds["median_usd_per_gpu_hour"])
    return ds


def _load(model, device):
    if model in _MODEL:
        return _MODEL[model]
    _MODEL.clear()
    import torch
    torch.set_num_threads(2)
    if model.startswith("google/timesfm"):
        import timesfm
        m = timesfm.TimesFM_2p5_200M_torch.from_pretrained(model)
        m.compile(timesfm.ForecastConfig(max_context=512, max_horizon=32, normalize_inputs=True,
                                         use_continuous_quantile_head=True, force_flip_invariance=True,
                                         infer_is_positive=True, fix_quantile_crossing=True))
    else:
        from chronos import BaseChronosPipeline
        m = BaseChronosPipeline.from_pretrained(model, device_map=device)
    _MODEL[model] = m
    return m


def _predict(model, m, xs, groups=None, covs=None):
    """xs: list of 1-d float arrays. Returns (levels, array (n, H, len(levels)))."""
    import torch
    if model.startswith("google/timesfm"):
        _, q = m.forecast(horizon=H, inputs=[x.astype(np.float32) for x in xs])
        return LV_BOLT, np.asarray(q)[:, :H, 1:10]
    if "chronos-2" in model:
        out = np.zeros((len(xs), H, len(LV_C2)))
        gl = groups if groups is not None else [0] * len(xs)
        for g in dict.fromkeys(gl):
            ix = [i for i, k in enumerate(gl) if k == g]
            inp = [{"target": xs[i], "past_covariates": covs[i]} if covs else xs[i] for i in ix]
            q, _ = m.predict_quantiles(inp, prediction_length=H, quantile_levels=LV_C2,
                                       cross_learning=groups is not None, batch_size=256)
            for i, qi in zip(ix, q):
                out[i] = qi[0].float().cpu().numpy()
        return LV_C2, out
    q, _ = m.predict_quantiles([torch.tensor(x, dtype=torch.float32) for x in xs], prediction_length=H,
                               quantile_levels=LV_BOLT)
    return LV_BOLT, q.float().cpu().numpy()


@register("fm2_live")
def make_live(model="amazon/chronos-bolt-small", ctx_len=512, log=False, group="none", cov=False,
              universe="rental_headline", device="cpu", dump="", n_origins=0, lo=0.1, hi=0.9):
    from gpuf import data
    m = _load(model, device)
    U = data.universe(universe)
    ds = load_daily_statistics() if cov else None
    cache, rows, done = {}, [], set()

    def run_origin(o, ctx):
        sids, xs, gs, cv, lasts = [], [], [], [], []
        for s in U:
            d, v = ctx.history(s)
            if len(v) < 8 or not (v > 0).all():
                continue
            gd, x = grid_values(d, v, ctx_len)
            meta = ctx.meta(s)
            sids.append(s)
            lasts.append(float(v[-1]))
            xs.append(np.log(x) if log else x.astype(float))
            gs.append((meta.get("source_id"), meta.get("instrument_class")))
            if cov:
                cv.append(covariates(ds, meta.get("source_id"), meta.get("instrument_class"), meta.get("gpu_model"),
                                     meta.get("pricing_tier"), gd, o))
        lv, q = _predict(model, m, xs, gs if group == "cc" else None, cv if cov else None)
        lv = list(lv)
        res = {}
        for s, last, qs in zip(sids, lasts, q):
            res[s] = (last, qs)
            for h in range(1, H + 1):
                rows.append((s, o, h, last, *qs[h - 1]))
        cache[o] = (lv, res)
        done.add(o)
        if dump and n_origins and len(done) == n_origins:
            cols = ["series_id", "origin_day", "horizon_days", "last"] + [f"q{l:g}" for l in lv]
            df = pd.DataFrame(rows, columns=cols)
            df["space"] = "log" if log else "lin"
            df.to_parquet(dump)

    def f(sid, days, vals, origin_day, horizons, ctx):
        if origin_day not in cache:
            run_origin(origin_day, ctx)
        lv, res = cache[origin_day]
        if sid not in res:
            return None
        last, qs = res[sid]
        out = {}
        for h in horizons:
            row = qs[h - 1]
            a, b, c = (float(np.interp(p, lv, row)) for p in (lo, 0.5, hi))
            if log:
                out[h] = (last * np.exp(a - b), last, last * np.exp(c - b))
            else:
                out[h] = (last + a - b, last, last + c - b)
        return out

    return f


def offsets(df, lo, hi):
    """Log offsets (down, up) of the lo/hi quantiles from the grid's own median, and the raw quantiles."""
    lv = sorted(float(c[1:]) for c in df.columns if c.startswith("q") and c[1:].replace(".", "").isdigit())
    Q = df[[f"q{l:g}" for l in lv]].to_numpy(float)
    a, b, c = (np.array([np.interp(p, lv, r) for r in Q]) for p in (lo, 0.5, hi))
    last = df["last"].to_numpy(float)
    if df["space"].iloc[0] == "log":
        return b - a, c - b, np.exp(a), np.exp(b), np.exp(c)
    # linear grid: width added to the last value, expressed as log offsets around last
    dn = -np.log(np.clip((last + a - b) / last, 1e-3, None))
    up = np.log(np.clip((last + c - b) / last, 1e-3, None))
    return dn, up, a, b, c


@register("fm2")
def make(grids=(), lo=0.1, hi=0.9, centre="last", scale=1.0):
    K = ["series_id", "origin_day", "horizon_days"]
    parts = []
    for i, p in enumerate(grids):
        g = pd.read_parquet(p)
        dn, up, a, b, c = offsets(g, lo, hi)
        parts.append(g[K + ["last"]].assign(**{f"dn{i}": dn, f"up{i}": up, f"a{i}": a, f"b{i}": b, f"c{i}": c}))
    df = parts[0]
    for p in parts[1:]:
        df = df.merge(p.drop(columns="last"), on=K)
    n = len(parts)
    dn = df[[f"dn{i}" for i in range(n)]].mean(axis=1).to_numpy() * scale
    up = df[[f"up{i}" for i in range(n)]].mean(axis=1).to_numpy() * scale
    last = df["last"].to_numpy()
    if centre == "last":
        q = np.c_[last * np.exp(-dn), last, last * np.exp(up)]
    else:
        q = np.exp(np.c_[[np.log(np.clip(df[f"{k}{i}"].to_numpy(), 1e-6, None)) for i in range(n)]
                         for k in "abc"].reshape(3, n, -1).mean(1).T) if n > 1 else df[["a0", "b0", "c0"]].to_numpy()
    tab = {(s, int(o), int(h)): tuple(r) for (s, o, h), r in zip(df[K].itertuples(index=False, name=None), q)}

    def f(sid, days, vals, origin_day, horizons, ctx):
        return {h: tab[(sid, int(origin_day), h)] for h in horizons if (sid, int(origin_day), h) in tab}

    return f
