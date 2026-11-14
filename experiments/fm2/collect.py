"""Dev only. Run one pretrained model over the dev origins through the harness and save its quantile grid.
Usage: collect.py TAG 'PARAMS_JSON' [--universe U]   -> runs/fm2/grid_TAG_U.parquet and prints the centre=last score."""
import json, os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "2")
from gpuf import harness, methods, splits
a = sys.argv[1:]
uni = a[a.index("--universe") + 1] if "--universe" in a else "rental_headline"
p = json.loads(a[1])
out = f"runs/fm2/grid_{a[0]}_{uni}.parquet"
p.update(dump=out, n_origins=len(splits.origins("dev")), universe=uni)
t = time.time()
r = harness.evaluate(methods.get("fm2_live", **p), "dev", uni, name="fm2_live", params=p)
print(a[0], uni, f"skill={r.summary['pooled_skill']:+.4f}", f"{time.time() - t:.0f}s", out, flush=True)
