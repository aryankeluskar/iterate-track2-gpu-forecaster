"""Offer panel behind the afhubbard daily medians (hyperscaler list/spot and the afhubbard neocloud classes).

The scored value `afhubbard.<class>.<gpu>.<tier>.median` equals round(median(usd_per_gpu_hour), 4) over EVERY
row of that (class, gpu_model, pricing_tier, dt), all 1-3 snapshots of the day pooled (verified: 100% of
13,188 series-days to 2026-10-13 against daily_statistics.csv). An offer is (provider, region_raw, sku_raw,
gpu_count); `snap` is the snapshot's rank within its day.

Memory: only integer codes and float64 prices are kept (about 20 bytes a row, about 75 MB for 3.7M rows).
`offers()` returns only rows dated on or before the origin, so a forecaster that reads the panel only through it
cannot see later rows.
"""
from __future__ import annotations

import functools

import numpy as np
import pandas as pd

from .data import PACK, starter_common

OBS = PACK / "rental_observations" / "source_id=afhubbard"
SRC = "afhubbard"
_ORD0 = starter_common.day_of(pd.Timestamp("1970-01-01").date())


def parse_sid(sid: str):
    src, cls, gpu, tier, stat = sid.split(".")
    return src, cls, gpu.replace("_", " "), tier


@functools.lru_cache(maxsize=1)
def load() -> dict:
    """{'rows': DataFrame(ser, day, snap, key, prov, price), 'series': {(cls, gpu, tier): code},
    'provs': [names], 'keys': [names]}. Days are starter day ordinals."""
    import duckdb
    con = duckdb.connect()
    con.sql("set threads=2")
    con.sql(f"""create temp table r as
        select instrument_class cls, gpu_model gpu, pricing_tier tier, cast(dt as date) d, snapshot_ts_utc ts,
               provider, coalesce(region_raw,'') || '|' || coalesce(sku_raw,'') || '|' || coalesce(cast(gpu_count as varchar),'') k,
               usd_per_gpu_hour price
        from read_parquet('{OBS}/*/*.parquet', hive_partitioning=false)
        where usd_per_gpu_hour is not null and gpu_model <> 'other'""")
    ser = con.sql("select distinct cls, gpu, tier from r order by all").df()
    provs = con.sql("select distinct provider from r order by 1").df()["provider"].tolist()
    keys = con.sql("select distinct provider || '|' || k kk from r order by 1").df()["kk"].tolist()
    con.register("ser", ser.assign(sc=np.arange(len(ser), dtype=np.int32)))
    con.register("pv", pd.DataFrame({"provider": provs, "pc": np.arange(len(provs), dtype=np.int16)}))
    con.register("kv", pd.DataFrame({"kk": keys, "kc": np.arange(len(keys), dtype=np.int32)}))
    df = con.sql(f"""select cast(s.sc as smallint) ser, cast(date_diff('day', date '1970-01-01', r.d) + {_ORD0} as integer) "day",
               cast(dense_rank() over (partition by r.d order by r.ts) - 1 as tinyint) snap,
               kv.kc key, pv.pc prov, r.price
        from r join ser s using (cls, gpu, tier) join pv using (provider) join kv on kv.kk = r.provider || '|' || r.k
        order by ser, "day", snap, key""").df()
    con.close()
    series = {(a, b, c): i for i, (a, b, c) in enumerate(ser[["cls", "gpu", "tier"]].itertuples(index=False))}
    return {"rows": df, "series": series, "provs": provs, "keys": keys}


@functools.lru_cache(maxsize=1)
def _index() -> dict:
    d = load()
    rows = d["rows"]
    cuts = np.r_[0, np.nonzero(np.diff(rows["ser"].to_numpy()))[0] + 1, len(rows)]
    return {int(rows["ser"].iat[a]): rows.iloc[a:b].reset_index(drop=True) for a, b in zip(cuts[:-1], cuts[1:])}


def code(sid: str):
    src, cls, gpu, tier = parse_sid(sid)
    return load()["series"].get((cls, gpu, tier)) if src == SRC else None


def supported(sid: str) -> bool:
    c = code(sid)
    return c is not None and c in _index()


def offers(sid: str, origin_day: int) -> pd.DataFrame:
    """Rows (day, snap, key, prov, price) of one series dated on or before origin_day."""
    g = _index().get(code(sid))
    if g is None:
        return pd.DataFrame(columns=["day", "snap", "key", "prov", "price"])
    return g.loc[g["day"] <= origin_day, ["day", "snap", "key", "prov", "price"]]


def daily_median(sid: str, origin_day: int) -> pd.Series:
    o = offers(sid, origin_day)
    return o.groupby("day")["price"].median().round(4)
