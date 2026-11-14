"""Offline combiner simulation on the cached dev bank (runs/stack/*.parquet). Uses the same weights()/blend() as the `stack` method."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np, pandas as pd
from gpuf import harness, methods
from gpuf.compare import paired
from gpuf.methods.stack import weights, blend, lookup, pin, TAUS

BANK = ["drift", "last", "mix_ref", "mix_dirk", "mix_all", "gbm", "calib", "chronos_last", "timesfm_last", "mix_narrow", "mix_wide"]
PATHS = [f"runs/stack/{b}.parquet" for b in BANK]
KEY = ["series_id", "origin_day", "horizon_days"]


def load():
    r = harness.evaluate(methods.get("replay", path=PATHS[2]), "dev", "rental_headline", name="stack_base", params={})
    cells = r.cells.reset_index(drop=True)
    lq = []
    for p in PATHS:
        t = pd.read_parquet(p)
        m = cells[KEY].merge(t, on=KEY, how="left", validate="one_to_one")
        assert m.q10.notna().all()
        lq.append(np.log(np.maximum(m[["q10", "q50", "q90"]].to_numpy(), 1e-9)))
    C = {"tday": cells.target_day.to_numpy(), "h": cells.horizon_days.to_numpy(),
         "g": (cells.source_id + "|" + cells.instrument_class).to_numpy(), "y": cells.y.to_numpy(), "logq": np.stack(lq)}
    return cells, C


def score_cells(cells, q):
    out = cells[KEY + ["origin_week", "baseline_loss", "origin_date", "source_id", "instrument_class"]].copy()
    y = cells.y.to_numpy()
    ls = np.stack([pin(y, q[:, t], TAUS[t]) for t in range(3)], 1)
    out[["q10", "q50", "q90"]] = q
    out["loss"] = ls.mean(1)
    return out


def run(cells, C, **p):
    n = len(cells)
    q = np.zeros((n, 3))
    origins = np.sort(cells.origin_day.unique())
    og = cells.origin_day.to_numpy()
    for d in origins:
        keys, eq = weights(d, C, **p)
        for i in np.nonzero(og == d)[0]:
            W = lookup(keys, eq, C["h"][i], C["g"][i], p.get("key", "h"))
            q[i] = blend(W, C["logq"][:, i, :])
    return q


def skill(c):
    return 1 - c.loss.sum() / c.baseline_loss.sum()


def subsets(cells):
    o = np.sort(cells.origin_day.unique())
    return {"all": o, "first25": o[:25], "last25": o[25:], "ex14": o[14:], "last25_ex14": o[25:]}


def weight_traj(cells, C, **p):
    """weights (E,) for each origin, per h and tau, sharing across groups when key='h'."""
    rows = []
    for d in np.sort(cells.origin_day.unique()):
        keys, eq = weights(d, C, **p)
        for h in (1, 3, 7):
            W = lookup(keys, eq, h, "", "h")
            rows.append((d, h, W.copy()))
    return rows
