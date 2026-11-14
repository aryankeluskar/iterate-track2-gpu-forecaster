import pandas as pd, numpy as np, datetime as dt, json
ROOT = "/Users/aryank/Developer/iterate_hackathon/track_2"
ev = pd.read_csv(f"{ROOT}/runs/exa_attrib/events_raw.csv", parse_dates=["date"])
ev = ev[ev.median_move.abs() > 0.005]
g = []
for (p, d), x in ev.groupby(["provider", "date"]):
    top = x.sort_values("score", ascending=False).iloc[0]
    g.append(dict(provider=p, date=d.date().isoformat(), gpu=top.gpu, tier=top.tier, old=top.old, new=top.new,
                  median_move=top.median_move, score=x.score.sum(), n_series=len(x),
                  gpus=sorted(set(x.gpu)), series_id=top.series_id, src=top.src, prov_chg=top.prov_chg))
m = pd.DataFrame(g).sort_values("score", ascending=False).reset_index(drop=True)
m["loss_share_total"] = m.score / m.score.sum()
top = m.head(25).copy()
# busiest loss days
cells = pd.read_parquet(f"{ROOT}/runs/failure/blend_dev_cells.parquet")
bd = cells.groupby("origin_date").baseline_loss.sum().sort_values(ascending=False).head(10)
print("busiest origin days:\n", bd / cells.baseline_loss.sum())
top.to_json(f"{ROOT}/runs/exa_attrib/top25.json", orient="records", indent=1)
m.to_csv(f"{ROOT}/runs/exa_attrib/events_merged.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 30)
print(top[["provider","date","gpu","old","new","prov_chg","median_move","n_series","score","loss_share_total"]].to_string())
print(len(m), "merged events; top25 share of total score", top.score.sum()/m.score.sum())

# busiest loss days: the largest event in (origin, origin+7] for each of the 10 busiest origin days
extra = []
have = set(zip(top.provider, top.date))
for od in bd.index:
    o = pd.Timestamp(od)
    w = m[(pd.to_datetime(m.date) > o) & (pd.to_datetime(m.date) <= o + pd.Timedelta(days=7))]
    for _, r in w.head(2).iterrows():
        if (r.provider, r.date) not in have:
            have.add((r.provider, r.date)); d = r.to_dict(); d["why"] = f"busy origin {od}"; extra.append(d)
ex = pd.DataFrame(extra)
ex.to_json(f"{ROOT}/runs/exa_attrib/extra.json", orient="records", indent=1)
print(ex[["provider","date","gpu","old","new","median_move","score","why"]].to_string())
print(sorted(set(top.provider) | set(ex.provider)))
