"""Steps 2-4: loss by cause for S0..S3, the up-move >5% misses of S3 and origin signals, calibration (dev rows <= 2026-10-13)."""
import sys, json, datetime as dt
import numpy as np, pandas as pd
sys.path.insert(0, "experiments/calendar")
import calendar_lib as cal

R = "experiments/autopsy2/results"
CUT = pd.Timestamp("2026-10-13")
K = ["series_id", "origin_day", "horizon_days"]
SYS = ["S0", "S1", "S2", "S3"]
out = {}

# ---------- cells ----------
hd = pd.read_parquet("experiments/autopsy/results/hday_cells_dev.parquet")
base = hd[K + ["origin_date", "source_id", "instrument_class", "y", "baseline", "baseline_loss", "cause", "rep_shapley", "comp_shapley",
               "n_offers_a", "n_entered", "n_exited", "prov_entered", "prov_exited", "prov_reprice_up", "prov_reprice_down", "pivotal"]].copy()
for s in SYS:
    c = pd.read_parquet(f"runs/autopsy2/cells_{s}.parquet")[K + ["q10", "q50", "q90", "loss", "baseline_loss"]]
    c = c.rename(columns={x: f"{s}_{x}" for x in ["q10", "q50", "q90", "loss", "baseline_loss"]})
    base = base.merge(c, on=K, how="inner")
assert len(base) == 4278 and np.allclose(base.baseline_loss, base.S3_baseline_loss)
base["o"] = pd.to_datetime(base.origin_date)
base["t"] = base.o + pd.to_timedelta(base.horizon_days, unit="D")
assert base.t.max() <= CUT
base["r"] = base.y / base.baseline - 1
base["gpu"] = base.series_id.str.split(".").str[2].str.replace("_", " ")
base["tier"] = base.series_id.str.split(".").str[3]

# ---------- offer panel, provider reprice rates ----------
pan = pd.read_parquet("runs/autopsy/panel.parquet", columns=["series_id", "source_id", "gpu_model", "pricing_tier", "dt", "provider", "offer", "usd_per_gpu_hour"])
pan = pan[(pan.dt <= CUT) & (pan.source_id != "afhubbard")]
po = pan.groupby(["source_id", "series_id", "gpu_model", "pricing_tier", "provider", "offer", "dt"]).usd_per_gpu_hour.mean().rename("p").reset_index()
po = po.sort_values(["series_id", "offer", "dt"])
po["dp"] = po.groupby(["series_id", "offer"]).p.diff()
po["rep"] = po.dp.abs() > 1e-9
po["up"] = po.dp > 1e-9
# provider-day on a collector: repriced any headline offer that day
pd_ = po[po.dp.notna()].groupby(["source_id", "provider", "dt"]).agg(rep=("rep", "any"), up=("up", "any")).reset_index()
pd_idx = {k: g.set_index("dt") for k, g in pd_.groupby(["source_id", "provider"])}


def rate(src, pv, o, W=21):
    g = pd_idx.get((src, pv))
    if g is None:
        return 0.0
    w = g[(g.index > o - pd.Timedelta(days=W)) & (g.index <= o)]
    return float(w.rep.mean()) if len(w) else 0.0


def first(s):
    return next((x for x in str(s).split(",") if x and x != "nan" and x != "None"), None)


# ---------- cause labels ----------
cal_rows = cal.load()


def announced(pv, gpu, tier, src, o, t):
    if pv is None:
        return False
    od, td = o.toordinal(), t.toordinal()
    for e in cal.scheduled_changes(od):
        if e["provider"] != pv:
            continue
        ed = cal.effective_day(e) + cal.COLLECTOR_LAG.get(src, 0)
        if not (od < ed <= td):
            continue
        if any(gpu in c["panel_gpus"] and tier in cal.TIER_MAP.get(c["tier"], set()) for c in e["changes"]):
            return True
    return False


def announced_any(pv, gpu, tier, src, o, t):  # regardless of publication date (for the 'late' diagnostic)
    od, td = o.toordinal(), t.toordinal()
    for e in cal_rows:
        ed = cal.effective_day(e) + cal.COLLECTOR_LAG.get(src, 0)
        if e["provider"] == pv and od < ed <= td and any(gpu in c["panel_gpus"] and tier in cal.TIER_MAP.get(c["tier"], set()) for c in e["changes"]):
            return True
    return False


labs, provs, rates = [], [], []
for r in base.itertuples():
    moved = abs(r.y - r.baseline) > 1e-9
    pv, rt = None, np.nan
    if not moved:
        lab = "none"
    elif r.source_id == "afhubbard":
        lab = "hyperscaler_spot"
    elif r.instrument_class == "marketplace_ask":
        lab, pv = "marketplace_ask", first(r.pivotal) or first(r.prov_reprice_up) or first(r.prov_reprice_down)
    else:
        compo = r.cause == "composition" or (r.cause == "mixed" and abs(r.comp_shapley) > abs(r.rep_shapley))
        pv = first(r.pivotal)
        if compo:
            ent, ex = set(str(r.prov_entered).split(",")), set(str(r.prov_exited).split(","))
            if pv in ent:
                lab = "entry"
            elif pv in ex:
                lab = "exit"
            else:
                lab = "entry" if r.n_entered > 0 else "exit"
            pv = pv or first(r.prov_entered if lab == "entry" else r.prov_exited)
        else:
            pv = pv or first(r.prov_reprice_up) or first(r.prov_reprice_down)
            rt = rate(r.source_id, pv, r.o)
            if rt > 0.15:
                lab = "dynamic_reprice"
            elif announced(pv, r.gpu, r.tier, r.source_id, r.o, r.t):
                lab = "announced_oneoff"
            else:
                lab = "unannounced_oneoff"
    labs.append(lab); provs.append(pv); rates.append(rt)
base["cause2"], base["provider"], base["prov_rate21"] = labs, provs, rates
base["late_announced"] = [(c == "unannounced_oneoff") and announced_any(p, g, ti, s, o, t)
                          for c, p, g, ti, s, o, t in zip(base.cause2, base.provider, base.gpu, base.tier, base.source_id, base.o, base.t)]
base.drop(columns=["o", "t"]).to_parquet("runs/autopsy2/cells_labelled.parquet")

# ---------- step 2: loss by cause ----------
ORDER = ["none", "dynamic_reprice", "announced_oneoff", "unannounced_oneoff", "entry", "exit", "marketplace_ask", "hyperscaler_spot"]
LV = base.baseline_loss.sum()
rows = []
for c in ORDER:
    g = base[base.cause2 == c]
    row = dict(cause=c, cells=len(g), share_lv_loss=g.baseline_loss.sum() / LV)
    for s in SYS:
        row[f"{s}_loss_over_lv"] = g[f"{s}_loss"].sum() / g.baseline_loss.sum() if g.baseline_loss.sum() > 0 else np.nan
        row[f"{s}_loss_share_of_total_lv"] = g[f"{s}_loss"].sum() / LV
        row[f"{s}_share_of_own_loss"] = g[f"{s}_loss"].sum() / base[f"{s}_loss"].sum()
    rows.append(row)
tab = pd.DataFrame(rows)
tot = dict(cause="total", cells=len(base), share_lv_loss=1.0)
for s in SYS:
    tot[f"{s}_loss_over_lv"] = base[f"{s}_loss"].sum() / LV; tot[f"{s}_loss_share_of_total_lv"] = tot[f"{s}_loss_over_lv"]; tot[f"{s}_share_of_own_loss"] = 1.0
tab = pd.concat([tab, pd.DataFrame([tot])], ignore_index=True)
tab.round(4).to_csv(f"{R}/loss_by_cause.csv", index=False)
print(tab[["cause", "cells", "share_lv_loss"] + [f"{s}_loss_over_lv" for s in SYS] + [f"{s}_share_of_own_loss" for s in SYS]].round(3).to_string())
out["late_announced_cells"] = int(base.late_announced.sum())
out["late_announced_lv_share"] = float(base[base.late_announced].baseline_loss.sum() / LV)
# S2 -> S3 change by cause, in points of total LV loss
out["S2_to_S3_drop_points_of_lv"] = {c: float((base[base.cause2 == c].S2_loss.sum() - base[base.cause2 == c].S3_loss.sum()) / LV) for c in ORDER}
out["S0_to_S3_drop_points_of_lv"] = {c: float((base[base.cause2 == c].S0_loss.sum() - base[base.cause2 == c].S3_loss.sum()) / LV) for c in ORDER}

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
cols = dict(zip(ORDER, ["#bbbbbb", "#1f77b4", "#2ca02c", "#d62728", "#ff7f0e", "#ffbb78", "#9467bd", "#8c564b"]))
fig, ax = plt.subplots(figsize=(10, 5))
names = {"S0": "S0 drift", "S1": "S1 mix", "S2": "S2 mix+gbm+chronos", "S3": "S3 +fm2+analog+prov"}
for i, s in enumerate(SYS):
    b = 0
    for c in ORDER:
        v = tab.loc[tab.cause == c, f"{s}_loss_share_of_total_lv"].item()
        ax.bar(i, v, bottom=b, color=cols[c], label=c if i == 0 else None, edgecolor="white", lw=0.5)
        b += v
    ax.text(i, b + 0.01, f"{b:.3f}", ha="center")
ax.axhline(1, color="k", ls=":", lw=1); ax.text(3.4, 1.0, "last value", va="bottom", ha="right", fontsize=8)
ax.set_xticks(range(4)); ax.set_xticklabels([names[s] for s in SYS], fontsize=9)
ax.set_ylabel("pinball loss / last-value loss (dev headline, 4,278 cells)"); ax.set_ylim(0, 1.08)
ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0)); ax.set_title("Dev loss by cause of the move, per system")
fig.tight_layout(); fig.savefig(f"{R}/loss_by_cause.png", dpi=130)

# ---------- signals at the origin, for every panel cell ----------
FAM = {"H100 SXM 80GB": "H100", "H100 80GB": "H100", "A100 SXM 80GB": "A100_80", "A100 80GB": "A100_80"}
po["fam"] = po.gpu_model.map(lambda g: FAM.get(g, g))
other = {"fastgpu_daily": "gpurentalprices", "gpurentalprices": "fastgpu_daily"}
# provider x collector x family x tier: dates with an up-reprice; dates listed
up_days = po[po.up].groupby(["source_id", "provider", "fam", "pricing_tier"]).dt.apply(set).to_dict()
up_days_gpu = po[po.up].groupby(["source_id", "provider", "series_id"]).dt.apply(set).to_dict()
up_days_any = po[po.up].groupby(["source_id", "provider"]).dt.apply(lambda x: sorted(set(x))).to_dict()
listed = po.groupby(["source_id", "fam", "pricing_tier", "dt"]).provider.apply(set).to_dict()
day_tab = {k: g for k, g in po.groupby(["series_id", "dt"])}


def win(days, o, W):
    return any(o - pd.Timedelta(days=W) < d <= o for d in days)


sig = []
for r in base.itertuples():
    o, t = pd.Timestamp(r.origin_date), pd.Timestamp(r.origin_date) + pd.Timedelta(days=r.horizon_days)
    A = day_tab.get((r.series_id, o))
    if A is None:
        sig.append({}); continue
    fam = FAM.get(r.gpu, r.gpu)
    prov_here = set(A.provider)
    m = float(np.median(A.p))
    loo = [abs(np.log(np.median(np.delete(A.p.values, i)) / m)) for i in range(len(A))] if len(A) > 1 else [0]
    s = dict(idx=r.Index, n_offers=len(A), fragility=max(loo))
    # (a) calendar: any panel provider has a usable announced change effective in (o, t]
    s["calendar"] = any(announced(pv, r.gpu, r.tier, r.source_id, o, t) for pv in prov_here)
    # (b) a provider in this panel raised this GPU family on the other collector in the last 7 days, not yet here
    oth = other[r.source_id]
    s["other_collector_up"] = any(win(up_days.get((oth, pv, fam, r.tier), ()), o, 7) and not win(up_days_gpu.get((r.source_id, pv, r.series_id), ()), o, 7) for pv in prov_here)
    # (c) a provider in this panel raised other GPUs on this collector in the last 7 days, not this one
    s["other_gpu_up"] = any(win(up_days_any.get((r.source_id, pv), ()), o, 7) and not win(up_days_gpu.get((r.source_id, pv, r.series_id), ()), o, 7) for pv in prov_here)
    # (d) a provider lists this family+tier on the other collector at the origin but is not in this panel
    s["listed_elsewhere"] = len(listed.get((oth, fam, r.tier, o), set()) - prov_here) > 0
    s["thin_panel"] = s["fragility"] > 0.05
    sig.append(s)
S = pd.DataFrame([x for x in sig if x]).set_index("idx")
base = base.join(S)
pnl = base[base.n_offers.notna()].copy()
pnl["up5"] = pnl.r > 0.05
SIGS = ["calendar", "other_collector_up", "other_gpu_up", "listed_elsewhere", "thin_panel"]

# ---------- step 3: up-moves >5% ----------
up = base[base.r > 0.05]
out["up5"] = dict(cells=len(up), share_lv=float(up.baseline_loss.sum() / LV), **{f"{s}_share_of_own_loss": float(up[f"{s}_loss"].sum() / base[f"{s}_loss"].sum()) for s in SYS},
                  **{f"{s}_loss_over_lv": float(up[f"{s}_loss"].sum() / up.baseline_loss.sum()) for s in SYS},
                  by_cause_S3_share=(up.groupby("cause2").S3_loss.sum() / base.S3_loss.sum()).round(4).to_dict())
top = up.sort_values("S3_loss", ascending=False).head(40).copy()
top["S3_share_of_total"] = top.S3_loss / base.S3_loss.sum()


def move_day(sid, o, t, b):
    for k in range(1, (t - o).days + 1):
        d = o + pd.Timedelta(days=k)
        A = day_tab.get((sid, d))
        if A is not None and abs(np.median(A.p) - b) > 1e-9:
            return d
    return pd.NaT


top["move_day"] = [move_day(r.series_id, pd.Timestamp(r.origin_date), pd.Timestamp(r.origin_date) + pd.Timedelta(days=r.horizon_days), r.baseline) for r in top.itertuples()]
top["episode"] = top.provider.fillna("?") + "@" + top.source_id.str[:3] + " " + top.series_id.str.split(".").str[2] + " " + top.move_day.dt.strftime("%m-%d").fillna("?")
cols_top = ["series_id", "origin_date", "horizon_days", "cause2", "provider", "prov_entered", "prov_reprice_up", "n_offers", "baseline", "S3_q10", "S3_q50", "S3_q90", "y", "r",
            "S3_loss", "S3_share_of_total", "move_day", "episode"] + SIGS
top[cols_top].round(4).to_csv(f"{R}/top40_up5_S3.csv", index=False)
ep = top.groupby("episode").agg(cells=("S3_loss", "size"), S3_share=("S3_share_of_total", "sum"), cause=("cause2", "first"), r=("r", "max"),
                                **{s: (s, "mean") for s in SIGS}).sort_values("S3_share", ascending=False)
ep.round(4).to_csv(f"{R}/top40_episodes.csv")
print(ep.round(3).to_string())
# full episodes over all up5 cells (to know total share per episode)
upp = up.copy()
upp["md"] = [move_day(r.series_id, pd.Timestamp(r.origin_date), pd.Timestamp(r.origin_date) + pd.Timedelta(days=r.horizon_days), r.baseline) if r.source_id != "afhubbard" else pd.NaT for r in upp.itertuples()]
upp["episode"] = upp.provider.fillna("?") + "@" + upp.source_id.str[:3] + " " + upp.series_id.str.split(".").str[2] + " " + upp.md.dt.strftime("%m-%d").fillna("?")
out["top40_share_of_S3_loss"] = float(top.S3_share_of_total.sum())
out["up5_episodes_all"] = (upp.groupby("episode").S3_loss.sum() / base.S3_loss.sum()).sort_values(ascending=False).head(15).round(4).to_dict()

# signal hit / false-alarm rates on all panel cells
sr = {}
for s in SIGS:
    x = pnl[s].astype(bool)
    sr[s] = dict(fires=round(float(x.mean()), 3), hit_rate_up5=round(float(x[pnl.up5].mean()), 3), false_alarm_rate=round(float(x[~pnl.up5].mean()), 3),
                 precision=round(float(pnl.up5[x].mean()), 3) if x.any() else None, base_rate=round(float(pnl.up5.mean()), 3),
                 hit_rate_top40=round(float(top[s].astype(float).mean()), 3),
                 up5_S3_loss_share_flagged=round(float(pnl[x & pnl.up5].S3_loss.sum() / pnl[pnl.up5].S3_loss.sum()), 3))
    for c in ["entry", "unannounced_oneoff", "dynamic_reprice"]:
        g = pnl[pnl.up5 & (pnl.cause2 == c)]
        sr[s][f"hit_{c}"] = round(float(g[s].astype(bool).mean()), 3) if len(g) else None
out["signals"] = sr
print(pd.DataFrame(sr).T.to_string())

# ---------- step 4: calibration ----------
b3 = base
b3["below"] = b3.y < b3.S3_q10 - 1e-12; b3["above"] = b3.y > b3.S3_q90 + 1e-12
b3["moved"] = (b3.y - b3.baseline).abs() > 1e-9
out["calib_by_h"] = b3.groupby("horizon_days").agg(n=("y", "size"), below_q10=("below", "mean"), above_q90=("above", "mean"),
                                                  S3_loss_share=("S3_loss", lambda v: v.sum() / b3.S3_loss.sum())).round(3).to_dict("index")
out["calib_by_cause"] = b3.groupby("cause2").agg(n=("y", "size"), below_q10=("below", "mean"), above_q90=("above", "mean")).round(3).to_dict("index")
out["calib_by_cause_h7"] = b3[b3.horizon_days == 7].groupby("cause2").agg(n=("y", "size"), below_q10=("below", "mean"), above_q90=("above", "mean")).round(3).to_dict("index")
nm = b3[~b3.moved]
out["width_cost_no_move"] = {s: round(float(nm[f"{s}_loss"].sum() / b3[f"{s}_loss"].sum()), 4) for s in SYS}
out["width_cost_no_move_points_of_lv"] = {s: round(float(nm[f"{s}_loss"].sum() / LV), 4) for s in SYS}
out["width_cost_no_move_by_h_S3"] = (nm.groupby("horizon_days").S3_loss.sum() / b3.S3_loss.sum()).round(4).to_dict()
out["width_cost_no_move_by_class_S3"] = (nm.groupby("instrument_class").S3_loss.sum() / b3.S3_loss.sum()).round(4).to_dict()
out["S3_loss_side"] = dict(above_q90_share=round(float(b3[b3.above].S3_loss.sum() / b3.S3_loss.sum()), 3),
                           below_q10_share=round(float(b3[b3.below].S3_loss.sum() / b3.S3_loss.sum()), 3))
out["S3_skill_halves"] = {k: round(1 - g.S3_loss.sum() / g.baseline_loss.sum(), 4) for k, g in b3.groupby(b3.origin_day <= dt.date(2026, 9, 11).toordinal())}
base.drop(columns=["below", "above"]).to_parquet("runs/autopsy2/cells_labelled.parquet")
json.dump(out, open(f"{R}/summary.json", "w"), indent=1, default=str)
print(json.dumps({k: out[k] for k in ["S2_to_S3_drop_points_of_lv", "up5", "calib_by_h", "calib_by_cause_h7", "width_cost_no_move", "S3_loss_side", "late_announced_cells", "top40_share_of_S3_loss", "up5_episodes_all"]}, indent=1, default=str))
