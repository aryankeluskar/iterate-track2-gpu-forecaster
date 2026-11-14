import sys, json
import numpy as np, pandas as pd
from gpuf import harness, methods, data
res = harness.evaluate(methods.get("drift"), "dev", "rental_headline", name="drift")
cells = res.cells.copy()
print(cells.columns.tolist(), len(cells), res.summary["pooled_skill"], res.summary["coverage"])
cells.to_pickle("runs/calib/drift_cells.pkl"); res.forecasts.to_pickle("runs/calib/drift_fc.pkl")
