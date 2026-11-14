"""v3 steps 2-4: assumption-sensitive decision table, sanity checks, recommendation direction tests, v2 -> v3 changes.

Frozen inputs (scenario rates, 0.25 noise, 0.35/0.40/0.25) are copied from scen_v2.py unchanged; the grid, the weight
alternatives, the sanity checks and the recommendation tests are frozen in experiments/longrun/protocol_v3.yaml.
Backtests are NOT re-run: v2_t3a / v2_t3c are read from file and only summarised by origin.
Run after panel_v3.py (and v2's aws.py, which wrote runs/longrun/bls_*.json):
  OMP_NUM_THREADS=2 .venv/bin/python experiments/longrun/code/scen_v3.py"""
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
SCEN = ["S1", "S2", "S3"]
WEIGHTS = {"frozen": {"S1": 0.35, "S2": 0.40, "S3": 0.25},
           "toward_shortage": {"S1": 0.50, "S2": 0.25, "S3": 0.25},
           "toward_glut": {"S1": 0.35, "S2": 0.25, "S3": 0.40}}
RATES = {"H100": {"S1": (-0.05, 0.10, 0.30), "trend": (-0.31, -0.20, -0.12), "glut": (-0.60, -0.45, -0.30)},
         "A100": {"S1": (-0.10, 0.00, 0.15), "trend": (-0.15, -0.10, -0.03), "glut": (-0.55, -0.40, -0.25)}}
NOISE_STATIC, NOISE_SPOT = 0.25, 0.60
UTIL = [0.50, 0.675, 0.85]
REAL = [0.70, 0.85, 1.00]
N = 20000            # draws per scenario
MONTHS = 120
TDP = {"H100": 700, "A100": 400}
LIFE = {"H100": (4.0, 7.0), "A100": (2.0, 5.0)}
FIXED = {"H100": (0.25, 0.45), "A100": (0.20, 0.35)}
MKT = {"H100": 20000.0, "A100": 7000.0}
NEW = {"H100": 30000.0, "A100": 15000.0}
out: dict = {}


def draw_rate(q, n):
    lo, mid, hi = (np.log1p(x) for x in q)
    return RNG.normal(mid, (hi - lo) / (2 * Z), n)


def sim_pool(chip: str, noise: float) -> tuple[np.ndarray, np.ndarray]:
    """N paths per scenario, stacked S1|S2|S3; monthly log index (3N x MONTHS+1) and labels. Same path rules as v2."""
    R, m = RATES[chip], np.arange(1, MONTHS + 1)[None, :]
    paths, labs = [], []
    for s in SCEN:
        r1, tr, gl = draw_rate(R["S1"], N)[:, None], draw_rate(R["trend"], N)[:, None], draw_rate(R["glut"], N)[:, None]
        rr = {"S1": np.where(m <= 12, r1, tr), "S2": np.broadcast_to(tr, (N, MONTHS)), "S3": np.where((m > 12) & (m <= 30), gl, tr)}[s]
        shocks = RNG.normal(0, noise / np.sqrt(12), (N, MONTHS))
        paths.append(np.concatenate([np.zeros((N, 1)), np.cumsum(rr / 12 + shocks, axis=1)], axis=1))
        labs.append(np.full(N, s))
    return np.vstack(paths), np.concatenate(labs)


def wq(x: np.ndarray, w: np.ndarray, qs=(0.1, 0.5, 0.9)) -> np.ndarray:
    o = np.argsort(x, kind="stable")
    cw = np.cumsum(w[o]); cw /= cw[-1]
    return np.array([x[o][min(np.searchsorted(cw, q), len(x) - 1)] for q in qs])


def wvec(lab: np.ndarray, ws: dict) -> np.ndarray:
    return np.select([lab == s for s in SCEN], [ws[s] / N for s in SCEN])


# ---------------------------------------------------------------- inputs
pan = json.load(open(RES / "v3_panel_summary.json"))
LV = {d["chip"]: d for d in pan["levels"]}
LEVEL = {"v3_unique": {c: LV[c]["v3_unique_median"] for c in ["H100", "A100"]},
         "v2_units": {c: LV[c]["v2_units_median"] for c in ["H100", "A100"]}}
ag = pd.read_csv(PACK / "aggregator_medians.csv", parse_dates=["week_start"])
agf = ag[ag.status != "provisional"]
INC_BASE = {c: float(agf[(agf.gpu_model == f"NVIDIA {c}") & (agf.pricing_mode == "reserved_36m")].sort_values("week_start").median_usd_per_gpu_hour.iloc[-4:].median()) for c in ["H100", "A100"]}
bls = json.load(open(RUNS / "bls_PCU221122221122.json"))["Results"]["series"][0]["data"]
b = pd.Series({pd.Period(f"{x['year']}-{x['period'][1:]}", "M"): float(x["value"]) for x in bls if x["period"].startswith("M")}).sort_index()
ELEC_G = float((b[pd.Period("2026-09", "M")] / b[pd.Period("2019-09", "M")]) ** (1 / 7) - 1)
out["income_base_reserved36m"], out["elec_cagr"] = INC_BASE, ELEC_G

POOL, LAB, DRAWS = {}, {}, {}
for chip in ["H100", "A100"]:
    POOL[chip], LAB[chip] = sim_pool(chip, NOISE_STATIC)
    n = 3 * N   # common random numbers for every non-grid input, shared by all cells
    DRAWS[chip] = {"r": RNG.uniform(0.10, 0.20, n), "life": RNG.uniform(*LIFE[chip], n), "fixed": RNG.uniform(*FIXED[chip], n),
                   "kwh": RNG.uniform(0.05, 0.12, n) * RNG.uniform(1.2, 1.5, n) * TDP[chip] / 1000,
                   "util_v2": RNG.uniform(0.5, 0.85, n), "real_v2": RNG.uniform(0.85, 1.0, n)}
SPOT = {c: sim_pool(c, NOISE_SPOT) for c in ["H100", "A100"]}


def income(chip, m0, util, real, path=None, fixed_add=0.0, kwh_mult=1.0, r_add=0.0, loan_r=None, horizon=None):
    """PV at month m0 (USD per GPU) of net rental income, v2 formula; util/real scalars or per-draw arrays."""
    d = DRAWS[chip]
    path = POOL[chip] if path is None else path
    r = (d["r"] + r_add) if loan_r is None else np.full(len(d["r"]), loan_r)
    life = d["life"] - m0 / 12
    val = np.zeros(len(r))
    for k in range(1, (int(horizon) if horizon else 96) + 1):
        m = m0 + k
        if m >= path.shape[1]:
            break
        rent = INC_BASE[chip] * real * np.exp(path[:, m])
        net = np.maximum((rent * util - (d["fixed"] + fixed_add) - d["kwh"] * kwh_mult * (1 + ELEC_G) ** (m / 12) * util) * 730, 0)
        alive = (k <= np.maximum(life, 0) * 12) if horizon is None else True
        val += np.where(alive, net / (1 + r) ** (k / 12), 0)
    return val


# ---------------------------------------------------------------- rent table (posted static rate-card median)
rent = []
for chip in ["H100", "A100"]:
    for base, lvs in LEVEL.items():
        lv = lvs[chip]
        for wn, ws in WEIGHTS.items():
            w = wvec(LAB[chip], ws)
            for h in (12, 24, 36):
                q = wq(lv * np.exp(POOL[chip][:, h]), w)
                row = {"chip": chip, "base": base, "level_nov2026": lv, "weights": wn, "h_months": h, "q10": q[0], "q50": q[1], "q90": q[2], "no_change": lv}
                if wn == "frozen":
                    qs = wq(lv * np.exp(SPOT[chip][0][:, h]), wvec(SPOT[chip][1], ws))
                    row.update({"q10_noise060": qs[0], "q90_noise060": qs[2]})
                rent.append(row)
rent = pd.DataFrame(rent)
rent.round(3).to_csv(RES / "v3_t2_rent_by_weights.csv", index=False)

# ---------------------------------------------------------------- value grid (income approach)
vals, VCELL, NC = [], {}, {}
for chip in ["H100", "A100"]:
    flat = np.zeros_like(POOL[chip])
    for m0 in (0, 24, 36):
        for u in UTIL:
            for rr in REAL:
                v = income(chip, m0, u, rr)
                vnc = income(chip, m0, u, rr, path=flat)
                VCELL[(chip, m0, u, rr)], NC[(chip, m0, u, rr)] = v, vnc
                qnc = np.percentile(vnc, [10, 50, 90])
                for wn, ws in WEIGHTS.items():
                    q = wq(v, wvec(LAB[chip], ws))
                    vals.append({"chip": chip, "m0": m0, "util": u, "real_over_posted": rr, "weights": wn,
                                 "q10": q[0], "q50": q[1], "q90": q[2], "nochange_q10": qnc[0], "nochange_q50": qnc[1], "nochange_q90": qnc[2]})
vals = pd.DataFrame(vals)
VCOLS = ["q10", "q50", "q90", "nochange_q10", "nochange_q50", "nochange_q90"]
vals.round({c: 0 for c in VCOLS}).to_csv(RES / "v3_t3_value_grid.csv", index=False)

# v2-style integrated value (util ~ U(0.5,0.85), real ~ U(0.85,1.0)), frozen weights: isolates Monte Carlo movement vs v2
v2style = []
for chip in ["H100", "A100"]:
    for m0 in (0, 24, 36):
        v = income(chip, m0, DRAWS[chip]["util_v2"], DRAWS[chip]["real_v2"])
        q = wq(v, wvec(LAB[chip], WEIGHTS["frozen"]))
        v2style.append({"chip": chip, "m0": m0, "q10": q[0], "q50": q[1], "q90": q[2]})
v2style = pd.DataFrame(v2style)
v2style.round(0).to_csv(RES / "v3_t3b_value_v2style_frozen.csv", index=False)

# ---------------------------------------------------------------- lender cover (v2 definition, common draws)
lend = []
for chip, terms in (("H100", (24, 36)), ("A100", (24, 36))):
    flat = np.zeros_like(POOL[chip])
    for T in terms:
        for u in UTIL:
            for rr in REAL:
                cov = income(chip, 0, u, rr, loan_r=0.10, horizon=T) + VCELL[(chip, T, u, rr)] / 1.10 ** (T / 12)
                cnc = income(chip, 0, u, rr, path=flat, loan_r=0.10, horizon=T) + NC[(chip, T, u, rr)] / 1.10 ** (T / 12)
                for wn, ws in WEIGHTS.items():
                    w = wvec(LAB[chip], ws)
                    q10 = wq(cov, w, (0.1,))[0]
                    lend.append({"chip": chip, "loan_months": T, "util": u, "real_over_posted": rr, "weights": wn,
                                 "q10_cover": q10, "ltv_q10_vs_market": q10 / MKT[chip],
                                 "nochange_ltv_q10": np.percentile(cnc, 10) / MKT[chip]})
lend = pd.DataFrame(lend)
lend.round(3).to_csv(RES / "v3_t4_lender_grid.csv", index=False)

# ---------------------------------------------------------------- sanity properties
san = []
for chip in ["H100", "A100"]:
    for m0 in (0, 24, 36):
        # P1: per draw, non-decreasing in utilisation (each real) and in realised rate (each util)
        worst_u = max(float(np.max(VCELL[(chip, m0, UTIL[i], rr)] - VCELL[(chip, m0, UTIL[i + 1], rr)])) for rr in REAL for i in range(2))
        worst_r = max(float(np.max(VCELL[(chip, m0, u, REAL[i])] - VCELL[(chip, m0, u, REAL[i + 1])])) for u in UTIL for i in range(2))
        san.append({"property": "P1 lower utilisation never raises value", "chip": chip, "m0": m0, "max_violation_usd": worst_u, "holds": worst_u <= 1e-6})
        san.append({"property": "P1 lower realised rent never raises value", "chip": chip, "m0": m0, "max_violation_usd": worst_r, "holds": worst_r <= 1e-6})
        base = VCELL[(chip, m0, 0.675, 0.85)]
        for lab, kw in (("fixed opex +0.10 USD/GPU-h", {"fixed_add": 0.10}), ("power price x1.5", {"kwh_mult": 1.5}), ("discount rate +5 points", {"r_add": 0.05})):
            worst = float(np.max(income(chip, m0, 0.675, 0.85, **kw) - base))
            san.append({"property": f"P2 higher cost never raises value: {lab}", "chip": chip, "m0": m0, "max_violation_usd": worst, "holds": worst <= 1e-6})
        # quantile level, same cells
        g = vals[(vals.chip == chip) & (vals.m0 == m0)]
        mono = all((g.sort_values(["weights", "real_over_posted", "util"]).groupby(["weights", "real_over_posted"]).q50.diff().dropna() >= -1e-6)) and \
            all((g.sort_values(["weights", "util", "real_over_posted"]).groupby(["weights", "util"]).q50.diff().dropna() >= -1e-6))
        san.append({"property": "P1 on displayed q50 (both directions, every weight set)", "chip": chip, "m0": m0, "max_violation_usd": np.nan, "holds": bool(mono)})
san = pd.DataFrame(san)
san.to_csv(RES / "v3_t5_sanity.csv", index=False)
out["sanity_all_hold"] = bool(san.holds.all())

# ---------------------------------------------------------------- recommendation direction tests (27 cells)
lvl = LEVEL["v3_unique"]
ratios = {d["chip"]: (d["v2_units_ratio_vs_frontier"], d["v3_unique_ratio_vs_frontier"]) for d in pan["levels"]}
tests = []


def rec(rid, text, series: pd.Series, cond, nochange_agrees=None):
    ok = series.apply(cond)
    tests.append({"id": rid, "test": text, "cells": len(series), "cells_direction_holds": int(ok.sum()),
                  "stat_min": float(series.min()), "stat_max": float(series.max()),
                  "verdict": "keep (conditional)" if ok.all() else "DROP", "no_change_agrees": nochange_agrees})


for rid, chip in (("R1", "H100"), ("R2", "A100")):
    s = rent[(rent.chip == chip) & (rent.base == "v3_unique") & (rent.h_months == 24)].q50 / lvl[chip]
    rec(rid, f"{chip} q50 posted rent at +24m / 6 Nov level < 1", s, lambda x: x < 1, nochange_agrees=False)
a = vals[(vals.chip == "A100")].pivot_table(index=["util", "real_over_posted", "weights"], columns="m0", values="q50")
rec("R3", "A100 q50 value +36m / q50 value Nov 2026 < 0.10", a[36] / a[0], lambda x: x < 0.10)
for T in (24, 36):
    s = lend[(lend.chip == "H100") & (lend.loan_months == T)].ltv_q10_vs_market
    rec(f"R4_{T}m", f"H100 {T}-month loan: q10 cover / 20k >= 0.60", s, lambda x: x >= 0.60)
h = vals[(vals.chip == "H100")].pivot_table(index=["util", "real_over_posted", "weights"], columns="m0", values="q50")
rec("R5", "H100 q50 value at +36m < 10.5k (35% of 30k)", h[36], lambda x: x < 10500)
s = rent[(rent.chip == "H100") & (rent.base == "v3_unique") & (rent.h_months == 12)].q90 / lvl["H100"]
rec("R6", "H100 q90 posted rent at +12m / 6 Nov level > 1", s, lambda x: x > 1, nochange_agrees=True)
rec("R7", "per-unit ratio vs frontier > 1 (H100, A100; v2 units and v3 unique)",
    pd.Series([ratios["H100"][0], ratios["H100"][1], ratios["A100"][0], ratios["A100"][1]]), lambda x: x > 1, nochange_agrees=True)
rec("R8", "H100 q50 value Nov 2026 - Nov 2028 > 10k (2 years of 6-year straight line)", h[0] - h[24], lambda x: x > 10000)
rec("R9", "H100 q50 value Nov 2026 > 15k (6-year straight-line book at age 3)", h[0], lambda x: x > 15000)
tests = pd.DataFrame(tests)
tests.round(3).to_csv(RES / "v3_t6_recommendation_tests.csv", index=False)

# ---------------------------------------------------------------- backtests already reported (read, not re-run)
btc = pd.read_csv(RES / "v2_t3c_backtest_aws_rolling.csv")
btc_o = btc.groupby(["variant", "origin"]).agg(n=("inside", "size"), coverage_mix=("inside", "mean"), coverage_nochange=("nochange_inside", "mean"),
                                               abs_log_err_mix=("abs_log_err_mix", "mean"), abs_log_err_nochange=("abs_log_err_nochange", "mean")).reset_index()
btc_o["mix_beats_nochange_on_error"] = btc_o.abs_log_err_mix < btc_o.abs_log_err_nochange
btc_o.round(3).to_csv(RES / "v3_t7_backtests_by_origin.csv", index=False)
bta = pd.read_csv(RES / "v2_t3a_backtest_mixture_1y.csv")
out["bt_a"] = {"n": len(bta), "coverage": float(bta.inside.mean()), "mae_mix": float(bta.abs_log_err_mix.mean()), "mae_nochange": float(bta.abs_log_err_nochange.mean())}

# ---------------------------------------------------------------- headline numbers v2 -> v3
v2p = {d["chip"]: d for d in json.load(open(RES / "v2_panel_summary.json"))["levels"]}
v2s = pd.read_csv(RES / "v2_t2_scenario_paths.csv")
v2s = v2s[v2s.base.str.startswith("static") & (v2s.scenario == "mixture")]
v2r = pd.read_csv(RES / "v2_t4_resale_income.csv")
v2l = pd.read_csv(RES / "v2_t5_lender_ltv.csv")
ch = []
for c in ["H100", "A100", "B200"]:
    ch.append({"number": f"{c} static rate-card level, 6 Nov (USD/GPU-h)", "v2": v2p[c]["static_median_usd"], "v3": LV[c]["v3_unique_median"],
               "why": f"v2 counted {v2p[c]['n_static_providers']} collector-provider units; v3 {LV[c]['v3_unique_n']} unique providers"})
for c in ["A100", "H100"]:
    ch.append({"number": f"{c} per-unit cost vs frontier (x)", "v2": v2p[c]["premium_vs_frontier_static"], "v3": LV[c]["v3_unique_ratio_vs_frontier"], "why": "unique-provider levels"})
for c in ["H100", "A100"]:
    for hm in (24, 36):
        o = v2s[(v2s.chip == c) & (v2s.h_months == hm)].iloc[0]
        n_ = rent[(rent.chip == c) & (rent.base == "v3_unique") & (rent.weights == "frozen") & (rent.h_months == hm)].iloc[0]
        for k in ("q10", "q50", "q90"):
            ch.append({"number": f"{c} rent +{hm}m {k}, frozen weights", "v2": o[k], "v3": n_[k], "why": "start level (unique providers) + Monte Carlo draw"})
for c in ["H100", "A100"]:
    for m0, at in ((0, "Nov 2026"), (24, "Nov 2028"), (36, "Nov 2029")):
        o = v2r[(v2r.chip == c) & (v2r["at"] == at)].iloc[0]
        n_ = v2style[(v2style.chip == c) & (v2style.m0 == m0)].iloc[0]
        ch.append({"number": f"{c} income value {at} q50 (v2-style inputs)", "v2": o.q50, "v3": n_.q50,
                   "why": "Monte Carlo draw only (income uses GetDeploying reserved-36m, not the panel level); v3 headline is now the grid"})
for _, o in v2l.iterrows():
    g = lend[(lend.chip == o.chip) & (lend.loan_months == o.loan_months) & (lend.weights == "frozen")].ltv_q10_vs_market
    ch.append({"number": f"{o.chip} {o.loan_months}-month LTV at q10", "v2": o.ltv_supported_vs_market, "v3": f"{g.min():.2f} to {g.max():.2f}",
               "why": "now a range over the utilisation x realised-rate grid, frozen weights; a conditional model output"})
pd.DataFrame(ch).to_csv(RES / "v3_t8_changes_vs_v2.csv", index=False)

json.dump(out, open(RES / "v3_summary.json", "w"), indent=1, default=str)

# ---------------------------------------------------------------- markdown tables for longrun_v3.md (numbers copied verbatim)
k = lambda x: f"{x / 1000:.1f}k"
md = ["## Table A. Posted rent, static rate-card median, unique providers (USD/GPU-h)\n",
      "| chip, horizon | no change | frozen 0.35/0.40/0.25: q50 (q10-q90) | toward shortage 0.50/0.25/0.25 | toward glut 0.35/0.25/0.40 | frozen, spot-level noise 0.60: q10-q90 | frozen, v2 collector-provider base: q50 (q10-q90) |",
      "|---|---|---|---|---|---|---|"]
for c in ["H100", "A100"]:
    for hm in (12, 24, 36):
        g = rent[(rent.chip == c) & (rent.h_months == hm)].set_index(["base", "weights"])
        f, s, gl, v2b = g.loc[("v3_unique", "frozen")], g.loc[("v3_unique", "toward_shortage")], g.loc[("v3_unique", "toward_glut")], g.loc[("v2_units", "frozen")]
        md.append(f"| {c}, +{hm} months | {f.no_change:.2f} | {f.q50:.2f} ({f.q10:.2f}-{f.q90:.2f}) | {s.q50:.2f} ({s.q10:.2f}-{s.q90:.2f}) | "
                  f"{gl.q50:.2f} ({gl.q10:.2f}-{gl.q90:.2f}) | {f.q10_noise060:.2f}-{f.q90_noise060:.2f} | {v2b.q50:.2f} ({v2b.q10:.2f}-{v2b.q90:.2f}) |")
for c in ["H100", "A100"]:
    md += [f"\n## Table B ({c}). Income-approach value per GPU (USD): q50 (q10-q90) under frozen weights; q50 under the two alternative weights; q50 with no change in rent\n",
           "| utilisation | realised / posted | Nov 2026 frozen | +24 m frozen | +24 m shortage / glut | +24 m no change | +36 m frozen | +36 m shortage / glut | +36 m no change |",
           "|---|---|---|---|---|---|---|---|---|"]
    for u in UTIL:
        for rr in REAL:
            g = vals[(vals.chip == c) & (vals.util == u) & (vals.real_over_posted == rr)].set_index(["m0", "weights"])
            cells = [f"{u:.3g}", f"{rr:.2f}", f"{k(g.loc[(0, 'frozen')].q50)} ({k(g.loc[(0, 'frozen')].q10)}-{k(g.loc[(0, 'frozen')].q90)})"]
            for m0 in (24, 36):
                f = g.loc[(m0, "frozen")]
                cells += [f"{k(f.q50)} ({k(f.q10)}-{k(f.q90)})", f"{k(g.loc[(m0, 'toward_shortage')].q50)} / {k(g.loc[(m0, 'toward_glut')].q50)}", k(f.nochange_q50)]
            md.append("| " + " | ".join(cells) + " |")
md += ["\n## Table C. Loan cover at q10 as a share of the used-market price (H100 20k, A100 7k); conditional model output, not an advance rate\n",
       "| chip, loan | utilisation | realised / posted | frozen | toward shortage | toward glut | no change in rent |", "|---|---|---|---|---|---|---|"]
for (c, T), g0 in lend.groupby(["chip", "loan_months"], sort=False):
    for u in UTIL:
        for rr in REAL:
            g = g0[(g0.util == u) & (g0.real_over_posted == rr)].set_index("weights")
            md.append(f"| {c}, {T} m | {u:.3g} | {rr:.2f} | {g.loc['frozen'].ltv_q10_vs_market:.2f} | {g.loc['toward_shortage'].ltv_q10_vs_market:.2f} | "
                      f"{g.loc['toward_glut'].ltv_q10_vs_market:.2f} | {g.loc['frozen'].nochange_ltv_q10:.2f} |")
md += ["\n## Table D. Backtests already reported in v2 (v2_t3c, AWS spot), by origin; not re-run\n",
       "| variant | origin | n | 80% coverage, method / no change | mean abs log error, method / no change | method better on error? |", "|---|---|---|---|---|---|"]
for _, r in btc_o.iterrows():
    md.append(f"| {r.variant} | {r.origin} | {r.n} | {r.coverage_mix:.2f} / {r.coverage_nochange:.2f} | {r.abs_log_err_mix:.2f} / {r.abs_log_err_nochange:.2f} | {'yes' if r.mix_beats_nochange_on_error else 'no'} |")
md += ["\n## Table E. Recommendation direction tests (protocol_v3 task4)\n", "| id | test | cells holding | statistic range | verdict | no change agrees? |", "|---|---|---|---|---|---|"]
for _, r in tests.iterrows():
    nca = "" if r.no_change_agrees is None or (isinstance(r.no_change_agrees, float) and np.isnan(r.no_change_agrees)) else ("yes" if r.no_change_agrees else "no")
    md.append(f"| {r.id} | {r.test} | {r.cells_direction_holds} of {r.cells} | {r.stat_min:.3g} to {r.stat_max:.3g} | {r.verdict} | {nca} |")
md += ["\n## Table F. Sanity properties\n", "| property | chip | from month | worst per-draw violation (USD; <= 0 means it holds) | holds |", "|---|---|---|---|---|"]
for _, r in san.iterrows():
    md.append(f"| {r.property} | {r.chip} | {r.m0} | {'' if np.isnan(r.max_violation_usd) else f'{r.max_violation_usd:.2f}'} | {r.holds} |")
open(RES / "v3_tables.md", "w").write("\n".join(md) + "\n")
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 500)
print(json.dumps(out, indent=1, default=str))
print(rent.round(2).to_string())
print(vals.round({c: 0 for c in VCOLS}).to_string())
print(v2style.round(0).to_string())
print(lend.round(3).to_string())
print(san.to_string())
print(tests.round(3).to_string())
print(btc_o.round(3).to_string())
print(pd.DataFrame(ch).round(3).to_string())
