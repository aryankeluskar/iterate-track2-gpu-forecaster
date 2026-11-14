"""Outcome-bucket breakdown of decision vs drift and mix on the test origins (share of baseline loss)."""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from gpuf import compare, harness, methods
from score import ORIG, MIX, DEC

r = {k: harness.evaluate(methods.get(m, **p), ORIG, "rental_headline", name=k).cells
     for k, (m, p) in {"decision": ("decision", DEC), "mix": ("mix", MIX), "drift": ("drift", {})}.items()}
m = r["decision"].merge(r["mix"][compare.KEY + ["loss"]], on=compare.KEY, suffixes=("", "_mix")).merge(
    r["drift"][compare.KEY + ["loss"]], on=compare.KEY, suffixes=("", "_drift"))
x = m["y"] / m["baseline"] - 1
m["bucket"] = np.select([x.abs() < 1e-9, x.abs() < 0.01, x.abs() <= 0.05, x > 0], ["no change", "<1%", "1-5%", "up>5%"], "down>5%")
B = m["baseline_loss"].sum()
for b, g in m.groupby("bucket"):
    print(f"{b:10s} n={len(g):4d} base_share={g.baseline_loss.sum()/B:.3f} vs_drift={(g.loss_drift.sum()-g.loss.sum())/B:+.4f} vs_mix={(g.loss_mix.sum()-g.loss.sum())/B:+.4f}")
