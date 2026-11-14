"""Save one method's dev forecasts for replay. Usage: dump.py OUT.parquet METHOD 'PARAMS_JSON' [--universe U] [--split dev]"""
import json, sys
from gpuf import harness, methods
a = sys.argv[1:]
split = a[a.index("--split") + 1] if "--split" in a else "dev"
uni = a[a.index("--universe") + 1] if "--universe" in a else "rental_headline"
assert split in ("dev", "dev_old"), "dev only"
p = json.loads(a[2])
r = harness.evaluate(methods.get(a[1], **p), split, uni, name=a[1], params=p)
r.cells[["series_id", "origin_day", "horizon_days", "q10", "q50", "q90"]].to_parquet(a[0])
print(a[0], len(r.cells))
