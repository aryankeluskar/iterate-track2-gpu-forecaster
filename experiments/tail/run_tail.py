"""Score tail variants on dev headline for two bases; coverage per tail and horizon, paired diffs, outcome buckets."""
import json, sys
import numpy as np, pandas as pd
from gpuf import harness, methods, compare
pd.set_option("display.width", 250)
U = "rental_headline"
MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
ENS3 = ["ens", {"members": [["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}],
                            ["mix", {"pool": "cc", "k": 20, "state": "dirk", "sk": 7, "hl": 30}],
                            ["mix", {"pool": "all", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]]}]
V = {"conf_all": dict(mode="conf", pool="all"), "conf_cc": dict(mode="conf", pool="cc"),
     "conf_all_pw1": dict(mode="conf", pool="all", pw=1),
     "ew_all_hl14": dict(mode="conf", pool="all", hl=14), "ew_all_hl30": dict(mode="conf", pool="all", hl=30),
     "ew_cc_hl30": dict(mode="conf", pool="cc", hl=30),
     "aci_all_g.01": dict(mode="aci", pool="all", gamma=0.01), "aci_all_g.02": dict(mode="aci", pool="all", gamma=0.02),
     "aci_all_g.05": dict(mode="aci", pool="all", gamma=0.05), "aci_cc_g.02": dict(mode="aci", pool="cc", gamma=0.02),
     "scale_all": dict(mode="scale", pool="all"), "scale_cc": dict(mode="scale", pool="cc"),
     "scale_all_pw1": dict(mode="scale", pool="all", pw=1)}
extra = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
if extra.pop('__only__', False):
    V = {}
V.update(extra)

def ev(m, p, name=None):
    return harness.evaluate(methods.get(m, **p), "dev", U, name=name or m, params=p).cells

def bucket(c):
    r = np.log(c["y"] / c["baseline"])
    return pd.Series(np.select([r == 0, r.abs() < 0.01, r.abs() < 0.05, r > 0], ["0 none", "1 <1%", "2 1-5%", "3 up>5%"], "4 down>5%"), index=c.index)

def cov(c):
    g = c.groupby("horizon_days")
    return pd.DataFrame({"below_q10": g.apply(lambda v: (v.y < v.q10).mean()), "above_q90": g.apply(lambda v: (v.y > v.q90).mean())}).round(3)

out = {}
for bname, base in (("mix", MIX), ("ens3", ENS3)):
    bc = ev(*base, name="base")
    T = bc["baseline_loss"].sum()
    bk = bucket(bc)
    print(f"\n===== base={bname}: skill {1 - bc.loss.sum() / T:.4f}  coverage[q10,q90] {((bc.y >= bc.q10) & (bc.y <= bc.q90)).mean():.3f}")
    print(cov(bc).T.to_string())
    rows = []
    for vn, vp in V.items():
        c = ev("tail", {"base": base, **vp}, "tail")
        d = compare.paired(c, bc)
        cv = cov(c)
        row = dict(variant=vn, skill=1 - c.loss.sum() / T, d_vs_base=d["d_pooled_skill"], lo=d["ci90_d_pooled_skill"][0], hi=d["ci90_d_pooled_skill"][1],
                   cov=((c.y >= c.q10) & (c.y <= c.q90)).mean(), **{f"up{h}": cv.loc[h, "above_q90"] for h in (1, 3, 7)}, **{f"dn{h}": cv.loc[h, "below_q10"] for h in (1, 3, 7)})
        for h in (1, 3, 7):
            m = c.horizon_days == h
            row[f"dskill_h{h}"] = (bc.loss[m].sum() - c.loss[m].sum()) / T
        for k in sorted(bk.unique()):
            row[f"d_{k}"] = (bc.loss[bk == k].sum() - c.loss[bk == k].sum()) / T
        rows.append(row)
        out[(bname, vn)] = c
    df = pd.DataFrame(rows).set_index("variant")
    print(df.round(4).to_string())
    df.round(5).to_csv(f"experiments/tail/results/variants_{bname}{'_x' if len(sys.argv) > 1 else ''}.csv")
pd.to_pickle(out, "runs/tail/cells%s.pkl" % ("_x" if "__x" in "".join(sys.argv) else ""))
