"""Score entry variants on dev headline. Usage: PYTHONPATH=src .venv/bin/python experiments/entry/score.py '[["name",{params}],...]'"""
import json, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs/entry"
K = ["series_id", "origin_day", "horizon_days"]


def cells(name, params):
    p = RUNS / f"{name}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    from gpuf import harness, methods
    f = methods.get("entry", **params)
    t = time.time()
    c = harness.evaluate(f, "dev", "rental_headline", name="entry", params=params).cells
    print(f"[{name}] {time.time()-t:.0f}s", file=sys.stderr)
    RUNS.mkdir(parents=True, exist_ok=True); c.to_parquet(p)
    return c


def event_flags(c):
    from gpuf import panel as P
    out = {}
    for sid in c.series_id.unique():
        if not P.supported(sid):
            continue
        o = P.offers(sid, 10 ** 9)
        o = o[o.day <= 739902]
        first = o.groupby("key").day.min(); byday = o.groupby("day").key.apply(set).to_dict()
        for (od, h), _ in c[c.series_id == sid].groupby(["origin_day", "horizon_days"]):
            t = od + h
            en = bool(((first > od) & (first <= t)).any())
            a, b = byday.get(od, set()), byday.get(t, set())
            out[(sid, od, h)] = (en, bool(a - b))
    return pd.DataFrame([(*k, *v) for k, v in out.items()], columns=K + ["entered", "left"])


def pin(c):
    return c


def summarize(name, a, params):
    from gpuf import compare
    d = pd.read_parquet(ROOT / "runs/panel/drift.parquet"); m = pd.read_parquet(ROOT / "runs/panel/mix.parquet")
    pv = pd.read_parquet(ROOT / "runs/prov/L1_W21_gdyn.parquet")
    B = a.baseline_loss.sum()
    out = {"name": name, "params": params, "skill": round(1 - a.loss.sum() / B, 4), "n": len(a),
           "coverage": round(float(((a.y >= a.q10) & (a.y <= a.q90)).mean()), 3),
           "prov_skill": round(1 - pv.loss.sum() / B, 4)}
    for rn, rc in (("drift", d), ("mix", m), ("prov", pv)):
        r = compare.paired(a, rc); out[f"d_{rn}"] = [round(r["d_pooled_skill"], 4)] + [round(x, 4) for x in r["ci90_d_pooled_skill"]]
    mid = np.sort(a.origin_day.unique())[len(a.origin_day.unique()) // 2]
    j = a.merge(pv[K + ["loss"]], on=K, suffixes=("", "_prov"))
    j["half"] = np.where(j.origin_day < mid, "1st", "2nd")
    for h, x in j.groupby("half"):
        out[f"vs_prov_{h}"] = round(float((x.loss_prov.sum() - x.loss.sum()) / x.baseline_loss.sum()), 4)
        r = compare.paired(a.merge(x[K], on=K), pv.merge(x[K], on=K)); out[f"vs_prov_{h}_ci"] = [round(z, 4) for z in r["ci90_d_pooled_skill"]]
    ef = event_flags(j)
    j = j.merge(ef, on=K, how="left")
    r = np.log(j.y / j.baseline)
    j["cat"] = np.select([j.entered.fillna(False).astype(bool) & j.left.fillna(False).astype(bool), j.entered.fillna(False).astype(bool),
                          j.left.fillna(False).astype(bool), r == 0], ["both", "entry", "exit", "nomove"], "other")
    out["cat"] = {k: {"n": len(x), "gain_vs_prov_share_of_B": round(float((x.loss_prov.sum() - x.loss.sum()) / B), 4),
                      "rel_loss": round(float(x.loss.sum() / x.loss_prov.sum()), 3)} for k, x in j.groupby("cat")}
    out["cov_h7"] = {"below_q10": round(float((a[a.horizon_days == 7].y < a[a.horizon_days == 7].q10).mean()), 3),
                     "above_q90": round(float((a[a.horizon_days == 7].y > a[a.horizon_days == 7].q90).mean()), 3)}
    pvh = pv[pv.horizon_days == 7]
    out["cov_h7_prov"] = {"below_q10": round(float((pvh.y < pvh.q10).mean()), 3), "above_q90": round(float((pvh.y > pvh.q90).mean()), 3)}
    out["changed_cells_vs_prov"] = int((j.q90.round(8) != pv.set_index(K).loc[list(map(tuple, j[K].to_numpy()))].q90.round(8).to_numpy()).sum())
    return out


def job(spec):
    name, params = spec
    return summarize(name, cells(name, params), params)


if __name__ == "__main__":
    specs = json.loads(sys.argv[1])
    with ProcessPoolExecutor(max_workers=min(4, len(specs))) as ex:
        for o in ex.map(job, specs):
            print(json.dumps(o))
            with open(ROOT / "experiments/entry/results/scores.jsonl", "a") as fh:
                fh.write(json.dumps(o) + "\n")
