"""Score hyper variants on afhubbard series of rental_all (and the 4 headline afhubbard series) against drift and mix,
by class, overall and on both dev halves; dev_old as robustness. Usage:
PYTHONPATH=src .venv/bin/python experiments/hyper/score.py SPEC.json [--split dev|dev_old]
SPEC.json: list of [name, method, params]. Cells cached under runs/hyper/<split>_<name>.parquet."""
import datetime as dt, json, resource, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs/hyper"
MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
CUT = dt.date(2026, 9, 11).toordinal()


def ids():
    from gpuf import data
    return [s for s in data.universe("rental_all") if s.startswith("afhubbard.")]


def cells(job):
    name, m, p, split = job
    f = RUNS / f"{split}_{name}.parquet"
    if f.exists():
        return name, pd.read_parquet(f), None
    from gpuf import harness, methods
    t = time.time()
    c = harness.evaluate(methods.get(m, **p), split, ids(), name=m, params=p).cells
    el = time.time() - t
    c.to_parquet(f)
    return name, c, (el, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9)


def table(cs, ref, head):
    from gpuf import compare
    out = []
    groups = [("all", lambda c: c), ("headline4", lambda c: c[c.series_id.isin(head)])]
    groups += [(k, (lambda k: lambda c: c[c.series_id.str.split(".").str[1] == k])(k)) for k in
               ("hyperscaler_spot", "hyperscaler_list", "neocloud_rate_card", "neocloud_spot")]
    halves = [("full", lambda c: c), ("H1", lambda c: c[c.origin_day <= CUT]), ("H2", lambda c: c[c.origin_day > CUT])]
    for name, c in cs.items():
        for g, gf in groups:
            for hn, hf in halves:
                a = hf(gf(c))
                if not len(a):
                    continue
                sk = 1 - a.loss.sum() / a.baseline_loss.sum()
                row = {"name": name, "group": g, "half": hn, "n": len(a), "skill": round(sk, 4),
                       "cov": round(float(((a.y >= a.q10) & (a.y <= a.q90)).mean()), 3)}
                for rn in ("drift", "mix"):
                    if rn == name:
                        continue
                    b = hf(gf(ref[rn]))
                    d = compare.paired(a, b, reps=1000)
                    row[f"d_{rn}"] = round(d["d_pooled_skill"], 4)
                    row[f"ci_{rn}"] = [round(x, 3) for x in d["ci90_d_pooled_skill"]]
                out.append(row)
    return pd.DataFrame(out)


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    split = sys.argv[sys.argv.index("--split") + 1] if "--split" in sys.argv else "dev"
    assert split in ("dev", "dev_old")
    RUNS.mkdir(parents=True, exist_ok=True)
    jobs = [("drift", "drift", {}, split), ("mix", MIX[0], MIX[1], split)] + [(n, m, p, split) for n, m, p in spec]
    cs = {}
    with ProcessPoolExecutor(max_workers=3) as ex:
        for name, c, info in ex.map(cells, jobs):
            cs[name] = c
            if info:
                print(f"[{name}] {info[0]:.0f}s, {info[0] / c.origin_day.nunique():.2f}s/origin, maxrss {info[1]:.2f} GB", file=sys.stderr)
    from gpuf import data
    head = [s for s in data.universe("rental_headline") if s.startswith("afhubbard.")]
    t = table(cs, cs, head)
    pd.set_option("display.width", 250)
    print(t.to_string(index=False))
    t.to_csv(ROOT / f"experiments/hyper/scores_{split}.csv", index=False, mode="a")
