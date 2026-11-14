"""Announced-repricing calendar for forecasters. Leak rule: an entry is usable at origin d only if published <= d.

    from calendar_lib import scheduled_changes, apply_to_panel
    for e in scheduled_changes(origin_day): ...           # origin_day: int ordinal (gpuf day) or ISO date string
    centre = apply_to_panel(panel_rows, provider, gpu, target_day, origin_day)

Each entry carries `changes` = [{gpu, panel_gpus, tier, old, new, pct}], `effective_date`, `effective_utc`, `published`,
`confidence` (A provider/primary, B secondary quoting primary, C reported after), `quote_states_effective_date`, `edited_after_published`.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import pathlib

import numpy as np

PATH = pathlib.Path(__file__).resolve().parents[2] / "data_out" / "repricing_calendar.jsonl"
# panel tiers an announced tier can apply to (capacity blocks are not in any panel)
TIER_MAP = {"on_demand": {"on_demand"}, "on_demand_deployment": {"serverless", "on_demand"},
            "high": {"community", "spot"}, "medium": {"community", "spot"}, "low": {"community", "spot"}, "lowest": {"community", "spot"},
            "capacity_block": set()}


def _day(x) -> int:
    if isinstance(x, (int, np.integer)):
        return int(x)
    return dt.date.fromisoformat(str(x)[:10]).toordinal()


def effective_day(e) -> int:
    """UTC calendar day on which the new price first applies (e.g. 00:00 IST Oct 5 -> Oct 4)."""
    return _day(e["effective_utc"][:10])


@functools.lru_cache(maxsize=1)
def load(path: str = str(PATH)) -> tuple:
    return tuple(json.loads(l) for l in open(path) if l.strip())


def scheduled_changes(origin_day, min_confidence: str = "B", only_future: bool = False) -> list[dict]:
    """Calendar entries usable at origin_day: published on or before it, confidence at least `min_confidence`.
    only_future=True keeps only entries whose effective day is after the origin (the ones a forecast still has to apply)."""
    d = _day(origin_day)
    out = [e for e in load() if _day(e["published"]) <= d and e["confidence"] <= min_confidence]
    if only_future:
        out = [e for e in out if effective_day(e) > d]
    return out


# Days between the UTC effective day and the first panel day showing the new price, measured on dev (B1: fastgpu 7/7 events +1, gpurentalprices 10/10 +0).
COLLECTOR_LAG = {"fastgpu_daily": 1, "gpurentalprices": 0}


def apply_to_panel(rows, provider: str, gpu: str, tier: str, target_day: int, origin_day: int, min_confidence: str = "B", lag: int = 0):
    """Median of the origin-day panel (rows: DataFrame with day, provider, price for ONE series) after applying every
    usable announced change for (provider, gpu, tier) whose effective day + lag is on or before target_day.
    Pass lag=COLLECTOR_LAG[src]. Returns (centre, applied_entries)."""
    d = _day(origin_day)
    cur = rows[rows["day"] == d]
    if cur.empty:
        return None, []
    prices = cur["price"].to_numpy(dtype=float).copy()
    prov = cur["provider"].to_numpy()
    applied = []
    for e in scheduled_changes(d, min_confidence):
        if e["provider"] != provider or effective_day(e) + lag > target_day or effective_day(e) + lag <= d:
            continue
        for c in e["changes"]:
            if gpu in c["panel_gpus"] and tier in TIER_MAP.get(c["tier"], set()) and c["new"] is not None:
                m = prov == provider
                if c["old"] is not None:   # several announced tiers per GPU (Salad): only reprice offers sitting at that tier's old price
                    m &= np.isclose(prices, c["old"], rtol=0.03)
                if m.any():
                    prices[m] = c["new"]
                    applied.append((e["provider"], e["effective_date"], c["gpu"], c["tier"]))
    return float(np.median(prices)), applied
