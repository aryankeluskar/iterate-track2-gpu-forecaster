import numpy as np, pandas as pd
pd.set_option("display.width",220); pd.set_option("display.max_columns",30)
from gpuf.scoring import pinball
from gpuf import data
c = pd.read_pickle("runs/calib/drift_cells.pkl")
store = data.load_store()
first = {s: store.arrays(s)[0][0] for s in c.series_id.unique()}
c["nh"] = c.origin_day - c.series_id.map(first) + 1
c["lo"] = c.q50 - c.q10; c["hi"] = c.q90 - c.q50
c["below"] = c.y < c.q10; c["above"] = c.y > c.q90
c["flat"] = (c.lo == 0) & (c.hi == 0)
B = c.baseline_loss.sum()
def rescored(df, cl, ch):
    q10 = df.q50 - cl * df.lo; q90 = df.q50 + ch * df.hi
    return (pinball(df.y.values, q10.values, .1) + pinball(df.y.values, df.q50.values, .5) + pinball(df.y.values, q90.values, .9)).sum() / 3
print("flat share", c.flat.mean(), "base total", B)
print("== coverage")
def cov(g): return pd.Series(dict(n=len(g), below=g.below.mean(), above=g.above.mean(), inside=1-g.below.mean()-g.above.mean(), loss_share=g.loss.sum()/c.loss.sum()))
for k in [["source_id"], ["instrument_class"], ["horizon_days"], ["source_id","instrument_class","horizon_days"]]:
    print(c[~c.flat].groupby(k).apply(cov, include_groups=False).round(3)); print()
c["hb"] = pd.cut(c.nh, [0, 20, 30, 40, 60, 80, 400])
print(c.groupby("hb", observed=True).apply(cov, include_groups=False).round(3))
print("== c sweep (joint c; also lower only / upper only), pooled skill vs last value, all dev")
cs = [0, .25, .5, .75, 1, 1.5]
for lab, f in [("both", lambda x: (x, x)), ("lower", lambda x: (x, 1)), ("upper", lambda x: (1, x))]:
    print(lab, [round(1 - rescored(c, *f(x)) / B, 4) for x in cs])
print("== by group (skill contribution as loss delta / total B), joint c")
for k, g in c.groupby(["source_id", "horizon_days"]):
    print(k, [round(-(rescored(g, x, x) - rescored(g, 1, 1)) / B, 4) for x in cs], "n", len(g))
for k, g in c.groupby(["source_id", "instrument_class"]):
    print(k, [round(-(rescored(g, x, x) - rescored(g, 1, 1)) / B, 4) for x in cs], "n", len(g))
print("== by group optimal separate lo/hi grid")
grid = [0, .25, .5, .75, 1, 1.25, 1.5]
for k, g in c.groupby(["source_id", "instrument_class", "horizon_days"]):
    bl = min(grid, key=lambda x: rescored(g, x, 1)); bh = min(grid, key=lambda x: rescored(g, 1, x))
    print(k, "c_lo*", bl, "c_hi*", bh, "gain", round(-(rescored(g, bl, bh) - rescored(g, 1, 1)) / B, 4))
