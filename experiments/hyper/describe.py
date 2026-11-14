"""Step 2: describe afhubbard repricing on rows dated <= 2026-10-13 (dev period = days >= 2026-08-11 unless noted)."""
import datetime as dt, resource, numpy as np, pandas as pd
from gpuf import data, panel_hyper as H
D = lambda s: dt.date.fromisoformat(s).toordinal()
CUT, DEV0 = D("2026-10-13"), D("2026-08-11")
L = H.load(); rows = L["rows"]; rows = rows[rows.day <= CUT]
inv = {v: k for k, v in L["series"].items()}; provs = L["provs"]
dup = rows.duplicated(["ser", "day", "snap", "key"]).mean()
print(f"rows {len(rows):,}; duplicate (ser,day,snap,key) share {dup:.4f}; snapshots/day {rows.groupby('day').snap.max().add(1).value_counts().to_dict()}")
# offer-day price = the day's last snapshot
od = rows.groupby(["ser", "key", "day"], sort=True).agg(prov=("prov", "first"), price=("price", "last")).reset_index()
od["cls"] = od.ser.map(lambda s: inv[s][0])
g = od.groupby(["ser", "key"])
od["pd"], od["pp"] = g.day.shift(1), g.price.shift(1)
c = od[(od.day - od.pd) == 1].copy()
c["r"] = np.log(c.price / c.pp); c["ch"] = c.r != 0
c["pname"] = c.prov.map(lambda p: provs[p])
dev = c[c.day >= DEV0]
print("\n== offer-day reprice rate, share up, median |size| (dev) by class x provider ==")
t = dev.groupby(["cls", "pname"]).agg(n=("ch", "size"), rate=("ch", "mean"),
    up=("r", lambda x: (x[x != 0] > 0).mean()), med_abs=("r", lambda x: x[x != 0].abs().median()),
    p90_abs=("r", lambda x: x[x != 0].abs().quantile(.9)))
t["share_of_reprices"] = (t.n * t.rate) / (t.n * t.rate).groupby(level=0).transform("sum")
print(t.round(4).to_string())
# provider-days: share of offers repriced (waves)
pdays = c.groupby(["cls", "pname", "day"]).agg(n=("ch", "size"), k=("ch", "sum"), up=("r", lambda x: (x > 0).sum()),
    mean_r=("r", lambda x: x[x != 0].mean() if (x != 0).any() else 0.0)).reset_index()
pdays["share"] = pdays.k / pdays.n
for name, sub in (("dev", pdays[pdays.day >= DEV0]), ("Jan-Oct13", pdays)):
    print(f"\n== provider-day wave stats ({name}): wave = provider-day with >=1 reprice ==")
    def ws(x):
        w = x[x.k > 0]
        nxt = x.set_index("day").k.gt(0)
        pers = (nxt & nxt.shift(1, fill_value=False)).sum() / max(nxt.shift(1, fill_value=False).sum(), 1)
        return pd.Series({"days": len(x), "wave_freq": len(w) / len(x), "share_med": w.share.median(), "share_p90": w.share.quantile(.9),
                          "big_wave_freq(share>.2)": (x.share > .2).mean(), "mixed_sign": ((w.up > 0) & (w.up < w.k)).mean(),
                          "p(wave|wave yday)": pers, "mean_r_med_abs": w.mean_r.abs().median()})
    print(sub.groupby(["cls", "pname"]).apply(ws).round(3).to_string())
# co-movement across providers on the same day
pd_any = pdays[pdays.day >= DEV0].assign(w=lambda x: x.k > 0).pivot_table(index="day", columns=["cls", "pname"], values="w", aggfunc="first")
print("\n== P(other provider/class waves | gcp spot waves) dev:", pd_any.loc[pd_any[("hyperscaler_spot", "gcp")] == True].mean().round(2).to_dict())
# AWS spot regional behaviour
aw = dev[(dev.cls == "hyperscaler_spot") & (dev.pname == "aws") & dev.ch]
print(f"\n== aws spot reprices (dev): n={len(aw)}, |r| quantiles {aw.r.abs().quantile([.1,.5,.9]).round(4).to_dict()}, up share {(aw.r>0).mean():.2f}")
ak = c[(c.cls == "hyperscaler_spot") & (c.pname == "aws")].sort_values(["ser", "key", "day"])
ak["prev_ch"] = ak.groupby(["ser", "key"]).r.shift(1)
x = ak.dropna(subset=["prev_ch"]); x = x[(x.prev_ch != 0) & (x.r != 0)]
print(f"   aws spot offer: corr of consecutive nonzero changes {np.corrcoef(x.r, x.prev_ch)[0,1]:.2f} (n={len(x)}), sign agree {(np.sign(x.r)==np.sign(x.prev_ch)).mean():.2f}")
# what moves the median: decompose daily median change
store = data.load_store(data.series_path())
ids = [s for s in data.universe("rental_all") if s.startswith("afhubbard.") and H.supported(s)]
rec = []
for s in ids:
    o = H.offers(s, CUT); sc = H.code(s); cls = s.split(".")[1]
    days = np.sort(o.day.unique()); days = days[days >= DEV0]
    for d in days:
        a, b = o[o.day == d - 1], o[o.day == d]
        if not len(a): continue
        m0, m1 = np.median(a.price), np.median(b.price)
        if m0 == m1: rec.append((s, cls, d, 0.0, "none", 0, 0)); continue
        # same-key counterfactual: yesterday's rows with today's last price per key where available (pure repricing)
        lastp = b.groupby("key").price.last()
        rp = a.key.map(lastp).fillna(a.price)
        mr = np.median(rp)
        rep_part = np.log(mr / m0); tot = np.log(m1 / m0)
        # how many offers changed and how many in the middle 10% ranks
        chk = (rp.to_numpy() != a.price.to_numpy())
        ranks = a.price.rank(pct=True).to_numpy()
        mid = (np.abs(ranks - .5) < .05)
        rec.append((s, cls, d, tot, "reprice" if abs(rep_part - tot) < 1e-9 else ("composition" if rep_part == 0 else "both"), chk.mean(), chk[mid].mean() if mid.any() else np.nan))
R = pd.DataFrame(rec, columns=["sid", "cls", "day", "r", "kind", "share_changed", "share_mid_changed"])
print("\n== daily median moves (dev, afhubbard series): share of series-days moving and their cause, by class ==")
mv = R[R.r != 0]
print(R.groupby("cls").apply(lambda x: pd.Series({"series_days": len(x), "move_rate": (x.r != 0).mean(),
    "abs_move_med": x.r[x.r != 0].abs().median(), "abs_move_p90": x.r[x.r != 0].abs().quantile(.9),
    "repricing_only": (x.kind == "reprice").sum() / max((x.r != 0).sum(), 1), "composition_only": (x.kind == "composition").sum() / max((x.r != 0).sum(), 1),
    "share_offers_changed_on_move_days": x.share_changed[x.r != 0].median(), "share_offers_changed_on_still_days": x.share_changed[x.r == 0].median(),
    "loss_weight_share_of_top10pct_moves": (x.r.abs().sort_values()[::-1].head(max(int(.1 * (x.r != 0).sum()), 1)).sum() / max(x.r.abs().sum(), 1e-12))})).round(3).to_string())
# hyperscaler_list steps: provider-wide? anything preceding?
hl = R[R.cls == "hyperscaler_list"]
print(f"\n== hyperscaler_list: {len(hl)} series-days, {int((hl.r!=0).sum())} moves; per series moves/day {(hl.r!=0).mean():.3f}")
st = hl[hl.r != 0].groupby("day").size()
print("   move days and #series moving that day:", {dt.date.fromordinal(int(k)).isoformat(): int(v) for k, v in st.items()})
hlpd = pdays[(pdays.cls == "hyperscaler_list")]
print("   hyperscaler_list provider-day reprice: ", hlpd[hlpd.day >= DEV0].groupby("pname").apply(lambda x: f"wave days {int((x.k>0).sum())}/{len(x)}, median share on wave days {x.share[x.k>0].median():.3f}").to_dict())
# precursors: is a series move day preceded within 3 days by a provider wave in hyperscaler_list / its spot sibling?
wd = set(hlpd[(hlpd.k > 0)].day)
md = sorted(set(hl[hl.r != 0].day)); still = sorted(set(hl[hl.r == 0].day) - set(md))
pre = lambda ds: np.mean([any((d - j) in wd for j in (1, 2, 3)) for d in ds]) if ds else np.nan
print(f"   P(any list-provider reprice in prior 3 days | series move day) {pre(md):.2f} vs | no-move day {pre(still):.2f}")
R.to_parquet("runs/hyper/median_moves.parquet"); pdays.to_parquet("runs/hyper/provider_days.parquet")
print(f"\nmaxrss {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1e9:.2f} GB")
