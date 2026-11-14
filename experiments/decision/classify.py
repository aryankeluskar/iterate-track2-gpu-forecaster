"""Step 2 baselines (base rate, logistic, LightGBM) and step 3 Laya zero-shot + temperature on the same cells.

usage: classify.py baselines | laya N_TRAIN N_TEST | report
"""
import json, os, sys, time
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar, minimize
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

CELLS = "runs/decision/cells.parquet"
OUT = "runs/decision"
NUM = ["dsc", "n_prov", "pos"] + [f"c{i}" for i in range(14)]
CAT = ["collector", "cls"]
K = {"y3": 3, "y5": 5}
FLAT = {"y3": 1, "y5": 2}


def metrics(p, y, k, flat):
    p = np.clip(p, 1e-6, 1); p = p / p.sum(1, keepdims=True)
    oh = np.eye(k)[y]
    move = (y != flat).astype(int)
    return dict(logloss=float(-np.log(p[np.arange(len(y)), y]).mean()), brier=float(((p - oh) ** 2).sum(1).mean()),
                acc=float((p.argmax(1) == y).mean()), auc_move=float(roc_auc_score(move, 1 - p[:, flat])) if 0 < move.mean() < 1 else np.nan)


def design(df, cols=None):
    X = df[NUM].copy()
    X["n_prov"] = X["n_prov"].fillna(-1); X["pos"] = X["pos"].fillna(0.5)
    X = X.fillna(0)
    X["log_dsc"] = np.log1p(df["dsc"]); X["chg3"] = (df[[f"c{i}" for i in range(11, 14)]].abs() > 0).any(axis=1).astype(float)
    X["absum"] = df[[f"c{i}" for i in range(14)]].abs().sum(1)
    X["h"] = df["horizon_days"]
    X = pd.concat([X, pd.get_dummies(df[CAT].astype(str)).astype(float)], axis=1)
    return X.reindex(columns=cols, fill_value=0.0) if cols is not None else X


def baselines(tr, te):
    out = {}
    for yk, k in K.items():
        # base rate by collector x horizon, Laplace-smoothed
        cnt = tr.groupby(["collector", "horizon_days"])[yk].value_counts().unstack(fill_value=0).reindex(columns=range(k), fill_value=0) + 0.5
        br = cnt.div(cnt.sum(1), axis=0)
        glob = np.bincount(tr[yk], minlength=k) + 0.5; glob = glob / glob.sum()
        key = pd.MultiIndex.from_frame(te[["collector", "horizon_days"]])
        p = br.reindex(key).to_numpy().copy(); p[np.isnan(p).any(1)] = glob
        out[(yk, "base_rate")] = p
        Xtr = design(tr); Xte = design(te, Xtr.columns)
        mu, sd = Xtr.mean(), Xtr.std().replace(0, 1)
        lr = LogisticRegression(C=1.0, max_iter=2000).fit((Xtr - mu) / sd, tr[yk])
        pl = np.zeros((len(te), k)); pl[:, lr.classes_] = lr.predict_proba((Xte - mu) / sd)
        out[(yk, "logistic")] = pl
        import lightgbm as lgb
        g = lgb.LGBMClassifier(objective="multiclass", n_estimators=300, learning_rate=0.03, num_leaves=15,
                               min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                               verbose=-1, n_jobs=2).fit(Xtr, tr[yk])
        pg = np.zeros((len(te), k)); pg[:, g.classes_] = g.predict_proba(Xte)
        out[(yk, "lightgbm")] = pg
    return out


# ---------------- Laya ----------------
QTEXT = {
    "y3": ("Over the next {h} days, will this posted GPU rental median price be lower, unchanged or higher than today?",
           {"lower": "the median price on day +{h} is below today's", "unchanged": "the median price on day +{h} equals today's exactly",
            "higher": "the median price on day +{h} is above today's"}),
    "y5": ("By how much will this posted GPU rental median price change over the next {h} days?",
           ["down more than 5%", "down a little (0 to 5%)", "unchanged", "up a little (0 to 5%)", "up more than 5%"]),
}


def questions(h):
    q3, c3 = QTEXT["y3"]; q5, c5 = QTEXT["y5"]
    return {"y3": {"type": "choice", "instructions": q3.format(h=h), "criteria": {k: v.format(h=h) for k, v in c3.items()}},
            "y5": {"type": "score", "instructions": q5.format(h=h), "criteria": c5}}


def state(r):
    r = r._asdict() if hasattr(r, "_asdict") else r
    r = type("R", (), r)
    return {"collector": r.collector, "instrument_class": r.cls, "gpu": r.gpu, "pricing_tier": r.tier,
            "daily_pct_changes_last14": [float(getattr(r, f"c{i}")) if np.isfinite(getattr(r, f"c{i}")) else None for i in range(14)],
            "days_since_last_change": int(r.dsc), "n_providers": None if not np.isfinite(r.n_prov) else int(r.n_prov),
            "median_position_p25_p75": None if not np.isfinite(r.pos) else round(float(r.pos), 2)}


def subsample(df, n, seed):
    ix = [g.sample(min(len(g), max(1, int(round(n * len(g) / len(df))))), random_state=seed).index
          for _, g in df.groupby(["collector", "horizon_days"])]
    return df.loc[np.concatenate(ix)]


def run_laya(sub, agent):
    logp = {yk: np.zeros((len(sub), k)) for yk, k in K.items()}
    pos = {ix: i for i, ix in enumerate(sub.index)}
    for h, g in sub.groupby("horizon_days"):
        qs = questions(h)
        states = [state(r) for r in g.itertuples()]
        res = agent.predict_batch(states, qs, batch_size=32)
        for ix, r in zip(g.index, res):
            a = r["answers"]
            p3 = np.array([a["y3"]["probabilities"][k] for k in ("lower", "unchanged", "higher")])
            p5 = np.array([a["y5"]["probabilities"][str(i)] for i in range(5)])
            logp["y3"][pos[ix]] = np.log(np.clip(p3, 1e-6, 1)); logp["y5"][pos[ix]] = np.log(np.clip(p5, 1e-6, 1))
    return logp


def softmax(z):
    z = z - z.max(1, keepdims=True); e = np.exp(z); return e / e.sum(1, keepdims=True)


def fit_temp(z, y):
    f = lambda lt: -np.log(softmax(z / np.exp(lt))[np.arange(len(y)), y] + 1e-12).mean()
    return float(np.exp(minimize_scalar(f, bounds=(-4, 4), method="bounded").x))


def fit_temp_bias(z, y, k):
    def f(w):
        p = softmax(z / np.exp(w[0]) + np.r_[0, w[1:]])
        return -np.log(p[np.arange(len(y)), y] + 1e-12).mean()
    return minimize(f, np.zeros(k), method="L-BFGS-B").x


def main():
    df = pd.read_parquet(CELLS)
    tr, te = df[df.split == "train"].copy(), df[df.split == "test"].copy()
    mode = sys.argv[1]
    if mode == "baselines":
        res = baselines(tr, te)
        rows = [dict(q=yk, model=m, subset=s, n=int(msk.sum()), **metrics(p[msk], te[yk].to_numpy()[msk], K[yk], FLAT[yk]))
                for (yk, m), p in res.items() for s, msk in (("all", np.ones(len(te), bool)), ("headline", te.headline.to_numpy()))]
        print(pd.DataFrame(rows).round(4).to_string())
        np.savez(f"{OUT}/baseline_probs.npz", **{f"{yk}_{m}": p for (yk, m), p in res.items()}, index=te.index.to_numpy())
    elif mode == "laya":
        import torch, laya
        torch.set_num_threads(2)
        ntr, nte = int(sys.argv[2]), int(sys.argv[3])
        agent = laya.load("convaiinnovations/laya", device="mps")
        agent.temperature = [1.0, 1.0, 1.0]; agent.temperature_by_options = {}
        for name, d, n in (("train", tr, ntr), ("test", te, nte)):
            sub = subsample(d, n, 0); t = time.time()
            lp = run_laya(sub, agent)
            print(name, len(sub), "cells", round(time.time() - t, 1), "s", flush=True)
            out = sub[["series_id", "origin_day", "horizon_days"]].copy()
            for yk, k in K.items():
                for j in range(k):
                    out[f"{yk}_lp{j}"] = lp[yk][:, j]
            out.to_parquet(f"{OUT}/laya_zs_{name}.parquet")
    elif mode == "report":
        report(df, tr, te)


def report(df, tr, te):
    key = ["series_id", "origin_day", "horizon_days"]
    ztr = pd.read_parquet(f"{OUT}/laya_zs_train.parquet").merge(df, on=key)
    zte = pd.read_parquet(f"{OUT}/laya_zs_test.parquet").merge(df.reset_index(), on=key)
    b = np.load(f"{OUT}/baseline_probs.npz", allow_pickle=True)
    rowpos = pd.Series(np.arange(len(b["index"])), index=b["index"])
    ix = rowpos.loc[zte["index"]].to_numpy()
    rows = []
    for yk, k in K.items():
        cols = [f"{yk}_lp{j}" for j in range(k)]
        Ztr, Zte = ztr[cols].to_numpy(), zte[cols].to_numpy()
        ytr, yte = ztr[yk].to_numpy(), zte[yk].to_numpy()
        T = fit_temp(Ztr, ytr); w = fit_temp_bias(Ztr, ytr, k)
        cands = {"laya_raw(T=1)": softmax(Zte), f"laya_temp(T={T:.2f})": softmax(Zte / T),
                 "laya_temp+bias": softmax(Zte / np.exp(w[0]) + np.r_[0, w[1:]])}
        for m in ("base_rate", "logistic", "lightgbm"):
            cands[m] = b[f"{yk}_{m}"][ix]
        hl = zte.headline.to_numpy()
        for m, p in cands.items():
            for s, msk in (("all", np.ones(len(yte), bool)), ("headline", hl)):
                rows.append(dict(q=yk, model=m, subset=s, n=int(msk.sum()), **metrics(p[msk], yte[msk], k, FLAT[yk])))
        # does Laya carry any signal: rank correlation of its P(move) with truth inside train
        print(yk, "train AUC move, raw laya:", round(roc_auc_score((ytr != FLAT[yk]).astype(int), 1 - softmax(Ztr)[:, FLAT[yk]]), 4),
              "mean raw probs test:", softmax(Zte).mean(0).round(3), "std of P(flat) test:", round(softmax(Zte)[:, FLAT[yk]].std(), 4))
    r = pd.DataFrame(rows).round(4)
    print(r.to_string())
    r.to_csv("experiments/decision/results_zeroshot.csv", index=False)


if __name__ == "__main__":
    main()
