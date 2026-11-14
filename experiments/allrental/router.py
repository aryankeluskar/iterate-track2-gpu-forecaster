"""Steps 2-5: candidate losses per cell, router rules chosen on early dev origins (<= 2026-09-11), reported on late origins.

All routing features are computed from rows dated on or before each origin.
"""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, "experiments/allrental")
from lib import ctx
from gpuf import compare

store, meta, sids, head = ctx()
base = pd.read_parquet("runs/allrental/lv_cells.parquet")
KEY = ["series_id", "origin_day", "horizon_days"]
base = base[KEY + ["y", "baseline", "baseline_loss", "cls", "src", "head", "half", "origin_week", "target_day"]].reset_index(drop=True)

FILES = {"drift": "runs/allrental/drift.parquet", "mix": "runs/allrental/mix_ref.parquet",
         "mix_cls": "runs/allrental/mix_cls.parquet", "mix_none": "runs/allrental/mix_none.parquet",
         "mix_k5": "runs/allrental/mix_k5.parquet", "mix_sk7": "runs/allrental/mix_sk7.parquet",
         "gbm": "runs/allrental/gbm.parquet",
         "chronos": "runs/cache/chronos_last_rental_all.parquet", "timesfm": "runs/cache/timesfm_last_rental_all.parquet"}
import os
FILES = {k: v for k, v in FILES.items() if os.path.exists(v)}
SCALES = (0.25, 0.5, 0.75, 1.0)
y, b = base.y.to_numpy(), base.baseline.to_numpy()


def pin(y, q, t):
    d = y - q
    return np.maximum(t * d, (t - 1) * d)


def loss_of(q10, q50, q90):
    return (pin(y, q10, .1) + pin(y, q50, .5) + pin(y, q90, .9)) / 3


Q = {}
for name, f in FILES.items():
    d = base[KEY].merge(pd.read_parquet(f)[KEY + ["q10", "q50", "q90"]], on=KEY, how="left")
    miss = d.q50.isna()
    for c in ("q10", "q50", "q90"):
        d.loc[miss, c] = b[miss]
    Q[name] = d[["q10", "q50", "q90"]].to_numpy()
    if miss.any():
        print(name, "missing cells filled with LV:", int(miss.sum()))
L = {"lv": base.baseline_loss.to_numpy()}
for name, q in Q.items():
    for s in SCALES:
        lq50 = np.log(q[:, 1])
        q10 = np.exp(lq50 + s * (np.log(q[:, 0]) - lq50)); q90 = np.exp(lq50 + s * (np.log(q[:, 2]) - lq50))
        L[f"{name}@{s}"] = loss_of(q10, q[:, 1], q90)
CANDS = [k for k in L]

# activity features at origin (rows <= origin only)
def feats():
    out = {n: np.zeros(len(base), int) for n in (7, 14, 30, 60)}
    hist = np.zeros(len(base), int)
    for sid, idx in base.groupby("series_id").indices.items():
        d, v = store.arrays(sid)
        ch = np.r_[0, (v[1:] != v[:-1]).astype(int)]
        cum = np.cumsum(ch)
        o = base.origin_day.to_numpy()[idx]
        hi = np.searchsorted(d, o, side="right") - 1
        hist[idx] = hi + 1
        for n in out:
            lo = np.searchsorted(d, o - n, side="right")  # first row dated > o-n
            out[n][idx] = cum[hi] - np.where(lo > 0, cum[np.maximum(lo - 1, 0)], 0)
    return out, hist
ACT, HIST = feats()
early = (base.half == "early").to_numpy(); late = ~early
cls = base.cls.to_numpy(); CLASSES = sorted(set(cls))
B = L["lv"]


def skill(loss, m):
    return 1 - loss[m].sum() / B[m].sum()


def pick_by_class(mask_fit, active=None, cands=CANDS):
    """Per class: candidate with the lowest summed loss on fit cells (restricted to active cells if given)."""
    ch = {}
    for c in CLASSES:
        m = mask_fit & (cls == c) & (active if active is not None else True)
        ch[c] = min(cands, key=lambda k: L[k][m].sum()) if m.any() else "lv"
    return ch


def apply(choice, active=None):
    out = B.copy()
    for c, k in choice.items():
        m = (cls == c) & (active if active is not None else True)
        out[m] = L[k][m]
    return out


def online(active=None, cands=CANDS, lookback=None):
    """At each origin, per class, the candidate with the lowest realised loss on cells whose target is <= origin."""
    out = B.copy()
    od, td = base.origin_day.to_numpy(), base.target_day.to_numpy()
    act = active if active is not None else np.ones(len(base), bool)
    Lm = np.stack([L[k] for k in cands], 1)
    for o in np.unique(od):
        cur = (od == o) & act
        past = (td <= o) & act
        if lookback:
            past &= td > o - lookback
        for c in CLASSES:
            m = cur & (cls == c)
            if not m.any():
                continue
            p = past & (cls == c)
            j = int(np.argmin(Lm[p].sum(0))) if p.any() else cands.index("mix@1.0")
            out[m] = Lm[m, j]
    return out


def report(name, loss):
    r = {"rule": name}
    for part, pm in (("all", np.ones(len(base), bool)), ("nonhead", ~base["head"].to_numpy()), ("head", base["head"].to_numpy())):
        for half, hm in (("early", early), ("late", late)):
            r[f"{part}_{half}"] = round(skill(loss, pm & hm), 4)
    return r


if __name__ == "__main__":
    rows = [report("lv", B), report("drift", L["drift@1.0"]), report("mix_ref", L["mix@1.0"])]
    for k in CANDS:
        if k.endswith("@1.0") or k.endswith("@0.5"):
            rows.append(report(k, L[k]))
    # R1: by class
    ch1 = pick_by_class(early); rows.append(report("R1_class", apply(ch1)))
    # R2: class + gate, grid on early
    best = None
    for n in (7, 14, 30, 60):
        for m in (1, 2, 3, 5, 8):
            a = ACT[n] >= m
            ch = pick_by_class(early, a)
            l = apply(ch, a)
            s = skill(l, early)
            rows.append(report(f"R2_gate_n{n}_m{m}", l))
            if best is None or s > best[0]:
                best = (s, n, m, ch)
    s, n, m, ch2 = best
    a2 = ACT[n] >= m
    L_R2 = apply(ch2, a2); rows.append(report(f"R2*_n{n}_m{m}", L_R2))
    # R3: online per class (with and without gate)
    L_R3 = online(); rows.append(report("R3_online", L_R3))
    L_R3g = online(a2); rows.append(report(f"R3_online_gate_n{n}_m{m}", L_R3g))
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
    df = pd.DataFrame(rows); print(df.to_string(index=False))
    print("R1 choice", ch1); print("R2 choice", ch2, "n", n, "m", m)
    json.dump({"R1": ch1, "R2": {"n": n, "m": m, "choice": ch2}}, open("runs/allrental/choices.json", "w"), indent=1)
    np.save("runs/allrental/L_R2.npy", L_R2); np.save("runs/allrental/L_R3g.npy", L_R3g)
