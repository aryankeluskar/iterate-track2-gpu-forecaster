"""Fixed forecaster + activity gate (no per-class model choice), ensembles, and gate diagnostics."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "experiments/allrental")
import router as R

def ens(names, s=1.0):
    lq = np.mean([np.log(R.Q[n]) for n in names], 0)
    q = np.exp(lq)
    l50 = lq[:, 1]
    return R.loss_of(np.exp(l50 + s * (lq[:, 0] - l50)), q[:, 1], np.exp(l50 + s * (lq[:, 2] - l50)))

E = {"ens_mc": ["mix", "chronos"], "ens_mct": ["mix", "chronos", "timesfm"], "ens_mctg": ["mix", "chronos", "timesfm", "gbm"],
     "ens_3mix": ["mix", "mix_cls", "mix_k5"], "ens_3mix_ct": ["mix", "mix_cls", "mix_k5", "chronos", "timesfm"]}
for k, v in E.items():
    for s in (0.75, 1.0):
        R.L[f"{k}@{s}"] = ens(v, s)
if __name__ == "__main__":
    rows = []
    for k in ["mix@1.0", "mix_cls@1.0"] + [f"{e}@{s}" for e in E for s in (0.75, 1.0)]:
        rows.append(R.report(k, R.L[k]))
        for n, m in ((14, 1), (30, 1), (30, 2), (60, 1), (60, 2), (60, 3)):
            a = R.ACT[n] >= m
            l = np.where(a, R.L[k], R.B)
            rows.append(R.report(f"  {k} gate n{n} m{m}", l))
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
    print(pd.DataFrame(rows).to_string(index=False))
    # gate diagnostics: share of cells gated, and mix loss minus LV loss on gated cells
    for n, m in ((30, 1), (60, 1), (60, 2)):
        g = R.ACT[n] < m
        print(f"n{n} m{m}: gated cells {g.mean():.3f}, LV-loss share in gated {R.B[g].sum()/R.B.sum():.3f}, "
              f"mix excess on gated {(R.L['mix@1.0'][g]-R.B[g]).sum()/R.B.sum():+.4f}, head cells gated {(g & R.base['head'].to_numpy()).sum()}")
