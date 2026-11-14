"""Step 3-5: shares by cause, persistence, offer hazards, reachability, blend-miss attribution (dev rows <= 2026-10-13)."""
import json, numpy as np, pandas as pd
import panel_load as pl, decomp as D

R = "experiments/autopsy/results"
rng = np.random.default_rng(0)
panel = pd.read_parquet("runs/autopsy/panel.parquet")
assert panel.dt.max() <= pd.Timestamp(pl.CUT)
tabs = D.day_tables(panel)
ev = pd.read_parquet(f"{R}/events_dev.parquet")
blend = pd.read_parquet("runs/failure/blend_dev_cells.parquet")
blend["o"] = pd.to_datetime(blend.origin_date)
blend["t"] = blend.o + pd.to_timedelta(blend.horizon_days, unit="D")
assert blend.t.max() <= pd.Timestamp(pl.CUT)
out = {}
WIN = pd.Timestamp("2026-08-04")  # common window start for afhubbard comparability
evw = ev[ev.date_b >= WIN].copy()


def med(sid, d):
    t = tabs[sid].get(d)
    return None if t is None else float(np.median(t.p))


# ---------- h-day decomposition of every blend cell ----------
cells = []
for r in blend.itertuples():
    A, B = tabs[r.series_id].get(r.o), tabs[r.series_id].get(r.t)
    if A is None or B is None:
        cells.append(dict(idx=r.Index, cause="no_panel"))
        continue
    d = D.decompose(A, B) if abs(np.median(A.p) - np.median(B.p)) > 1e-9 else dict(cause="none", dlog=0.0, rep=0.0, comp=0.0)
    d["idx"] = r.Index
    # reachability: nearest distinct order statistics / midpoints of origin panel around its median
    if d["cause"] != "none":
        x = np.unique(A.p.round(6))
        m, y = float(np.median(A.p)), float(np.median(B.p))
        lo, hi = x[x < m - 1e-9][::-1], x[x > m + 1e-9]
        for k in (1, 2, 3):
            os_ = np.r_[lo[:k], hi[:k]]
            win = np.r_[lo[:k][::-1], m, hi[:k]]
            mids = (win[:-1] + win[1:]) / 2
            tol = max(0.005, 1e-4 * m)
            d[f"reach_os_k{k}"] = bool(np.any(np.abs(os_ - y) <= tol))
            d[f"reach_osmid_k{k}"] = bool(np.any(np.abs(np.r_[os_, mids] - y) <= tol))
            d[f"reach_any_value"] = bool(np.any(np.abs(x - y) <= tol))
    cells.append(d)
cells = pd.DataFrame(cells).set_index("idx")
cb = blend.join(cells.drop(columns=[c for c in cells.columns if c in blend.columns], errors="ignore"))
cb["lv_abs_err"] = (cb.y - cb.baseline).abs()
cb.drop(columns=["o", "t"]).to_parquet(f"{R}/hday_cells_dev.parquet")
out["origin_median_matches_baseline"] = float(np.mean([abs(med(r.series_id, r.o) - r.baseline) < 0.0051 for r in blend.itertuples() if med(r.series_id, r.o) is not None]))

# ---------- shares by cause, collector, class ----------
def shares(df, by):
    g = df.groupby(by)
    return pd.DataFrame({"n": g.size(), "share_changes": g.size() / len(df), "share_abs_dlog": g.abs_dlog.sum() / df.abs_dlog.sum()}).round(3)

sh = {"all": shares(evw, "cause"), "by_source": shares(evw, ["source_id", "cause"]), "by_class": shares(evw, ["instrument_class", "cause"])}
out["event_shares_since_0804"] = {k: v.reset_index().to_dict("records") for k, v in sh.items()}
lv = {}
for h, g in cb[cb.cause != "no_panel"].groupby("horizon_days"):
    tot = g.lv_abs_err.sum()
    lv[int(h)] = {"all": (g.groupby("cause").lv_abs_err.sum() / tot).round(3).to_dict(),
                  "by_source": (g.groupby(["source_id", "cause"]).lv_abs_err.sum() / tot).round(3).reset_index().to_dict("records"),
                  "by_class": (g.groupby(["instrument_class", "cause"]).lv_abs_err.sum() / tot).round(3).reset_index().to_dict("records"),
                  "n_cells": g.groupby("cause").size().to_dict()}
out["last_value_abs_error_share"] = lv

# ---------- persistence: next h-day change on the jump ----------
def boot_slope(x, y, wk, B=2000):
    X = np.c_[np.ones_like(x), x]
    b = np.linalg.lstsq(X, y, rcond=None)[0][1]
    uw = np.unique(wk)
    bs = []
    for _ in range(B):
        s = rng.choice(uw, len(uw))
        ii = np.concatenate([np.flatnonzero(wk == w) for w in s])
        if len(ii) < 3 or np.ptp(x[ii]) == 0:
            continue
        bs.append(np.linalg.lstsq(X[ii], y[ii], rcond=None)[0][1])
    return round(float(b), 3), [round(float(v), 3) for v in np.quantile(bs, [0.05, 0.95])]

pers = []
for e in evw.itertuples():
    for h in (1, 3, 7):
        mb, mh = med(e.series_id, e.date_b), med(e.series_id, e.date_b + pd.Timedelta(days=h))
        if mh is not None:
            pers.append(dict(cause=e.cause, source_id=e.source_id, h=h, jump=e.dlog, fwd=np.log(mh / mb),
                             wk=str(e.date_b.to_period("W")), big=abs(e.dlog) > 0.05))
pers = pd.DataFrame(pers)
res = {}
for (c, h), g in pers.groupby(["cause", "h"]):
    s, ci = boot_slope(g.jump.values, g.fwd.values, g.wk.values)
    res[f"{c}_h{h}"] = dict(n=len(g), slope=s, ci90=ci,
                            share_fully_reverted=round(float((np.abs(g.fwd + g.jump) < 1e-6).mean()), 3))
for (src, h), g in pers[pers.cause == "repricing"].groupby(["source_id", "h"]):
    s, ci = boot_slope(g.jump.values, g.fwd.values, g.wk.values, 1000)
    res[f"repricing_{src}_h{h}"] = dict(n=len(g), slope=s, ci90=ci)
out["persistence_slope_fwd_on_jump"] = res

# ---------- offer-level hazards (per offer per observed day pair; afhubbard: daily mean price per offer) ----------
po = panel[panel.dt >= WIN].groupby(["source_id", "series_id", "offer", "provider", "dt"]).usd_per_gpu_hour.mean().rename("p").reset_index()
po = po.sort_values(["series_id", "offer", "dt"])
days_by_sid = {s: sorted(g.dt.unique()) for s, g in po.groupby("series_id")}
nxt = {s: dict(zip(d[:-1], d[1:])) for s, d in days_by_sid.items()}
po["dt_next"] = [nxt[s].get(d) for s, d in zip(po.series_id, po.dt)]
po = po[po.dt_next.notna()]
key = po.set_index(["series_id", "offer", "dt"]).p
look = po[["series_id", "offer", "dt_next"]].apply(tuple, axis=1)
pnext = key.reindex(pd.MultiIndex.from_tuples(look.tolist())).values
po["exit"] = np.isnan(pnext)
po["reprice"] = ~po.exit & (np.abs(pnext - po.p.values) > 1e-9)
po["reprice_up"] = po.reprice & (pnext > po.p.values)
haz = {}
for src, g in po.groupby("source_id"):
    pv = g.groupby("provider").agg(n=("reprice", "size"), r=("reprice", "sum"), x=("exit", "sum"))
    p0 = g.reprice.mean()
    # dispersion across providers: chi2/df of reprice counts vs a common rate
    chi = (((pv.r - pv.n * p0) ** 2) / (pv.n * p0 * (1 - p0) + 1e-12)).sum() / max(len(pv) - 1, 1)
    dd = g.groupby("dt").agg(n=("reprice", "size"), r=("reprice", "sum"))
    chid = (((dd.r - dd.n * p0) ** 2) / (dd.n * p0 * (1 - p0) + 1e-12)).sum() / max(len(dd) - 1, 1)
    # provider-day clustering: given a provider repriced one offer that day, chance it repriced another of its offers
    pdd = g.groupby(["provider", "dt"]).agg(n=("reprice", "size"), r=("reprice", "sum"))
    multi = pdd[(pdd.n >= 2) & (pdd.r >= 1)]
    top = (pv.r / pv.r.sum()).sort_values(ascending=False).head(5)
    haz[src] = dict(offer_days=len(g), p_reprice=round(p0, 4), p_reprice_up_share=round(g.reprice_up.sum() / max(g.reprice.sum(), 1), 3),
                    p_exit=round(g.exit.mean(), 4), dispersion_by_provider=round(chi, 2), dispersion_by_day=round(chid, 2),
                    p_other_offer_repriced_given_one=round(float(((multi.r - 1) / (multi.n - 1)).mean()) if len(multi) else float("nan"), 3),
                    top5_provider_share_of_reprices=top.round(3).to_dict(),
                    top5_share_of_offer_days=(pv.n[top.index] / pv.n.sum()).round(3).to_dict())
out["offer_hazards_since_0804"] = haz

# ---------- exits: return within 1, 3, 7 days at the same price ----------
ex = po[po.exit]
ret = []
for r in ex.itertuples():
    for h in (1, 3, 7):
        hit_same = hit_any = False
        for k in range(1, h + 1):
            d = r.dt_next + pd.Timedelta(days=k)
            v = key.get((r.series_id, r.offer, d))
            if v is not None and not np.isnan(v):
                hit_any = True
                hit_same = abs(v - r.p) < 1e-9
                break
        ret.append(dict(source_id=r.source_id, h=h, ret_any=hit_any, ret_same=hit_same))
ret = pd.DataFrame(ret)
out["exit_return"] = {f"{s}_h{h}": dict(n=len(g), returned=round(g.ret_any.mean(), 3), returned_same_price=round(g.ret_same.mean(), 3))
                      for (s, h), g in ret.groupby(["source_id", "h"])}

# ---------- reachability ----------
rc = cb[cb.cause.isin(["repricing", "composition", "mixed"])]
reach = {}
for (h, c), g in rc.groupby(["horizon_days", "cause"]):
    reach[f"h{h}_{c}"] = dict(n=len(g), **{k: round(float(g[k].mean()), 3) for k in g.columns if k.startswith("reach_")})
for h, g in rc.groupby("horizon_days"):
    reach[f"h{h}_all"] = dict(n=len(g), loss_weighted_osmid_k2=round(float((g.reach_osmid_k2 * g.lv_abs_err).sum() / g.lv_abs_err.sum()), 3),
                              **{k: round(float(g[k].mean()), 3) for k in g.columns if k.startswith("reach_")})
    for s, gs in g.groupby("source_id"):
        reach[f"h{h}_{s}"] = dict(n=len(gs), **{k: round(float(gs[k].mean()), 3) for k in ("reach_os_k1", "reach_osmid_k2", "reach_osmid_k3", "reach_any_value")})
out["reachability"] = reach

# ---------- blend misses ----------
cbv = cb[cb.cause != "no_panel"].copy()
cbv["miss"] = (cbv.y < cbv.q10) | (cbv.y > cbv.q90)
cbv["miss_side"] = np.where(cbv.y > cbv.q90, "above", np.where(cbv.y < cbv.q10, "below", "in"))
thr = cbv.loss.quantile(0.9)
cbv["top10"] = cbv.loss >= thr
tot = cbv.loss.sum()
bm = {"n_cells": len(cbv), "blend_loss_share_by_cause_all_cells": (cbv.groupby("cause").loss.sum() / tot).round(3).to_dict(),
      "n_by_cause_all_cells": cbv.groupby("cause").size().to_dict()}
for name, m in (("outside_q10_q90", cbv.miss), ("top10pct_loss", cbv.top10)):
    g = cbv[m]
    bm[name] = dict(n=int(m.sum()), share_of_total_blend_loss=round(g.loss.sum() / tot, 3),
                    n_by_cause=g.groupby("cause").size().to_dict(),
                    loss_share_of_total_by_cause=(g.groupby("cause").loss.sum() / tot).round(3).to_dict(),
                    by_h_cause=(g.groupby(["horizon_days", "cause"]).loss.sum() / tot).round(3).rename(lambda x: str(x)).to_dict(),
                    by_side_cause=(g.groupby(["miss_side", "cause"]).loss.sum() / tot).round(3).rename(lambda x: str(x)).to_dict())
bm["top_series_by_cause_loss"] = {c: (g.groupby("series_id").loss.sum() / tot).sort_values(ascending=False).head(4).round(3).to_dict()
                                  for c, g in cbv[cbv.top10].groupby("cause")}
out["blend_misses"] = bm
cbv.drop(columns=["o", "t"]).to_parquet("runs/autopsy/blend_cells_attrib.parquet")
def clean(o):
    if isinstance(o, dict):
        return {("|".join(map(str, k)) if isinstance(k, tuple) else str(k)): clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    return o


out = clean(out)
json.dump(out, open(f"{R}/step3_summary.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str))
