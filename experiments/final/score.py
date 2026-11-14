"""Dev scoring of `final` (halves.py style). One process, no torch: pretrained members come from runs/final.

Runs `final` once on dev rental_all with every member recorded, then re-blends the recorded member outputs
for each configuration (leave-one-out, gate) and scores them with the harness scorer. The re-blend of the
full configuration is checked to equal the harness run of `final` exactly. Also scores, for information,
fragility wrapped around the six-member blend (base = that blend, replayed from file).

Usage: PYTHONPATH=src .venv/bin/python experiments/final/score.py [--smoke N] > experiments/final/results/dev.txt
"""
import datetime as dt
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np
import pandas as pd

from gpuf import compare, data, harness, methods, splits
from gpuf.methods.allrental import gated
from gpuf.methods.final import MEMBERS, blend
from gpuf.scoring import score_fast

CUT = dt.date(2026, 9, 11).toordinal()
H = (1, 3, 7)
RUNS = data.ROOT / "runs/final"
smoke = int(sys.argv[sys.argv.index("--smoke") + 1]) if "--smoke" in sys.argv else 0
origins = splits.origins("dev")[-smoke:] if smoke else "dev"
t0 = time.time()
U_ALL, U_HEAD = data.universe("rental_all"), data.universe("rental_headline")
HEAD = set(U_HEAD)
store = data.load_store(data.series_path())
meta = harness.static_meta(data.load_catalog())

f = methods.get("final", record=True)
run = harness.evaluate(f, origins, "rental_all", name="final", params={"record": True})
print(f"# final on dev rental_all: {len(run.cells)} cells, {time.time() - t0:.0f}s", flush=True)
hist = {}  # (sid, origin) -> (days, vals) for the gate
for (s, o) in f.outs:
    d, v = store.history(s, o)
    hist[(s, o)] = (d, v)


def reblend(members, gate=None, scope="all"):
    rows = []
    for (s, o), outs in f.outs.items():
        d, v = hist[(s, o)]
        last = float(v[-1])
        if gate and not (scope == "nonhead" and s in HEAD) and gated(d, v, o, gate[0], gate[1]):
            res = {h: (last, last, last) for h in H}
        else:
            res, _ = blend({m: outs[m] for m in members}, H, last)
        for h in H:
            (a, b, c), _ = harness._clean(res[h], last)
            rows.append((s, o, h, a, b, c, last, 0))
    fc = pd.DataFrame(rows, columns=["series_id", "origin_day", "horizon_days", "q10", "q50", "q90", "baseline", "filled"])
    cells, _ = score_fast(fc, store, U_ALL, H)
    cells["instrument_class"] = cells["series_id"].map(lambda x: meta.get(x, {}).get("instrument_class", ""))
    return cells, fc


cfg = {"final": (MEMBERS, None, "all"), "final_gate14_all": (MEMBERS, (14, 1), "all"),
       "final_gate14_nonhead": (MEMBERS, (14, 1), "nonhead"), "mix": (("mix",), None, "all")}
for m in MEMBERS:
    cfg[f"loo_-{m}"] = (tuple(x for x in MEMBERS if x != m), None, "all")
for m in MEMBERS:
    cfg[f"only_{m}"] = ((m,), None, "all")
C = {}
for k, (mem, g, sc) in cfg.items():
    C[k], fc = reblend(mem, g, sc)
    if k == "loo_-fragility":
        p6 = RUNS / "blend6_dev_rental_all.parquet"
        fc.to_parquet(p6, index=False)
chk = C["final"].merge(run.cells, on=["series_id", "origin_day", "horizon_days"], suffixes=("", "_h"))
assert len(chk) == len(run.cells) == len(C["final"]), "re-blend cell set differs from the harness run"
assert np.array_equal(chk["loss"].to_numpy(), chk["loss_h"].to_numpy()), "re-blend differs from the harness run"
print("# re-blend of the full configuration equals the harness run of final exactly", flush=True)

alt = methods.get("fragility", base="replay", base_params={"path": str(p6)}, mode="mix", boost=20, bkind="any")
C["alt_frag_wraps_blend6"] = harness.evaluate(alt, origins, "rental_all", name="fragility",
                                              params={"base": "blend6 replay"}).cells
C["drift"] = harness.evaluate(methods.get("drift"), origins, "rental_all", name="drift").cells
print(f"# scored in {time.time() - t0:.0f}s", flush=True)


def sk(c):
    return 1 - c.loss.sum() / c.baseline_loss.sum()


def halves_line(name, c, ref, ref_name):
    out = [f"{name:<24} skill {sk(c):+.4f} | first {sk(c[c.origin_day <= CUT]):+.4f} second {sk(c[c.origin_day > CUT]):+.4f}"]
    for lab, mc, mr in (("all", slice(None), slice(None)), ("first", c.origin_day <= CUT, ref.origin_day <= CUT),
                        ("second", c.origin_day > CUT, ref.origin_day > CUT)):
        r = compare.paired(c[mc], ref[mr])
        lo, hi = r["ci90_d_pooled_skill"]
        out.append(f"{lab} d={r['d_pooled_skill']:+.4f} [{lo:+.3f},{hi:+.3f}]")
    cov = ((c.y >= c.q10) & (c.y <= c.q90)).mean()
    out.append(f"cov {cov:.2f}")
    return "  ".join(out)


def sub(c, uni):
    return c[c.series_id.isin(HEAD)] if uni == "headline" else c


for uni in ("headline", "all"):
    print(f"\n## rental_{uni}: against mix (d = config - mix, 90% week-block bootstrap)")
    ref = sub(C["mix"], uni)
    print(f"{'mix':<24} skill {sk(ref):+.4f} | first {sk(ref[ref.origin_day <= CUT]):+.4f} second {sk(ref[ref.origin_day > CUT]):+.4f}  n {len(ref)}")
    for k in ["drift", "final", "final_gate14_all", "final_gate14_nonhead", "alt_frag_wraps_blend6"] + \
             [f"only_{m}" for m in MEMBERS]:
        if uni == "headline" and k == "final_gate14_nonhead":
            continue
        print(halves_line(k, sub(C[k], uni), ref, "mix"), flush=True)
    print(f"\n## rental_{uni}: final against drift")
    print(halves_line("final", sub(C["final"], uni), sub(C["drift"], uni), "drift"))
    print(f"\n## rental_{uni}: leave-one-out, d = final - final without member (positive = member helps)")
    for m in MEMBERS:
        print(halves_line(f"-{m}", sub(C["final"], uni), sub(C[f"loo_-{m}"], uni), "loo").replace(
            f"skill {sk(sub(C['final'], uni)):+.4f}", f"loo skill {sk(sub(C[f'loo_-{m}'], uni)):+.4f}"), flush=True)
    print(f"\n## rental_{uni}: gate effect, d = gated - ungated final")
    for k in ("final_gate14_all", "final_gate14_nonhead"):
        if uni == "headline" and k == "final_gate14_nonhead":
            continue
        print(halves_line(k, sub(C[k], uni), sub(C["final"], uni), "final"))

print("\n## rental_all by instrument class: pooled skill (cells, first / second half)")
keys = ["drift", "mix", "final", "final_gate14_all", "final_gate14_nonhead", "alt_frag_wraps_blend6"] + [f"loo_-{m}" for m in MEMBERS]
rows = []
for k in keys:
    c = C[k]
    for cls, g in c.groupby("instrument_class"):
        rows.append((cls, k, len(g), sk(g), sk(g[g.origin_day <= CUT]) if (g.origin_day <= CUT).any() else np.nan,
                     sk(g[g.origin_day > CUT])))
T = pd.DataFrame(rows, columns=["class", "config", "n", "full", "first", "second"])
with pd.option_context("display.width", 250, "display.max_rows", 500, "display.float_format", "{:+.3f}".format):
    print(T.pivot_table(index=["class", "n"], columns="config", values="full").T.round(3).T.to_string())
    print("\nfirst / second half")
    print(T.pivot_table(index="class", columns="config", values=["first", "second"]).round(3).T.to_string())

hl = C["final"][C["final"].instrument_class == "hyperscaler_list"]
if len(hl):
    print("\n## hyperscaler_list series under final (skill, share of cells gated by [14,1])")
    g = C["final_gate14_all"]
    for s, x in hl.groupby("series_id"):
        xg = g[g.series_id == s]
        zero = ((xg.q10 == xg.q90)).mean()
        print(f"{s:<70} n {len(x):4d} final {sk(x):+.3f} gated {sk(xg):+.3f} mix {sk(C['mix'][C['mix'].series_id == s]):+.3f} zero-width {zero:.2f}")

use = pd.Series({k: "+".join(v) for k, v in ((k, tuple(m for m in MEMBERS if f.outs[k][m] is not None)) for k in f.outs)})
print("\n## members available per (series, origin) on dev rental_all")
print(use.value_counts().to_string())
print(f"\n# total {time.time() - t0:.0f}s")
