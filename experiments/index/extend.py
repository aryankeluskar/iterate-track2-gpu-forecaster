"""Descriptive extension (after the acceptance test was settled; no rule changed): the index through 2026-11-06 for
every gpuf.panel series among the 37 scored series, data_out/balanced_index.csv, and one figure per frontier chip.
Dates after 2026-10-06 are outside the tested window.
Run: OMP_NUM_THREADS=2 PYTHONPATH=src .venv/bin/python experiments/index/extend.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from gpuf import data, panel  # noqa: E402
from gpuf import index as gi  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "results"
CUT, TSTART, TEND = gi.ordinal("2026-11-06"), gi.ordinal("2026-09-08"), gi.ordinal("2026-10-06")

tabs = []
for sid in sorted(data.universe("rental_headline")):
    if not panel.supported(sid):
        continue
    src, cls, gpu, tier = panel.parse_sid(sid)
    t = gi.compute(src, gpu, cls, tier, CUT)
    t.insert(0, "series_id", sid)
    t["tested_contract"] = (cls == gi.CLS) and (tier == gi.TIER)
    t["in_tested_window"] = (t.day >= TSTART) & (t.day <= TEND)
    tabs.append(t)
T = pd.concat(tabs, ignore_index=True)
cols = ["date", "collector", "gpu_model", "index_level", "daily_change", "providers", "offers", "largest_provider_share",
        "one_provider_removal", "valid", "series_id", "instrument_class", "pricing_tier", "posted_median",
        "providers_present", "offers_present", "largest_provider", "anchor", "observed", "tested_contract", "in_tested_window"]
T[cols].to_csv(ROOT / "data_out" / "balanced_index.csv", index=False, float_format="%.6g")

# descriptive: collector disagreement outside the tested window (target days 2026-10-14..2026-11-06), same 11 pairs
import contextlib, io, sys  # noqa: E401,E402
sys.path.insert(0, str(Path(__file__).parent))
with contextlib.redirect_stdout(io.StringIO()):
    import acceptance as AP  # noqa: E402  (same pair list; re-running it rewrites identical files)
tdays = np.arange(gi.ordinal("2026-10-14"), CUT + 1)
P = {s: gi.paths(*s, to_day=CUT) for s in {s for p in AP.PAIRS for s in p}}
d7 = lambda p, c: p[c].reindex(tdays).to_numpy() - p[c].reindex(tdays - 7).to_numpy()
ext = {c: float(np.nanmean([np.abs(d7(P[a], c) - d7(P[b], c)) for a, b in AP.PAIRS])) for c in ["index_log", "posted_log", "balanced_log"]}
ext["n_pair_days"] = len(tdays) * len(AP.PAIRS)
sub = T[T.tested_contract & (T.day > TEND)]
ext["invalid_days_share_rate_card_series"] = float((~sub.valid & ~sub.anchor).mean())
ext["mean_largest_provider_share_on_moving_days"] = float(sub.largest_provider_share.mean())
(OUT / "extension_descriptive.json").write_text(json.dumps(ext, indent=2))
print(json.dumps(ext, indent=2))

CHIPS = {"H100": [("fastgpu_daily", "H100 SXM 80GB"), ("gpurentalprices", "H100 SXM 80GB"), ("gpurentalprices", "H100 80GB")],
         "H200": [("fastgpu_daily", "H200"), ("gpurentalprices", "H200")],
         "B200": [("fastgpu_daily", "B200"), ("gpurentalprices", "B200")],
         "B300": [("fastgpu_daily", "B300"), ("gpurentalprices", "B300")],
         "A100 80GB": [("fastgpu_daily", "A100 80GB"), ("gpurentalprices", "A100 SXM 80GB")]}
COLORS = ["tab:blue", "tab:orange", "tab:green"]
for chip, panels in CHIPS.items():
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(10, 6.2), sharex=True, gridspec_kw=dict(height_ratios=[3, 1]))
    for (src, gpu), c in zip(panels, COLORS):
        t = T[(T.collector == src) & (T.gpu_model == gpu) & T.tested_contract].copy()
        x = pd.to_datetime(t.date)
        lab = f"{'fastgpu' if src.startswith('fast') else 'gpurentalprices'} {gpu}"
        ax.plot(x, t.posted_median, color=c, ls="--", lw=1.1, alpha=0.8, label=f"{lab}: posted median")
        ax.plot(x, t.index_level, color=c, lw=2.0, label=f"{lab}: index")
        inv = ~t.valid & ~t.anchor
        ax.scatter(x[inv], t.index_level[inv], color=c, marker="x", s=18, zorder=3)
        ax2.plot(x, t.providers, color=c, lw=1.2)
    for a in (ax, ax2):
        a.axvspan(pd.Timestamp("2026-09-08"), pd.Timestamp("2026-10-06"), color="0.92", zorder=0)
        a.axvline(pd.Timestamp("2026-10-06"), color="0.4", lw=0.8)
        for d in ("2026-10-01", "2026-10-05"):
            a.axvline(pd.Timestamp(d), color="tab:red", lw=0.7, ls=":")
    ymax = ax.get_ylim()[1]
    ax.text(pd.Timestamp("2026-09-09"), ymax, "tested window", va="top", fontsize=8, color="0.3")
    ax.text(pd.Timestamp("2026-10-07"), ymax, "outside tested window (descriptive)", va="top", fontsize=8, color="0.3")
    ax.text(pd.Timestamp("2026-10-01"), ax.get_ylim()[0], " Nebius", fontsize=7, color="tab:red", va="bottom")
    ax.text(pd.Timestamp("2026-10-05"), ax.get_ylim()[0], " Jarvislabs", fontsize=7, color="tab:red", va="bottom")
    ax.set_ylabel("USD per GPU-hour")
    ax.set_title(f"{chip}, on-demand rate cards: posted median (dashed) vs provider-balanced index (solid); x = invalid day")
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(0, 0.93))
    ax2.set_ylabel("matched\nproviders")
    fig.tight_layout()
    fig.savefig(OUT / f"fig_{chip.replace(' ', '_')}.png", dpi=120)
    plt.close(fig)
print("rows", len(T), "series", T.series_id.nunique())
