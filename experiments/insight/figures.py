"""Figures for results/insight.md. Run after analysis.py (reads its CSVs and runs/insight/paths.pkl)."""
import datetime as dt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

R = Path(__file__).parent / "results"
P = pd.read_pickle("runs/insight/paths.pkl")
dates = lambda idx: [dt.date.fromordinal(int(d)) for d in idx]
short = lambda s: s.replace(".median", "").replace("neocloud_", "").replace("gpurentalprices", "GRP").replace("fastgpu_daily", "FG").replace("afhubbard", "AFH").replace("hyperscaler_", "hs_")

# F1 index quality card
c = pd.read_csv(R / "t1_index_quality_card.csv").iloc[::-1]
col = c.mid_class.map({"static": "tab:blue", "intermediate": "tab:orange", "dynamic": "tab:red"})
fig, ax = plt.subplots(figsize=(9, 10))
y = np.arange(len(c))
ax.barh(y, c.worst_removal_pct, color=col, alpha=0.85)
ax.scatter(100 * c.max_pass_through / 4, y, marker="|", color="k", s=60, label="share of a provider's repricing passed to the median (x 25%)")
for i, (u, n, p) in enumerate(zip(c.do_not_use_alone, c.n_offers, c.n_providers)):
    ax.text(61, i, f"{n}/{p}" + ("  x" if u else "  ok"), va="center", fontsize=7)
ax.set_yticks(y, [short(s) for s in c.series_id], fontsize=7)
ax.set_xlim(0, 70)
ax.axvline(5, color="grey", ls=":")
ax.set_xlabel("largest change of the 6 Nov median from removing one offer or one provider (%)")
ax.set_title("Index quality, 37 scored series on 2026-11-06 (top = most robust)\nmiddle provider: blue static, orange intermediate, red dynamic\nright: offers/providers; x = do not use alone", fontsize=9)
ax.legend(loc="lower right", fontsize=7)
fig.tight_layout(); fig.savefig(R / "fig1_index_quality.png", dpi=130); plt.close(fig)

# F2 cross-collector: raw medians vs static balanced index
pairs = [k for k in P["Q2paths"] if k[0].split(".")[2] in ("B200", "H100_SXM_80GB", "B300", "H200") and k[1].split(".")[2] == k[0].split(".")[2]]
fig, axs = plt.subplots(1, len(pairs), figsize=(4 * len(pairs), 3.6), sharey=True)
for ax, k in zip(axs, pairs):
    Q = P["Q2paths"][k]
    for coll, ls in (("fastgpu", "-"), ("gpurentalprices", "--")):
        d = Q[coll]
        ax.plot(dates(d.index), 100 * (np.exp(d["median"]) - 1), ls, color="tab:red", label=f"{coll} posted median")
        ax.plot(dates(d.index), 100 * (np.exp(d["static_mean"]) - 1), ls, color="tab:blue", label=f"{coll} static offers, mean change")
    ax.set_title(k[0].split(".")[2] + " on-demand rate card", fontsize=9)
    ax.tick_params(axis="x", labelrotation=45, labelsize=7)
    ax.axhline(0, color="grey", lw=0.5)
axs[0].set_ylabel("change since 8 Sep 2026 (%)")
axs[-1].legend(fontsize=6)
fig.suptitle("Same GPU, two collectors: the posted medians disagree; the mean change of static offers agrees better", fontsize=10)
fig.tight_layout(); fig.savefig(R / "fig2_cross_collector.png", dpi=130); plt.close(fig)

# F3 static index vs headline vs dynamic, gpurentalprices from 4 Aug
fams = ["H100", "H200", "B200", "B300", "A100 80GB"]
steps = pd.read_csv(R / "t4a_large_static_steps.csv")
fig, axs = plt.subplots(1, len(fams), figsize=(4 * len(fams), 3.6), sharey=True)
for ax, f in zip(axs, fams):
    d = P["paths3"][("gpurentalprices", f)]
    ax.plot(dates(d.index), 100 * (np.exp(d.static_index) - 1), color="tab:blue", label="static providers, equal weight")
    ax.plot(dates(d.index), 100 * (np.exp(d.all_offer_median) - 1), color="tab:red", label="median of all offers")
    ax.plot(dates(d.index), 100 * (np.exp(d.dynamic) - 1), color="tab:orange", lw=0.8, label="dynamic providers' median")
    for _, s in steps[steps.fams.str.contains(f.split()[0])].iterrows():
        ax.axvline(dt.date.fromisoformat(s.date), color="grey", lw=0.5, ls=":")
        ax.text(dt.date.fromisoformat(s.date), ax.get_ylim()[1] if False else 52, s.provider[:6], rotation=90, fontsize=6, va="top")
    ax.set_title(f + " on demand (gpurentalprices)", fontsize=9)
    ax.tick_params(axis="x", labelrotation=45, labelsize=7)
    ax.set_ylim(-15, 55)
axs[0].set_ylabel("change since 4 Aug 2026 (%)")
axs[0].legend(fontsize=6, loc="upper left")
fig.suptitle("Static rate cards rose in a few dated steps; the posted median rose about twice as much", fontsize=10)
fig.tight_layout(); fig.savefig(R / "fig3_static_vs_headline.png", dpi=130); plt.close(fig)

# F4 dispersion over time
d5 = pd.read_csv(R / "t5a_dispersion_weekly.csv")
fig, ax = plt.subplots(figsize=(8, 4))
for f, color in zip(["A100 40GB", "A100 80GB", "H100", "H200", "B200", "B300"], plt.cm.viridis(np.linspace(0, 0.9, 6))):
    for s, ls in (("gpurentalprices", "-"), ("fastgpu_daily", "--")):
        x = d5[(d5.fam == f) & (d5.src == s) & (d5.n_prov >= 4)]
        ax.plot(pd.to_datetime(x.week_start), x.p75_p25, ls, color=color, label=f if s == "gpurentalprices" else None)
ax.set_ylabel("75th / 25th percentile of provider prices")
ax.set_xlabel("week (solid gpurentalprices, dashed fastgpu)")
ax.set_title("Spread of on-demand prices across providers for the same GPU", fontsize=10)
ax.legend(fontsize=7, ncol=3)
fig.tight_layout(); fig.savefig(R / "fig4_dispersion.png", dpi=130); plt.close(fig)

# F5 per-unit price by chip, one dot per provider, last 4 weeks
pp = pd.read_pickle("runs/insight/last4.pkl")
U = {"A100 80GB": 1.0, "H100": 2.46, "H200": 2.72, "B200": 7.91, "B300": 8.77}
fig, ax = plt.subplots(figsize=(8, 4))
for i, f in enumerate(U):
    for j, (s, m) in enumerate((("gpurentalprices", "o"), ("fastgpu_daily", "s"))):
        v = pp[(pp.src == s) & (pp.fam == f)].price / U[f]
        ax.scatter(np.full(len(v), i + (j - 0.5) * 0.25) + np.random.default_rng(i).uniform(-0.06, 0.06, len(v)), v, marker=m, s=14, alpha=0.7,
                   color="tab:blue" if j == 0 else "tab:green", label=s if i == 0 else None)
ax.set_xticks(range(len(U)), list(U))
ax.set_yscale("log")
ax.set_ylabel("USD per hour per A100-equivalent\nunit of inference work")
ax.set_title("Older chips cost more per unit of work at almost every provider\n(one dot per provider, 12 Oct to 6 Nov)", fontsize=9)
ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(R / "fig5_per_unit.png", dpi=130); plt.close(fig)
print("ok")
