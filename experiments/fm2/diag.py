"""Dev only. Where does a pretrained width (centre = last) beat mix's width, and does it track recent volatility?
Usage: diag.py GRID.parquet"""
import sys
import numpy as np, pandas as pd
from gpuf import compare, data, harness, methods

K = compare.KEY
g = sys.argv[1]
fm = harness.evaluate(methods.get("fm2", grids=[g]), "dev", "rental_headline").cells
mx = harness.evaluate(methods.get("replay", path="runs/fm2/mix_dev_rental_headline.parquet"), "dev", "rental_headline").cells
c = fm.merge(mx[K + ["q10", "q90", "loss"]], on=K, suffixes=("", "_m"))
store = data.load_store(data.series_path())

feat = {}
for s, o in c[["series_id", "origin_day"]].drop_duplicates().itertuples(index=False):
    d, v = store.history(s, int(o))
    lv = np.log(v)
    r = np.diff(lv)
    dd = np.diff(d)
    rec = (d[1:] > o - 14)
    feat[(s, o)] = dict(n_hist=len(v), chg14=int((r[rec] != 0).sum()), vol14=np.abs(r[rec]).mean() if rec.any() else 0.0,
                        volall=np.abs(r).mean() if len(r) else 0.0, chg_last3=int((r[d[1:] > o - 3] != 0).sum()))
F = pd.DataFrame([dict(series_id=s, origin_day=o, **f) for (s, o), f in feat.items()])
c = c.merge(F, on=["series_id", "origin_day"])
c["w_fm"] = np.log(c["q90"] / c["q10"])
c["w_mix"] = np.log(c["q90_m"] / c["q10_m"])
c["up_fm"], c["up_mix"] = np.log(c["q90"] / c["baseline"]), np.log(c["q90_m"] / c["baseline"])
c["dn_fm"], c["dn_mix"] = np.log(c["baseline"] / c["q10"]), np.log(c["baseline"] / c["q10_m"])
c["move"] = np.abs(np.log(c["y"] / c["baseline"]))
c["gain"] = c["loss_m"] - c["loss"]  # > 0: fm better
B = c["baseline_loss"].sum()


def tab(by):
    t = c.groupby(by).apply(lambda x: pd.Series(dict(
        n=len(x), loss_share=x["baseline_loss"].sum() / B, gain_vs_mix=x["gain"].sum() / B,
        skill_fm=1 - x["loss"].sum() / x["baseline_loss"].sum(), skill_mix=1 - x["loss_m"].sum() / x["baseline_loss"].sum(),
        w_fm=x["w_fm"].median(), w_mix=x["w_mix"].median(), cov_fm=((x.y >= x.q10) & (x.y <= x.q90)).mean(),
        cov_mix=((x.y >= x.q10_m) & (x.y <= x.q90_m)).mean())), include_groups=False)
    print(t.round(4).to_string(), "\n")


c["hist"] = pd.cut(c["n_hist"], [0, 60, 90, 10 ** 6], labels=["<=60", "61-90", ">90"])
c["recent"] = np.where(c["chg_last3"] > 0, "chg<3d", np.where(c["chg14"] > 0, "chg4-14d", "quiet14d"))
c["volratio"] = pd.cut(c["vol14"] / c["volall"].replace(0, np.nan), [-1, 0.5, 1.5, 1e9], labels=["recent<long", "similar", "recent>long"])
for by in ["horizon_days", "instrument_class", "source_id", "hist", "recent", "volratio", ["horizon_days", "recent"]]:
    tab(by)
print("median offsets by horizon (log): up/dn")
print(c.groupby("horizon_days")[["up_fm", "up_mix", "dn_fm", "dn_mix"]].median().round(4).to_string(), "\n")
print("Spearman rank corr of width with: recent vol14, long-run volall, realised |move|")
for h, x in c.groupby("horizon_days"):
    sp = lambda a, b: x[a].rank().corr(x[b].rank())
    print(h, {w: (round(sp(w, "vol14"), 3), round(sp(w, "volall"), 3), round(sp(w, "move"), 3)) for w in ("w_fm", "w_mix")})
# regression of log width on log recent and log long-run vol (cells where both > 0)
x = c[(c.vol14 > 0) & (c.volall > 0)]
for w in ("w_fm", "w_mix"):
    X = np.c_[np.ones(len(x)), np.log(x.vol14), np.log(x.volall), np.log(x.horizon_days)]
    b = np.linalg.lstsq(X, np.log(x[w].clip(1e-5)), rcond=None)[0]
    print(w, "log width ~ log vol14 %.3f + log volall %.3f + log h %.3f" % tuple(b[1:]), f"(n={len(x)})")
print("\ntop series by gain vs mix (share of total baseline loss)")
s = c.groupby("series_id").apply(lambda x: pd.Series(dict(gain=x.gain.sum() / B, share=x.baseline_loss.sum() / B,
                                                          w_fm=x.w_fm.median(), w_mix=x.w_mix.median())), include_groups=False).sort_values("gain")
print(pd.concat([s.head(5), s.tail(5)]).round(4).to_string())
