"""Third look (dev only): what the members do in the days right after a large one-day step in the published median."""
import numpy as np, pandas as pd
from gpuf import data
D = pd.read_parquet("runs/maturity/cells.parquet")
store = data.load_store(data.series_path())
MEM = ["mix", "gbm", "chronos", "analog", "prov", "fm2", "fragility"]
T = (0.1, 0.5, 0.9); Q = ("q10", "q50", "q90")
def pin(y, f, t):
    d = y - f; return np.maximum(t * d, (t - 1) * d)
def loss_of(members):
    tot = np.zeros(len(D))
    for t, q in zip(T, Q):
        L = np.log(np.maximum(np.stack([D[f"{m}_{q}"].to_numpy(float) for m in members]), 1e-9))
        n = (~np.isnan(L)).sum(0)
        f = np.where(n > 0, np.exp(np.nansum(L, 0) / np.maximum(n, 1)), D["last"].to_numpy())
        tot += pin(D["y"].to_numpy(), f, t)
    return tot / 3
SYS = {"drift": ["drift"], "mix": ["mix"], "final7": MEM, "no_pre": [m for m in MEM if m not in ("chronos", "fm2")],
       "analog": ["analog"], "prov": ["prov"], "fragility": ["fragility"], "gbm": ["gbm"], "chronos": ["chronos"], "fm2": ["fm2"]}
for k, m in SYS.items():
    D["L_" + k] = loss_of(m)
pairs = D[["series_id", "origin_day"]].drop_duplicates()
def recent(s, o):
    d, v = store.history(s, o)
    lv = np.log(v)
    big = 0.0; age = 99
    for k in range(1, min(4, len(v))):       # largest one-day step among the last three daily changes, and how many days ago
        c = lv[-k] - lv[-k - 1]
        if abs(c) > abs(big):
            big, age = c, k - 1
    return big, age
r = [recent(s, o) for s, o in zip(pairs.series_id, pairs.origin_day)]
pairs["step"], pairs["age"] = [x[0] for x in r], [x[1] for x in r]
D = D.merge(pairs, on=["series_id", "origin_day"])
C = list(SYS)
def tab(title, groups):
    print(f"\n## {title}")
    print(f"{'slice':<34}{'cells':>6}{'ser':>5}{'orig':>5}{'moved':>7} " + "".join(f"{c:>10}" for c in C))
    for lab, g in groups:
        if not len(g) or g.baseline_loss.sum() <= 0: continue
        print(f"{lab:<34}{len(g):>6}{g.series_id.nunique():>5}{g.origin_day.nunique():>5}{(g.y != g['last']).mean():>7.2f} " +
              "".join(f"{1 - g['L_' + c].sum() / g.baseline_loss.sum():>+10.4f}" for c in C))
for name, X in [("the 37 headline series", D[D.in37]), ("other active rental series", D[~D.in37 & ~D.gate14])]:
    a = X.step.abs()
    tab(f"{name}: by the largest one-day step in the last 3 days (log)", [("no step (0)", X[a == 0]), ("0 to 2%", X[(a > 0) & (a < 0.02)]),
        ("2 to 5%", X[(a >= 0.02) & (a < 0.05)]), ("5 to 10%", X[(a >= 0.05) & (a < 0.10)]), ("10% or more", X[a >= 0.10])])
    big = X[a >= 0.05]
    tab(f"{name}: step of 5% or more, by sign", [("up", big[big.step > 0]), ("down", big[big.step < 0])])
    tab(f"{name}: step of 5% or more, by horizon", [(f"h={h}", big[big.horizon_days == h]) for h in (1, 3, 7)])
    tab(f"{name}: step of 5% or more on the origin day itself", [("age 0", big[big.age == 0])])
    print(f"   loss share: cells with a step of 5% or more carry {big.L_final7.sum() / X.L_final7.sum():.2%} of final7's loss and {big.baseline_loss.sum() / X.baseline_loss.sum():.2%} of last-value loss ({len(big) / len(X):.1%} of cells)")
    # widths at h=7 after a big step
    g = big[big.horizon_days == 7]
    print("   h=7 after a 5%+ step: mean upper log distance " + "  ".join(f"{m} {np.log(g[m + '_q90'] / g['last']).mean():+.3f}" for m in ["mix", "chronos", "fm2", "analog", "prov"]) +
          f" | realised mean log change {np.log(g.y / g['last']).mean():+.3f}, mean abs {np.abs(np.log(g.y / g['last'])).mean():.3f}, unchanged {(g.y == g['last']).mean():.2f}")
