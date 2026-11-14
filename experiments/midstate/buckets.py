"""Dev only: cases per rate bucket at early/mid/late origins, pooled in (collector, class), h=3 and h=7."""
import datetime as dt, numpy as np, pandas as pd
from gpuf import panel
from gpuf.methods import midstate as M
for src, cls in [("fastgpu_daily", "neocloud_rate_card"), ("gpurentalprices", "neocloud_rate_card")]:
    for od in ["2026-08-18", "2026-09-15", "2026-10-06"]:
        o = dt.date.fromisoformat(od).toordinal()
        for h in (3, 7):
            pt = M.provider_tables(src, o, 14)
            if pt is None: print(src, od, "no pairs"); continue
            pi, d0, C = pt
            n = np.zeros(5, int); nown = np.zeros(5, int); ns = 0
            for pk in panel.group_series(f"{src}.{cls}.X.Y.median"):
                t = M.panel_cases(pk, o, pi, d0, C, 14)
                bk = np.where((t["nn"] >= 5) & ~np.isnan(t["rate"]), np.searchsorted([0.02, 0.15, 0.5], t["rate"], side="right"), -1)
                j = np.searchsorted(t["day"], t["day"] + h); ok = j < len(t["day"]); i = np.nonzero(ok)[0]; j = j[ok]
                m = t["day"][j] == t["day"][i] + h; b = bk[i[m]]
                for q in range(-1, 4): n[q + 1] += (b == q).sum()
            print(src, cls, "origin", od, "h", h, "cases [unknown,<2%,2-15%,15-50%,>50%]:", n.tolist())
