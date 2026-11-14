"""Figures for longrun.md v2 (after panel_v2.py and scen_v2.py)."""
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import json  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[3]
RES = ROOT / "experiments/longrun/results"

t = pd.read_csv(RES / "v2_t1_panel_decomposition.csv")
t = t[t.series.str.contains("all SKUs")]
gd = json.load(open(RES / "v2_panel_summary.json"))["getdeploying"]
fig, ax = plt.subplots(figsize=(9, 4))
chips = ["A100", "H100", "H200", "B200", "B300"]
x = np.arange(len(chips))
for j, (lab, f) in enumerate([("posted median, gpurentalprices (4 Aug-6 Nov)", lambda c: t[(t.chip == c) & (t.src == "gpurentalprices")].posted_median_dlog.iloc[0]),
                              ("same static offers, gpurentalprices", lambda c: t[(t.chip == c) & (t.src == "gpurentalprices")].static_mean_dlog.iloc[0]),
                              ("posted median, fastgpu (8 Sep-6 Nov)", lambda c: t[(t.chip == c) & (t.src == "fastgpu_daily")].posted_median_dlog.iloc[0]),
                              ("same static offers, fastgpu", lambda c: t[(t.chip == c) & (t.src == "fastgpu_daily")].static_mean_dlog.iloc[0]),
                              ("GetDeploying weekly median (3 Aug-26 Oct)", lambda c: gd[c]["aug03_to_oct26_dlog"])]):
    ax.bar(x + (j - 2) * 0.16, [100 * f(c) for c in chips], 0.16, label=lab)
ax.set_xticks(x); ax.set_xticklabels(chips)
ax.set_ylabel("price change, log points (about %)")
ax.set_title("How much of the autumn 2026 rise survives on the same static rate-card offers", fontsize=10)
ax.axhline(0, color="k", lw=0.6)
ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(RES / "v2_fig1_panel_decomposition.png", dpi=130)

s = pd.read_csv(RES / "v2_t2_scenario_paths.csv")
s = s[s.base.str.startswith("static")]
fig, axs = plt.subplots(1, 2, figsize=(10, 4))
cols = {"S1": "C3", "S2": "C0", "S3": "C2", "mixture": "k"}
names = {"S1": "shortage persists to end-2027 (p=0.35)", "S2": "eases to multi-year trend (p=0.40)", "S3": "successor glut from 2028 (p=0.25)", "mixture": "mixture"}
for ax, chip in zip(axs, ["H100", "A100"]):
    g = s[s.chip == chip]
    lv = g.level_nov2026.iloc[0]
    for k, sc in enumerate(["S1", "S2", "S3", "mixture"]):
        r = g[g.scenario == sc].sort_values("h_months")
        hx = np.r_[0, r.h_months.values] + (k - 1.5) * 0.8
        ax.errorbar(hx[1:], r.q50, yerr=[r.q50 - r.q10, r.q90 - r.q50], fmt="o-", color=cols[sc], capsize=3, label=names[sc], lw=2 if sc == "mixture" else 1)
    ax.axhline(lv, color="grey", ls="--", lw=0.8)
    ax.set_xticks([12, 24, 36]); ax.set_xticklabels(["Nov 2027", "Nov 2028", "Nov 2029"])
    ax.set_ylabel("USD per GPU-hour, static rate-card median")
    ax.set_title(f"{chip}: q10, median, q90 by scenario (dashed: 6 Nov 2026 level {lv:.2f})", fontsize=9)
axs[0].legend(fontsize=7)
fig.tight_layout(); fig.savefig(RES / "v2_fig3_scenarios.png", dpi=130)

d = pd.read_csv(RES / "v2_t6_depreciation.csv")
r = pd.read_csv(RES / "v2_t4_resale_income.csv")
fig, axs = plt.subplots(1, 2, figsize=(10, 4))
pub = {"H100": [(2026.7, 18000, 22000, "used trades, GPUaaS Sep 2026"), (2026.45, 22000, 25000, "Mercatus Jun 2026"), (2026.7, 14000, 22550, "eBay asks, Caladan Sep 2026")],
       "A100": [(2026.85, 5000, 9500, "80GB used, Luminix Nov 2026")]}
for ax, chip in zip(axs, ["H100", "A100"]):
    g = d[d.chip == chip]
    ax.plot(g.year + 0.85, g.economic_value_q50, "k-o", label="income-approach value, mixture median")
    rr = r[r.chip == chip]
    yrs = {"Nov 2026": 2026.85, "Nov 2028": 2028.85, "Nov 2029": 2029.85}
    ax.errorbar([yrs[a] for a in rr["at"]], rr.q50, yerr=[rr.q50 - rr.q10, rr.q90 - rr.q50], fmt="none", ecolor="k", capsize=4, alpha=0.6, label="q10-q90")
    for L, c in [(4, "C1"), (5, "C2"), (6, "C0")]:
        ax.plot(g.year + 0.85, g[f"book_SL{L}y"], color=c, ls="--", label=f"book value, {L}-year straight line")
    for k, (yy, lo, hi, lab) in enumerate(pub[chip]):
        ax.vlines(yy + 0.05 * k, lo, hi, color="C3", lw=4, alpha=0.7, label=lab if k == 0 else None)
    ax.set_xlabel("date"); ax.set_ylabel("USD per GPU")
    ax.set_title(f"{chip}: economic value vs book value (bought {'Nov 2023 at 30k' if chip == 'H100' else 'Nov 2020 at 15k'})", fontsize=9)
    ax.legend(fontsize=6)
fig.tight_layout(); fig.savefig(RES / "v2_fig4_value_vs_book.png", dpi=130)
print("ok")
