"""Paired comparison of two methods on the same cells."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

KEY = ["series_id", "origin_day", "horizon_days"]


def paired(cells_a: pd.DataFrame, cells_b: pd.DataFrame, reps: int = 2000, seed: int = 0, dm_lag: int = 6) -> dict:
    """A minus B. d_pooled_skill > 0 and d_pooled_loss < 0 mean A is better.

    90% intervals: block bootstrap over origin ISO weeks (weeks resampled with replacement, all cells of a
    week kept together). DM: mean of per-origin mean loss differences over its Newey-West standard error
    (Bartlett, dm_lag lags, since h <= 7 targets overlap across neighbouring daily origins); normal p-value.
    """
    m = cells_a[KEY + ["origin_week", "loss", "baseline_loss"]].merge(
        cells_b[KEY + ["loss"]], on=KEY, suffixes=("_a", "_b"), validate="one_to_one")
    if len(m) != len(cells_a) or len(m) != len(cells_b):
        raise ValueError(f"cell sets differ: {len(cells_a)} vs {len(cells_b)}, {len(m)} shared")
    la, lb, base = m["loss_a"].to_numpy(), m["loss_b"].to_numpy(), m["baseline_loss"].to_numpy()
    B = base.mean()
    out = {"n_cells": int(len(m)), "pooled_loss_a": float(la.mean()), "pooled_loss_b": float(lb.mean()),
           "d_pooled_loss": float(la.mean() - lb.mean()), "d_pooled_skill": float((lb.mean() - la.mean()) / B)}

    weeks, w_idx = np.unique(m["origin_week"].to_numpy(), return_inverse=True)
    W = len(weeks)
    sa, sb, sbase, n = (np.bincount(w_idx, weights=x, minlength=W) for x in (la, lb, base, np.ones(len(m))))
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, W, size=(reps, W))
    M = np.zeros((reps, W))
    np.add.at(M, (np.repeat(np.arange(reps), W), draws.ravel()), 1.0)
    A, Bb, Bs, N = M @ sa, M @ sb, M @ sbase, M @ n
    dl = (A - Bb) / N
    ds = (Bb - A) / Bs
    out["n_weeks"] = int(W)
    out["ci90_d_pooled_loss"] = [float(x) for x in np.quantile(dl, [0.05, 0.95])]
    out["ci90_d_pooled_skill"] = [float(x) for x in np.quantile(ds, [0.05, 0.95])]

    d_t = (m.assign(d=la - lb).groupby("origin_day")["d"].mean()).to_numpy()
    T = len(d_t)
    out["n_origins"] = int(T)
    if T > 1:
        e = d_t - d_t.mean()
        lrv = e @ e / T
        for k in range(1, min(dm_lag, T - 1) + 1):
            lrv += 2 * (1 - k / (dm_lag + 1)) * (e[k:] @ e[:-k]) / T
        se = math.sqrt(lrv / T) if lrv > 0 else float("nan")
        dm = d_t.mean() / se if se and se == se else float("nan")
        out.update(dm_stat=float(dm), dm_p_two_sided=float(math.erfc(abs(dm) / math.sqrt(2))) if dm == dm else None,
                   dm_lag=dm_lag)
    return out
