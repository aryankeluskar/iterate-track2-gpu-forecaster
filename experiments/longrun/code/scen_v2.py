"""v2 steps 2-5: scenario rental paths, backtests (a, b, c), income-approach resale, lender LTV, economic depreciation.
Scenario definitions and probabilities are frozen in experiments/longrun/protocol_v2.yaml (written before this ran).
Run after aws.py and panel_v2.py:  OMP_NUM_THREADS=2 .venv/bin/python experiments/longrun/code/scen_v2.py"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
PACK = ROOT / "data/pack/gpu-price-pack-v0.1.1-handover"
RES = ROOT / "experiments/longrun/results"
RUNS = ROOT / "runs/longrun"
RNG = np.random.default_rng(20261114)
Z = 1.2816
P = {"S1": 0.35, "S2": 0.40, "S3": 0.25}
# annual rates as (q10, q50, q90) of the simple annual change; converted to log-normal draws of the log rate
RATES = {"H100": {"S1": (-0.05, 0.10, 0.30), "trend": (-0.31, -0.20, -0.12), "glut": (-0.60, -0.45, -0.30)},
         "A100": {"S1": (-0.10, 0.00, 0.15), "trend": (-0.15, -0.10, -0.03), "glut": (-0.55, -0.40, -0.25)}}
NOISE_STATIC = 0.25      # log per sqrt(year), panel-robust level
NOISE_POSTED = 0.41      # log per sqrt(year), posted medians (v1 calibration on 26-week no-change errors)
out: dict = {}


def draw_rate(q, n):
    lo, mid, hi = (np.log1p(x) for x in q)
    return RNG.normal(mid, (hi - lo) / (2 * Z), n)


def simulate(chip: str, n: int, months: int, noise: float, rates=None, probs=P):
    """Monthly log-index paths (n x months+1) and the scenario label of each draw."""
    rates = rates or RATES[chip]
    lab = RNG.choice(list(probs), n, p=list(probs.values()))
    r1, tr, gl = draw_rate(rates["S1"], n), draw_rate(rates["trend"], n), draw_rate(rates["glut"], n)
    m = np.arange(1, months + 1)
    monthly = np.empty((n, months))
    for i, s in enumerate(lab):
        if s == "S1":
            rr = np.where(m <= 12, r1[i], tr[i])
        elif s == "S2":
            rr = np.full(months, tr[i])
        else:
            rr = np.where((m > 12) & (m <= 30), gl[i], tr[i])
        monthly[i] = rr / 12
    shocks = RNG.normal(0, noise / np.sqrt(12), (n, months))
    path = np.concatenate([np.zeros((n, 1)), np.cumsum(monthly + shocks, axis=1)], axis=1)
    return path, lab


# ---------------------------------------------------------------- scenario rental paths
pan = json.load(open(RES / "v2_panel_summary.json"))
LEVEL = {d["chip"]: d["static_median_usd"] for d in pan["levels"]}
ag = pd.read_csv(PACK / "aggregator_medians.csv", parse_dates=["week_start"])
agf = ag[ag.status != "provisional"]
GD = {c: float(agf[(agf.gpu_model == f"NVIDIA {c}") & (agf.pricing_mode == "on_demand")].sort_values("week_start").median_usd_per_gpu_hour.iloc[-4:].median()) for c in ["H100", "A100"]}
N = 20000
rows = []
PATHS = {}
for chip in ["H100", "A100"]:
    path, lab = simulate(chip, N, 120, NOISE_STATIC)
    PATHS[chip] = (path, lab)
    for base, lv in [("static rate-card median (panel-robust)", LEVEL[chip]), ("GetDeploying on-demand median", GD[chip])]:
        for h in (12, 24, 36):
            x = lv * np.exp(path[:, h])
            for s in ["S1", "S2", "S3", "mixture"]:
                xs = x if s == "mixture" else x[lab == s]
                q = np.percentile(xs, [10, 50, 90])
                rows.append({"chip": chip, "base": base, "level_nov2026": lv, "h_months": h, "scenario": s,
                             "q10": q[0], "q50": q[1], "q90": q[2]})
scen = pd.DataFrame(rows)
scen.round(3).to_csv(RES / "v2_t2_scenario_paths.csv", index=False)

# ---------------------------------------------------------------- BLS electricity distribution PPI (power-cost side)
bls = json.load(open(RUNS / "bls_PCU221122221122.json"))["Results"]["series"][0]["data"]
b = pd.Series({pd.Period(f"{x['year']}-{x['period'][1:]}", "M"): float(x["value"]) for x in bls if x["period"].startswith("M")}).sort_index()
b = b[b.index <= pd.Period("2026-09", "M")]   # Oct 2026 print is published after the 6 Nov cutoff
out["bls_ppi_elec_dist"] = {"sep2026": float(b[pd.Period("2026-09", "M")]), "yoy_sep2026": float(b[pd.Period("2026-09", "M")] / b[pd.Period("2025-09", "M")] - 1),
                            "cagr_2019_09_to_2026_09": float((b[pd.Period("2026-09", "M")] / b[pd.Period("2019-09", "M")]) ** (1 / 7) - 1),
                            "vintage": "BLS API pulled 2026-11-14; Jul-Sep 2026 flagged preliminary; Oct 2026 excluded (published after cutoff)"}

# ---------------------------------------------------------------- backtest (a): mixture one year ahead, origin Nov 2025
MAPR = {"A100": "A100", "H100": "H100", "H200": "H100", "B200": "H100", "B300": "H100"}
bt = []
for chip in ["A100", "H100", "H200", "B200", "B300"]:
    for mode in ["on_demand", "spot", "reserved_12m", "reserved_36m"]:
        s = agf[(agf.gpu_model == f"NVIDIA {chip}") & (agf.pricing_mode == mode)].set_index("week_start").median_usd_per_gpu_hour.sort_index()
        if len(s) < 30 or s.index[0] > pd.Timestamp("2025-12-01"):
            continue
        o, t = s.index[0], pd.Timestamp("2026-10-26")
        h = (t - o).days / 30.44
        path, lab = simulate(MAPR[chip], 4000, int(np.ceil(h)), NOISE_POSTED)
        x = s.iloc[0] * np.exp(path[:, int(round(h))])
        q = np.percentile(x, [10, 50, 90])
        bt.append({"series": f"{chip}/{mode}", "origin": o.date(), "truth": s[t], "q10": q[0], "q50": q[1], "q90": q[2],
                   "nochange": s.iloc[0], "inside": q[0] <= s[t] <= q[2], "above_q90": s[t] > q[2],
                   "abs_log_err_mix": abs(np.log(s[t] / q[1])), "abs_log_err_nochange": abs(np.log(s[t] / s.iloc[0]))})
bta = pd.DataFrame(bt)
bta.round(3).to_csv(RES / "v2_t3a_backtest_mixture_1y.csv", index=False)
out["bt_a"] = {"n": len(bta), "coverage80": float(bta.inside.mean()), "share_above_q90": float(bta.above_q90.mean()),
               "mae_mix": float(bta.abs_log_err_mix.mean()), "mae_nochange": float(bta.abs_log_err_nochange.mean())}

# ---------------------------------------------------------------- backtest (b): per-unit premium decay as predictor
U = {"A100": 1.0, "H100": 2.464960, "H200": 2.716192, "B200": 7.914753}
btb = []
for mode in ["on_demand", "spot", "reserved_12m", "reserved_36m"]:
    w = agf[agf.pricing_mode == mode].pivot_table(index="week_start", columns="gpu_model", values="median_usd_per_gpu_hour")
    for chip in ["A100", "H100", "H200"]:
        r = np.log((w[f"NVIDIA {chip}"] / U[chip]) / (w["NVIDIA B200"] / U["B200"])).dropna()
        tr = r[r.index <= pd.Timestamp("2026-04-27")]
        t = pd.Timestamp("2026-10-26")
        if len(tr) < 15 or t not in r.index:
            continue
        x = (tr.index - tr.index[0]).days / 7.0
        bfit = np.polyfit(x, tr.values, 1)
        hx = (t - tr.index[0]).days / 7.0
        pred = np.polyval(bfit, hx)
        btb.append({"series": f"{chip}/{mode}", "premium_apr26": float(np.exp(tr.iloc[-1])), "premium_pred_oct26": float(np.exp(pred)),
                    "premium_true_oct26": float(np.exp(r[t])), "fit_annual_change": float(np.exp(bfit[0] * 52.18) - 1),
                    "err_trend": abs(r[t] - pred), "err_nochange": abs(r[t] - tr.iloc[-1])})
btbd = pd.DataFrame(btb)
btbd.round(3).to_csv(RES / "v2_t3b_backtest_premium.csv", index=False)
out["bt_b"] = {"n": len(btbd), "share_trend_better": float((btbd.err_trend < btbd.err_nochange).mean()),
               "mae_trend": float(btbd.err_trend.mean()), "mae_nochange": float(btbd.err_nochange.mean()),
               "share_premium_fell": float((btbd.premium_true_oct26 < btbd.premium_apr26).mean())}

# ---------------------------------------------------------------- backtest (c): AWS spot, year-end origins, method as run then
az = pd.read_parquet(RUNS / "aws_daily_az.parquet")
az["w"] = az.day.dt.to_period("W-SUN").dt.start_time
azw = az.groupby(["instance_type", "segment", "az", "w"]).p.mean().reset_index()
azw["y"] = np.log(azw.p)
daily = pd.read_parquet(RUNS / "aws_daily.parquet")
mon = daily.groupby(["instance_type", daily.day.dt.to_period("M")]).p.median()


def fe_rate(d: pd.DataFrame) -> float:
    d = d.assign(t=(d.w - d.w.min()).dt.days / 365.25)
    t = d.t - d.groupby("az").t.transform("mean")
    y = d.y - d.groupby("az").y.transform("mean")
    return float(np.exp((t * y).sum() / (t ** 2).sum()) - 1)


btc = []
CH = {"p3.16xlarge": "V100", "p4d.24xlarge": "A100", "p5.48xlarge": "H100", "p5en.48xlarge": "H200"}
for variant, noise_c in [("as_run_then_noise0.25", 0.25), ("as_run_then_noise0.60", 0.60), ("frozen_v2_rates_noise0.60", 0.60)]:
  for org in ["2023-12", "2024-12", "2025-12"]:
    op = pd.Period(org, "M")
    for it, chip in CH.items():
        hist = azw[(azw.instance_type == it) & (azw.segment == "A") & (azw.w <= op.end_time)]
        if hist.w.nunique() < 16 or (it, op) not in mon.index:
            continue
        tr = fe_rate(hist)
        trq = (tr - 0.10, tr, tr + 0.08)   # trend as estimated then, +-~1 sd of the multi-year fits
        rates = {"S1": (-0.05, 0.10, 0.30) if chip != "A100" and chip != "V100" else (-0.10, 0.0, 0.15), "trend": trq,
                 "glut": (trq[0] - 0.30, tr - 0.25, trq[2] - 0.20)}
        lv = mon[(it, op)]
        for h in (12, 24):
            tp = op + h
            hh = h
            if (it, tp) not in mon.index:      # archive ends 2026-10: use the last available month, note it
                cand = [p for p in mon[it].index if op < p <= tp]
                if not cand or (cand[-1] - op).n < h - 2:
                    continue
                tp, hh = cand[-1], (cand[-1] - op).n
            path, _ = simulate("H100", 4000, hh, noise_c, rates=(RATES["A100" if chip in ("A100", "V100") else "H100"] if variant.startswith("frozen") else rates))
            x = lv * np.exp(path[:, hh])
            q = np.percentile(x, [10, 50, 90])
            truth = mon[(it, tp)]
            sd = noise_c * np.sqrt(hh / 12)
            btc.append({"variant": variant, "origin": org, "instance_type": it, "chip": chip, "h_target_months": h, "target": str(tp), "trend_rate_then": tr,
                        "level": lv, "truth": truth, "q10": q[0], "q50": q[1], "q90": q[2], "inside": q[0] <= truth <= q[2],
                        "nochange_inside": lv * np.exp(-Z * sd) <= truth <= lv * np.exp(Z * sd),
                        "abs_log_err_mix": abs(np.log(truth / q[1])), "abs_log_err_nochange": abs(np.log(truth / lv))})
btcd = pd.DataFrame(btc)
btcd.round(3).to_csv(RES / "v2_t3c_backtest_aws_rolling.csv", index=False)
out["bt_c"] = btcd.groupby("variant").agg(n=("inside", "size"), coverage80_mix=("inside", "mean"), coverage80_nochange=("nochange_inside", "mean"),
                                          mae_mix=("abs_log_err_mix", "mean"), mae_nochange=("abs_log_err_nochange", "mean")).round(3).to_dict("index")
out["bt_c_by_h"] = btcd.groupby(["variant", "h_target_months"])[["inside", "nochange_inside", "abs_log_err_mix", "abs_log_err_nochange"]].mean().round(3).reset_index().to_dict("records")

# ---------------------------------------------------------------- resale by income approach along the scenario paths
TDP = {"H100": 700, "A100": 400}
LIFE = {"H100": (4.0, 7.0), "A100": (2.0, 5.0)}   # physical life cap: H100 7-10 yr total, A100 8-11 yr total (V100 still rents at 9 yr, CCIR)          # remaining economic life at Nov 2026, years
FIXED = {"H100": (0.25, 0.45), "A100": (0.20, 0.35)}     # colo, network, maintenance, USD per GPU-hour
ELEC_G = out["bls_ppi_elec_dist"]["cagr_2019_09_to_2026_09"]
INC_BASE = {c: float(agf[(agf.gpu_model == f"NVIDIA {c}") & (agf.pricing_mode == "reserved_36m")].sort_values("week_start").median_usd_per_gpu_hour.iloc[-4:].median()) for c in ["H100", "A100"]}
out["income_base_reserved36m"] = INC_BASE


def income(chip: str, m0: int, n: int = N, loan_r=None, horizon=None):
    """PV at month m0 (per GPU, USD) of net rental income over the remaining life, along the same simulated paths."""
    path, lab = PATHS[chip]
    path, lab = path[:n], lab[:n]
    util = RNG.uniform(0.5, 0.85, n)
    real = RNG.uniform(0.85, 1.0, n)           # realised rate / GetDeploying reserved_36m median (what a lessor can lock)
    r = RNG.uniform(0.10, 0.20, n) if loan_r is None else np.full(n, loan_r)
    life = RNG.uniform(*LIFE[chip], n) - m0 / 12
    fixed = RNG.uniform(*FIXED[chip], n)
    kwh = RNG.uniform(0.05, 0.12, n) * RNG.uniform(1.2, 1.5, n) * TDP[chip] / 1000
    val = np.zeros(n)
    hz = int(horizon) if horizon else 96
    for k in range(1, hz + 1):
        m = m0 + k
        if m >= path.shape[1]:
            break
        rent = INC_BASE[chip] * real * np.exp(path[:, m])
        net = np.maximum((rent * util - fixed - kwh * (1 + ELEC_G) ** (m / 12) * util) * 730, 0)
        alive = k <= np.maximum(life, 0) * 12 if horizon is None else np.ones(n, bool)
        val += np.where(alive, net / (1 + r) ** (k / 12), 0)
    return val, {"util": util, "life": life + m0 / 12, "r": r}


res = []
sens = []
VALS = {}
for chip in ["H100", "A100"]:
    for m0 in (0, 24, 36):
        v, par = income(chip, m0)
        VALS[(chip, m0)] = v
        q = np.percentile(v, [10, 50, 90])
        res.append({"chip": chip, "at": {0: "Nov 2026", 24: "Nov 2028", 36: "Nov 2029"}[m0], "q10": q[0], "q50": q[1], "q90": q[2]})
        if m0 == 0:
            for k in ["util", "life", "r"]:
                lo, hi = np.percentile(par[k], [20, 80])
                sens.append({"chip": chip, "input": k, "low (bottom quintile)": f"{lo:.2f}", "value q50 if low": float(np.median(v[par[k] <= lo])),
                             "high (top quintile)": f"{hi:.2f}", "value q50 if high": float(np.median(v[par[k] >= hi]))})
resd = pd.DataFrame(res)
resd.round(0).to_csv(RES / "v2_t4_resale_income.csv", index=False)
pd.DataFrame(sens).round(0).to_csv(RES / "v2_t4b_resale_sensitivity.csv", index=False)

# ---------------------------------------------------------------- lender: LTV the q10 path supports
MKT = {"H100": 20000.0, "A100": 7000.0}    # published used mid-points (GPUaaS 18-22k; Luminix A100 80GB 5-9.5k)
lend = []
for chip in ["H100", "A100"]:
    for T in (24, 36):
        inc, _ = income(chip, 0, loan_r=0.10, horizon=T)          # cash available over the loan term, at a 10% loan rate
        resid, _ = income(chip, T)                                  # collateral value at maturity (income approach)
        cover = inc + resid / 1.10 ** (T / 12)
        q10 = float(np.percentile(cover, 10))
        lend.append({"chip": chip, "loan_months": T, "q10_cover_usd": q10, "ltv_supported_vs_market": q10 / MKT[chip],
                     "q10_residual_at_maturity_usd": float(np.percentile(resid, 10)),
                     "q10_residual_share_of_new_30k": float(np.percentile(resid, 10)) / (30000 if chip == "H100" else 15000),
                     "q50_residual_at_maturity_usd": float(np.percentile(resid, 50))})
lendd = pd.DataFrame(lend)
lendd.round(3).to_csv(RES / "v2_t5_lender_ltv.csv", index=False)

# ---------------------------------------------------------------- economic depreciation vs straight line
dep = []
NEW = {"H100": (30000.0, 2023.9), "A100": (15000.0, 2020.9)}   # purchase price, purchase date (decimal year)
for chip in ["H100", "A100"]:
    vq = {y: float(np.median(income(chip, 12 * y)[0])) for y in range(0, 6)}
    cost, t0 = NEW[chip]
    for y in range(0, 6):
        age = 2026.9 + y - t0
        row = {"chip": chip, "year": 2026 + y, "age_years": round(age, 1), "economic_value_q50": vq[y],
               "economic_dep_in_year": (vq[y - 1] - vq[y]) if y > 0 else np.nan}
        for L in (4, 5, 6):
            row[f"book_SL{L}y"] = max(cost * (1 - age / L), 0)
        dep.append(row)
depd = pd.DataFrame(dep)
depd.round(0).to_csv(RES / "v2_t6_depreciation.csv", index=False)

json.dump(out, open(RES / "v2_summary.json", "w"), indent=1, default=str)
pd.set_option("display.width", 220)
print(json.dumps(out, indent=1, default=str))
print(scen[scen.base.str.startswith("static")].round(2).to_string())
print(scen[scen.base.str.startswith("GetD") & (scen.scenario == "mixture")].round(2).to_string())
print(bta.round(3).to_string()); print(btbd.round(3).to_string()); print(btcd[btcd.variant.str.startswith("frozen")].round(3).to_string())
print(resd.round(0).to_string()); print(pd.DataFrame(sens).round(0).to_string()); print(lendd.round(3).to_string()); print(depd.round(0).to_string())
