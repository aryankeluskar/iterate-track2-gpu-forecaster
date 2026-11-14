import pandas as pd, json
ROOT = "/Users/aryank/Developer/iterate_hackathon/track_2"
m = pd.read_csv(f"{ROOT}/runs/exa_attrib/events_merged.csv")
m["cls"] = m.series_id.str.split(".").str[1]
A = m.head(25).assign(stratum="A_top25")
B = m[(m.cls == "neocloud_rate_card")].head(15)
B = B[~B.set_index(["provider","date"]).index.isin(A.set_index(["provider","date"]).index)].assign(stratum="B_rate_card")
X = pd.DataFrame(json.load(open(f"{ROOT}/runs/exa_attrib/extra.json"))).assign(stratum="C_busy_day", cls="")
sel = pd.concat([A, B, X]).reset_index(drop=True)
sel["date"] = pd.to_datetime(sel.date)
sel["k"] = sel.provider + sel.gpu + sel.old.round(2).astype(str) + sel.new.round(2).astype(str)
sel = sel.sort_values("date")
first = sel.groupby("k").date.transform("min")
sel["also_seen"] = (sel.date != first)
sel = sel[(sel.date - first).dt.days.abs() > 3].assign(x=0).drop(columns="x") if False else sel[~((sel.date != first) & ((sel.date - first).dt.days <= 3))]
sel["date"] = sel.date.dt.date.astype(str)
sel = sel.reset_index(drop=True)
sel["id"] = range(len(sel))
sel.to_csv(f"{ROOT}/runs/exa_attrib/selected.csv", index=False)
pd.set_option("display.width", 250)
print(sel[["id","stratum","provider","date","gpu","cls","old","new","median_move","n_series","score"]].to_string())
print(sorted(sel.provider.unique()))
