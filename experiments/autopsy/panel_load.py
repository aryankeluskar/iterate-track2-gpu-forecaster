"""Offer-level loader for the 37 rental_headline series (own copy; dev rows only, dt <= 2026-10-13)."""
import duckdb, pandas as pd
from gpuf import data

P = "data/pack/gpu-price-pack-v0.1.1-handover/rental_observations"
CUT = "2026-10-13"
COLS = "source_id, instrument_class, gpu_model, pricing_tier, cast(dt as date) dt, snapshot_ts_utc, provider, region_raw, sku_raw, gpu_count, usd_per_gpu_hour, quality_flag, available, extra_json"


def headline_ids():
    return data.universe("rental_headline")


def parse(sid):
    src, cls, gm, tier, _ = sid.split(".")
    return src, cls, gm.replace("_", " "), tier


def load_rows(cut=CUT):
    ids = headline_ids()
    keys = pd.DataFrame([dict(zip(["source_id", "instrument_class", "gpu_model", "pricing_tier"], parse(s)), series_id=s) for s in ids])
    con = duckdb.connect()
    con.register("keys", keys)
    out = []
    for src in keys.source_id.unique():
        q = f"""select k.series_id, {COLS.replace('source_id,', 'o.source_id,').replace('instrument_class,', 'o.instrument_class,').replace('gpu_model,', 'o.gpu_model,').replace('pricing_tier,', 'o.pricing_tier,')}
                from read_parquet('{P}/source_id={src}/*/*.parquet', hive_partitioning=false) o
                join keys k on o.source_id=k.source_id and o.instrument_class=k.instrument_class
                 and o.gpu_model=k.gpu_model and o.pricing_tier=k.pricing_tier
                where cast(o.dt as date) <= date '{cut}'"""
        out.append(con.sql(q).df())
    df = pd.concat(out, ignore_index=True)
    df["dt"] = pd.to_datetime(df["dt"])
    return df
