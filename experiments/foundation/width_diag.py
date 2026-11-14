"""Dev only. Why does Chronos's width (last-value centre) work? Compare interval shape with mix and drift."""
import numpy as np, pandas as pd
from gpuf import harness, methods, compare
M = {"drift": ("drift", {}), "mix": ("mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}),
     "chronos_last": ("chronos", {"centre": "last"})}
R = {k: harness.evaluate(methods.get(m, **p), "dev", "rental_headline", name=m, params=p).cells for k, (m, p) in M.items()}
live = (R["drift"]["q10"] != R["drift"]["q90"]).to_numpy()
rows = []
for k, c in R.items():
    c = c.copy()
    c["up"] = np.log(c["q90"] / c["q50"]); c["dn"] = np.log(c["q50"] / c["q10"])
    c["move"] = np.abs(np.log(c["y"] / c["baseline"]))
    c["below"] = c["y"] < c["q10"]; c["above"] = c["y"] > c["q90"]
    for h, g in c[live].groupby("horizon_days"):
        rows.append(dict(method=k, h=h, skill=1 - g["loss"].sum() / g["baseline_loss"].sum(), up=g["up"].median(), dn=g["dn"].median(),
                         below=g["below"].mean(), above=g["above"].mean(),
                         width_move_corr=np.corrcoef((g["up"] + g["dn"]).rank(), g["move"].rank())[0, 1],
                         loss_q10=g["loss_q10"].sum() / g["baseline_loss"].sum() / 3, loss_q50=g["loss_q50"].sum() / g["baseline_loss"].sum() / 3,
                         loss_q90=g["loss_q90"].sum() / g["baseline_loss"].sum() / 3))
print(pd.DataFrame(rows).round(4).to_string(index=False))
