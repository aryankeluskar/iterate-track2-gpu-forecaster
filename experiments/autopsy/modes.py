"""Step 6: blend-loss attribution to cause x pivotal provider; failure_modes.json."""
import json, numpy as np, pandas as pd
R = "experiments/autopsy/results"
cb = pd.read_parquet("runs/autopsy/blend_cells_attrib.parquet")
ev = pd.read_parquet(f"{R}/events_dev.parquet"); ev = ev[ev.date_b >= "2026-08-04"]
tot = cb.loss.sum()
cb["p0"] = cb.pivotal.fillna("").str.split(",").str[0]
cb["prov_all"] = (cb.prov_entered.fillna("") + "," + cb.prov_exited.fillna("") + "," + cb.prov_reprice_up.fillna("") + "," + cb.prov_reprice_down.fillna(""))
def mode(r):
    if r.cause in ("none", "no_panel"): return "no_move"
    if r.cause == "composition": return "composition_entry_exit"
    if r.cause == "mixed": return "mixed_reprice_plus_entry_exit"
    if r.p0 == "verda": return "repricing_verda_staircase"
    if r.p0 == "sfcompute": return "repricing_sfcompute_marketplace_ask"
    if r.source_id == "afhubbard" or r.instrument_class == "hyperscaler_spot": return "repricing_hyperscaler_spot"
    if r.p0 == "scaleway": return "repricing_scaleway_small_drift"
    return "repricing_other_provider"
cb["mode"] = cb.apply(mode, axis=1)
g = cb.groupby("mode")
tab = pd.DataFrame({"n_cells": g.size(), "loss_share": g.loss.sum() / tot,
                    "miss_n": g.miss.sum(), "miss_loss_share": cb[cb.miss].groupby("mode").loss.sum() / tot,
                    "share_above_q90": g.apply(lambda x: (x.miss_side == "above").mean()),
                    "lv_loss_share": g.baseline_loss.sum() / cb.baseline_loss.sum(),
                    "blend_vs_lv": g.loss.sum() / g.baseline_loss.sum()}).fillna(0).sort_values("loss_share", ascending=False).round(3)
by_h = (cb.groupby(["mode", "horizon_days"]).loss.sum() / tot).unstack().round(3)
top_series = {m: (x.groupby("series_id").loss.sum() / tot).sort_values(ascending=False).head(3).round(3).to_dict() for m, x in cb.groupby("mode")}
# examples: largest one-day events per mode, with providers
def evmode(e):
    if e.cause == "composition": return "composition_entry_exit"
    if e.cause == "mixed": return "mixed_reprice_plus_entry_exit"
    p0 = (e.pivotal or "").split(",")[0]
    if p0 == "verda": return "repricing_verda_staircase"
    if p0 == "sfcompute": return "repricing_sfcompute_marketplace_ask"
    if e.instrument_class == "hyperscaler_spot": return "repricing_hyperscaler_spot"
    if p0 == "scaleway": return "repricing_scaleway_small_drift"
    return "repricing_other_provider"
ev["mode"] = ev.apply(evmode, axis=1)
evc = ev.groupby("mode").agg(n_events=("dlog", "size"), abs_dlog_share=("abs_dlog", "sum"), up_share=("dlog", lambda s: (s > 0).mean()),
                              med_abs_dlog=("abs_dlog", "median"))
evc["abs_dlog_share"] /= ev.abs_dlog.sum()
def ex(r):
    who = r.pivotal or ""
    act = []
    if r.prov_entered: act.append(f"entered: {r.prov_entered}")
    if r.prov_exited: act.append(f"exited: {r.prov_exited}")
    if r.prov_reprice_up: act.append(f"repriced up: {r.prov_reprice_up}")
    if r.prov_reprice_down: act.append(f"repriced down: {r.prov_reprice_down}")
    return f"{r.date_a.date()}->{r.date_b.date()} {r.series_id}: median {r.m_a:.3f}->{r.m_b:.3f} ({r.dlog:+.3f} log), pivotal provider {who or 'n/a'}; {'; '.join(act)}; offers {r.n_offers_a}->{r.n_offers_b}"
examples = {m: [ex(r) for r in x.sort_values("abs_dlog", ascending=False).head(2).itertuples()] for m, x in ev.groupby("mode")}
# Verda: is the next step visible? share of Verda median-moving reprices preceded by a Verda reprice (any series, same collector) within 7 days
pan = pd.read_parquet("runs/autopsy/panel.parquet")
pv = pan[(pan.provider == "verda") & (pan.dt >= "2026-08-01")].groupby(["source_id", "series_id", "dt"]).usd_per_gpu_hour.mean().reset_index().sort_values(["series_id", "dt"])
pv["chg"] = pv.groupby("series_id").usd_per_gpu_hour.diff().abs() > 1e-9
vdays = pv[pv.chg].groupby("source_id").dt.apply(lambda s: sorted(set(s)))
vv = ev[ev["mode"] == "repricing_verda_staircase"]
prec = [any((d < r.date_b) and (d >= r.date_b - pd.Timedelta(days=7)) for d in vdays.get(r.source_id, [])) for r in vv.itertuples()]
verda_daily_rate = {s: round(len(d) / pv[pv.source_id == s].dt.nunique(), 3) for s, d in vdays.items()}
out = dict(table=tab.reset_index().to_dict("records"), by_h=by_h.reset_index().to_dict("records"), top_series=top_series,
           event_level=evc.round(3).reset_index().to_dict("records"), examples=examples,
           verda_preceded_by_verda_reprice_within7=round(float(np.mean(prec)), 3), verda_n=len(vv), verda_share_of_days_with_any_reprice=verda_daily_rate)
json.dump(out, open("runs/autopsy/modes_raw.json", "w"), indent=1, default=str)
print(tab.to_string()); print(by_h.to_string()); print(evc.round(3).to_string())
print(json.dumps({k: out[k] for k in ("top_series", "examples", "verda_preceded_by_verda_reprice_within7", "verda_n", "verda_share_of_days_with_any_reprice")}, indent=1, default=str))
