"""Figures for longrun.md (run after analysis.py). Each instrument is drawn as its own series; nothing is chained."""
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[3]
RES = ROOT / "experiments/longrun/results"
RUNS = ROOT / "runs/longrun"

r = pd.read_csv(RES / "t1b_weekly_per_unit_ratio_vs_B200_on_demand.csv", parse_dates=["week_start"]).set_index("week_start")
fig, ax = plt.subplots(figsize=(8, 4))
for c in ["A100", "H100", "H200", "B300"]:
    ax.plot(r.index, r[c], label=c)
ax.axhline(1, color="k", lw=0.8, ls="--")
ax.set_ylabel("USD per capability unit-hour, ratio to B200")
ax.set_title("Per-unit-of-work rental price relative to B200\naggregator_median (GetDeploying), on_demand, weekly; units: MLPerf cross-benchmark median (A100=1)", fontsize=9)
ax.legend()
fig.tight_layout()
fig.savefig(RES / "fig1_per_unit_ratio.png", dpi=130)

d = pd.read_parquet(RUNS / "aws_daily.parquet")
fig, ax = plt.subplots(figsize=(9, 4.2))
for it, col in [("p4d.24xlarge", "C0"), ("p4de.24xlarge", "C2"), ("p5.48xlarge", "C3"), ("p5en.48xlarge", "C4")]:
    for i, (seg, g) in enumerate(d[d.instance_type == it].groupby("segment")):
        w = g.set_index("day").p.resample("W").median()
        ax.plot(w.index, w.values, color=col, label=it if i == 0 else None)
ax.axvspan(pd.Timestamp("2026-03-01"), pd.Timestamp("2026-06-30"), color="grey", alpha=0.25, label="archive hole (not interpolated)")
for day, lab in [("2024-11-18", "H200/B200 (Epoch)"), ("2025-06-01", "AWS on-demand cut"), ("2025-07-24", "p6-b200 on AWS"), ("2025-08-22", "B300 (Epoch)"), ("2025-11-20", "p6-b300 on AWS")]:
    ax.axvline(pd.Timestamp(day), color="k", lw=0.6, ls=":")
    ax.text(pd.Timestamp(day), ax.get_ylim()[1] if False else 9.5, lab, rotation=90, fontsize=6, va="top")
ax.set_yscale("log")
ax.set_ylabel("USD per GPU-hour (log)")
ax.set_title("AWS EC2 spot (hyperscaler_spot), Linux, weekly median across AZs of end-of-day price; two segments", fontsize=9)
ax.legend(fontsize=7, loc="lower left")
fig.tight_layout()
fig.savefig(RES / "fig2_aws_spot.png", dpi=130)

p = pd.read_csv(RES / "t4_projections.csv")
p = p[p.instrument == "aggregator_median/on_demand"]
fig, axs = plt.subplots(1, 2, figsize=(9, 4), sharey=False)
for ax, c in zip(axs, ["H100", "A100"]):
    s = p[p.chip == c]
    for j, (m, col) in enumerate([("decay", "C0"), ("parity_strict", "C1"), ("parity_premium_persists", "C2")]):
        for k, T in enumerate([24, 36]):
            x = k * 4 + j
            row = s[(s.model == m) & (s.horizon_m == T)].iloc[0]
            ax.errorbar(x, row.q50, yerr=[[row.q50 - row.q10], [row.q90 - row.q50]], fmt="o", color=col, capsize=4, label=m if k == 0 else None)
    ax.axhline(s.p0_nov2026.iloc[0], color="k", ls="--", lw=0.8, label="Nov 2026 level")
    ax.set_xticks([1, 5]); ax.set_xticklabels(["+24 m (Nov 2028)", "+36 m (Nov 2029)"])
    ax.set_title(f"{c}: aggregator_median on_demand, q10/q50/q90", fontsize=9)
    ax.set_ylabel("USD per GPU-hour")
axs[0].legend(fontsize=7)
fig.tight_layout()
fig.savefig(RES / "fig3_projections.png", dpi=130)
print("ok")
