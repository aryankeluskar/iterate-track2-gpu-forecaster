"""Audit item 4: are the dev and validation intervals and p-values for the four kept directions trustworthy?

Dev headline only (no validation scoring). For each kept direction (as queried on validation) against mix:
  week-block bootstrap (project's compare.paired), number of distinct week resamples,
  DM with Newey-West lag 6 over origin days (normal and Student-t with HLN small-sample correction),
  circular moving-block bootstrap over origin days with blocks of 7 days.
Then the validation p-values (read from data_out/val_gate.jsonl, not recomputed) are re-assessed by simulating the
DM statistic on 18-day series under the null with the autocorrelation of the dev daily loss differences.
Usage: PYTHONPATH=src .venv/bin/python experiments/audit/stats.py
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

from gpuf import compare, data, harness, methods

OUT = Path(__file__).resolve().parent / "results"
MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
FM2 = ["fm2", {"grids": ["runs/fm2/grid_bs16_rental_headline.parquet"], "lo": 0.15}]
CANDS = {
    "q6_mix+analog": ["ens", {"members": [MIX, ["analog", {"pool": "all", "k": 600, "drop": ["n14", "sign"]}]]}],
    "q7_mix+prov": ["ens", {"members": [MIX, ["prov", {"L": 1, "W": 21, "gate": "dyn"}]]}],
    "q8_mix+fm2": ["ens", {"members": [MIX, FM2]}],
    "q9_fragility": ["fragility", {"mode": "mix", "boost": 20, "bkind": "any"}],
}
rng = np.random.default_rng(0)


def cells(m, p):
    return harness.evaluate(methods.get(m, **p), "dev", "rental_headline", name=m, params=p).cells


def daily(c, ref):
    k = ["series_id", "origin_day", "horizon_days"]
    m = c[k + ["loss", "baseline_loss"]].merge(ref[k + ["loss"]], on=k, suffixes=("_a", "_b"))
    g = m.groupby("origin_day").agg(a=("loss_a", "sum"), b=("loss_b", "sum"), base=("baseline_loss", "sum"), n=("loss_a", "size"))
    return g.sort_index()


def nw_dm(d, lag=6):
    T = len(d)
    e = d - d.mean()
    lrv = e @ e / T
    for k in range(1, min(lag, T - 1) + 1):
        lrv += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / T
    return d.mean() / math.sqrt(lrv / T) if lrv > 0 else float("nan")


def hln(dm, T, h=7):
    """Harvey, Leybourne and Newbold (1997) small-sample correction; compare with t(T-1)."""
    return dm * math.sqrt((T + 1 - 2 * h + h * (h - 1) / T) / T)


def block_boot(g, L=7, reps=4000):
    T = len(g)
    A, B, Bs = g["a"].to_numpy(), g["b"].to_numpy(), g["base"].to_numpy()
    nb = -(-T // L)
    starts = rng.integers(0, T, (reps, nb))
    idx = ((starts[:, :, None] + np.arange(L)) % T).reshape(reps, -1)[:, :T]
    ds = (B[idx].sum(1) - A[idx].sum(1)) / Bs[idx].sum(1)
    return [float(x) for x in np.quantile(ds, [0.05, 0.95])], float((ds <= 0).mean())


def acf(x, K):
    x = x - x.mean()
    v = x @ x / len(x)
    return np.array([1.0] + [(x[k:] @ x[:-k]) / len(x) / v for k in range(1, K + 1)])


def sim_null(d_dev, T=18, reps=20000, lag=6):
    """DM stats on T-day null series: (a) Gaussian with dev ACF up to lag 10 (tapered), (b) circular block
    bootstrap (L=7) of the centred dev series."""
    r = acf(d_dev, 10) * np.r_[1.0, 1 - np.arange(1, 11) / 11]
    C = np.array([[r[abs(i - j)] if abs(i - j) <= 10 else 0.0 for j in range(T)] for i in range(T)])
    w, V = np.linalg.eigh(C)
    Lc = V * np.sqrt(np.clip(w, 0, None))
    Z = rng.standard_normal((reps, T)) @ Lc.T
    gauss = np.array([nw_dm(z, lag) for z in Z])
    e = d_dev - d_dev.mean()
    n = len(e)
    starts = rng.integers(0, n, (reps, -(-T // 7)))
    idx = ((starts[:, :, None] + np.arange(7)) % n).reshape(reps, -1)[:, :T]
    boot = np.array([nw_dm(z, lag) for z in e[idx]])
    return gauss, boot


ref = cells(*MIX)
gate = {json.loads(l)["name"]: json.loads(l) for l in open(data.DATA_OUT / "val_gate.jsonl")}
res = {"dev_weeks": None, "directions": {}}
for name, spec in CANDS.items():
    c = cells(*spec)
    r = compare.paired(c, ref)
    g = daily(c, ref)
    d = ((g["a"] - g["b"]) / g["n"]).to_numpy()  # per-origin mean loss difference, as compare.paired
    T = len(d)
    dm = nw_dm(d)
    W = r["n_weeks"]
    out = {"d_pooled_skill": r["d_pooled_skill"], "week_boot_ci90": r["ci90_d_pooled_skill"], "n_weeks": W,
           "distinct_week_resamples": math.comb(2 * W - 1, W), "n_origin_days": T,
           "dm_nw6": dm, "p1_normal": float(st.norm.cdf(dm)),
           "dm_hln": hln(dm, T), "p1_hln_t": float(st.t.cdf(hln(dm, T), T - 1)),
           "acf_daily_diff_1_7": [round(float(x), 3) for x in acf(d, 7)[1:]]}
    for lag in (10, 14):
        out[f"p1_normal_nw{lag}"] = float(st.norm.cdf(nw_dm(d, lag)))
    out["dayblock7_ci90"], out["dayblock7_p_d_le_0"] = block_boot(g)
    vg = next((v for k, v in gate.items() if k.startswith(name.split("_")[0] + "_")), None)
    if vg:
        gauss, boot = sim_null(d)
        z = vg["dm_stat"]
        out["val"] = {"logged_dm_stat": z, "logged_p_one_sided": vg["p_one_sided"], "logged_ci90": vg["ci90"],
                      "p_sim_gauss_devacf": float((gauss <= z).mean()), "p_sim_block_bootstrap": float((boot <= z).mean()),
                      "size_at_nominal_0.05_gauss": float((gauss <= st.norm.ppf(0.05)).mean()),
                      "size_at_nominal_0.05_boot": float((boot <= st.norm.ppf(0.05)).mean()),
                      "size_at_nominal_0.10_gauss": float((gauss <= st.norm.ppf(0.10)).mean())}
    res["directions"][name] = out
    print(name, json.dumps(out), flush=True)
res["val_weeks"] = {"n_weeks": 3, "distinct_week_resamples": math.comb(5, 3), "origins_per_week": [6, 7, 5]}
# BH at 10% on the simulated p-values (four queries of Amendment 2)
for key in ("logged_p_one_sided", "p_sim_gauss_devacf", "p_sim_block_bootstrap"):
    ps = sorted((v["val"][key], k) for k, v in res["directions"].items() if "val" in v)
    m = len(ps)
    kmax = max([i + 1 for i, (p, _) in enumerate(ps) if p <= 0.10 * (i + 1) / m], default=0)
    res[f"bh10_pass_{key}"] = [k for _, k in ps[:kmax]]
print(json.dumps({k: v for k, v in res.items() if k.startswith("bh") or k == "val_weeks"}, indent=1))
(OUT / "stats.json").write_text(json.dumps(res, indent=1))
