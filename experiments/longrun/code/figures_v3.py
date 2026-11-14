"""Figures for longrun_v3.md (after panel_v3.py and scen_v3.py)."""
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[3]
RES = ROOT / "experiments/longrun/results"

lv = pd.read_csv(RES / "v3_t1b_levels_two_definitions.csv").set_index("chip")
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
x = np.arange(len(lv))
for j, (col, lab) in enumerate([("v2_units", "v2: collector-provider units"), ("v3_unique", "v3: unique providers")]):
    axs[0].bar(x + (j - 0.5) * 0.38, lv[f"{col}_median"], 0.38, label=lab)
    axs[1].bar(x + (j - 0.5) * 0.38, lv[f"{col}_ratio_vs_frontier"], 0.38, label=lab)
    for i, c in enumerate(lv.index):
        axs[0].text(i + (j - 0.5) * 0.38, lv.loc[c, f"{col}_median"] + 0.1, f"n={lv.loc[c, col + '_n']}", ha="center", fontsize=6)
for ax, yl in zip(axs, ["USD per GPU-hour, median of static rate cards, 6 Nov 2026", "cost per capability unit / frontier (B200, B300 min)"]):
    ax.set_xticks(x); ax.set_xticklabels(lv.index); ax.set_ylabel(yl, fontsize=8); ax.legend(fontsize=7)
axs[1].axhline(1, color="k", lw=0.6)
fig.suptitle("Base level under two provider definitions", fontsize=10)
fig.tight_layout(); fig.savefig(RES / "v3_fig1_levels_two_definitions.png", dpi=130)

v = pd.read_csv(RES / "v3_t3_value_grid.csv")
v = v[v.weights == "frozen"]
fig, axs = plt.subplots(2, 2, figsize=(9, 7))
for r, chip in enumerate(["H100", "A100"]):
    for c, m0 in enumerate([24, 36]):
        g = v[(v.chip == chip) & (v.m0 == m0)].pivot_table(index="util", columns="real_over_posted", values="q50").sort_index(ascending=False)
        ax = axs[r, c]
        im = ax.imshow(g.values / 1000, cmap="viridis", vmin=0, vmax=v[(v.chip == chip) & (v.m0 > 0)].q50.max() / 1000)
        for i in range(3):
            for j in range(3):
                ax.text(j, i, f"{g.values[i, j] / 1000:.1f}k", ha="center", va="center", color="w", fontsize=9)
        ax.set_xticks(range(3)); ax.set_xticklabels([f"{x:.2f}" for x in g.columns]); ax.set_yticks(range(3)); ax.set_yticklabels([f"{x:.3g}" for x in g.index])
        ax.set_xlabel("realised rent / posted (reserved 36 m)", fontsize=8); ax.set_ylabel("utilisation", fontsize=8)
        ax.set_title(f"{chip}, value at +{m0} months (q50, frozen weights)", fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.04, label="kUSD per GPU")
fig.tight_layout(); fig.savefig(RES / "v3_fig2_value_grid.png", dpi=130)
print("ok")
