"""Dev only. Score midstate variants in parallel; save each variant's cells to runs/midstate/<name>.parquet."""
import json, sys
from concurrent.futures import ProcessPoolExecutor
MIX = {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}
V = {
 "drift": ("drift", {}), "mix": ("mix", MIX),
 "mid14": ("midstate", {"state": "mid", "w": 14}),
 "midchg14": ("midstate", {"state": "midchg", "w": 14}),
 "mid7": ("midstate", {"state": "mid", "w": 7}),
 "mid21": ("midstate", {"state": "mid", "w": 21}),
 "mid14_last": ("midstate", {"state": "mid", "w": 14, "centre": "last"}),
 "midchg14_last": ("midstate", {"state": "midchg", "w": 14, "centre": "last"}),
 "mid14_b2": ("midstate", {"state": "mid", "w": 14, "bounds": [0.05, 0.3]}),
 "mid14_b5": ("midstate", {"state": "mid", "w": 14, "bounds": [0.01, 0.1, 0.3, 0.6]}),
 "mid14_tail": ("midstate", {"state": "mid", "w": 14, "tailsign": True}),
 "mid14_gap": ("midstate", {"state": "mid", "w": 14, "gapclip": 3.0}),
 "midchg14_k40": ("midstate", {"state": "midchg", "w": 14, "k": 40}),
 "mid14_nmin80": ("midstate", {"state": "mid", "w": 14, "nmin": 80}),
}
def one(name):
    from gpuf import harness, methods
    m, p = V[name]
    r = harness.evaluate(methods.get(m, **p), "dev", "rental_headline", name=m, params=p)
    r.cells.to_parquet(f"runs/midstate/{name}.parquet")
    return name
if __name__ == "__main__":
    names = sys.argv[1:] or list(V)
    with ProcessPoolExecutor(max_workers=6) as ex:
        for n in ex.map(one, names): print("done", n, flush=True)
