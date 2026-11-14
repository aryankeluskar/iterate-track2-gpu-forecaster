"""Part 2: changes aimed at the gpurentalprices H100 marketplace series, scored on that series and outside it."""
import json, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from score import ref
from gpuf import compare
K = compare.KEY
S = "gpurentalprices.marketplace_ask.H100_80GB.spot.median"
p0 = pd.read_parquet("runs/prov/L1_W21_gdyn.parquet"); mix = ref("mix")
B = p0.baseline_loss.sum()
out = {}
for n in ("p2_noret_mkt", "p2_bidir", "p2_mkt_base"):
    a = pd.read_parquet(f"runs/prov/{n}.parquet")
    r = {"skill": round(1 - a.loss.sum() / B, 4), "vs_prov": [round(x, 4) for x in [compare.paired(a, p0)["d_pooled_skill"], *compare.paired(a, p0)["ci90_d_pooled_skill"]]]}
    for nm, m in (("series", a.series_id == S), ("outside", a.series_id != S)):
        x, y = a[m], p0.merge(a[m][K], on=K)
        r[f"{nm}_gain_vs_prov_share_of_total_B"] = round(float((y.loss.sum() - x.loss.sum()) / B), 5)
        r[f"{nm}_cells_changed"] = int((x.sort_values(K)[["q10", "q50", "q90"]].to_numpy() != y.sort_values(K)[["q10", "q50", "q90"]].to_numpy()).any(1).sum())
    xs = a[a.series_id == S]; ms = mix[mix.series_id == S]; ps = p0[p0.series_id == S]
    r["series_skill(variant,prov,mix)"] = [round(1 - v.loss.sum() / v.baseline_loss.sum(), 4) for v in (xs, ps, ms)]
    out[n] = r
    print(n, json.dumps(r))
json.dump(out, open("experiments/prov/results/part2.json", "w"), indent=1)
