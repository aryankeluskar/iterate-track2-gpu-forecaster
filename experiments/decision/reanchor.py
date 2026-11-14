"""ReAnchor-style check: multinomial logistic on Laya's 8 zero-shot log-probs (3-way + 5-level), fit on train subsample."""
import sys, os
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
sys.path.insert(0, os.path.dirname(__file__))
from classify import metrics, design, CELLS
key = ["series_id", "origin_day", "horizon_days"]
df = pd.read_parquet(CELLS)
tag = sys.argv[1] if len(sys.argv) > 1 else "zs"
tr = pd.read_parquet(f"runs/decision/laya_{tag}_train.parquet").merge(df, on=key)
te = pd.read_parquet(f"runs/decision/laya_{tag}_test.parquet").merge(df, on=key)
L = [c for c in tr.columns if "_lp" in c]
for name, cols in (("laya logprobs only", L), ("laya + horizon/collector", L + ["h", "collector_afhubbard", "collector_fastgpu_daily", "collector_gpurentalprices"])):
    Xtr = pd.concat([tr[L], design(tr)], axis=1)[cols]; Xte = pd.concat([te[L], design(te, design(tr).columns)], axis=1)[cols]
    for yk, k, fl in (("y3", 3, 1), ("y5", 5, 2)):
        lr = LogisticRegression(max_iter=3000).fit(Xtr, tr[yk])
        p = np.zeros((len(te), k)); p[:, lr.classes_] = lr.predict_proba(Xte)
        print(tag, name, yk, {a: round(b, 4) for a, b in metrics(p, te[yk].to_numpy(), k, fl).items()})
# fairness: same 2k train rows, numeric features
import lightgbm as lgb
Xtr, Xte = design(tr), design(te, design(tr).columns)
mu, sd = Xtr.mean(), Xtr.std().replace(0, 1)
for yk, k, fl in (("y3", 3, 1),):
    for nm, mdl, a, b in (("logistic_2k", LogisticRegression(max_iter=3000), (Xtr - mu) / sd, (Xte - mu) / sd),
                          ("lightgbm_2k", lgb.LGBMClassifier(objective="multiclass", n_estimators=300, learning_rate=0.03, num_leaves=15,
                                                             min_child_samples=40, verbose=-1, n_jobs=2), Xtr, Xte)):
        mdl.fit(a, tr[yk]); p = np.zeros((len(te), k)); p[:, mdl.classes_] = mdl.predict_proba(b)
        print(tag, nm, yk, {x: round(y, 4) for x, y in metrics(p, te[yk].to_numpy(), k, fl).items()})
