"""Step 1: per-cell dev forecasts and losses for S0..S3 through the harness (dev split only)."""
import os, sys
os.environ.setdefault("OMP_NUM_THREADS", "2")
from gpuf import harness, methods

MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
GBM = ["gbm", {"mode": "full", "train": "all", "save_importance": False}]
CHR = ["replay", {"path": "runs/cache/chronos_last_rental_headline.parquet"}]
FM2 = ["fm2", {"grids": ["runs/fm2/grid_bs16_rental_headline.parquet"], "lo": 0.15}]
ANA = ["analog", {"pool": "all", "k": 600, "drop": ["n14", "sign"]}]
PRV = ["prov", {"L": 1, "W": 21, "gate": "dyn"}]
SYS = {"S0": ["drift", {}], "S1": MIX, "S2": ["ens", {"members": [MIX, GBM, CHR]}],
       "S3": ["ens", {"members": [MIX, GBM, CHR, FM2, ANA, PRV]}]}
for k in sys.argv[1:] or SYS:
    m, p = SYS[k]
    c = harness.evaluate(methods.get(m, **p), "dev", "rental_headline", name=m, params=p).cells
    c.to_parquet(f"runs/autopsy2/cells_{k}.parquet")
    print(k, len(c), 1 - c.loss.sum() / c.baseline_loss.sum(), flush=True)
