"""Dev only. Score fm2 variants from saved grids against drift and mix, plus the 50/50 log blend with mix.
Usage: score.py SPEC.json   (list of [label, fm2_params]); prints one line per variant."""
import json, os, sys
import numpy as np
from gpuf import compare, harness, methods

MIX = {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}
MIXP = "runs/fm2/mix_dev_rental_headline.parquet"


def ev(m, p):
    return harness.evaluate(methods.get(m, **p), "dev", "rental_headline", name=m, params=p).cells


def skill(c):
    return 1 - c["loss"].sum() / c["baseline_loss"].sum()


def ref():
    if not os.path.exists(MIXP):
        ev("mix", MIX)  # warm
        c = harness.evaluate(methods.get("mix", **MIX), "dev", "rental_headline").cells
        c[compare.KEY + ["q10", "q50", "q90"]].to_parquet(MIXP)
    return ev("drift", {}), ev("replay", {"path": MIXP})


def line(label, c, drift, mix, blend=None):
    dd, dm = compare.paired(c, drift), compare.paired(c, mix)
    hs = " ".join(f"h{h}={skill(g):+.3f}" for h, g in c.groupby("horizon_days"))
    src = " ".join(f"{s[:4]}={(g['loss_d'].sum() - g['loss'].sum()) / c['baseline_loss'].sum():+.3f}"
                   for s, g in c.merge(drift[compare.KEY + ['loss']], on=compare.KEY, suffixes=('', '_d')).groupby('source_id'))
    cov = ((c["y"] >= c["q10"]) & (c["y"] <= c["q90"])).mean()
    s = (f"{skill(c):+.4f} vsdrift={dd['d_pooled_skill']:+.4f}[{dd['ci90_d_pooled_skill'][0]:+.3f},{dd['ci90_d_pooled_skill'][1]:+.3f}] "
         f"vsmix={dm['d_pooled_skill']:+.4f}[{dm['ci90_d_pooled_skill'][0]:+.3f},{dm['ci90_d_pooled_skill'][1]:+.3f}] cov={cov:.2f} {hs} | vs drift by src {src}")
    if blend is not None:
        db = compare.paired(blend, mix)
        s += f" | blend={skill(blend):+.4f} vsmix={db['d_pooled_skill']:+.4f}[{db['ci90_d_pooled_skill'][0]:+.3f},{db['ci90_d_pooled_skill'][1]:+.3f}]"
    print(f"{label:28s} {s}", flush=True)


if __name__ == "__main__":
    drift, mix = ref()
    line("drift", drift, drift, mix)
    line("mix", mix, drift, mix)
    for label, p in json.load(open(sys.argv[1])):
        c = ev("fm2", p)
        b = ev("ens", {"members": [["replay", {"path": MIXP}], ["fm2", p]]}) if p.get("centre", "last") == "last" else None
        line(label, c, drift, mix, b)
