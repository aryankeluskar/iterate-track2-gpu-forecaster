"""Orchestrator's dev gate (EVAL_PROTOCOL.md, Amendment 2, rule 1): score candidates against a reference on dev headline,
overall and on both halves of dev (origins up to 2026-09-11, and from 2026-09-12).

Usage: PYTHONPATH=src .venv/bin/python experiments/halves.py SPEC.json [--universe rental_headline]
SPEC.json: {"ref": [method, params], "cands": {"name": [method, params], ...}}
"""
import datetime as dt, json, sys
from gpuf import compare, harness, methods

spec = json.load(open(sys.argv[1]))
uni = sys.argv[sys.argv.index("--universe") + 1] if "--universe" in sys.argv else "rental_headline"
CUT = dt.date(2026, 9, 11).toordinal()


def cells(m, p):
    return harness.evaluate(methods.get(m, **p), "dev", uni, name=m, params=p).cells


def skill(c):
    return 1 - c.loss.sum() / c.baseline_loss.sum()


ref = cells(*spec["ref"])
print(f"{'ref':<28} skill {skill(ref):+.4f}  first {skill(ref[ref.origin_day <= CUT]):+.4f}  second {skill(ref[ref.origin_day > CUT]):+.4f}  n {len(ref)}")
for name, (m, p) in spec["cands"].items():
    c = cells(m, p)
    out = [f"{name:<28} skill {skill(c):+.4f}"]
    for lab, mask_c, mask_r in (("all", slice(None), slice(None)), ("first", c.origin_day <= CUT, ref.origin_day <= CUT), ("second", c.origin_day > CUT, ref.origin_day > CUT)):
        r = compare.paired(c[mask_c], ref[mask_r])
        lo, hi = r["ci90_d_pooled_skill"]
        out.append(f"{lab} d={r['d_pooled_skill']:+.4f} [{lo:+.3f},{hi:+.3f}]" + (f" dm_p1={r['dm_p_two_sided'] / 2 if r['dm_stat'] < 0 else 1 - r['dm_p_two_sided'] / 2:.3f}" if lab == "all" else ""))
    cov = ((c.y >= c.q10) & (c.y <= c.q90)).mean(); up7 = (c[c.horizon_days == 7].y > c[c.horizon_days == 7].q90).mean()
    out.append(f"cov {cov:.2f} h7>q90 {up7:.2f} q50r {c.loss_q50.sum() / max(ref.loss_q50.sum(), 1e-12):.3f}")
    print("  ".join(out), flush=True)
