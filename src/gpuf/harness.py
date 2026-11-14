"""Leak-safe evaluation harness.

A forecaster is a callable

    f(sid, days, vals, origin_day, horizons, ctx) -> {h: (q10, q50, q90)}

`days, vals` are read-only copies of that series' rows dated on or before origin_day (day
ordinals, USD per GPU-hour). `ctx` is an OriginContext: every array it holds was truncated
at origin_day before the forecaster was called, so no attribute or method of it can reach a
later row. A horizon the forecaster leaves out is filled with the last-value baseline (zero
skill for that cell, as Sunday's frozen-mode scorer does). Returned quantiles go through the
starter's own monotone(); non-positive quantiles are floored at POSITIVE_FLOOR and counted.

Not enforceable in Python and left to code review: reading the series CSV from disk inside a
forecaster, or walking interpreter frames / gc to reach the harness's full store.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import data, splits
from .data import starter_common
from .scoring import score_fast, summarize

POSITIVE_FLOOR = 1e-6

# Catalog fields that describe what a series IS; safe at any origin.
STATIC_META_FIELDS = ("series_id", "table", "source_id", "instrument_class", "statistic", "gpu_model",
                      "pricing_tier", "instance_type", "az_global_id", "product_description",
                      "benchmark_contract", "truth_availability", "source_url", "licence_id")
# Catalog fields computed from data up to the catalog's as_of date (2026-11-06 for the protocol
# catalog). They look ahead for any earlier origin and must NOT be used as features. ctx.meta never
# returns them: tier, tier_reason, members (AZ membership from the archive length), first_date,
# last_date, n_days, n_calendar_days, n_filled_days, as_of, n_days_to_as_of, last_date_to_as_of,
# last_value_to_as_of, median_n_providers, min_n_providers, n_distinct_values_90d.
AS_OF_FIELDS = ("tier", "tier_reason", "members", "first_date", "last_date", "n_days", "n_calendar_days",
                "n_filled_days", "as_of", "n_days_to_as_of", "last_date_to_as_of", "last_value_to_as_of",
                "median_n_providers", "min_n_providers", "n_distinct_values_90d")


def _ro(a: np.ndarray) -> np.ndarray:
    a = np.array(a, copy=True)  # a fresh copy: .base is None, so the full series is unreachable
    a.flags.writeable = False
    return a


_EMPTY = (_ro(np.empty(0, np.int64)), _ro(np.empty(0, np.float64)))


class OriginContext:
    """Every series' history at one origin. Built from arrays already truncated at the origin."""

    __slots__ = ("origin_day", "_hist", "_meta")

    def __init__(self, origin_day: int, hist: dict, meta: dict):
        self.origin_day = int(origin_day)
        self._hist = hist
        self._meta = meta

    def ids(self) -> list[str]:
        """Series with at least one row on or before the origin."""
        return list(self._hist)

    def history(self, sid: str) -> tuple[np.ndarray, np.ndarray]:
        """(days, vals) dated on or before the origin; empty arrays for an unknown or not-yet-started series."""
        return self._hist.get(sid, _EMPTY)

    def meta(self, sid: str) -> dict:
        """STATIC_META_FIELDS of the catalog row only (see AS_OF_FIELDS for what is withheld and why)."""
        return dict(self._meta.get(sid, {}))


def static_meta(catalog: pd.DataFrame) -> dict[str, dict]:
    cols = [c for c in STATIC_META_FIELDS if c in catalog.columns]
    return {r["series_id"]: r for r in catalog[cols].to_dict("records")}


def make_context(store, origin_day: int, meta: dict) -> OriginContext:
    hist = {}
    for sid in store.ids():
        d, v = store.history(sid, origin_day)
        if len(d):
            hist[sid] = (_ro(d), _ro(v))
    return OriginContext(origin_day, hist, meta)


def _clean(q, last: float) -> tuple[tuple[float, float, float], int]:
    q10, q50, q90 = (float(x) for x in q)
    if not all(math.isfinite(x) for x in (q10, q50, q90)):
        raise ValueError(f"non-finite quantiles {q}")
    q10, q50, q90 = starter_common.monotone(q10, q50, q90)
    n_clip = sum(x <= 0 for x in (q10, q50, q90))
    if n_clip:
        q10, q50, q90 = (max(x, POSITIVE_FLOOR) for x in (q10, q50, q90))
    return (q10, q50, q90), n_clip


def forecast(forecaster, origin_days, sids, horizons, store, meta) -> tuple[pd.DataFrame, dict]:
    """Forecast rows for every (sid, origin) with history. Columns: series_id, origin_day, horizon_days,
    q10, q50, q90, baseline (last value on or before the origin), filled (1 = filled from baseline)."""
    rows, n_filled, n_clipped = [], 0, 0
    horizons = tuple(int(h) for h in horizons)
    for o in sorted(set(int(x) for x in origin_days)):
        ctx = make_context(store, o, meta)
        for sid in sids:
            days, vals = ctx.history(sid)
            if len(days) == 0:
                continue
            last = float(vals[-1])
            out = forecaster(sid, days, vals, o, horizons, ctx) or {}
            for h in horizons:
                q = out.get(h)
                filled = q is None
                if filled:
                    q = (last, last, last)
                    n_filled += 1
                (q10, q50, q90), nc = _clean(q, last)
                n_clipped += nc
                rows.append((sid, o, h, q10, q50, q90, last, int(filled)))
    fc = pd.DataFrame(rows, columns=["series_id", "origin_day", "horizon_days", "q10", "q50", "q90", "baseline", "filled"])
    return fc, {"filled_from_baseline": n_filled, "quantiles_clipped": n_clipped}


@dataclass
class EvalResult:
    cells: pd.DataFrame
    summary: dict
    forecasts: pd.DataFrame
    info: dict = field(default_factory=dict)

    def official(self, workdir) -> dict:
        """Score the same forecasts with starter/scorer.py (backtest mode)."""
        from .scoring import score_official
        return score_official(self.forecasts, self.info["sids"], self.info["horizons"], self.info["series_path"], workdir)


def resolve_origins(split, unlock_test: bool = False, who: str = "") -> tuple[str, list[int]]:
    if isinstance(split, str):
        return split, splits.origins(split, unlock_test=unlock_test, who=who)
    days = sorted({x if isinstance(x, (int, np.integer)) else starter_common.day_of(starter_common.parse_date(x))
                   for x in split})
    if splits.touches(days, splits.TEST):
        if not unlock_test:
            raise splits.LockedSplit("these origins include locked test days; pass --unlock-test")
        splits.append_log(splits.TEST_LOG, {"event": "unlock", "who": who, "origins": "custom"})
    return "custom", [int(d) for d in days]


def evaluate(forecaster, split, universe="rental_headline", horizons=(1, 3, 7), *, series_path: str | None = None,
             catalog: pd.DataFrame | None = None, name: str | None = None, params: dict | None = None,
             unlock_test: bool = False) -> EvalResult:
    """Score `forecaster` on a split ('dev', 'val', 'test', 'starter15' or a list of origins) and a universe
    (a protocol universe name, or a list of series ids, e.g. from data.catalog_ids on another catalog).

    Every evaluation touching a validation origin is appended to data_out/val_query_log.jsonl; test
    origins need unlock_test=True and are logged to data_out/test_unlock_log.jsonl.
    """
    name = name or getattr(forecaster, "__name__", "forecaster")
    split_name, origins = resolve_origins(split, unlock_test, who=name)
    spath = series_path or data.series_path()
    store = data.load_store(spath)
    meta = static_meta(data.load_catalog())
    sids = data.universe(universe, catalog)
    t0 = time.time()
    fc, fcounts = forecast(forecaster, origins, sids, horizons, store, meta)
    cells, counts = score_fast(fc, store, sids, horizons)
    counts.update(fcounts)
    for c in ("instrument_class", "source_id"):
        cells[c] = cells["series_id"].map(lambda s, c=c: meta.get(s, {}).get(c, ""))
    summary = summarize(cells, horizons, counts)
    summary["wall_time_s"] = round(time.time() - t0, 3)
    uname = universe if isinstance(universe, str) else f"custom[{len(sids)}]"
    info = {"split": split_name, "universe": uname, "sids": sids, "horizons": tuple(horizons),
            "origins": origins, "series_path": spath, "method": name, "params": params or {}}
    headline = {k: summary[k] for k in ("pooled_skill", "pooled_loss", "baseline_loss", "n_cells")}
    if splits.touches(origins, splits.VAL):
        splits.append_log(splits.VAL_LOG, {"method": name, "params": params or {}, "split": split_name,
                                           "universe": uname, "result": headline})
    if splits.touches(origins, splits.TEST):
        splits.append_log(splits.TEST_LOG, {"event": "result", "method": name, "params": params or {},
                                            "universe": uname, "result": headline})
    return EvalResult(cells, summary, fc, info)
