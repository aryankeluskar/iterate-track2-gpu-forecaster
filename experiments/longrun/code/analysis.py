"""Long-run view of H100 / A100 rental and resale. Steps 1-5 of experiments/longrun/protocol.yaml.

Run: PYTHONPATH=src .venv/bin/python experiments/longrun/code/aws.py && .venv/bin/python experiments/longrun/code/analysis.py
Instruments are kept apart: aggregator_median (GetDeploying, by pricing_mode), daily_statistics (source x class x tier),
hyperscaler_spot (AWS, segments A and B either side of the 2026-03..06 hole, never bridged)."""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
PACK = ROOT / "data/pack/gpu-price-pack-v0.1.1-handover"
RUNS = ROOT / "runs/longrun"
RES = ROOT / "experiments/longrun/results"
RES.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20261114)
NB = 1000
CHIPS = ["A100", "H100", "H200", "B200", "B300"]
AGG_NAME = {c: f"NVIDIA {c}" for c in CHIPS}
DS_NAME = {"A100": ["A100 SXM 80GB", "A100 80GB"], "H100": ["H100 SXM 80GB", "H100 80GB"], "H200": ["H200"], "B200": ["B200"], "B300": ["B300"]}
UNIT_SETS = {"xbench": "ship_only_inf_cross_benchmark_median_a100ref_sxm80", "llm_offline": "ship_only_inf_llm_offline_a100ref_sxm80",
             "llm_server": "ship_only_inf_llm_server_a100ref_sxm80", "spec_fp16": "spec_fp16_bf16_tensor_flops"}
TDP = {"A100": 400, "H100": 700, "H200": 700, "B200": 1000, "B300": 1100}
AGG_MODES = ["on_demand", "spot", "reserved_12m", "reserved_36m"]
AWS_CHIP = {"p4d.24xlarge": "A100 40GB", "p4de.24xlarge": "A100 80GB", "p5.48xlarge": "H100", "p5e.48xlarge": "H200", "p5en.48xlarge": "H200",
            "p6-b200.48xlarge": "B200", "p6-b300.48xlarge": "B300"}
EVENTS = {"Epoch H200/B200 release (2024-11-15/18)": "2024-11-18", "Epoch B300 release": "2025-08-22",
          "AWS p5en (H200) first tick": "2024-12-12", "AWS p5e (H200) first tick": "2025-04-30",
          "AWS p6-b200 first tick": "2025-07-24", "AWS p6-b300 first tick": "2025-11-20"}
SEG_A_END = pd.Timestamp("2026-02-28")
out: dict = {}


def units() -> pd.DataFrame:
    u = pd.read_csv(PACK / "capability/capability_units.csv")
    rows = {k: u[u.benchmark_set_id == v].set_index("gpu_generation").capability_units_per_accelerator for k, v in UNIT_SETS.items()}
    return pd.DataFrame(rows).loc[CHIPS]


def fe_slope(df: pd.DataFrame, t="t", y="y", g="g") -> float:
    """Slope of y on t with group fixed effects (within estimator)."""
    d = df[[t, y, g]].copy()
    d[t] = d[t] - d.groupby(g)[t].transform("mean")
    d[y] = d[y] - d.groupby(g)[y].transform("mean")
    den = (d[t] ** 2).sum()
    return float((d[t] * d[y]).sum() / den) if den > 0 else np.nan


def block_boot(df: pd.DataFrame, block: int, stat, tcol="w") -> np.ndarray:
    """Moving-block pairs bootstrap over the distinct values of tcol (weeks); keeps every row of a resampled week."""
    ws = np.sort(df[tcol].unique())
    n = len(ws)
    if n < block + 2:
        return np.array([np.nan])
    by = {w: g for w, g in df.groupby(tcol)}
    res = []
    for _ in range(NB):
        starts = RNG.integers(0, n - block + 1, size=int(np.ceil(n / block)))
        pick = np.concatenate([ws[s:s + block] for s in starts])[:n]
        res.append(stat(pd.concat([by[w] for w in pick])))
    return np.array(res)


def ann(b_per_week: float) -> float:
    return float(np.exp(b_per_week * 52.18) - 1)


# ---------------------------------------------------------------- data
agg = pd.read_csv(PACK / "aggregator_medians.csv", parse_dates=["week_start"])
agg = agg[agg.gpu_model.isin(AGG_NAME.values())].assign(chip=lambda d: d.gpu_model.str.replace("NVIDIA ", ""))
agg_final = agg[agg.status != "provisional"]
ds = pd.read_csv(PACK / "daily_statistics.csv", parse_dates=["date"])
U = units()
out["units"] = U.round(3).to_dict()

# ---------------------------------------------------------------- step 1: USD per capability unit-hour
rows = []
last4 = agg_final[agg_final.week_start >= agg_final.week_start.max() - pd.Timedelta(weeks=3)]
for m in AGG_MODES:
    p = last4[last4.pricing_mode == m].groupby("chip").median_usd_per_gpu_hour.median()
    rows.append({"instrument": f"aggregator_median/getdeploying/{m}", **p.to_dict()})
recent = ds[(ds.date >= "2026-10-07") & (ds.date <= "2026-11-06")]
for (src, cls, tier), g in recent.groupby(["source_id", "instrument_class", "pricing_tier"]):
    p = {}
    for c, names in DS_NAME.items():
        for nm in names:
            s = g[g.gpu_model == nm]
            if len(s):
                p[c] = s.median_usd_per_gpu_hour.median()
                break
    if sum(k in p for k in CHIPS) >= 4 and ("B200" in p or "B300" in p) and ("A100" in p or "H100" in p):
        rows.append({"instrument": f"{cls}/{src}/{tier}", **p})
price = pd.DataFrame(rows).set_index("instrument")[CHIPS]
price.to_csv(RES / "t1_price_per_gpu_hour.csv")
per_unit = price / U["xbench"]
frontier = per_unit[["B200", "B300"]].min(axis=1)   # cheapest frontier unit on that instrument
rel = per_unit.div(frontier, axis=0)
# capability-set range of the A100 and H100 ratio (ratio uses the same unit set for numerator and frontier)
rng = {}
for c in ["A100", "H100", "H200"]:
    vals = []
    for k in UNIT_SETS:
        pu = price / U[k]
        vals.append(pu[c] / pu[["B200", "B300"]].min(axis=1))
    v = pd.concat(vals, axis=1)
    rng[c] = (v.min(axis=1), v.max(axis=1))
t1 = per_unit.round(3).add_suffix("_usd_per_unit_h")
for c in ["A100", "H100", "H200"]:
    t1[f"{c}_vs_frontier"] = rel[c].round(2)
    t1[f"{c}_vs_frontier_range"] = [f"{a:.2f}-{b:.2f}" for a, b in zip(*rng[c])]
t1.to_csv(RES / "t1_usd_per_capability_unit.csv")
out["step1_rel_median_across_instruments"] = rel[["A100", "H100", "H200"]].median().round(2).to_dict()
out["step1_n_instruments"] = int(len(rel))

# weekly per-unit ratio on aggregator on-demand and its trend
wk = agg_final[agg_final.pricing_mode == "on_demand"].pivot_table(index="week_start", columns="chip", values="median_usd_per_gpu_hour")
wk_pu = wk[CHIPS] / U["xbench"]
wk_rel = wk_pu.div(wk_pu["B200"], axis=0)
wk_rel.to_csv(RES / "t1b_weekly_per_unit_ratio_vs_B200_on_demand.csv")
trend = {}
for c in ["A100", "H100", "H200", "B300"]:
    s = np.log(wk_rel[c].dropna())
    d = pd.DataFrame({"t": (s.index - s.index[0]).days / 7.0, "y": s.values, "g": 0, "w": s.index})
    b = fe_slope(d)
    bs = block_boot(d, 8, fe_slope)
    trend[c] = {"first4": float(np.exp(s.iloc[:4].mean())), "last4": float(np.exp(s.iloc[-4:].mean())), "n_weeks": int(len(s)),
                "annual_change_of_ratio": ann(b), "ci90": [ann(np.nanpercentile(bs, 5)), ann(np.nanpercentile(bs, 95))]}
out["step1b_ratio_trend_vs_B200"] = trend

# ---------------------------------------------------------------- step 2: within-chip decay
dec = []
for c in CHIPS:
    for m in AGG_MODES:
        s = agg_final[(agg_final.chip == c) & (agg_final.pricing_mode == m)].set_index("week_start").median_usd_per_gpu_hour.sort_index()
        if len(s) < 20:
            continue
        d = pd.DataFrame({"t": (s.index - s.index[0]).days / 7.0, "y": np.log(s.values), "g": 0, "w": s.index})
        b = fe_slope(d)
        bs = block_boot(d, 8, fe_slope)
        dec.append({"instrument": f"aggregator_median/{m}", "chip": c, "from": s.index[0].date(), "to": s.index[-1].date(), "n": len(s),
                    "annual": ann(b), "lo90": ann(np.nanpercentile(bs, 5)), "hi90": ann(np.nanpercentile(bs, 95)), "b": b, "bs": bs})
az = pd.read_parquet(RUNS / "aws_daily_az.parquet")
az["w"] = az.day.dt.to_period("W-SUN").dt.start_time
azw = az.groupby(["instance_type", "segment", "az", "w"]).p.mean().reset_index()
azw["y"] = np.log(azw.p)
azw["g"] = azw.az


def aws_fit(d: pd.DataFrame, label: str, it: str, block=8) -> dict:
    d = d.assign(t=(d.w - d.w.min()).dt.days / 7.0)
    b = fe_slope(d)
    bs = block_boot(d, block, fe_slope)
    return {"instrument": label, "chip": AWS_CHIP[it] + f" ({it})", "from": d.w.min().date(), "to": d.w.max().date(), "n": d.w.nunique(),
            "annual": ann(b), "lo90": ann(np.nanpercentile(bs, 5)), "hi90": ann(np.nanpercentile(bs, 95)), "b": b, "bs": bs}


for it in AWS_CHIP:
    for seg in ["A", "B"]:
        d = azw[(azw.instance_type == it) & (azw.segment == seg)]
        if d.w.nunique() >= 10:
            dec.append(aws_fit(d, f"hyperscaler_spot/aws/seg{seg}", it, block=8 if seg == "A" else 3))
    d = azw[(azw.instance_type == it) & (azw.segment == "A") & (azw.w >= "2025-03-01")]
    if d.w.nunique() >= 10:
        dec.append(aws_fit(d, "hyperscaler_spot/aws/segA_last12m", it))
decdf = pd.DataFrame(dec)
decdf.drop(columns=["b", "bs"]).round(3).to_csv(RES / "t2_decay_rates.csv", index=False)

# yearly slopes for AWS segment A (does decay change with age?)
yr = []
for it in ["p4d.24xlarge", "p5.48xlarge"]:
    d0 = azw[(azw.instance_type == it) & (azw.segment == "A")]
    for y0 in pd.date_range("2022-06-01", "2025-06-01", freq="6MS"):
        d = d0[(d0.w >= y0) & (d0.w < y0 + pd.DateOffset(months=12))]
        if d.w.nunique() >= 30:
            r = aws_fit(d, "12m window", it)
            yr.append({"instance_type": it, "window_start": y0.date(), "annual": r["annual"], "lo90": r["lo90"], "hi90": r["hi90"]})
pd.DataFrame(yr).round(3).to_csv(RES / "t2b_aws_rolling_12m_decay.csv", index=False)

# event study: slope 26 weeks before vs after, AWS segment A, A100 (p4d) and H100 (p5)
ev = []
for name, day in EVENTS.items():
    e = pd.Timestamp(day)
    for it in ["p4d.24xlarge", "p5.48xlarge"]:
        d0 = azw[(azw.instance_type == it) & (azw.segment == "A")]
        pre = d0[(d0.w >= e - pd.Timedelta(weeks=26)) & (d0.w < e)]
        post = d0[(d0.w >= e) & (d0.w < min(e + pd.Timedelta(weeks=26), SEG_A_END))]
        if pre.w.nunique() < 10 or post.w.nunique() < 10:
            continue
        rp, rq = aws_fit(pre, "pre", it, 4), aws_fit(post, "post", it, 4)
        diff = (rq["bs"][:NB] - rp["bs"][:NB]) * 52.18
        ev.append({"event": name, "date": day, "instance_type": it, "pre_annual": rp["annual"], "post_annual": rq["annual"],
                   "post_weeks": post.w.nunique(), "diff_log_per_yr": (rq["b"] - rp["b"]) * 52.18,
                   "diff_lo90": float(np.nanpercentile(diff, 5)), "diff_hi90": float(np.nanpercentile(diff, 95))})
evdf = pd.DataFrame(ev)
evdf.round(3).to_csv(RES / "t2c_event_study.csv", index=False)
out["step2_event_mean_diff_log_per_yr"] = float(evdf.diff_log_per_yr.mean())
out["step2_event_share_steeper_after"] = float((evdf.diff_log_per_yr < 0).mean())

# ---------------------------------------------------------------- step 3: backtests
def score(rows: list[dict]) -> dict:
    r = pd.DataFrame(rows)
    res = {"n": len(r)}
    for k in ["decay", "nochange"]:
        e = np.log(r.truth) - np.log(r[f"{k}_q50"])
        res[f"{k}_mae_log"] = float(e.abs().mean())
        res[f"{k}_bias_log"] = float(e.mean())
        res[f"{k}_cover80"] = float(((r.truth >= r[f"{k}_q10"]) & (r.truth <= r[f"{k}_q90"])).mean())
        pin = 0
        for q in (0.1, 0.5, 0.9):
            u = r.truth - r[f"{k}_q{int(q * 100)}"]
            pin += np.maximum(q * u, (q - 1) * u).mean() / 3
        res[f"{k}_pinball"] = float(pin)
    res["skill_vs_nochange"] = 1 - res["decay_pinball"] / res["nochange_pinball"]
    # paired bootstrap of the MAE difference over series
    e1 = (np.log(r.truth) - np.log(r.decay_q50)).abs().values
    e0 = (np.log(r.truth) - np.log(r.nochange_q50)).abs().values
    bs = [np.mean((e1 - e0)[RNG.integers(0, len(r), len(r))]) for _ in range(NB)]
    res["mae_diff_ci90"] = [float(np.percentile(bs, 5)), float(np.percentile(bs, 95))]
    return res, r


Z = 1.2816
# (a) aggregator: fit weeks 2025-11-03..2026-04-27, forecast 2026-10-26 (26 weeks), every model x the four modes
aggall = pd.read_csv(PACK / "aggregator_medians.csv", parse_dates=["week_start"])
aggall = aggall[aggall.status != "provisional"]
ORIG, TGT = pd.Timestamp("2026-04-27"), pd.Timestamp("2026-10-26")
H = (TGT - ORIG).days / 7
bt = []
for (gm, m), s in aggall[aggall.pricing_mode.isin(AGG_MODES)].groupby(["gpu_model", "pricing_mode"]):
    s = s.set_index("week_start").median_usd_per_gpu_hour.sort_index()
    tr = s[(s.index <= ORIG) & (s.index >= "2025-11-03")]
    if len(tr) < 22 or TGT not in s.index or ORIG not in tr.index:
        continue
    t = (tr.index - tr.index[0]).days / 7.0
    y = np.log(tr.values)
    b = np.polyfit(t, y, 1)[0]
    sd = np.std(np.diff(y), ddof=1) * np.sqrt(H)
    sd = max(sd, 0.02)
    lv = tr.iloc[-1]
    c = lv * np.exp(b * H)
    bt.append({"series": f"{gm}/{m}", "headline": gm in AGG_NAME.values(), "truth": s[TGT], "decay_q50": c,
               "decay_q10": c * np.exp(-Z * sd), "decay_q90": c * np.exp(Z * sd),
               "nochange_q50": lv, "nochange_q10": lv * np.exp(-Z * sd), "nochange_q90": lv * np.exp(Z * sd)})
s_all, r_all = score(bt)
s_head, r_head = score([x for x in bt if x["headline"]])
r_all.round(4).to_csv(RES / "t3a_backtest_aggregator.csv", index=False)
out["step3a_aggregator_all"] = s_all
out["step3a_aggregator_5chips"] = s_head

# (b) AWS: fit 24 months to 2025-10-31 on segment A (AZ fixed effects), forecast monthly AZ-median Jul..Oct 2026 (segment B)
daily = pd.read_parquet(RUNS / "aws_daily.parquet")
daily["mon"] = daily.day.dt.to_period("M")
mon = daily.groupby(["instance_type", "mon"]).p.median()
bt2 = []
for it in ["p4d.24xlarge", "p4de.24xlarge", "p5.48xlarge", "p5en.48xlarge", "p5e.48xlarge"]:
    d = azw[(azw.instance_type == it) & (azw.segment == "A") & (azw.w <= "2025-10-31") & (azw.w >= "2023-11-01")]
    if d.w.nunique() < 20:
        continue
    d = d.assign(t=(d.w - d.w.min()).dt.days / 7.0)
    b = fe_slope(d)
    m = mon[it]
    tr = m[(m.index <= pd.Period("2025-10", "M")) & (m.index >= pd.Period("2023-11", "M"))]
    lv = tr.iloc[-1]
    sdm = np.std(np.diff(np.log(tr.values)), ddof=1)
    for tg in ["2026-07", "2026-08", "2026-09", "2026-10"]:
        hm = (pd.Period(tg, "M") - pd.Period("2025-10", "M")).n
        sd = sdm * np.sqrt(hm)
        c = lv * np.exp(b * hm * 4.348)
        bt2.append({"series": it, "target": tg, "h_months": hm, "truth": m[pd.Period(tg, "M")], "decay_q50": c,
                    "decay_q10": c * np.exp(-Z * sd), "decay_q90": c * np.exp(Z * sd), "nochange_q50": lv,
                    "nochange_q10": lv * np.exp(-Z * sd), "nochange_q90": lv * np.exp(Z * sd), "fit_annual": ann(b)})
s_aws, r_aws = score(bt2)
r_aws.round(4).to_csv(RES / "t3b_backtest_aws.csv", index=False)
out["step3b_aws"] = s_aws

# ---------------------------------------------------------------- step 4: projections at +24 / +36 months
def hw_price_perf() -> dict:
    h = pd.read_csv(PACK / "hardware_fundamentals/hardware_fundamentals.csv", parse_dates=["release_date"])
    h = h[(h.vendor.str.contains("NVIDIA", na=False)) & h.release_price_usd.notna() & h.fp16_tflops.notna() & (h.release_date >= "2016-01-01")]
    x = (h.release_date - pd.Timestamp("2020-01-01")).dt.days / 365.25
    y = np.log(h.fp16_tflops / h.release_price_usd)
    b = np.polyfit(x, y, 1)[0]
    bs = []
    for _ in range(NB):
        i = RNG.integers(0, len(h), len(h))
        bs.append(np.polyfit(x.values[i], y.values[i], 1)[0])
    return {"n": int(len(h)), "flops_per_usd_growth_per_yr": float(np.exp(b) - 1),
            "ci90": [float(np.exp(np.percentile(bs, 5)) - 1), float(np.exp(np.percentile(bs, 95)) - 1)], "b": b, "bs": np.array(bs)}


pp = hw_price_perf()
out["step4_hw_price_performance"] = {k: v for k, v in pp.items() if k not in ("b", "bs")}

N = 20000
ELEC = RNG.uniform(0.05, 0.12, N)        # USD per kWh, industrial / colo pass-through range
PUE = RNG.uniform(1.2, 1.5, N)
unit_draw = RNG.choice(list(UNIT_SETS), N)
proj = []
paths = {}
for c in ["H100", "A100"]:
    for m in ["on_demand", "spot"]:
        p0 = float(price.loc[f"aggregator_median/getdeploying/{m}", c])
        # decay model: pool of instrument estimates for this chip (each drawn from its own bootstrap)
        pool = decdf[(decdf.chip.str.startswith(c)) & (~decdf.instrument.str.contains("segB"))]
        pick = RNG.integers(0, len(pool), N)
        g = np.array([pool.iloc[i].bs[RNG.integers(0, len(pool.iloc[i].bs))] for i in pick]) * 52.18  # log per yr
        wsd = np.std(np.diff(np.log(agg_final[(agg_final.chip == c) & (agg_final.pricing_mode == m)].sort_values("week_start").median_usd_per_gpu_hour)), ddof=1)
        # strict per-unit parity: frontier per-unit price today x units, frontier unit price declines at g_f
        pf0 = float(price.loc[f"aggregator_median/getdeploying/{m}", ["B200", "B300"]].div(U.loc[["B200", "B300"], "xbench"]).min())
        b200 = decdf[(decdf.chip == "B200") & (decdf.instrument == f"aggregator_median/{m}")]
        gf_a = b200.iloc[0].bs[RNG.integers(0, NB, N)] * 52.18 if len(b200) else np.zeros(N)
        gf_b = -pp["bs"][RNG.integers(0, NB, N)]
        gf = np.where(RNG.random(N) < 0.5, gf_a, gf_b)
        ui = np.array([U.loc[c, k] for k in unit_draw])
        uf = np.array([U.loc["B300", k] for k in unit_draw])
        prem0 = float(rel.loc[f"aggregator_median/getdeploying/{m}", c])
        ptr = trend[c]["annual_change_of_ratio"]
        for T in (24, 36):
            yrs = T / 12
            noise = RNG.normal(0, wsd * np.sqrt(T * 4.348), N)
            dm = p0 * np.exp(g * yrs + noise)
            handicap = np.maximum(TDP[c] - ui * TDP["B300"] / uf, 0) / 1000 * PUE * ELEC
            par = np.maximum(ui * (pf0 * U.loc["B300", "xbench"] / U.loc["B300", "xbench"]) * np.exp(gf * yrs) - handicap, 0.01)
            # premium-persists variant: today's per-unit premium, moving at its observed 12-month trend (capped at 1x floor)
            prem = np.maximum(prem0 * (1 + ptr) ** yrs, 1.0)
            pp_ = np.maximum(par * prem, 0.01)
            for name, x in [("decay", dm), ("parity_strict", par), ("parity_premium_persists", pp_)]:
                q = np.percentile(x, [10, 50, 90])
                proj.append({"chip": c, "instrument": f"aggregator_median/{m}", "p0_nov2026": p0, "horizon_m": T, "model": name,
                             "q10": q[0], "q50": q[1], "q90": q[2]})
            paths[(c, m, T)] = dm
        out[f"step4_{c}_{m}_decay_rate_q10_50_90"] = (np.exp(np.percentile(g, [10, 50, 90])) - 1).round(3).tolist()
        out[f"step4_{c}_{m}_handicap_usd_h_q50"] = float(np.median(np.maximum(TDP[c] - ui * TDP["B300"] / uf, 0) / 1000 * PUE * ELEC))
projdf = pd.DataFrame(proj)
projdf.round(3).to_csv(RES / "t4_projections.csv", index=False)

# ---------------------------------------------------------------- step 5: income-approach value per GPU (Nov 2026)
def income_value(c: str, n: int = 20000, start_m: int = 0) -> np.ndarray:
    p0 = float(price.loc["aggregator_median/getdeploying/on_demand", c])
    pool = decdf[(decdf.chip.str.startswith(c)) & (~decdf.instrument.str.contains("segB"))]
    pick = RNG.integers(0, len(pool), n)
    g = np.array([pool.iloc[i].bs[RNG.integers(0, len(pool.iloc[i].bs))] for i in pick]) * 52.18
    util = RNG.uniform(0.5, 0.85, n)
    r = RNG.uniform(0.10, 0.20, n)
    life = RNG.uniform(*({"H100": (2, 5), "A100": (1, 4)}[c]), n)
    fixed = RNG.uniform(*({"H100": (0.25, 0.45), "A100": (0.20, 0.35)}[c]), n)  # colo, network, maintenance, USD per GPU-hour
    elec = RNG.uniform(0.05, 0.12, n) * RNG.uniform(1.2, 1.5, n) * TDP[c] / 1000
    val = np.zeros(n)
    for mth in range(start_m + 1, start_m + 61):
        rent = p0 * np.exp(g * mth / 12)
        net = np.maximum((rent * util - fixed - elec * util) * 730, 0)  # operator idles the GPU when net < 0
        alive = (mth - start_m) <= life * 12
        val += np.where(alive, net / (1 + r) ** ((mth - start_m) / 12), 0)
    return val, dict(util=util, r=r, life=life, fixed=fixed, g=g)


res5 = {}
sens = []
for c in ["H100", "A100"]:
    v, par = income_value(c)
    res5[c] = {"q10": float(np.percentile(v, 10)), "q50": float(np.median(v)), "q90": float(np.percentile(v, 90))}
    v24, _ = income_value(c, start_m=24)
    res5[c + "_at_+24m"] = {"q10": float(np.percentile(v24, 10)), "q50": float(np.median(v24)), "q90": float(np.percentile(v24, 90))}
    for k, a in par.items():
        lo, hi = np.percentile(a, [20, 80])
        sens.append({"chip": c, "input": k, "low_quintile_value_q50": float(np.median(v[a <= lo])), "high_quintile_value_q50": float(np.median(v[a >= hi])),
                     "low_input": float(lo), "high_input": float(hi)})
pd.DataFrame(sens).round(3).to_csv(RES / "t5_income_sensitivity.csv", index=False)
out["step5_income_value_per_gpu"] = res5

json.dump(out, open(RES / "summary.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str))
print(price.round(3).to_string())
print(t1.to_string())
print(decdf.drop(columns=["b", "bs"]).round(3).to_string())
print(evdf.round(3).to_string())
print(projdf.round(2).to_string())
print(pd.DataFrame(sens).round(2).to_string())
