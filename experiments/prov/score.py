"""Score prov variants on dev headline. Usage: PYTHONPATH=src .venv/bin/python experiments/prov/score.py SPEC.json
SPEC.json: list of [name, params]. Cells -> runs/prov/<name>.parquet (with the middle-provider state per cell),
summary lines -> experiments/prov/results/scores.jsonl. Reference cells (drift, mix, panel v1_hl14) are read from
runs/panel/*.parquet (dev only)."""
import json, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs/prov"
TAUS = (0.1, 0.5, 0.9)


def cells(name, params):
    p = RUNS / f"{name}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    from gpuf import harness, methods
    f = methods.get("prov", **params)
    t = time.time()
    c = harness.evaluate(f, "dev", "rental_headline", name="prov", params=params).cells
    stt = pd.DataFrame([(s, o, v["dyn_near"], v["mid_rate"], v["mid_drift"]) for (s, o), v in f.state.items()],
                       columns=["series_id", "origin_day", "dyn_near", "mid_rate", "mid_drift"])
    c = c.merge(stt, on=["series_id", "origin_day"], how="left")
    print(f"[{name}] {time.time() - t:.0f}s", file=sys.stderr)
    RUNS.mkdir(parents=True, exist_ok=True)
    c.to_parquet(p)
    return c


def ref(name):
    return pd.read_parquet(ROOT / f"runs/panel/{name}.parquet")


def rescore(c):
    c = c.copy()
    y, b = c.y.to_numpy(), c.baseline.to_numpy()
    pin = lambda f, t: np.maximum(t * (y - f), (t - 1) * (y - f))
    for t, q in zip(TAUS, ("q10", "q50", "q90")):
        c[f"loss_{q}"] = pin(c[q].to_numpy(), t)
    c["loss"] = (c.loss_q10 + c.loss_q50 + c.loss_q90) / 3
    return c


def blend(a, b, wa=0.5):
    K = ["series_id", "origin_day", "horizon_days"]
    m = a.merge(b[K + ["q10", "q50", "q90"]], on=K, suffixes=("", "_b"))
    for q in ("q10", "q50", "q90"):
        m[q] = np.exp(wa * np.log(m[q]) + (1 - wa) * np.log(m[q + "_b"]))
    return rescore(m.drop(columns=[q + "_b" for q in ("q10", "q50", "q90")]))


def bucket(c):
    r = np.log(c["y"] / c["baseline"])
    return np.select([r == 0, r.abs() < 0.01, r.abs() <= 0.05, r > 0.05], ["none", "<1%", "1-5%", "up>5%"], "down>5%")


def summarize(name, a, params):
    from gpuf import compare
    d, m, pn = ref("drift"), ref("mix"), ref("v1_hl14")
    K = compare.KEY
    B = a.baseline_loss.sum()
    q50r = lambda x: round(float(x.loss_q50.sum() / ((x.y - x.baseline).abs() * 0.5).sum()), 4)
    out = {"name": name, "params": params, "skill": round(1 - a.loss.sum() / B, 4),
           "coverage": round(float(((a.y >= a.q10) & (a.y <= a.q90)).mean()), 3)}
    for rn, rc in (("drift", d), ("mix", m), ("panel", pn)):
        c = compare.paired(a, rc)
        out[f"d_{rn}"] = [round(c["d_pooled_skill"], 4)] + [round(x, 4) for x in c["ci90_d_pooled_skill"]]
    for rn, rc in (("mix", m), ("panel", pn)):
        bl = blend(a, rc)
        c = compare.paired(bl, m)
        out[f"blend_{rn}_skill"] = round(1 - bl.loss.sum() / B, 4)
        out[f"blend_{rn}_vs_mix"] = [round(c["d_pooled_skill"], 4)] + [round(x, 4) for x in c["ci90_d_pooled_skill"]]
        out[f"blend_{rn}_q50r"] = q50r(bl)
    out["q50r"] = q50r(a)
    dyn = a.mid_rate.fillna(0) > 0.5
    out["q50r_mid_dyn>50%"] = q50r(a[dyn]); out["n_mid_dyn"] = int(dyn.sum())
    out["q50r_dyn_near"] = q50r(a[a.dyn_near.fillna(False).astype(bool)])
    out["q50r_mix_mid_dyn"] = q50r(m.merge(a[K][dyn.values], on=K))
    out["tails_by_h(below_q10,above_q90)"] = {int(h): [round(float((x.y < x.q10).mean()), 3), round(float((x.y > x.q90).mean()), 3)]
                                             for h, x in a.groupby("horizon_days")}
    j = a.merge(m[K + ["loss"]], on=K, suffixes=("", "_mix"))
    j["bucket"] = bucket(j)
    mid = np.sort(j.origin_day.unique())[len(j.origin_day.unique()) // 2]
    j["half"] = np.where(j.origin_day < mid, "1st", "2nd")
    for col in ("source_id", "horizon_days", "bucket", "half"):
        out[f"gain_vs_mix_by_{col}"] = {str(k): round(float((v.loss_mix.sum() - v.loss.sum()) / B), 4) for k, v in j.groupby(col)}
    out["skill_by_half"] = {k: [round(float(1 - v.loss.sum() / v.baseline_loss.sum()), 4), round(float(1 - v.loss_mix.sum() / v.baseline_loss.sum()), 4)]
                            for k, v in j.groupby("half")}
    s = j.groupby("series_id").apply(lambda v: (v.loss_mix.sum() - v.loss.sum()) / B, include_groups=False).sort_values()
    out["top_series_vs_mix"] = {k.split(".", 1)[1][:38]: round(float(v), 4) for k, v in pd.concat([s.head(3), s.tail(3)]).items()}
    return out


def job(spec):
    name, params = spec
    return summarize(name, cells(name, params), params)


if __name__ == "__main__":
    specs = json.load(open(sys.argv[1]))
    with ProcessPoolExecutor(max_workers=min(6, len(specs))) as ex:
        for o in ex.map(job, specs):
            print(json.dumps(o))
            with open(ROOT / "experiments/prov/results/scores.jsonl", "a") as fh:
                fh.write(json.dumps(o) + "\n")
