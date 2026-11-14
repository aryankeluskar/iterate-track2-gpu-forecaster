"""Run many (method, params) variants on one split in parallel and print a compact table.

Usage: PYTHONPATH=src .venv/bin/python experiments/sweep.py SPEC.json [--split dev] [--universe rental_headline] [--by]
SPEC.json: a list of [method, params]. Each result is appended to data_out/trajectory.jsonl.
--by adds the paired skill difference against drift by collector and by horizon.
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor


def one(job):
    method, params, split, universe, by = job
    from gpuf import compare, harness, methods, run
    rec = run.run(method, split, universe, params)
    extra = {}
    if by:
        res = harness.evaluate(methods.get(method, **params), split, universe, name=method, params=params)
        ref = harness.evaluate(methods.get("drift"), split, universe, name="drift", params={"role": "ref"})
        m = res.cells.merge(ref.cells[compare.KEY + ["loss"]], on=compare.KEY, suffixes=("", "_d"))
        m = m.merge(ref.cells[compare.KEY + ["q10", "q90"]], on=compare.KEY, suffixes=("", "_d"))
        m["drift_state"] = (m["q10_d"] == m["q90_d"]).map({True: "flat", False: "live"})
        extra["skill_where_drift_live"] = {k: round(float(1 - v[c].sum() / v["baseline_loss"].sum()), 4)
                                           for k, c in (("method", "loss"), ("drift", "loss_d"))
                                           for v in [m[m["drift_state"] == "live"]]}
        for col in ("source_id", "horizon_days", "instrument_class"):
            g = m.groupby(col)
            extra[col] = {str(k): round(float((v["loss_d"].sum() - v["loss"].sum()) / m["baseline_loss"].sum()), 4)
                          for k, v in g}
    return rec, extra


if __name__ == "__main__":
    args = sys.argv[1:]
    spec = json.load(open(args[0]))
    split = args[args.index("--split") + 1] if "--split" in args else "dev"
    universe = args[args.index("--universe") + 1] if "--universe" in args else "rental_headline"
    by = "--by" in args
    if split not in ("dev", "dev_old"):
        raise SystemExit("sweep.py is for dev only; validation is run one query at a time with gpuf.run")
    jobs = [(m, p, split, universe, by) for m, p in spec]
    with ProcessPoolExecutor(max_workers=10) as ex:
        for (m, p, *_), (r, extra) in zip(jobs, ex.map(one, jobs)):
            print(f"{r['pooled_skill']:+.4f} d={r['skill_vs_drift']:+.4f} ci=[{r['ci90_vs_drift'][0]:+.3f},{r['ci90_vs_drift'][1]:+.3f}] "
                  f"cov={r['coverage']:.2f} med={r['skill_median_of_series']:+.3f} {m} {json.dumps(p)}")
            for k, v in extra.items():
                print("     ", k, v)
