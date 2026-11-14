"""Step 1: profile non-headline loss on rental_all dev using last-value loss (truth table from drift dump origins)."""
import numpy as np, pandas as pd, sys
sys.path.insert(0, "experiments/allrental")
from lib import ctx, score, activity
store, meta, sids, head = ctx()
from gpuf import splits
rows = []
for o in splits.DEV:
    for s in sids:
        d, v = store.history(s, o)
        if len(d):
            for h in (1, 3, 7):
                rows.append((s, o, h, v[-1], v[-1], v[-1]))
fc = pd.DataFrame(rows, columns=["series_id", "origin_day", "horizon_days", "q10", "q50", "q90"])
c = score(fc, store, meta, sids, head)
c.to_parquet("runs/allrental/lv_cells.parquet")
tot = c.baseline_loss.sum()
print("cells", len(c), "series", c.series_id.nunique(), "head share", c[c["head"]].baseline_loss.sum() / tot)
nh = c[~c["head"]]
print("non-head zero-loss cell share", (nh.baseline_loss == 0).mean())
# per series profile at end of dev (origin 2026-10-06) using history to that origin only
o_end = splits.DEV[-1]
ser = nh.groupby("series_id").agg(loss=("baseline_loss", "sum"), cls=("cls", "first"), src=("src", "first"),
                                   n=("loss", "size"), price=("baseline", "median"))
ser["share"] = ser.loss / tot
feat = []
for s in ser.index:
    d, v = store.history(s, o_end)
    feat.append((s, len(d), activity(d, v, o_end, 30), activity(d, v, o_end, 60), int(o_end - d[-1]),
                 int((v[1:] != v[:-1]).sum()) / max(len(v) - 1, 1)))
f = pd.DataFrame(feat, columns=["series_id", "hist", "ch30", "ch60", "stale", "chg_rate"]).set_index("series_id")
ser = ser.join(f)
pd.set_option("display.width", 220); pd.set_option("display.max_rows", 200)
g = ser.groupby(["src", "cls"]).agg(n_ser=("loss", "size"), share=("share", "sum"),
     top1=("share", "max"), dead60=("ch60", lambda x: (x == 0).sum()), dead30=("ch30", lambda x: (x == 0).sum()),
     stale3=("stale", lambda x: (x > 3).sum()))
g["top1_frac"] = g.top1 / g.share
def top5(x): return x.nlargest(5).sum()
g["top5_frac"] = ser.groupby(["src", "cls"]).share.apply(top5) / g.share
print(g.sort_values("share", ascending=False).round(3))
print("\nby class:"); print(ser.groupby("cls").agg(n=("loss","size"), share=("share","sum"), dead60=("ch60", lambda x:(x==0).sum())).round(3))
print("\ntop 25 non-head series by loss share:")
print(ser.sort_values("share", ascending=False).head(25)[["share", "cls", "src", "price", "hist", "ch30", "ch60", "chg_rate", "stale"]].round(3))
# loss share of series by activity bucket (ch30 at end), and dead-series share of loss
ser["act"] = pd.cut(ser.ch30, [-1, 0, 2, 5, 10, 1000], labels=["0", "1-2", "3-5", "6-10", ">10"])
print("\nloss share by ch30 bucket (non-head):"); print(ser.groupby("act", observed=True).agg(n=("loss","size"), share=("share","sum")).round(3))
ser.to_csv("experiments/allrental/results/nonhead_series_profile.csv")
