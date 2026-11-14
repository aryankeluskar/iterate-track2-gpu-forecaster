import json, numpy as np, pandas as pd
from sweep import *
pd.set_option("display.width", 250)
cfgs = {"all_full": A(pool="all", k=600), "all_dropn14sign": A(pool="all", k=600, drop=["n14", "sign"]),
        "cc_full": A(pool="cc", k=600), "cc_dropnprov": A(pool="cc", k=600, drop=["nprov"]),
        "cc300": A(pool="cc", k=300), "all_dropn14sign_s12": A(pool="all", k=600, drop=["n14", "sign"], scale=1.2)}
for n, c in cfgs.items(): line(n, *c)
best = "all_dropn14sign"
for name in ("all_dropn14sign", "cc_full"):
    ens = ("ens", {"members": [list(MIX), [cfgs[name][0], cfgs[name][1]]]})
    line(f"blend mix + {name}", *ens)
ens3 = ("ens", {"members": [list(MIX), list(cfgs["all_dropn14sign"]), list(cfgs["cc_full"])]})
line("blend mix + all_dropn14sign + cc_full", *ens3)
d = cells("drift", {}); x = cells(*MIX); b = cells(*cfgs[best]); bl = cells("ens", {"members": [list(MIX), list(cfgs[best])]})
T = d.baseline_loss.sum()
r = np.log(d["y"] / d["baseline"])
kind = pd.Series(np.select([r == 0, r.abs() < 0.01, r.abs() < 0.05, r > 0], ["0 no change", "1 <1%", "2 1-5%", "3 up>5%"], "4 down>5%"), index=d.index)
def tab(col):
    out = {}
    for lab, c in (("drift", d), ("mix", x), (best, b), ("blend", bl)):
        g = c.groupby(col if not isinstance(col, pd.Series) else col.values)
        out[lab] = (1 - g.loss.sum() / g.baseline_loss.sum())
    return pd.DataFrame(out).round(3)
for col in ("source_id", "horizon_days", "instrument_class"):
    print("\nskill by", col); print(tab(col).to_string())
print("\nskill by outcome bucket (loss share of base in col base):")
t = tab(kind); t["base_share"] = (d.groupby(kind.values).baseline_loss.sum() / T).round(3); print(t.to_string())
print("\nloss relative to total last-value loss, by outcome bucket")
print(pd.DataFrame({l: c.groupby(kind.values).loss.sum() / T for l, c in (("drift", d), ("mix", x), (best, b), ("blend", bl))}).round(4).to_string())
print("\ncoverage by horizon", {h: round(float(((v.y >= v.q10) & (v.y <= v.q90)).mean()), 2) for h, v in b.groupby("horizon_days")})
print("share of truths above q90 by horizon", {h: round(float((v.y > v.q90).mean()), 2) for h, v in b.groupby("horizon_days")})
# top series moved vs mix
s = pd.DataFrame({"base": d.groupby("series_id").baseline_loss.sum(), "mix": x.groupby("series_id").loss.sum(), "an": b.groupby("series_id").loss.sum()})
s["gain_vs_mix"] = (s.mix - s.an) / T
print("\nlargest gains/losses vs mix as share of total base loss")
print(pd.concat([s.sort_values("gain_vs_mix").head(3), s.sort_values("gain_vs_mix").tail(3)])[["gain_vs_mix"]].round(4).to_string())
