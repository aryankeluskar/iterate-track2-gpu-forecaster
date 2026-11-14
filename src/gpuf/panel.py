"""Offer panel behind each daily median: rental_observations rows for fastgpu_daily and gpurentalprices.

The scored value `<src>.<class>.<gpu>.<tier>.median` is median(usd_per_gpu_hour) over every row of that
(collector, class, gpu_model, pricing_tier, dt). A persistent offer is identified by
(provider, region_raw, sku_raw, gpu_count) plus an occurrence index among same-key rows of the day (price
order), which keeps the panel equal to the row set so the median is reproduced exactly. fastgpu rows are
already one per provider x region per day; gpurentalprices needs sku and gpu_count to separate offers.

afhubbard (hyperscaler spot, up to three snapshots a day, thousands of AZ rows) is not loaded: methods fall
back to their base forecaster for those series.

Everything is loaded once into memory; `offers` and `group_offers` return only rows dated on or before
the origin, so a forecaster that reads the panel only through them cannot see later rows.
"""
from __future__ import annotations

import functools

import numpy as np
import pandas as pd

from .data import PACK, starter_common

SOURCES = ("fastgpu_daily", "gpurentalprices")
OBS = PACK / "rental_observations"


def parse_sid(sid: str):
    src, cls, gpu, tier, stat = sid.split(".")
    return src, cls, gpu.replace("_", " "), tier


@functools.lru_cache(maxsize=1)
def load() -> pd.DataFrame:
    """All rows of SOURCES: src, cls, gpu, tier, day, key (persistent offer id), provider, price."""
    import duckdb
    frames = []
    for s in SOURCES:
        q = f"""select source_id src, instrument_class cls, gpu_model gpu, pricing_tier tier, cast(dt as date) d,
                       provider, coalesce(region_raw,'') region, coalesce(sku_raw,'') sku,
                       coalesce(cast(gpu_count as varchar),'') gc, usd_per_gpu_hour price
                from read_parquet('{OBS}/source_id={s}/*/*.parquet', hive_partitioning=true)
                where usd_per_gpu_hour is not null"""
        frames.append(duckdb.sql(q).df())
    df = pd.concat(frames, ignore_index=True)
    df["day"] = pd.to_datetime(df["d"]).map(lambda x: starter_common.day_of(x.date())).astype(np.int64)
    base = df["provider"] + "|" + df["region"] + "|" + df["sku"] + "|" + df["gc"]
    df = df.assign(base=base).sort_values(["src", "cls", "gpu", "tier", "day", "base", "price"], kind="stable")
    occ = df.groupby(["src", "cls", "gpu", "tier", "day", "base"]).cumcount()
    df["key"] = df["base"] + "#" + occ.astype(str)
    return df[["src", "cls", "gpu", "tier", "day", "key", "provider", "price"]].reset_index(drop=True)


@functools.lru_cache(maxsize=1)
def _index():
    df = load()
    by_series = {k: g.reset_index(drop=True) for k, g in df.groupby(["src", "cls", "gpu", "tier"], sort=False)}
    return by_series


def supported(sid: str) -> bool:
    src, cls, gpu, tier = parse_sid(sid)
    return src in SOURCES and (src, cls, gpu, tier) in _index()


def offers(sid: str, origin_day: int) -> pd.DataFrame:
    """Rows (day, key, provider, price) of one series dated on or before origin_day."""
    g = _index().get(parse_sid(sid))
    if g is None:
        return pd.DataFrame(columns=["day", "key", "provider", "price"])
    return g.loc[g["day"] <= origin_day, ["day", "key", "provider", "price"]]


def group_series(sid: str) -> list:
    """Every (src, cls, gpu, tier) panel of the same collector and instrument class."""
    src, cls, _, _ = parse_sid(sid)
    return [k for k in _index() if k[0] == src and k[1] == cls]


def panel_offers(key, origin_day: int) -> pd.DataFrame:
    g = _index()[key]
    return g.loc[g["day"] <= origin_day, ["day", "key", "provider", "price"]]


def daily_median(sid: str, origin_day: int) -> pd.Series:
    o = offers(sid, origin_day)
    return o.groupby("day")["price"].median()
