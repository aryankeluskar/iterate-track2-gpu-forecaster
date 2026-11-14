"""Steps 1-2: offer panel, key stability, median reproduction, one row per median change (dev rows <= 2026-10-13)."""
import json, numpy as np, pandas as pd
import panel_load as pl, decomp as D

R = "experiments/autopsy/results"
rows = pd.read_parquet("runs/autopsy/rows.parquet")
assert rows.dt.max() <= pd.Timestamp(pl.CUT)
panel = D.offer_panel(rows)
panel.to_parquet("runs/autopsy/panel.parquet")
out = {}

# key stability: per collector, share of offers on day t still present on the next observed day; offer lifetimes
stab = []
for sid, g in panel.groupby("series_id"):
    days = sorted(g.dt.unique())
    sets = {d: set(g.offer[g.dt == d]) for d in days}
    provs = {d: set(g.provider[g.dt == d]) for d in days}
    for a, b in zip(days[:-1], days[1:]):
        stab.append(dict(source_id=g.source_id.iloc[0], series_id=sid, surv=len(sets[a] & sets[b]) / len(sets[a]),
                         prov_surv=len(provs[a] & provs[b]) / len(provs[a]), n=len(sets[a])))
stab = pd.DataFrame(stab)
life = panel.groupby(["source_id", "series_id", "offer"]).dt.nunique().reset_index()
ndays = panel.groupby("series_id").dt.nunique()
life["frac"] = life.dt / life.series_id.map(ndays)
out["key"] = {s: dict(key=D.KEYS[s], next_day_offer_survival=round(g.surv.mean(), 4),
                      next_day_provider_survival=round(g.prov_surv.mean(), 4),
                      offers_per_series_day=round(g.n.mean(), 1),
                      share_offers_present_all_days=round((life[life.source_id == s].frac == 1).mean(), 3),
                      n_distinct_offers=int((life.source_id == s).sum()))
              for s, g in stab.groupby("source_id")}

# reproduction against the harness series (unfilled days only)
sd = pd.read_csv("runs/series/series_daily.csv", usecols=["series_id", "date", "value", "is_filled"])
sd = sd[sd.series_id.isin(pl.headline_ids())]
sd["dt"] = pd.to_datetime(sd.date)
med = panel.groupby(["series_id", "dt"]).usd_per_gpu_hour.median().rename("panel_median").reset_index()
j = sd.merge(med, on=["series_id", "dt"], how="left")
j = j[(j.dt <= pl.CUT)]
ju = j[j.is_filled == 0]
ju = ju[ju.dt >= ju.series_id.map(panel.groupby("series_id").dt.min())]
ju["src"] = ju.series_id.str.split(".").str[0]
ju["ok"] = (ju.panel_median - ju.value).abs() <= 0.0051
out["reproduction"] = {s: dict(series_days=len(g), exact_within_half_cent=round(g.ok.mean(), 4),
                               missing_panel=int(g.panel_median.isna().sum()),
                               max_abs_diff=round(float((g.panel_median - g.value).abs().max()), 4))
                       for s, g in ju.groupby("src")}
out["filled_days_in_dev"] = int((j.is_filled == 1).sum())

# events: consecutive observed days with a median change
tabs = D.day_tables(panel)
ev = []
for sid, t in tabs.items():
    days = sorted(t)
    for a, b in zip(days[:-1], days[1:]):
        ma, mb = np.median(t[a].p), np.median(t[b].p)
        if abs(mb - ma) < 1e-9:
            continue
        r = D.decompose(t[a], t[b])
        r.update(series_id=sid, date_a=a, date_b=b, gap_days=(b - a).days)
        ev.append(r)
ev = pd.DataFrame(ev)
ev[["source_id", "instrument_class"]] = ev.series_id.str.split(".", expand=True)[[0, 1]]
ev["abs_dlog"] = ev.dlog.abs()
ev.to_parquet(f"{R}/events_dev.parquet")
cols = ["series_id", "date_a", "date_b", "m_a", "m_b", "dlog", "rep", "comp", "cause", "cause_shapley", "pivotal",
        "prov_reprice_up", "prov_reprice_down", "prov_entered", "prov_exited", "n_offers_a", "n_offers_b", "n_repriced", "n_entered", "n_exited"]
ev.sort_values("abs_dlog", ascending=False).head(60)[cols].to_csv(f"{R}/events_dev_top60.csv", index=False)
out["n_events"] = len(ev)
out["cause_counts"] = ev.cause.value_counts().to_dict()
out["cause_shapley_agree"] = round(float((ev.cause == ev.cause_shapley).mean()), 3)
out["n_pairs"] = int(sum(len(t) - 1 for t in tabs.values()))
json.dump(out, open(f"{R}/step12_summary.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str))
