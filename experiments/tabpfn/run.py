"""Usage: run.py NAME 'PARAMS_JSON' -> evaluates tabpfn on dev headline, saves cells to runs/tabpfn/cells_NAME.parquet."""
import os, sys, json, time
os.environ.update(OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")
from gpuf import harness, methods
name, p = sys.argv[1], json.loads(sys.argv[2])
t = time.time()
r = harness.evaluate(methods.get("tabpfn", **p), "dev", "rental_headline", name="tabpfn", params=p)
r.cells.to_parquet(f"runs/tabpfn/cells_{name}.parquet")
r.forecasts.to_parquet(f"runs/tabpfn/fc_{name}.parquet")
print(name, json.dumps(p), "skill", round(r.summary["pooled_skill"], 4), "cov", r.summary.get("coverage"), "t", round(time.time() - t))
