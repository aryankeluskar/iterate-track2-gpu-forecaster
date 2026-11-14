import pandas as pd
from sweep import *
rows = {}
base = dict(k=600, drop=["n14", "sign"])
V = {"self k300": dict(pool="self", k=300, drop=["n14", "sign"]), "cc": dict(pool="cc", **base), "class (cross-collector)": dict(pool="class", **base),
     "all": dict(pool="all", **base), "all excl afhubbard": dict(pool="all", excl=["afhubbard"], **base),
     "class excl afhubbard": dict(pool="class", excl=["afhubbard"], **base),
     "all excl fastgpu+gpurp (afhubbard+tanod only)": dict(pool="all", excl=["fastgpu_daily", "gpurentalprices"], **base),
     "all, full features cc-like (drop none)": dict(pool="all", k=600)}
for n, p in V.items():
    c = cells("analog", p); g = c.groupby("source_id")
    rows[n] = {**(1 - g.loss.sum() / g.baseline_loss.sum()).round(3).to_dict(), "pooled": round(1 - c.loss.sum() / c.baseline_loss.sum(), 3)}
d = cells("drift", {}); g = d.groupby("source_id"); rows["drift"] = {**(1 - g.loss.sum() / g.baseline_loss.sum()).round(3).to_dict(), "pooled": round(1 - d.loss.sum() / d.baseline_loss.sum(), 3)}
x = cells(*MIX); g = x.groupby("source_id"); rows["mix"] = {**(1 - g.loss.sum() / g.baseline_loss.sum()).round(3).to_dict(), "pooled": round(1 - x.loss.sum() / x.baseline_loss.sum(), 3)}
print(pd.DataFrame(rows).T.to_string())
