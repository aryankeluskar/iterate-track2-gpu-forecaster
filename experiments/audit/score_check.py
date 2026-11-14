"""Audit item 3: reproduce logged dev numbers with the organisers' starter/scorer.py (subprocess, backtest mode),
compare with the fast scorer cell by cell, and check that zero-width forecasts are scored as valid.
Dev split only. Usage: PYTHONPATH=src .venv/bin/python experiments/audit/score_check.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from gpuf import data, harness, methods

OUT = Path(__file__).resolve().parent / "results"
WORK = data.ROOT / "runs" / "audit" / "official"
MIX = {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}
CASES = {
    "drift": ("drift", {}),
    "mix": ("mix", MIX),
    "mix+analog": ("ens", {"members": [["mix", MIX], ["analog", {"pool": "all", "k": 600, "drop": ["n14", "sign"]}]]}),
    "zero_width_last": ("last_value", {}),
}
LOGGED = {"drift": 0.0886, "mix": 0.1691, "mix+analog": 0.1999, "zero_width_last": 0.0}
res = {}
for name, (m, p) in CASES.items():
    r = harness.evaluate(methods.get(m, **p), "dev", "rental_headline", name=m, params=p)
    off = r.official(WORK / name.replace("+", "_"))
    c = pd.read_csv(WORK / name.replace("+", "_") / "cells.csv")
    status_counts = c["status"].value_counts().to_dict()
    c = c[c["status"] == "scored"]
    fast = r.cells
    k = ["series_id", "origin_date", "horizon_days"]
    mm = fast.merge(c, on=k, suffixes=("_f", "_o"))
    out = {"logged": LOGGED[name], "fast_pooled_skill": r.summary["pooled_skill"], "official_pooled_skill": off.get("pooled_skill"),
           "official_report_headline": {k: v for k, v in (off["report"] or {}).items() if "skill" in k or k == "status"}, "official_cell_status": status_counts,
           "official_status": (off["report"] or {}).get("status"), "returncode": off["returncode"],
           "n_cells_fast": int(len(fast)), "n_cells_official": int(len(c)), "n_matched": int(len(mm)),
           "max_abs_cell_loss_diff": float(np.max(np.abs(mm["loss_f"] - mm["loss_o"]))),
           "max_abs_cell_baseline_diff": float(np.max(np.abs(mm["baseline_loss_f"] - mm["baseline_loss_o"]))),
           "agree_6dp": bool(round(r.summary["pooled_skill"], 6) == round(off.get("pooled_skill"), 6)),
           "fast_counts": r.summary["counts"], "official_counts": (off["report"] or {}).get("counts")}
    # independent recomputation of the pinball loss from the official per-cell truths and quantiles
    y = c["y"].to_numpy()
    pin = lambda q, t: np.maximum(t * (y - q), (t - 1) * (y - q))
    own = (pin(c["q10"].to_numpy(), .1) + pin(c["q50"].to_numpy(), .5) + pin(c["q90"].to_numpy(), .9)) / 3
    base = (pin(c["baseline_q10"].to_numpy(), .1) + pin(c["baseline_q50"].to_numpy(), .5) + pin(c["baseline_q90"].to_numpy(), .9)) / 3
    out["hand_pooled_skill"] = float(1 - own.mean() / base.mean())
    out["zero_width_rows_scored"] = int(((c["q10"] == c["q50"]) & (c["q50"] == c["q90"])).sum())
    res[name] = out
    print(name, json.dumps(out), flush=True)
(OUT / "score_check.json").write_text(json.dumps(res, indent=1, default=str))
