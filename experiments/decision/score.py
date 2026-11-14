"""Step 4 scoring on rental_headline, test origins 2026-09-22..2026-10-06 only (dev split days)."""
import json
import numpy as np
from gpuf import compare, harness, methods, splits

ORIG = [d for d in splits.DEV if splits._day("2026-09-22") <= d <= splits._day("2026-10-06")]
MIX = {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}
DEC = {"path": "runs/decision/lgbm_probs.parquet"}
SPECS = {"drift": ("drift", {}), "mix": ("mix", MIX), "decision": ("decision", DEC),
         "ens_mix_decision": ("ens", {"members": [["mix", MIX], ["decision", DEC]]})}


def bucket(r):
    x = r["y"] / r["last"] - 1 if "last" in r else np.nan
    return x


res = {k: harness.evaluate(methods.get(m, **p), ORIG, "rental_headline", name=k, params=p) for k, (m, p) in SPECS.items()}
for k, r in res.items():
    c = r.cells
    print(f"{k:18s} skill={r.summary['pooled_skill']:+.4f} n={len(c)} cov={r.summary.get('coverage', float('nan'))}")
for a in ("decision", "ens_mix_decision", "mix"):
    for b in ("drift", "mix"):
        if a == b:
            continue
        d = compare.paired(res[a].cells, res[b].cells)
        print(f"{a} - {b}: d_skill={d['d_pooled_skill']:+.4f} ci90={[round(x, 4) for x in d.get('ci90_d_skill', d.get('ci90', []))]}",
              {k: v for k, v in d.items() if 'ci' in k})
c, cm, cd = res["decision"].cells, res["mix"].cells, res["drift"].cells
B = c["baseline_loss"].sum()
m = c.merge(cm[compare.KEY + ["loss"]], on=compare.KEY, suffixes=("", "_mix")).merge(cd[compare.KEY + ["loss"]], on=compare.KEY, suffixes=("", "_drift"))
print(m.columns.tolist())
for col in ("source_id", "horizon_days"):
    print(col, m.groupby(col).apply(lambda g: json.dumps({"vs_drift": round((g.loss_drift.sum() - g.loss.sum()) / B, 4),
                                                         "vs_mix": round((g.loss_mix.sum() - g.loss.sum()) / B, 4)})).to_dict())
