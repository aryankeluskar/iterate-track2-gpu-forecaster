"""Two scorers that must agree: FAST (in-process, vectorised) and OFFICIAL (starter/scorer.py subprocess).

Official semantics replicated by FAST (backtest mode, skill baseline last_value):
- scored set = the universe ids present in the series file; origins = origins with at least one forecast row;
- a cell (sid, origin, h) is scored only if a truth row exists dated exactly origin + h (else missing_truth;
  gaps are not filled) and the series has a row on or before the origin (else missing_baseline);
- baseline = last row on or before the origin, however stale (no staleness limit), flat q10 = q50 = q90;
- pooled = mean cell loss over all scored cells (each cell weighs equally, so expensive, volatile series
  dominate); skill = 1 - loss / baseline loss;
- per-series skill: series whose mean baseline loss is exactly 0 get skill None (baseline_degenerate) and
  drop out of mean/median/geomean, but their cells stay in pooled. Per-series values are rounded to 6
  decimals before the across-series stats, exactly as the official report does (geomean ratio floored at 1e-3).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import run_starter, starter_common, starter_scorer

fnum = starter_common.fnum
TAUS = (0.1, 0.5, 0.9)


def _skill(loss, base):
    return None if base == 0 else 1.0 - loss / base


def _lookup(store, sid: str, targets: np.ndarray) -> np.ndarray:
    days, vals = store.arrays(sid)
    idx = np.minimum(np.searchsorted(days, targets), len(days) - 1)
    return np.where(days[idx] == targets, vals[idx], np.nan)


def pinball(y: np.ndarray, f: np.ndarray, tau: float) -> np.ndarray:
    d = y - f
    return np.maximum(tau * d, (tau - 1.0) * d)


def score_fast(fc: pd.DataFrame, store, sids: list[str], horizons) -> tuple[pd.DataFrame, dict]:
    """Per-cell frame (sorted like the official scorer: universe order, origin, horizon) and cell counts."""
    horizons = np.asarray(list(horizons), dtype=np.int64)
    sids = [s for s in sids if s in store]
    fc = fc[fc["series_id"].isin(sids)].reset_index(drop=True)
    target = (fc["origin_day"] + fc["horizon_days"]).to_numpy(np.int64)
    y = np.full(len(fc), np.nan)
    for sid, idx in fc.groupby("series_id").indices.items():
        y[idx] = _lookup(store, sid, target[idx])
    counts = {"scored": int((~np.isnan(y)).sum()), "missing_truth": int(np.isnan(y).sum()), "missing_baseline": 0}
    # grid cells with no forecast row because the series had no history at that origin
    origins = np.unique(fc["origin_day"].to_numpy(np.int64))
    have = fc.groupby("series_id")["origin_day"].unique().to_dict()
    for sid in sids:
        miss = np.setdiff1d(origins, have.get(sid, np.empty(0, np.int64)))
        if len(miss):
            t = (miss[:, None] + horizons[None, :]).ravel()
            got = ~np.isnan(_lookup(store, sid, t))
            counts["missing_baseline"] += int(got.sum())
            counts["missing_truth"] += int((~got).sum())
    cells = fc.assign(target_day=target, y=y)[~np.isnan(y)].copy()
    rank = {s: i for i, s in enumerate(sids)}
    cells["_rank"] = cells["series_id"].map(rank)
    cells = cells.sort_values(["_rank", "origin_day", "horizon_days"], kind="stable").drop(columns="_rank")
    yv, b = cells["y"].to_numpy(), cells["baseline"].to_numpy()
    for tau, col in zip(TAUS, ("q10", "q50", "q90")):
        cells[f"loss_{col}"] = pinball(yv, cells[col].to_numpy(), tau)
    cells["loss"] = (cells["loss_q10"] + cells["loss_q50"] + cells["loss_q90"]) / 3.0
    cells["baseline_loss"] = (pinball(yv, b, 0.1) + pinball(yv, b, 0.5) + pinball(yv, b, 0.9)) / 3.0
    cells["origin_date"] = cells["origin_day"].map(starter_common.iso)
    cells["origin_week"] = cells["origin_day"].map(lambda d: "%d-W%02d" % starter_common.date_of(d).isocalendar()[:2])
    return cells.reset_index(drop=True), counts


def _pooled(c: pd.DataFrame) -> dict:
    if len(c) == 0:
        return {"n_cells": 0, "pooled_loss": None, "baseline_loss": None, "pooled_skill": None, "coverage": None}
    loss, base = float(np.mean(c["loss"].to_numpy())), float(np.mean(c["baseline_loss"].to_numpy()))
    y, q10, q90 = c["y"].to_numpy(), c["q10"].to_numpy(), c["q90"].to_numpy()
    return {"n_cells": int(len(c)), "n_series": int(c["series_id"].nunique()), "pooled_loss": loss,
            "baseline_loss": base, "pooled_skill": _skill(loss, base),
            "coverage": {"below_q10": float(np.mean(y < q10)), "within_q10_q90": float(np.mean((q10 <= y) & (y <= q90))),
                         "above_q90": float(np.mean(y > q90))}}


def _series_stats(c: pd.DataFrame, official_rounding: bool) -> dict:
    skills, ratios, n_degen = [], [], 0
    for _, g in c.groupby("series_id", sort=False):
        loss, base = float(np.mean(g["loss"].to_numpy())), float(np.mean(g["baseline_loss"].to_numpy()))
        n_degen += base == 0
        if official_rounding:  # scorer.py's overall block: rounded per-series entries
            sk = fnum(_skill(loss, base))
            if sk is not None:
                skills.append(sk)
                if fnum(base):
                    ratios.append(fnum(loss) / fnum(base))
        else:  # scorer.py's by_horizon block: unrounded
            skills.append(_skill(loss, base))
            if base:
                ratios.append(loss / base)
    out = starter_scorer.series_stats(skills, ratios)
    out["n_series_baseline_degenerate"] = int(n_degen)
    return out


def summarize(cells: pd.DataFrame, horizons, counts: dict | None = None) -> dict:
    s = {**_pooled(cells), **_series_stats(cells, True)}
    s["n_origins"] = int(cells["origin_day"].nunique()) if len(cells) else 0
    s["counts"] = counts or {}
    s["by_horizon"] = {str(h): {**_pooled(g), **_series_stats(g, False)}
                       for h, g in ((h, cells[cells["horizon_days"] == h]) for h in horizons)}
    if "instrument_class" in cells:
        s["by_instrument_class"] = {k: {**_pooled(g), **_series_stats(g, True)}
                                    for k, g in cells.groupby("instrument_class", sort=True)}
    return s


# ---------------------------------------------------------------- official ----
def forecast_csv_frame(fc: pd.DataFrame) -> pd.DataFrame:
    iso = {d: starter_common.iso(d) for d in pd.unique(pd.concat([fc["origin_day"], fc["origin_day"] + fc["horizon_days"]]))}
    return pd.DataFrame({
        "series_id": fc["series_id"], "origin_date": fc["origin_day"].map(iso), "horizon_days": fc["horizon_days"],
        "q10": fc["q10"], "q50": fc["q50"], "q90": fc["q90"],
        "target_date": (fc["origin_day"] + fc["horizon_days"]).map(iso),
    })


def score_official(fc: pd.DataFrame, sids: list[str], horizons, truth_path, workdir, history_path=None,
                   frozen_cutoff: str | None = None, forecast_path=None) -> dict:
    """Write fc in the starter schema (full float precision) and run starter/scorer.py on it.
    Returns the parsed JSON report plus full-precision pooled numbers from its per-cell CSV
    (the JSON rounds to 6 decimals)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    fpath, ids_path = workdir / "forecast.csv", workdir / "series_ids.txt"
    rpath, cpath = workdir / "report.json", workdir / "cells.csv"
    for p in (rpath, cpath):
        p.unlink(missing_ok=True)
    if forecast_path:  # score an existing file as is (the submission)
        fpath = Path(forecast_path)
    else:
        forecast_csv_frame(fc).to_csv(fpath, index=False)
    ids_path.write_text("\n".join(sids) + "\n")
    args = ["--forecast", fpath, "--truth", truth_path, "--history", history_path or truth_path,
            "--series-ids", f"@{ids_path}", "--horizons", ",".join(map(str, horizons)),
            "--out", rpath, "--per-cell", cpath]
    if frozen_cutoff:
        args += ["--frozen-cutoff", frozen_cutoff]
    r = run_starter("scorer.py", *args)
    out = {"returncode": r.returncode, "stdout": r.stdout.strip(), "stderr": r.stderr.strip(),
           "report": json.loads(rpath.read_text()) if rpath.exists() else None, "forecast_csv": str(fpath)}
    c = pd.read_csv(cpath) if cpath.exists() and cpath.stat().st_size > 4 else None
    if c is not None and "loss" in c and len(c):
        loss, base = float(np.mean(c["loss"].to_numpy())), float(np.mean(c["baseline_loss"].to_numpy()))
        out.update(n_cells=int(len(c)), pooled_loss=loss, baseline_loss=base, pooled_skill=_skill(loss, base))
    return out
