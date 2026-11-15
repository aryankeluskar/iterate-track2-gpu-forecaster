"""Four official skill aggregates on development cells only.

Reads runs/maturity/cells.parquet. Refuses any origin on or after 2026-10-13.
Does not forecast, does not write the validation log, and does not read the late window.

The decision this run can change: if the submitted blend's mean skill already
beats drift by 0.02 in both halves of dev, a width change motivated by the
late window is not allowed. If it does not, a width rule has to clear both
halves on mean skill and must not lower pooled skill.
"""
from __future__ import annotations

import datetime as dt
import json
import sys

import numpy as np
import pandas as pd

from gpuf.scoring import _series_stats, pinball

DEV_END = dt.date(2026, 10, 13).toordinal()
HALF = dt.date(2026, 9, 12).toordinal()
MEMBERS = ("mix", "gbm", "chronos", "analog", "prov", "fm2", "fragility")
SOURCE = "runs/maturity/cells.parquet"


def _load() -> pd.DataFrame:
    df = pd.read_parquet(SOURCE)
    if int(df["origin_day"].max()) >= DEV_END:
        raise SystemExit(f"refusing: origin {int(df['origin_day'].max())} is on or after 2026-10-13")
    need = ["series_id", "origin_day", "horizon_days", "y", "last", "in37", "gate14", "final_loss", "baseline_loss"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(f"refusing: missing columns {missing}")
    return df[df["in37"]].reset_index(drop=True)


def _blend(df: pd.DataFrame) -> np.ndarray:
    acc = np.zeros((len(df), 3))
    n = np.zeros(len(df))
    for m in MEMBERS:
        q = df[[f"{m}_q10", f"{m}_q50", f"{m}_q90"]].to_numpy(float)
        ok = np.isfinite(q).all(axis=1) & (q > 0).all(axis=1)
        acc[ok] += np.log(q[ok])
        n[ok] += 1
    if (n == 0).any():
        raise SystemExit("refusing: a headline cell has no member")
    return np.exp(acc / n[:, None])


def _losses(y: np.ndarray, q: np.ndarray) -> np.ndarray:
    return (pinball(y, q[:, 0], 0.1) + pinball(y, q[:, 1], 0.5) + pinball(y, q[:, 2], 0.9)) / 3.0


def _frame(df: pd.DataFrame, q: np.ndarray, loss: np.ndarray) -> pd.DataFrame:
    out = df[["series_id", "origin_day", "horizon_days", "y", "baseline_loss"]].copy()
    out["q10"], out["q50"], out["q90"] = q[:, 0], q[:, 1], q[:, 2]
    out["loss"] = loss
    return out


def _report(cells: pd.DataFrame) -> dict:
    y = cells["y"].to_numpy()
    cov = float(np.mean((cells["q10"] <= y) & (y <= cells["q90"])))
    pooled_loss = float(cells["loss"].mean())
    base = float(cells["baseline_loss"].mean())
    stats = _series_stats(cells, True)
    return {
        "n_cells": int(len(cells)),
        "n_series_skill": int(stats["n_series_with_skill"]),
        "pooled": None if base == 0 else 1.0 - pooled_loss / base,
        "mean": stats["skill_mean_of_series"],
        "median": stats["skill_median_of_series"],
        "geomean": stats["skill_geomean"],
        "coverage": cov,
        "above_q90": float(np.mean(y > cells["q90"])),
    }


def _slice(df: pd.DataFrame, q: np.ndarray, mask: np.ndarray) -> dict:
    sub = df.loc[mask].reset_index(drop=True)
    loss = _losses(sub["y"].to_numpy(float), q[mask.to_numpy()])
    return _report(_frame(sub, q[mask.to_numpy()], loss))


def main() -> int:
    df = _load()
    q = _blend(df)
    y = df["y"].to_numpy(float)
    loss = _losses(y, q)
    gap = float(np.max(np.abs(loss - df["final_loss"].to_numpy(float))))
    if gap > 1e-6:
        print(f"WARNING blend loss differs from saved final_loss by {gap:.3e}")
    else:
        print(f"blend matches saved final_loss, max abs {gap:.3e}")

    drift = df[["drift_q10", "drift_q50", "drift_q90"]].to_numpy(float)
    last = np.repeat(df["last"].to_numpy(float)[:, None], 3, axis=1)
    # planted contrasts. not candidates.
    zero = np.repeat(q[:, 1:2], 3, axis=1)
    gate = df["gate14"].to_numpy(bool)
    gated_q = np.where(gate[:, None], last, q)

    masks = {
        "all": pd.Series(True, index=df.index),
        "first_half": df["origin_day"] < HALF,
        "second_half": df["origin_day"] >= HALF,
        "h1": df["horizon_days"] == 1,
        "h3": df["horizon_days"] == 3,
        "h7": df["horizon_days"] == 7,
    }
    systems = {"final": q, "drift": drift, "last_value": last, "zero_width_at_q50": zero, "gate14_zero": gated_q}
    out = {"source": SOURCE, "n_rows": int(len(df)), "blend_vs_saved_final_loss": gap, "slices": {}}
    for name, mask in masks.items():
        out["slices"][name] = {sys: _slice(df, qq, mask) for sys, qq in systems.items()}
        row = out["slices"][name]
        print(
            f"{name:12} final pooled {row['final']['pooled']:.4f} mean {row['final']['mean']:.4f} "
            f"median {row['final']['median']:.4f} geo {row['final']['geomean']:.4f} | "
            f"drift pooled {row['drift']['pooled']:.4f} mean {row['drift']['mean']:.4f} "
            f"median {row['drift']['median']:.4f} geo {row['drift']['geomean']:.4f}"
        )
    path = "experiments/hill/aggregates.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print("wrote", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
