"""Index-quality and economic-insight tables for the 37 headline rental series (slug `insight`).

Descriptive only: reads pack rows up to 2026-11-06, writes nothing any forecaster reads.
Run: OMP_NUM_THREADS=2 PYTHONPATH=src .venv/bin/python experiments/insight/analysis.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from gpuf import data, panel

OUT = Path(__file__).parent / "results"
OUT.mkdir(exist_ok=True)
D = lambda s: dt.date.fromisoformat(s).toordinal()
CUTOFF = D("2026-11-06")
DYN, STATIC = 0.15, 0.02
RNG = np.random.default_rng(0)
iso = lambda d: dt.date.fromordinal(int(d)).isoformat()

df = panel.load()
df = df[df.day <= CUTOFF].copy()

# ---------- per-offer daily changes and provider reprice rates ----------
df = df.sort_values(["src", "cls", "gpu", "tier", "key", "day"])
g = df.groupby(["src", "cls", "gpu", "tier", "key"])
df["pday"], df["pprice"] = g["day"].shift(1), g["price"].shift(1)
C = df[df.day - df.pday == 1].copy()
C["r"] = np.log(C.price / C.pprice)
C["ch"] = C.r != 0


def rate(src, prov, end=CUTOFF, w=21):
    x = C[(C.src == src) & (C.provider == prov) & (C.day <= end) & (C.day > end - w)]
    return (x.ch.mean() if len(x) else np.nan), len(x)


prov_full = C.groupby(["src", "provider"]).agg(offer_days=("ch", "size"), reprice_rate=("ch", "mean"),
                                               n_reprice=("ch", "sum"),
                                               up_share=("r", lambda x: (x[x != 0] > 0).mean() if (x != 0).any() else np.nan)).reset_index()
prov_full["rate21"] = [rate(s, p)[0] for s, p in zip(prov_full.src, prov_full.provider)]
prov_full["class"] = np.where(prov_full.reprice_rate < STATIC, "static",
                              np.where(prov_full.reprice_rate >= DYN, "dynamic", "intermediate"))
prov_full.to_csv(OUT / "t0_provider_reprice_rates.csv", index=False)
PCLASS = {(r.src, r.provider): r["class"] for _, r in prov_full.iterrows()}


# ---------- Q1: index quality card ----------
def card_stats(prices: np.ndarray, provs: np.ndarray):
    o = np.argsort(prices, kind="stable"); p, pv = prices[o], provs[o]
    n = len(p); m = np.median(p)
    lo, hi = (n - 1) // 2, n // 2
    frag = max(abs(np.median(np.delete(p, i)) / m - 1) for i in range(n)) if n > 1 else np.nan
    below = p[lo - 1] if lo - 1 >= 0 else np.nan
    above = p[hi + 1] if hi + 1 < n else np.nan
    gap = (above - below) / m
    q25, q75 = np.percentile(p, [25, 75])
    pfr = max((abs(np.median(p[pv != u]) / m - 1) for u in set(pv) if (pv != u).any()), default=np.nan)
    pt = {u: (np.median(np.where(pv == u, p * 1.1, p)) / m - 1) / 0.1 for u in set(pv)}  # share of a +10% provider repricing passed to the median
    top = max(pt, key=pt.get)
    return dict(n_offers=n, n_providers=len(set(pv)), median=m, mid_providers="|".join(sorted(set(pv[[lo, hi]]))),
                fragility_pct=100 * frag, provider_fragility_pct=100 * pfr, max_pass_through=pt[top], pass_through_provider=top,
                mid_provider_offer_share=max((pv == u).mean() for u in set(pv[[lo, hi]])), neighbour_gap_pct=100 * gap, iqr_spread_pct=100 * (q75 - q25) / m,
                p25=q25, p75=q75, min=p[0], max=p[-1])


head = data.universe("rental_headline")
rows = []
for sid in head:
    src = sid.split(".")[0]
    if not panel.supported(sid):
        continue
    o = panel.offers(sid, CUTOFF)
    last = o[o.day == CUTOFF]
    st = card_stats(last.price.values, last.provider.values)
    mids = st["mid_providers"].split("|")
    rates = [rate(src, p) for p in mids]
    st["mid_rate21"] = max(r[0] for r in rates if not np.isnan(r[0])) if any(not np.isnan(r[0]) for r in rates) else np.nan
    # history: share of days the median moved; fragility over the last 30 days
    med = o.groupby("day").price.median()
    med = med[med.index >= CUTOFF - 60]
    dd = med.index.to_series().diff() == 1
    mv = (np.log(med).diff()[dd] != 0)
    st["move_share_60d"] = mv.mean()
    fr = []
    for d, od in o[o.day > CUTOFF - 30].groupby("day"):
        fr.append(card_stats(od.price.values, od.provider.values)["fragility_pct"])
    st["fragility_30d_p10"], st["fragility_30d_p90"] = np.percentile(fr, [10, 90])
    rows.append(dict(series_id=sid, src=src, **st))

# afhubbard hyperscaler spot: hundreds of AZ rows, 1 to 3 snapshots a day
AF = panel.PACK / "rental_observations" / "source_id=afhubbard"
af_models = {s: panel.parse_sid(s)[2] for s in head if s.startswith("afhubbard")}
q = f"""select cast(dt as date) d, gpu_model, provider, coalesce(region_raw,'')||'|'||coalesce(sku_raw,'')||'|'||coalesce(cast(gpu_count as varchar),'') k,
               usd_per_gpu_hour price
        from read_parquet('{AF}/*/*.parquet', hive_partitioning=false)
        where instrument_class='hyperscaler_spot' and pricing_tier='spot' and usd_per_gpu_hour is not null
          and cast(dt as date) between date '2026-10-15' and date '2026-11-06'
          and gpu_model in ({",".join("'" + m + "'" for m in af_models.values())})"""
A = duckdb.sql(q).df()
A["day"] = pd.to_datetime(A.d).map(lambda x: x.toordinal())
for sid, gm in af_models.items():
    a = A[A.gpu_model == gm]
    last = a[a.day == CUTOFF]
    st = card_stats(last.price.values, last.provider.values)
    daily = a.groupby(["provider", "k", "day"]).price.median().reset_index().sort_values(["provider", "k", "day"])
    daily["pd"], daily["pp"] = daily.groupby(["provider", "k"]).day.shift(1), daily.groupby(["provider", "k"]).price.shift(1)
    dc = daily[(daily.day - daily.pd == 1) & (daily.day > CUTOFF - 21)]
    mids = st["mid_providers"].split("|")
    st["mid_rate21"] = (dc[dc.provider.isin(mids)].price != dc[dc.provider.isin(mids)].pp).mean()
    med = a.groupby("day").price.median()
    st["move_share_60d"] = (np.log(med).diff().dropna() != 0).mean()
    st["fragility_30d_p10"] = st["fragility_30d_p90"] = np.nan
    rows.append(dict(series_id=sid, src="afhubbard", **st))

card = pd.DataFrame(rows)
card["mid_dynamic"] = card.mid_rate21 >= DYN
card["mid_class"] = np.where(card.mid_rate21 >= DYN, "dynamic", np.where(card.mid_rate21 < STATIC, "static", "intermediate"))
# robustness: a membership change moves the median by up to `fragility`; a dynamic middle moves it most days.
card["worst_removal_pct"] = card[["fragility_pct", "provider_fragility_pct"]].max(axis=1)
card["do_not_use_alone"] = (card.worst_removal_pct > 5) | (card.max_pass_through >= 0.75) | (card.n_providers < 5) | card.mid_dynamic
card["risk_score"] = card.worst_removal_pct + card.neighbour_gap_pct / 2 + 10 * card.max_pass_through + 10 * card.mid_dynamic + np.where(card.n_providers < 5, 5, 0)
card = card.sort_values("risk_score").reset_index(drop=True)
card.index += 1
card.index.name = "rank_most_robust"
card.to_csv(OUT / "t1_index_quality_card.csv")

# ---------- Q2: common versus idiosyncratic movement, GPUs on both collectors ----------
fg = {s for s in head if s.startswith("fastgpu_daily")}
gr = {s for s in head if s.startswith("gpurentalprices")}
pairs = [(f, "gpurentalprices" + f[len("fastgpu_daily"):]) for f in sorted(fg) if "gpurentalprices" + f[len("fastgpu_daily"):] in gr]
pairs.append(("fastgpu_daily.neocloud_rate_card.A100_80GB.on_demand.median", "gpurentalprices.neocloud_rate_card.A100_SXM_80GB.on_demand.median"))
pairs.append(("fastgpu_daily.neocloud_rate_card.H100_SXM_80GB.on_demand.median", "gpurentalprices.neocloud_rate_card.H100_80GB.on_demand.median"))
START2 = D("2026-09-08")


def indices(sid):
    """Daily log-level paths from START2 to CUTOFF: raw median and three panel-robust alternatives."""
    src = sid.split(".")[0]
    o = panel.offers(sid, CUTOFF)
    o = o[o.day >= START2]
    o = o.assign(cl=[PCLASS.get((src, p), "static") for p in o.provider])
    days = np.arange(START2, CUTOFF + 1)
    W = o.pivot_table(index="day", columns="key", values="price").reindex(days)
    prov_of = o.drop_duplicates("key").set_index("key").provider
    static_keys = [k for k in W.columns if PCLASS.get((src, prov_of[k]), "static") == "static"]
    raw = np.log(W.median(axis=1))
    bal, rep, stat, smean = [0.0], [0.0], [0.0], [0.0]
    for i in range(1, len(days)):
        a, b = W.iloc[i - 1], W.iloc[i]
        both = a.notna() & b.notna()
        bal.append(bal[-1] + (np.log(b[both].median() / a[both].median()) if both.any() else 0.0))
        rep.append(rep[-1] + (np.log(b[both] / a[both]).median() if both.any() else 0.0))
        sb = both & W.columns.isin(static_keys)
        stat.append(stat[-1] + (np.log(b[sb].median() / a[sb].median()) if sb.any() else 0.0))
        smean.append(smean[-1] + (np.log(b[sb] / a[sb]).mean() if sb.any() else 0.0))
    raw = raw.ffill().bfill()
    raw = raw - raw.iloc[0]
    return pd.DataFrame({"median": raw.values, "balanced_median": bal, "median_offer_change": rep, "static_balanced": stat, "static_mean": smean}, index=days)


Q2rows, Q2paths = [], {}
for f, gsid in pairs:
    P = {c: indices(s) for c, s in (("fastgpu", f), ("gpurentalprices", gsid))}
    Q2paths[(f, gsid)] = P
    for stat in P["fastgpu"].columns:
        a, b = P["fastgpu"][stat], P["gpurentalprices"][stat]
        j7 = pd.concat([a.diff(7), b.diff(7)], axis=1).dropna(); a7, b7 = j7.iloc[:, 0], j7.iloc[:, 1]
        a1, b1 = a.diff().dropna(), b.diff().dropna()
        Q2rows.append(dict(pair=f.split(".")[2] + "~" + gsid.split(".")[2], stat=stat,
                           move_days_fg=(a1 != 0).mean(), move_days_gr=(b1 != 0).mean(),
                           abs_daily_fg=a1.abs().mean(), abs_daily_gr=b1.abs().mean(),
                           total_fg=a.iloc[-1], total_gr=b.iloc[-1], total_gap=abs(a.iloc[-1] - b.iloc[-1]),
                           mad7_gap=(a7 - b7).abs().mean(),
                           corr7=np.corrcoef(a7, b7)[0, 1] if a7.std() > 0 and b7.std() > 0 else np.nan))
Q2 = pd.DataFrame(Q2rows)
Q2.to_csv(OUT / "t2_cross_collector.csv", index=False)
# week-block bootstrap of the pooled 7-day disagreement, robust minus raw (paired)
weeks = np.arange(START2 + 7, CUTOFF + 1)
wk = (weeks - weeks[0]) // 7
gaps = {}
for stat in ["median", "balanced_median", "median_offer_change", "static_balanced", "static_mean"]:
    M = []
    for k, P in Q2paths.items():
        M.append((P["fastgpu"][stat].diff(7) - P["gpurentalprices"][stat].diff(7)).reindex(weeks).abs().values)
    gaps[stat] = np.array(M)  # pairs x days
boot = {}
for stat in gaps:
    if stat == "median":
        continue
    diff = gaps[stat] - gaps["median"]
    ests = []
    for _ in range(2000):
        ws = RNG.choice(np.unique(wk), len(np.unique(wk)))
        idx = np.concatenate([np.where(wk == w)[0] for w in ws])
        ests.append(np.nanmean(diff[:, idx]))
    boot[stat] = dict(raw=float(np.nanmean(gaps["median"])), robust=float(np.nanmean(gaps[stat])),
                      diff=float(np.nanmean(diff)), ci90=[float(np.percentile(ests, 5)), float(np.percentile(ests, 95))])
Q2sum = Q2.groupby("stat")[["move_days_fg", "move_days_gr", "abs_daily_fg", "abs_daily_gr", "total_gap", "mad7_gap", "corr7"]].mean()
Q2sum.to_csv(OUT / "t2b_cross_collector_summary.csv")

# ---------- Q3: static rate-card providers, level and steps ----------
def family(g):
    if g.startswith("H100"): return "H100"
    if g.startswith("A100") and "40" in g: return "A100 40GB"
    if g.startswith("A100"): return "A100 80GB"
    if g in ("H200", "B200", "B300"): return g
    return None


R = df[(df.tier == "on_demand") & df.cls.isin(["neocloud_rate_card", "hyperscaler_list"])].copy()
R["fam"] = R.gpu.map(family)
R = R[R.fam.notna()]
R["pclass"] = [PCLASS.get((s, p), "static") for s, p in zip(R.src, R.provider)]
cal = [json.loads(l) for l in open("data_out/repricing_calendar.jsonl")]
calmap = {}
for c in cal:
    for ch in c["changes"]:
        for pg in ch.get("panel_gpus", []):
            fm = family(pg)
            if fm:
                calmap.setdefault((c["provider"], fm), []).append(c)
Cs = C[(C.tier == "on_demand") & C.cls.isin(["neocloud_rate_card", "hyperscaler_list"])].copy()
Cs["fam"] = Cs.gpu.map(family)
Cs = Cs[Cs.fam.notna()]
Cs["pclass"] = [PCLASS.get((s, p), "static") for s, p in zip(Cs.src, Cs.provider)]
steps = Cs[(Cs.pclass != "dynamic") & (Cs.r.abs() >= 0.03)]
steps = steps.groupby(["src", "provider", "fam", "day"]).agg(n_offers=("r", "size"), med_step=("r", "median")).reset_index()


def link(r):
    for c in calmap.get((r.provider, r.fam), []):
        if abs(D(c["effective_date"]) - r.day) <= 2:
            return f'{c["provider"]} {c["effective_date"]} (published {c["published"]}, lead {c["lead_days"]} d)'
    return ""


steps["calendar"] = steps.apply(link, axis=1)
steps["date"] = steps.day.map(iso)
steps["pct"] = 100 * (np.exp(steps.med_step) - 1)
steps.drop(columns="day").to_csv(OUT / "t3a_static_steps.csv", index=False)


def breadth(src, start, end):
    """Per (family): static providers present on both dates, and how many net up/down/flat."""
    x = R[(R.src == src) & (R.pclass == "static")]
    a = x[x.day == start].groupby(["fam", "provider"]).price.median()
    b = x[x.day == end].groupby(["fam", "provider"]).price.median()
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    j["r"] = np.log(j.b / j.a)
    out = j.groupby(level=0).agg(n_static=("r", "size"), n_up=("r", lambda v: (v > 0.005).sum()),
                                 n_down=("r", lambda v: (v < -0.005).sum()), median_change_pct=("r", lambda v: 100 * (np.exp(v.median()) - 1)),
                                 mean_change_pct=("r", lambda v: 100 * (np.exp(v.mean()) - 1)))
    up = j[j.r > 0.005].reset_index().groupby("fam").provider.agg(lambda v: ",".join(sorted(v)))
    out["who_up"] = up
    # headline-style medians over all offers on the two dates, and the dynamic providers' path
    allx = R[R.src == src]
    for lab, cond in (("all_offer_median_change_pct", None), ("dynamic_change_pct", "dynamic")):
        y = allx if cond is None else allx[allx.pclass == cond]
        ma = y[y.day == start].groupby("fam").price.median(); mb = y[y.day == end].groupby("fam").price.median()
        out[lab] = 100 * (mb / ma - 1)
    out["src"], out["start"], out["end"] = src, iso(start), iso(end)
    return out.reset_index()


B3 = pd.concat([breadth("gpurentalprices", D("2026-08-04"), CUTOFF), breadth("fastgpu_daily", D("2026-09-08"), CUTOFF)])
B3.to_csv(OUT / "t3b_static_breadth.csv", index=False)

# equal-weight static provider index per family (chained balanced provider medians), plus dynamic and all-offer medians
paths3 = {}
for src, start in (("gpurentalprices", D("2026-08-04")), ("fastgpu_daily", D("2026-09-08"))):
    for fam in ["H100", "A100 80GB", "H200", "B200", "B300"]:
        x = R[(R.src == src) & (R.fam == fam)]
        days = np.arange(start, CUTOFF + 1)
        PV = x[x.pclass == "static"].groupby(["day", "provider"]).price.median().unstack().reindex(days)
        idx = [0.0]
        for i in range(1, len(days)):
            a, b = PV.iloc[i - 1], PV.iloc[i]; both = a.notna() & b.notna()
            idx.append(idx[-1] + (np.log(b[both] / a[both]).mean() if both.any() else 0.0))
        allm = np.log(x.groupby("day").price.median().reindex(days))
        dyn = np.log(x[x.pclass == "dynamic"].groupby("day").price.median().reindex(days))
        paths3[(src, fam)] = pd.DataFrame({"static_index": idx, "all_offer_median": allm - allm.dropna().iloc[0],
                                            "dynamic": dyn - (dyn.dropna().iloc[0] if dyn.notna().any() else 0)}, index=days)

# ---------- Q4: announcements and horizon ----------
big = steps[(steps.src == "gpurentalprices") | (steps.src == "fastgpu_daily")]
big = big[big.med_step.abs() >= np.log(1.10)]
ev = big.drop_duplicates(["provider", "fam", "date"])
ev_pf = ev.groupby(["provider", "day"]).agg(fams=("fam", lambda v: ",".join(sorted(set(v)))), calendar=("calendar", "max"),
                                            pct=("pct", "median")).reset_index()
ev_pf["date"] = ev_pf.day.map(iso)
ev_pf["announced_ahead"] = ev_pf.calendar.str.contains("lead") & ~ev_pf.calendar.str.contains("lead -") & ~ev_pf.calendar.str.contains("lead 0 ")
ev_pf.to_csv(OUT / "t4a_large_static_steps.csv", index=False)
ann = [c for c in cal if any(family(pg) for ch in c["changes"] for pg in ch.get("panel_gpus", []))]
T4 = pd.DataFrame([dict(provider=c["provider"], effective=c["effective_date"], published=c["published"], lead_days=c["lead_days"],
                        ahead=c["announced_before_effective"], confidence=c["confidence"],
                        changes="; ".join(f'{ch["gpu"]} {ch.get("old")}->{ch.get("new")}' for ch in c["changes"] if family(ch["gpu"].split(" (")[0]) or "H100" in ch["gpu"]))
                   for c in ann])
T4.to_csv(OUT / "t4b_calendar_gpu_entries.csv", index=False)

# Lambda 16 Nov: recompute every headline median with Lambda's announced rates on the 6 Nov panel
lam = {"B200": (6.69, 7.69), "H100": (3.99, 4.59), "A100 80GB": (2.79, 3.19), "A100 40GB": (1.99, 1.99)}
L = []
for sid in head:
    if not panel.supported(sid):
        continue
    o = panel.offers(sid, CUTOFF); last = o[o.day == CUTOFF].copy()
    fam = family(panel.parse_sid(sid)[2])
    isl = last.provider.str.contains("lambda")
    if not isl.any() or fam not in lam:
        continue
    old, new = lam[fam]
    prev = o[o.day == CUTOFF - 1].set_index("key").price
    pending = isl & last.key.map(prev).eq(last.price)  # not yet showing the new rate on 6 Nov
    p2 = last.price.where(~pending, last.price * new / old)
    m5 = prev.median()
    L.append(dict(series_id=sid, n_offers=len(last), lambda_offers=int(isl.sum()), lambda_pending=int(pending.sum()),
                  lambda_price_now=last.price[isl].round(3).tolist(), median_5nov=m5, median_6nov=last.price.median(),
                  change_5_to_6nov_pct=100 * (last.price.median() / m5 - 1),
                  median_if_pending_applied=p2.median(), change_if_applied_pct=100 * (p2.median() / last.price.median() - 1)))
T4c = pd.DataFrame(L)
T4c.to_csv(OUT / "t4c_lambda_nov16_counterfactual.csv", index=False)

# ---------- Q5: dispersion across providers ----------
UNITS = {"A100 80GB": 1.0, "A100 40GB": np.nan, "H100": 2.46, "H200": 2.72, "B200": 7.91, "B300": 8.77}
X = R.copy()
X["week"] = (X.day - D("2026-08-03")) // 7
PP = X.groupby(["src", "fam", "week", "provider"]).price.median().reset_index()  # one vote per provider per week
def disp(v):
    v = np.sort(v.values)
    q25, q75 = np.percentile(v, [25, 75])
    return pd.Series(dict(n_prov=len(v), p75_p25=q75 / q25, max_min=v[-1] / v[0]))
D5 = PP.groupby(["src", "fam", "week"]).price.apply(disp).unstack().reset_index()
D5["week_start"] = (D("2026-08-03") + 7 * D5.week).map(iso)
D5.to_csv(OUT / "t5a_dispersion_weekly.csv", index=False)
last4 = PP[PP.week >= PP.week.max() - 3].groupby(["src", "fam", "provider"]).price.median().reset_index()
D5b = last4.groupby(["src", "fam"]).price.apply(disp).unstack()
# bootstrap over providers for p75/p25
ci = {}
for (s, f), v in last4.groupby(["src", "fam"]).price:
    v = v.values
    bs = [np.percentile(b := RNG.choice(v, len(v)), 75) / np.percentile(b, 25) for _ in range(2000)]
    ci[(s, f)] = (np.percentile(bs, 5), np.percentile(bs, 95))
D5b["p75_p25_ci90"] = [f"{ci[k][0]:.2f}-{ci[k][1]:.2f}" for k in D5b.index]
# per-unit overlap: share of (old-chip provider, B200 provider) pairs where the old chip is cheaper per unit of work
ov = []
for s in ("gpurentalprices", "fastgpu_daily"):
    b2 = last4[(last4.src == s) & (last4.fam == "B200")].price.values / UNITS["B200"]
    for f in ("A100 80GB", "H100", "H200"):
        v = last4[(last4.src == s) & (last4.fam == f)].price.values / UNITS[f]
        if len(v) and len(b2):
            ov.append(dict(src=s, fam=f, n_old=len(v), n_b200=len(b2), share_pairs_old_cheaper_per_unit=(v[:, None] < b2[None, :]).mean(),
                           cheapest_old_over_median_b200=v.min() / np.median(b2), median_ratio=np.median(v) / np.median(b2)))
D5c = pd.DataFrame(ov)
D5b.to_csv(OUT / "t5b_dispersion_last4w.csv")
D5c.to_csv(OUT / "t5c_per_unit_overlap.csv", index=False)

pd.to_pickle(last4, Path("runs/insight/last4.pkl"))
pd.to_pickle(dict(paths3=paths3, Q2paths=Q2paths, boot=boot), Path("runs/insight/paths.pkl"))
json.dump(dict(boot=boot), open(OUT / "summary.json", "w"), indent=1)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 60)
print(card[["series_id", "n_offers", "n_providers", "mid_providers", "mid_rate21", "fragility_pct", "provider_fragility_pct", "max_pass_through", "pass_through_provider", "neighbour_gap_pct", "iqr_spread_pct", "move_share_60d", "do_not_use_alone"]].round(3).to_string())
print(Q2sum.round(4).to_string()); print(json.dumps(boot, indent=1))
print(Q2[Q2.stat == "median"].round(3).to_string()); print(Q2[Q2.stat == "static_balanced"].round(3).to_string()); print(Q2[Q2.stat == "static_mean"].round(3).to_string())
print(B3.round(2).to_string())
print(steps.drop(columns="day").round(3).to_string())
print(ev_pf.to_string()); print(T4.to_string()); print(T4c.round(3).to_string())
print(D5b.round(2).to_string()); print(D5c.round(3).to_string())
print(prov_full.sort_values("n_reprice", ascending=False).head(15).round(3).to_string())
