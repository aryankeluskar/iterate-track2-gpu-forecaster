"""Part 1: prov with and without the announced-repricing calendar (`cal`) on dev headline.
Usage: PYTHONPATH=src .venv/bin/python experiments/prov/score_cal.py
Affected cells = experiments/calendar/results/b2_cells.csv (origin in [published, effective), target >= effective)."""
import json, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from score import cells, ref, blend, ROOT
from gpuf import compare
from gpuf.data import starter_common

BASEP = {"L": 1, "W": 21, "gate": "dyn"}
VAR = {"prov": BASEP,
       "cal": {**BASEP, "cal": True},
       "cal_nolag": {**BASEP, "cal": True, "cal_lag": False},
       "cal_pe0": {**BASEP, "cal": True, "cal_pe": 0.0}}
K = compare.KEY


def q50r(x):
    return round(float(x.loss_q50.sum() / ((x.y - x.baseline).abs() * 0.5).sum()), 4)


def pair(a, b, mask=None):
    if mask is not None:
        a, b = a[mask.values], b.merge(a[mask.values][K], on=K)
    c = compare.paired(a, b)
    return [round(c["d_pooled_skill"], 4)] + [round(x, 4) for x in c["ci90_d_pooled_skill"]]


if __name__ == "__main__":
    names = {"prov": "L1_W21_gdyn", "cal": "L1_W21_gdyn_cal", "cal_nolag": "L1_W21_gdyn_cal_nolag", "cal_pe0": "L1_W21_gdyn_cal_pe0"}
    with ProcessPoolExecutor(4) as ex:
        C = dict(zip(VAR, ex.map(cells, [names[k] for k in VAR], VAR.values())))
    mix = ref("mix")
    b2 = pd.read_csv(ROOT / "experiments/calendar/results/b2_cells.csv")
    b2["origin_day"] = b2.origin.map(lambda s: starter_common.day_of(starter_common.parse_date(s)))
    aff_keys = b2.rename(columns={"series": "series_id", "h": "horizon_days"})[K]
    p0 = C["prov"].sort_values(K).reset_index(drop=True)
    aff = p0[K].merge(aff_keys.assign(aff=True), on=K, how="left").aff.fillna(False).astype(bool)
    mid = np.sort(p0.origin_day.unique())[len(p0.origin_day.unique()) // 2]
    half2 = p0.origin_day >= mid
    out = {"n_affected": int(aff.sum()), "n_cells": len(p0)}
    for v in ("cal", "cal_nolag", "cal_pe0"):
        a = C[v].sort_values(K).reset_index(drop=True)
        diff = (a[["q10", "q50", "q90"]].to_numpy() != p0[["q10", "q50", "q90"]].to_numpy()).any(1)
        r = {"cells_changed": int(diff.sum()), "changed_outside_affected": int((diff & ~aff.values).sum()),
             "unaffected_identical": bool((a[~aff][["q10", "q50", "q90"]].to_numpy() == p0[~aff][["q10", "q50", "q90"]].to_numpy()).all()),
             "skill": round(1 - a.loss.sum() / a.baseline_loss.sum(), 4)}
        for nm, msk in (("all", None), ("half1", ~half2), ("half2", half2), ("affected", aff), ("unaffected", ~aff)):
            r[f"vs_prov_{nm}"] = pair(a, p0, msk)
            r[f"vs_mix_{nm}"] = pair(a, mix, msk)
        r["q50r_affected"] = {"cal": q50r(a[aff.values]), "prov": q50r(p0[aff.values]), "mix": q50r(mix.merge(p0[aff.values][K], on=K))}
        r["skill_affected"] = {"cal": round(1 - a[aff.values].loss.sum() / a[aff.values].baseline_loss.sum(), 4),
                               "prov": round(1 - p0[aff.values].loss.sum() / p0[aff.values].baseline_loss.sum(), 4)}
        ev = a[aff.values].merge(b2.rename(columns={"series": "series_id", "h": "horizon_days"})[K + ["event"]], on=K)
        r["q50r_by_event"] = {e: q50r(x) for e, x in ev.groupby("event")}
        r["tails_affected(below,above)"] = [round(float((a[aff.values].y < a[aff.values].q10).mean()), 3), round(float((a[aff.values].y > a[aff.values].q90).mean()), 3)]
        bl = blend(a, mix); bl0 = blend(p0, mix)
        r["blend_mix_vs_blend_mix_nocal"] = pair(bl, bl0)
        r["blend_mix_skill"] = round(1 - bl.loss.sum() / bl.baseline_loss.sum(), 4)
        out[v] = r
    print(json.dumps(out, indent=1))
    json.dump(out, open(ROOT / "experiments/prov/results/cal_summary.json", "w"), indent=1)
