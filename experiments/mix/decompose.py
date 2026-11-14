"""Where does mix's dev gain over drift come from: cells where drift fell back to flat (under 20 samples) or not?"""
import json, sys
from gpuf import harness, methods, compare
ref = harness.evaluate(methods.get("drift"), "dev", "rental_headline", name="drift", params={"role": "ref"})
flat = (ref.cells["q10"] == ref.cells["q90"])
B = ref.cells["baseline_loss"].sum()
print("drift flat cells: %d of %d, share of baseline loss %.2f" % (flat.sum(), len(flat), ref.cells.loc[flat, "baseline_loss"].sum() / B))
for name, p in json.load(open(sys.argv[1])):
    res = harness.evaluate(methods.get(name, **p), "dev", "rental_headline", name=name, params=p)
    m = res.cells.merge(ref.cells[compare.KEY + ["loss", "q10", "q90"]], on=compare.KEY, suffixes=("", "_d"))
    fl = m["q10_d"] == m["q90_d"]
    out = {}
    for lab, mask in (("drift_flat", fl), ("drift_live", ~fl)):
        s = m[mask]
        out[lab] = "skill %.3f vs drift %.3f" % (1 - s["loss"].sum() / s["baseline_loss"].sum(), 1 - s["loss_d"].sum() / s["baseline_loss"].sum())
    print(name, json.dumps(p), out)
