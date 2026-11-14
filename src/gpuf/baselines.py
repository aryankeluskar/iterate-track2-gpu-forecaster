"""Starter baselines as harness forecasters, computed by the starter's own forecast_one."""
from __future__ import annotations

from .data import SeriesStore, starter_baselines


class _OneSeries(SeriesStore):
    """A SeriesStore holding one already-truncated series, so forecast_one sees exactly the harness's arrays."""

    def __init__(self, sid, days, vals):
        self._d = {sid: (days, vals)}


def starter_method(method: str, min_samples: int = 20, lookback_days: int | None = None):
    def f(sid, days, vals, origin_day, horizons, ctx):
        rows = starter_baselines.forecast_one(_OneSeries(sid, days, vals), sid, origin_day, list(horizons),
                                              method, min_samples, lookback_days)
        return {r["horizon_days"]: (r["q10"], r["q50"], r["q90"]) for r in rows}

    f.__name__ = method
    return f


drift = starter_method("drift")
last_value = starter_method("last_value")
