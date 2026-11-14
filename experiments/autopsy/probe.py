"""Probes for failure-mode entries: relabels, pre-exit visibility, one-step fragility, provider repricing patterns."""
import json, numpy as np, pandas as pd
import decomp as D
R = "experiments/autopsy/results"
ev = pd.read_parquet(f"{R}/events_dev.parquet"); ev = ev[ev.date_b >= "2026-08-04"]
panel = pd.read_parquet("runs/autopsy/panel.parquet")
tabs = D.day_tables(panel)
out = {}
c = ev[ev.cause == "composition"].copy()
c["relabel"] = [bool(set(a.split(",")) & set(b.split(",")) - {""}) for a, b in zip(c.prov_entered, c.prov_exited)]
c["kind"] = np.where(c.relabel, "relabel", np.where(c.n_entered > 0, np.where(c.n_exited > 0, "enter+exit", "entry"), "exit"))
out["composition_kinds"] = c.groupby("kind").agg(n=("dlog", "size"), abs_dlog=("abs_dlog", "sum"), up=("dlog", lambda s: int((s > 0).sum()))).to_dict("index")
out["composition_top_providers"] = pd.concat([c.prov_entered.str.split(","), c.prov_exited.str.split(",")]).explode().replace("", np.nan).dropna().value_counts().head(8).to_dict()
# fragility: |log change| of median if exactly one offer at the median-adjacent position leaves (max over dropping each distinct offer)
def frag(A):
    m = np.median(A.p); best = 0
    for o in A.offer.unique():
        x = A.p[A.offer != o]
        if len(x): best = max(best, abs(np.log(np.median(x) / m)))
    return best
c["fragility"] = [frag(tabs[s][d]) for s, d in zip(c.series_id, c.date_a)]
out["composition_jump_vs_one_offer_fragility"] = dict(corr=round(float(np.corrcoef(c.abs_dlog, c.fragility)[0, 1]), 3),
    share_jump_within_10pct_of_fragility=round(float((np.abs(c.abs_dlog - c.fragility) <= 0.1 * c.abs_dlog + 1e-6).mean()), 3),
    median_ratio=round(float(np.median(c.abs_dlog / c.fragility.replace(0, np.nan))), 3))
# fragility distribution over all series-days (non-afhubbard) and whether composition events concentrate on fragile days
alld = [(s, d) for s, t in tabs.items() if not s.startswith("afhubbard") for d in t if d >= pd.Timestamp("2026-08-04")]
fr = pd.Series([frag(tabs[s][d]) for s, d in alld], index=pd.MultiIndex.from_tuples(alld))
out["fragility_all_days_quantiles"] = fr.quantile([.25, .5, .75, .9]).round(4).to_dict()
out["fragility_composition_days_quantiles"] = c[~c.series_id.str.startswith("afhubbard")].fragility.quantile([.25, .5, .75, .9]).round(4).to_dict()
# exits preceded by available==False or by a reprice in the previous 3 days (gpurentalprices / fastgpu)
p = panel[(panel.dt >= "2026-08-04") & (panel.source_id != "afhubbard")]
out["available_false_rows"] = int((p.available == False).sum())
# repricing by provider: up/down, size, reversal within 7 days (offer goes back to previous price)
po = p.groupby(["source_id", "series_id", "offer", "provider", "dt"]).usd_per_gpu_hour.mean().rename("p").reset_index().sort_values(["series_id", "offer", "dt"])
po["prev"] = po.groupby(["series_id", "offer"]).p.shift()
rp = po[po.prev.notna() & ((po.p - po.prev).abs() > 1e-9)].copy()
rp["lr"] = np.log(rp.p / rp.prev)
def back(r):
    g = po[(po.series_id == r.series_id) & (po.offer == r.offer) & (po.dt > r.dt) & (po.dt <= r.dt + pd.Timedelta(days=7))]
    return bool((np.abs(g.p - r.prev) < 1e-9).any())
rp["back7"] = [back(r) for r in rp.itertuples()]
out["reprices_by_provider"] = rp.groupby(["source_id", "provider"]).agg(n=("lr", "size"), up=("lr", lambda s: int((s > 0).sum())),
    med_abs_lr=("lr", lambda s: round(float(s.abs().median()), 4)), back_to_prev_within7=("back7", "mean"),
    n_series=("series_id", "nunique")).query("n>=5").round(3).reset_index().to_dict("records")
# median-moving reprices: which providers are pivotal in repricing events
r = ev[ev.cause == "repricing"]
out["repricing_pivotal_provider_counts"] = r.groupby("source_id").pivotal.apply(lambda s: s.str.split(",").str[0].value_counts().head(5).to_dict()).to_dict()
out["repricing_pivotal_provider_absdlog_share"] = (r.assign(p0=r.pivotal.str.split(",").str[0]).groupby(["source_id", "p0"]).abs_dlog.sum() / r.abs_dlog.sum()).sort_values(ascending=False).head(10).round(3).to_dict()
c.to_parquet("runs/autopsy/composition_events.parquet")
def clean(o):
    if isinstance(o, dict): return {("|".join(map(str, k)) if isinstance(k, tuple) else str(k)): clean(v) for k, v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    return o
json.dump(clean(out), open(f"{R}/probe_summary.json", "w"), indent=1, default=str)
print(json.dumps(clean(out), indent=1, default=str))
