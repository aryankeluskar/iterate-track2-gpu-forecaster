"""Numbers for insight_v2.md: how much of the static statistics' low collector disagreement comes from pairs that never moved.
Reads experiments/insight/results/t2_cross_collector.csv (written by insight/analysis.py); computes nothing new from the pack.
Run: .venv/bin/python experiments/longrun/code/insight_v2_check.py"""
import json
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
t = pd.read_csv(ROOT / "experiments/insight/results/t2_cross_collector.csv")
flat = lambda r: r.move_days_fg == 0 and r.move_days_gr == 0
out = {}
for stat in ["static_balanced", "static_mean"]:
    s = t[t.stat == stat]
    out[stat] = {"pairs": len(s), "never_moved_either_collector": [p for p, f in zip(s.pair, s.apply(flat, axis=1)) if f],
                 "moved_in_one_collector_only": [r.pair for _, r in s.iterrows() if (r.move_days_fg == 0) != (r.move_days_gr == 0)]}
    active = s[~s.apply(flat, axis=1)].pair
    for st in ["median", "balanced_median", stat]:
        g = t[t.stat == st].set_index("pair").mad7_gap
        out[stat][f"mad7_{st}_all_pairs"] = float(g.mean())
        out[stat][f"mad7_{st}_active_pairs"] = float(g[active].mean())
    out[stat]["n_active"] = int(len(active))
json.dump(out, open(ROOT / "experiments/longrun/results/v3_insight_check.json", "w"), indent=1)
print(json.dumps(out, indent=1))
