"""One validation query under EVAL_PROTOCOL.md Amendment 2: "blend of a direction with mix, against mix", frozen params.

Usage: PYTHONPATH=src .venv/bin/python experiments/valgate.py NAME 'CANDIDATE_JSON' [--universe rental_headline]
CANDIDATE_JSON: [method, params]. Appends one line to data_out/val_gate.jsonl; the harness logs the query in val_query_log.jsonl.
Orchestrator only. Declare the query in research-log.md and commit before running.
"""
import json, math, sys
from gpuf import compare, data, harness, methods

MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
name, cand = sys.argv[1], json.loads(sys.argv[2])
uni = sys.argv[sys.argv.index("--universe") + 1] if "--universe" in sys.argv else "rental_headline"
ref_spec = json.loads(sys.argv[sys.argv.index("--ref") + 1]) if "--ref" in sys.argv else MIX


def cells(m, p, role):
    return harness.evaluate(methods.get(m, **p), "val", uni, name=m, params={**p, "role": role} if role else p).cells


c, ref = harness.evaluate(methods.get(cand[0], **cand[1]), "val", uni, name=cand[0], params=cand[1]).cells, None
ref = harness.evaluate(methods.get(ref_spec[0], **ref_spec[1]), "val", uni, name=ref_spec[0], params=ref_spec[1]).cells
drift = harness.evaluate(methods.get("drift"), "val", uni, name="drift", params={}).cells
sk = lambda x: float(1 - x.loss.sum() / x.baseline_loss.sum())
r = compare.paired(c, ref)
p1 = r["dm_p_two_sided"] / 2 if r["dm_stat"] < 0 else 1 - r["dm_p_two_sided"] / 2   # one-sided: candidate has lower loss
h7 = c[c.horizon_days == 7]
rec = {"name": name, "universe": uni, "candidate": cand, "ref": ref_spec, "n_cells": int(len(c)), "skill": sk(c), "ref_skill": sk(ref), "drift_skill": sk(drift),
       "d_vs_ref": r["d_pooled_skill"], "ci90": r["ci90_d_pooled_skill"], "dm_stat": r["dm_stat"], "p_one_sided": p1,
       "d_vs_drift": compare.paired(c, drift)["d_pooled_skill"], "ci90_vs_drift": compare.paired(c, drift)["ci90_d_pooled_skill"],
       "coverage": float(((c.y >= c.q10) & (c.y <= c.q90)).mean()), "h7_above_q90": float((h7.y > h7.q90).mean()),
       "by_horizon": {int(h): float((ref[ref.horizon_days == h].loss.sum() - v.loss.sum()) / ref.baseline_loss.sum()) for h, v in c.groupby("horizon_days")},
       "by_source": {s: float((ref[ref.source_id == s].loss.sum() - v.loss.sum()) / ref.baseline_loss.sum()) for s, v in c.groupby("source_id")}}
with open(data.DATA_OUT / "val_gate.jsonl", "a") as f:
    f.write(json.dumps(rec) + "\n")
print(json.dumps(rec, indent=1))
