"""Does a provider's event on one series raise the chance of an event on its other series over the next 1-3 days?
Dev rows only (day <= 2026-10-13). Unit: (provider, series B, day t) with the provider present in B on day t.
Treated: the provider had an event on some other series of the same collector on day t. Outcome: event of that
provider on B in days t+1..t+3 (comp = enter/exit; any = also repricing)."""
import json
import numpy as np
import pandas as pd
from gpuf import panel, splits
from gpuf.methods.fragility import build_events

CUT = splits.DEV[-1] + 7
df = panel.load()
df = df[df.day <= CUT]
ev = build_events(df)
P = ev["P"]
pres = df.groupby(["src", "provider", "day"])["key"].size()
ser = df.assign(sid=list(zip(df.src, df.cls, df.gpu, df.tier))).groupby(["src", "provider", "day"])["sid"].agg(lambda s: set(s))
out = {}
for kind in ("comp", "any"):
    P["e"] = (P.comp > 0) if kind == "comp" else ((P.comp + P.rep) > 0)
    E = P[P.e].groupby(["src", "provider", "day"])["sid"].agg(lambda s: set(s))
    evset = {(r.src, r.provider, r.day, r.sid) for r in P[P.e].itertuples()}
    for win in (1, 3):
        tr = [0, 0]; ct = [0, 0]
        for (src, prov, t), sids in ser.items():
            if t > CUT - win:
                continue
            others = E.get((src, prov, t), set())
            for s in sids:
                hit = any((src, prov, t + k, s) in evset for k in range(1, win + 1))
                treated = len(others - {s}) > 0
                (tr if treated else ct)[0] += 1
                (tr if treated else ct)[1] += hit
        out[f"{kind}_win{win}"] = dict(treated_n=tr[0], treated_hit=tr[1], treated_rate=round(tr[1] / max(tr[0], 1), 4),
                                       base_n=ct[0], base_hit=ct[1], base_rate=round(ct[1] / max(ct[0], 1), 4),
                                       ratio=round((tr[1] / max(tr[0], 1)) / max(ct[1] / max(ct[0], 1), 1e-9), 2))
print(json.dumps(out, indent=1))
json.dump(out, open("experiments/fragility/results/cluster_test.json", "w"), indent=1)
