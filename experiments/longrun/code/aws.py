"""AWS spot (hyperscaler_spot) daily per-GPU price per instance type, from change events, two segments either side of the
archive hole 2026-03-01..2026-06-30. Within a segment each AZ's price is carried forward day by day from its last change
event; nothing is carried across the hole. Daily value = median across AZs of the end-of-day price (Linux/UNIX only)."""
from __future__ import annotations

import pathlib

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
PACK = ROOT / "data/pack/gpu-price-pack-v0.1.1-handover"
OUT = ROOT / "runs/longrun"
TYPES = ["p3.16xlarge", "p4d.24xlarge", "p4de.24xlarge", "p5.48xlarge", "p5e.48xlarge", "p5en.48xlarge", "p6-b200.48xlarge", "p6-b300.48xlarge"]
SEGMENTS = {"A": ("2022-05-31", "2026-02-28"), "B": ("2026-07-01", "2026-10-31")}


def events() -> pd.DataFrame:
    q = f"""select instance_type, az_global_id az, ts_utc, cast(usd_per_gpu_hour as double) p
            from read_parquet('{PACK}/aws_spot_ticks/*.parquet')
            where instance_type in ({",".join(repr(t) for t in TYPES)}) and product_description = 'Linux/UNIX'
              and usd_per_gpu_hour is not null"""
    return duckdb.sql(q).df()


def daily(ev: pd.DataFrame) -> pd.DataFrame:
    ev = ev.assign(day=ev.ts_utc.dt.floor("D")).sort_values("ts_utc")
    last = ev.groupby(["instance_type", "az", "day"]).p.last().reset_index()
    rows = []
    for seg, (a, b) in SEGMENTS.items():
        days = pd.date_range(a, b, freq="D")
        s = last[(last.day >= a) & (last.day <= b)]
        for (it, az), g in s.groupby(["instance_type", "az"]):
            x = g.set_index("day").p.reindex(days).ffill().dropna()
            rows.append(pd.DataFrame({"instance_type": it, "az": az, "day": x.index, "p": x.values, "segment": seg}))
    d = pd.concat(rows)
    d.to_parquet(OUT / "aws_daily_az.parquet")
    out = d.groupby(["instance_type", "segment", "day"]).agg(p=("p", "median"), n_az=("az", "nunique")).reset_index()
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    ev = events()
    first = ev.groupby("instance_type").ts_utc.min()
    first.to_csv(OUT / "aws_first_seen.csv")
    print(first)
    d = daily(ev)
    d.to_parquet(OUT / "aws_daily.parquet")
    print(d.groupby(["instance_type", "segment"]).agg(n=("p", "size"), first=("day", "min"), last=("day", "max"),
                                                      p_first=("p", "first"), p_last=("p", "last"), n_az=("n_az", "median")))
