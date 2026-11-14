"""Step 1 check: panel medians reproduce the scored series (days <= 2026-10-13)."""
import time
import numpy as np
from gpuf import data, panel, splits
from gpuf.data import starter_common as sc
CUT = sc.day_of(sc.parse_date("2026-10-13"))
t = time.time(); panel.load(); print("load s", round(time.time() - t, 1), len(panel.load()))
store = data.load_store(data.series_path())
tot = ok = 0; carry = 0
for sid in data.universe("rental_headline"):
    if not panel.supported(sid):
        print("fallback", sid); continue
    d, v = store.history(sid, CUT)
    m = panel.daily_median(sid, CUT)
    a = m.reindex(d)
    have = ~np.isnan(a.to_numpy())
    carry += int((~have).sum())
    good = np.isclose(a.to_numpy()[have], v[have], rtol=0, atol=5e-4)
    tot += int(have.sum()); ok += int(good.sum())
    if not good.all():
        print(sid, "mismatch", int((~good).sum()), "of", int(have.sum()))
print("series-days matched", ok, "/", tot, "; store days without panel rows", carry)
