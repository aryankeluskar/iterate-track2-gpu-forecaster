"""Post-hoc diagnostics (NOT part of the frozen acceptance test; written after seeing its result).

Is the index's lower collector disagreement only a matter of moving less? Scale-free checks on the same 11 pairs and
22 target days: disagreement divided by the mean size of the 7-day moves, the correlation of the two collectors'
7-day changes, the result without the one pair whose fastgpu side is never valid, and without Verda.
Run: OMP_NUM_THREADS=2 PYTHONPATH=src .venv/bin/python experiments/index/posthoc.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).parent))
import acceptance as A  # noqa: E402  (re-runs the frozen test; numbers are identical)

from gpuf import index as gi  # noqa: E402

res = {}
for st in ["index", "posted", "balanced"]:
    fa = np.array([A.d7(A.P[a], st) for a, b in A.PAIRS])
    fb = np.array([A.d7(A.P[b], st) for a, b in A.PAIRS])
    amp = np.nanmean((np.abs(fa) + np.abs(fb)) / 2)
    m = np.isfinite(fa) & np.isfinite(fb)
    keep = np.array([p[0][1] != "RTX 6000 Ada" for p in A.PAIRS])
    res[st] = dict(D=float(np.nanmean(np.abs(fa - fb))), mean_abs_move=float(amp),
                   D_over_move=float(np.nanmean(np.abs(fa - fb)) / amp),
                   corr_7d=float(np.corrcoef(fa[m], fb[m])[0, 1]),
                   D_without_rtx6000ada=float(np.nanmean(np.abs(fa - fb)[keep])))
# index and posted with Verda deleted on both collectors
nv = {}
for st in ["index", "posted"]:
    g = []
    for a, b in A.PAIRS:
        pa, pb = gi.paths(*a, to_day=A.END, exclude="verda"), gi.paths(*b, to_day=A.END, exclude="verda")
        g.append(np.abs(A.d7(pa, st) - A.d7(pb, st)))
    nv[st] = float(np.nanmean(g))
res["without_verda"] = nv
(A.OUT / "posthoc.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res, indent=2))
