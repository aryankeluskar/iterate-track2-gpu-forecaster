"""10 provider-gpu-date pairs with no repricing of that provider-gpu in D-21..D+7 (rows <= 2026-10-13)."""
import duckdb, pandas as pd, numpy as np, json
ROOT = "/Users/aryank/Developer/iterate_hackathon/track_2"
PACK = f"{ROOT}/data/pack/gpu-price-pack-v0.1.1-handover/rental_observations/source_id=%s/*/*.parquet"
sel = pd.read_csv(f"{ROOT}/runs/exa_attrib/selected.csv")
ev_prov = set(sel[sel.cls == "neocloud_rate_card"].provider)
cat = pd.read_csv(f"{ROOT}/runs/series/series_catalog.csv"); cat = cat[(cat.tier == "headline") & (cat.instrument_class == "neocloud_rate_card")]
cands = []
for _, c in cat.iterrows():
    o = duckdb.execute(f"""select dt::date d, provider, median(usd_per_gpu_hour) p from read_parquet('{PACK % c.source_id}')
        where gpu_model=? and pricing_tier=? and instrument_class=? and dt<=date '2026-10-13' group by all""",
        [c.gpu_model, c.pricing_tier, c.instrument_class]).df()
    o["d"] = pd.to_datetime(o.d)
    for prov, x in o.groupby("provider"):
        if prov not in ev_prov: continue
        x = x.sort_values("d").reset_index(drop=True)
        chg = (x.p.pct_change().abs() > 0.005)
        cd = x.d[chg]
        for _, r in x.iterrows():
            if r.d < pd.Timestamp("2026-09-08") + pd.Timedelta(days=0) or r.d > pd.Timestamp("2026-10-06"): continue
            if ((cd >= r.d - pd.Timedelta(days=21)) & (cd <= r.d + pd.Timedelta(days=7))).any(): continue
            cands.append(dict(provider=prov, gpu=c.gpu_model, tier=c.pricing_tier, date=r.d.date().isoformat(), price=r.p))
cd = pd.DataFrame(cands)
print(len(cd), "candidate pairs;", cd.groupby("provider").size().to_dict())
rng = np.random.default_rng(7)
cd = cd.sample(frac=1, random_state=7)
pick, cnt = [], {}
for _, r in cd.iterrows():
    k = (r.provider, r.gpu)
    if cnt.get(r.provider, 0) >= 2 or any(p["provider"] == r.provider and p["gpu"] == r.gpu for p in pick): continue
    cnt[r.provider] = cnt.get(r.provider, 0) + 1; pick.append(r.to_dict())
    if len(pick) == 10: break
pd.DataFrame(pick).to_csv(f"{ROOT}/runs/exa_attrib/controls.csv", index=False)
print(pd.DataFrame(pick))
