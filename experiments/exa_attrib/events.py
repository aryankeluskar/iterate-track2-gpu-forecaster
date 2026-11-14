"""Provider repricing events behind the headline series' median moves. Rows dated <= 2026-10-13 only."""
import datetime as dt
import duckdb, pandas as pd, numpy as np

ROOT = "/Users/aryank/Developer/iterate_hackathon/track_2"
PACK = f"{ROOT}/data/pack/gpu-price-pack-v0.1.1-handover/rental_observations/source_id=%s/*/*.parquet"
CUT = "2026-10-13"
cat = pd.read_csv(f"{ROOT}/runs/series/series_catalog.csv")
cat = cat[cat.tier == "headline"]
cells = pd.read_parquet(f"{ROOT}/runs/failure/blend_dev_cells.parquet")
share = cells.groupby("series_id").baseline_loss.sum()
share = share / share.sum()

rows = []
for _, c in cat.iterrows():
    sid = c.series_id
    q = f"""select dt::date d, provider, median(usd_per_gpu_hour) p, count(*) n
      from read_parquet('{PACK % c.source_id}') where gpu_model=? and pricing_tier=? and instrument_class=? and dt<=date '{CUT}'
      group by all"""
    o = duckdb.execute(q, [c.gpu_model, c.pricing_tier, c.instrument_class]).df()
    o["d"] = pd.to_datetime(o.d)
    med = o.groupby("d").p.median()  # note: median over provider medians, approximates the series
    full = duckdb.execute(f"""select dt::date d, median(usd_per_gpu_hour) m, count(distinct provider) np from read_parquet('{PACK % c.source_id}')
      where gpu_model=? and pricing_tier=? and instrument_class=? and dt<=date '{CUT}' group by all order by 1""",
      [c.gpu_model, c.pricing_tier, c.instrument_class]).df()
    full["d"] = pd.to_datetime(full.d); full = full.set_index("d")
    mv = np.log(full.m).diff()
    full["prev"] = full.index.to_series().shift(1)
    pv = o.pivot(index="d", columns="provider", values="p").sort_index()
    for prov in pv.columns:
        s = pv[prov].dropna()
        for d, new in s.items():
            prev_days = s.index[s.index < d]
            if len(prev_days) == 0 or (d - prev_days[-1]).days > 3: continue
            old = s[prev_days[-1]]
            if old > 0 and abs(new / old - 1) >= 0.02 and d in mv.index and pd.notna(mv[d]):
                rows.append(dict(series_id=sid, provider=prov, gpu=c.gpu_model, tier=c.pricing_tier, cls=c.instrument_class,
                                 src=c.source_id, date=d.date(), old=old, new=new, prov_chg=new / old - 1,
                                 median_move=float(mv[d]), n_prov=int(full.np[d]), loss_share=float(share.get(sid, 0))))
ev = pd.DataFrame(rows)
ev["score"] = ev.median_move.abs() * ev.loss_share
ev.to_csv(f"{ROOT}/runs/exa_attrib/events_raw.csv", index=False)
print(len(ev), "raw provider-series events;", (ev.median_move.abs() > 0).sum(), "with median moving")
