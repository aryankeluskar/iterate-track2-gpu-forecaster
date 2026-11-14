import json, sys, pathlib, datetime as dt
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from gpuf import panel
from final import CLASS_SLOT

R = pathlib.Path(__file__).parent / "results"
THR, MINPAIRS = 0.15, 14
rng = np.random.default_rng(0)
lab = pd.DataFrame([json.loads(l) for l in open(R / "provider_policy.jsonl")])[["provider", "slot", "label", "strength"]]
m = pd.read_csv(R / "measured_rates.csv")
m["slot"] = m.cls.map(CLASS_SLOT)
m = m.merge(lab, on=["provider", "slot"], how="left")
BRIEFED = set("verda scaleway spheron sfcompute aws nebius digitalocean crusoe lambdalabs hyperstack coreweave".split())
out = []
P = lambda *a: out.append(" ".join(str(x) for x in a))

# unit level: provider x collector x class
u = m[m.pairs >= MINPAIRS].copy()
u["hi"] = u.p_rep >= THR
P("## Unit table (provider x collector x class), pairs >= 14:", len(u), "units;", u.provider.nunique(), "providers")
P(u.sort_values("p_rep", ascending=False)[["provider", "src", "cls", "label", "strength", "offer_days", "pairs", "n_rep", "p_rep", "up_share"]].round(3).to_string(index=False))

# provider x slot level (collectors pooled)
ps = u.groupby(["provider", "slot", "label"], dropna=False).agg(pairs=("pairs", "sum"), n_rep=("n_rep", "sum"), n_up=("n_up", "sum")).reset_index()
ps["rate"] = ps.n_rep / ps.pairs
ps["up_share"] = ps.n_up / ps.n_rep.where(ps.n_rep > 0)
ps["hi"] = ps.rate >= THR
ps["label"] = ps.label.fillna("UNKNOWN")


def boot(df, f, B=1000):
    df = df.reset_index(drop=True); grp = {k: v.values for k, v in df.groupby("provider").groups.items()}; ids = list(grp); vals = []
    for _ in range(B):
        s = rng.choice(len(ids), len(ids)); d = df.iloc[np.concatenate([grp[ids[i]] for i in s])]
        v = f(d)
        if v == v: vals.append(v)
    return np.percentile(vals, [5, 95]).round(3)


def auc(d):
    pos, neg = d[d.hi & (d.label != "UNKNOWN")], d[(~d.hi) & (d.label != "UNKNOWN")]
    if len(pos) == 0 or len(neg) == 0: return np.nan
    sp, sn = (pos.label == "DYNAMIC").values.astype(float)[:, None], (neg.label == "DYNAMIC").values.astype(float)[None, :]
    return float(((sp > sn) + 0.5 * (sp == sn)).mean())


def report(df, name):
    P(f"\n## {name}: provider x slot units = {len(df)}")
    for l, g in df.groupby("label"):
        pooled = g.n_rep.sum() / g.pairs.sum()
        lo, hi = boot(g, lambda d: d.n_rep.sum() / d.pairs.sum())
        P(f"{l:8s} n_units={len(g):2d} pairs={g.pairs.sum():6d} pooled_rate={pooled:.3f} [{lo},{hi}] unit_mean={g.rate.mean():.3f} median={g.rate.median():.3f} share_hi={g.hi.mean():.2f} up_share_pooled={g.n_up.sum()/max(g.n_rep.sum(),1):.2f}")
    k = df[df.label != "UNKNOWN"]
    a = auc(k); lo, hi = boot(k, auc)
    P(f"AUC DYNAMIC vs rate>=15%: {a:.3f} 90% cluster-bootstrap [{lo},{hi}] on {len(k)} units ({int(k.hi.sum())} high-rate, {int((~k.hi).sum())} low-rate)")
    P("confusion (rows label, cols rate>=15%):")
    P(pd.crosstab(df.label, df.hi.map({True: "high", False: "low"})).to_string())


report(ps, "ALL provider-slot units")
report(ps[~ps.provider.isin(BRIEFED)], "NOT briefed providers (labeller was not told their rates)")
report(ps[ps.label.isin(["UNKNOWN"]) | (ps.strength != "weak") | True], "dummy") if False else None
strong = ps.merge(lab[["provider", "slot", "strength"]], on=["provider", "slot"], how="left")
report(strong[(strong.strength == "strong") | (strong.label == "UNKNOWN")], "STRONG-evidence labels only (plus UNKNOWN)")
for slot in ("RATE", "SPOT"):
    report(ps[ps.slot == slot], f"slot {slot}")
P("\n## provider x slot table")
P(ps.sort_values("rate", ascending=False).round(3).to_string(index=False))
P("\n## misses: label DYNAMIC & low, or FIXED & high")
P(ps[((ps.label == "DYNAMIC") & ~ps.hi) | ((ps.label == "FIXED") & ps.hi)].sort_values("rate").round(3).to_string(index=False))
P("\n## Verda units"); P(u[u.provider == "verda"][["src", "cls", "label", "offer_days", "pairs", "n_rep", "p_rep", "up_share"]].round(3).to_string(index=False))

# early-history test
CUT = dt.date(2026, 10, 13).toordinal(); LASTO = dt.date(2026, 10, 6).toordinal(); FIRSTO = dt.date(2026, 8, 18).toordinal()
df = panel.load(); df = df[df.day <= CUT].copy()
df["slot"] = df.cls.map(CLASS_SLOT)
df = df.sort_values(["src", "cls", "gpu", "tier", "key", "day"])
g = df.groupby(["src", "cls", "gpu", "tier", "key"])
df["pd"] = g["day"].shift(1); df["pp"] = g["price"].shift(1)
c = df[df.day - df.pd == 1].copy(); c["ch"] = (c.price != c.pp).astype(int)
cd = c.groupby(["src", "cls", "slot", "provider", "day"]).agg(k=("ch", "sum"), n=("ch", "size")).reset_index()
first = df.groupby(["src", "cls", "slot", "provider"]).day.min().rename("first").reset_index()
labmap = {(r.provider, r.slot): r.label for r in lab.itertuples()}
cd["label"] = [labmap.get((p, s), "UNKNOWN") for p, s in zip(cd.provider, cd.slot)]
rows = []
for r in first.itertuples():
    for hd in (3, 7, 13):
        o = r.first + hd - 1                      # origin day: provider has hd days of history including o
        if not (FIRSTO <= o <= LASTO): continue
        lbl = labmap.get((r.provider, r.slot), "UNKNOWN")
        own = cd[(cd.src == r.src) & (cd.cls == r.cls) & (cd.provider == r.provider)]
        truth_d = own[own.day > o]
        if truth_d.n.sum() < MINPAIRS: continue
        truth = truth_d.k.sum() / truth_d.n.sum()
        oth = cd[(cd.src == r.src) & (cd.cls == r.cls) & (cd.provider != r.provider) & (cd.day <= o)]
        if oth.n.sum() == 0: continue
        pooled = oth.k.sum() / oth.n.sum()
        o_lab = cd[(cd.slot == r.slot) & (cd.provider != r.provider) & (cd.label == lbl) & (cd.day <= o)] if lbl != "UNKNOWN" else oth
        lab_t = o_lab.k.sum() / o_lab.n.sum() if o_lab.n.sum() else pooled
        o_all = cd[(cd.slot == r.slot) & (cd.provider != r.provider) & (cd.label == lbl)] if lbl != "UNKNOWN" else cd[(cd.src == r.src) & (cd.cls == r.cls) & (cd.provider != r.provider)]
        lab_all = o_all.k.sum() / o_all.n.sum()
        rows.append(dict(src=r.src, cls=r.cls, provider=r.provider, label=lbl, hist_days=hd, origin=dt.date.fromordinal(o).isoformat(), truth=truth, truth_pairs=int(truth_d.n.sum()),
                         pooled=pooled, label_prior_to_origin=lab_t, label_prior_all_other_data=lab_all))
E = pd.DataFrame(rows)
E.to_csv(R / "early_history_cases.csv", index=False)
P("\n## Early-history test: cases (unit x history length), n =", len(E), "units =", E[["src", "cls", "provider"]].drop_duplicates().shape[0])
if len(E):
    for nm, col in (("pooled collector-class", "pooled"), ("label mean, other providers, data up to origin", "label_prior_to_origin"), ("label mean, other providers, all data to 10-13 (not origin-safe)", "label_prior_all_other_data")):
        E["err_" + col] = (E[col] - E.truth).abs()
    for hd, d in list(E.groupby("hist_days")) + [("all", E)]:
        P(f"history={hd}: n={len(d)}  MAE pooled={d.err_pooled.mean():.3f}  label(to origin)={d.err_label_prior_to_origin.mean():.3f}  label(all other)={d.err_label_prior_all_other_data.mean():.3f}  | const-zero={d.truth.mean():.3f} mean truth")
        for l, gg in d.groupby("label"):
            P(f"    {l:8s} n={len(gg):2d} truth={gg.truth.mean():.3f} pooled={gg.pooled.mean():.3f} lab_to_origin={gg.label_prior_to_origin.mean():.3f} lab_all={gg.label_prior_all_other_data.mean():.3f}")
    wc = E.provider.unique()
    # cluster bootstrap on provider for the paired difference at all lengths
    def diff(d, a, b): return (d["err_" + a] - d["err_" + b]).mean()
    ids = E.provider.unique(); bs = []; Eg = {i: E[E.provider == i] for i in ids}
    for _ in range(1000):
        s = rng.choice(ids, len(ids)); d = E[E.provider.isin(s)] if False else pd.concat([Eg[i] for i in s]); bs.append(diff(d, "pooled", "label_prior_to_origin"))
    P("paired error difference pooled - label(to origin), mean", round(diff(E, "pooled", "label_prior_to_origin"), 4), "90% provider-bootstrap", np.percentile(bs, [5, 95]).round(4))
    bs = []
    for _ in range(1000):
        s = rng.choice(ids, len(ids)); d = E[E.provider.isin(s)] if False else pd.concat([Eg[i] for i in s]); bs.append(diff(d, "pooled", "label_prior_all_other_data"))
    P("paired error difference pooled - label(all other data), mean", round(diff(E, "pooled", "label_prior_all_other_data"), 4), "90% provider-bootstrap", np.percentile(bs, [5, 95]).round(4))
    P(E.round(3).to_string(index=False))
(R / "score_report.txt").write_text("\n".join(out) + "\n")
print("\n".join(out))
