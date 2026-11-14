"""Step 1: are panel entries/exits predictable from a provider's footprint elsewhere? Dev rows only (day <= 2026-10-13).
Usage: OMP_NUM_THREADS=2 PYTHONPATH=src .venv/bin/python experiments/entry/measure.py
Writes experiments/entry/results/{lift.txt,price.txt,events.parquet}."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
from gpuf import panel as P
from gpuf.data import starter_common as sc

CUT = sc.day_of(pd.Timestamp("2026-10-13").date())
OUT = Path(__file__).parent / "results"
K = (1, 3, 7)
rng = np.random.default_rng(0)

df = P.load()
df = df[df["day"] <= CUT]
provs = sorted(df["provider"].unique()); pidx = {p: i for i, p in enumerate(provs)}
df["pi"] = df["provider"].map(pidx)
panels = {s: sorted(set(map(tuple, df.loc[df.src == s, ["cls", "gpu", "tier"]].drop_duplicates().to_numpy()))) for s in P.SOURCES}
days = {s: np.sort(df.loc[df.src == s, "day"].unique()) for s in P.SOURCES}
price, med, pres = {}, {}, {}
for s in P.SOURCES:
    d = days[s]; di = {x: i for i, x in enumerate(d)}; pn = {k: i for i, k in enumerate(panels[s])}
    A = np.full((len(pn), len(provs), len(d)), np.nan); Md = np.full((len(pn), len(d)), np.nan)
    x = df[df.src == s]
    pj = np.array([pn[k] for k in zip(x.cls, x.gpu, x.tier)]); dj = x["day"].map(di).to_numpy()
    g = pd.DataFrame({"p": pj, "q": x.pi.to_numpy(), "t": dj, "v": x.price.to_numpy()})
    a = g.groupby(["p", "q", "t"]).v.median().reset_index()
    A[a.p, a.q, a.t] = a.v
    m = g.groupby(["p", "t"]).v.median().reset_index(); Md[m.p, m.t] = m.v
    price[s], med[s], pres[s] = A, Md, ~np.isnan(A)
other = {"fastgpu_daily": "gpurentalprices", "gpurentalprices": "fastgpu_daily"}

rows = []  # one row per (kind, src, panel, provider, t) at risk
ent_ev = []  # entry events for pricing
for s in P.SOURCES:
    pr, A, Md, d = pres[s], price[s], med[s], days[s]
    npn, nq, nt = pr.shape
    ever = np.cumsum(pr, axis=2) > 0
    entry = np.zeros_like(pr); entry[:, :, 1:] = pr[:, :, 1:] & ~ever[:, :, :-1]
    exitv = np.zeros_like(pr); exitv[:, :, 1:] = pr[:, :, :-1] & ~pr[:, :, 1:]
    Esum, Xsum = entry.sum(0), exitv.sum(0)  # prov x t
    first_panel_day = np.array([np.nonzero(pr[p].any(0))[0][0] if pr[p].any() else nt for p in range(npn)])
    gpus = np.array([k[1] for k in panels[s]]); clss = np.array([k[0] for k in panels[s]])
    o = other[s]; opn = {(k[0], k[1]): [] for k in panels[o]}
    for i, k in enumerate(panels[o]): opn[(k[0], k[1])].append(i)
    od = {x: i for i, x in enumerate(days[o])}
    seen_any_s = np.cumsum(pr.any(0), axis=1) > 0
    for t in range(8, nt):
        if d[t] - d[t - 1] != 1:
            continue
        seen_o = np.zeros(nq, bool)
        j = od.get(d[t - 1])
        if j is not None:
            seen_o = pres[o][:, :, :j + 1].any(axis=(0, 2))
        known = seen_any_s[:, t - 1] | seen_o
        for p in range(npn):
            if first_panel_day[p] > t - 1 or not pr[p, :, t - 1].any():
                continue
            here1 = pr[p, :, t - 1]
            ever_p = ever[p, :, t - 1]
            samegpu_oth = np.zeros(nq, bool)
            if j is not None:
                for oi in opn.get((clss[p], gpus[p]), []):
                    samegpu_oth |= pres[o][oi, :, j]
            oth_gpu = pr[gpus != gpus[p], :, t - 1].any(0) if (gpus != gpus[p]).any() else np.zeros(nq, bool)
            fl = {"a_same_gpu_other_coll": samegpu_oth, "b_other_gpu_same_coll": oth_gpu}
            for k in K:
                lo = max(t - k, 1)
                fl[f"c_entered_other_panel_{k}d"] = (Esum[:, lo:t] - entry[p, :, lo:t]).sum(1) > 0
                fl[f"d_left_other_panel_{k}d"] = (Xsum[:, lo:t] - exitv[p, :, lo:t]).sum(1) > 0
            for k in K:
                fl[f"e_left_same_gpu_other_coll_{k}d"] = np.zeros(nq, bool)
            if j is not None:
                for k in K:
                    lo = max(j - k + 1, 1); f = np.zeros(nq, bool)
                    for oi in opn.get((clss[p], gpus[p]), []):
                        ex = (pres[o][oi, :, lo - 1:j] & ~pres[o][oi, :, lo:j + 1]).any(1) if lo - 1 < j else np.zeros(nq, bool)
                        f |= ex
                    fl[f"e_left_same_gpu_other_coll_{k}d"] = f
            fl["any_footprint"] = fl["a_same_gpu_other_coll"] | fl["b_other_gpu_same_coll"]
            # entry: at risk = known to either collector, never in this panel
            risk = known & ~ever_p
            ev = entry[p, :, t]
            for q in np.nonzero(risk)[0]:
                rows.append(("entry", s, p, q, d[t], bool(ev[q]), *[bool(v[q]) for v in fl.values()]))
            # entries by providers never seen anywhere before (unpredictable)
            novel = ev & ~known
            for q in np.nonzero(novel)[0]:
                rows.append(("novel_entry", s, p, q, d[t], True, *[False] * len(fl)))
            # exit: at risk = present at t-1
            for q in np.nonzero(here1)[0]:
                rows.append(("exit", s, p, q, d[t], bool(exitv[p, q, t]), *[bool(v[q]) for v in fl.values()]))
            for q in np.nonzero(ev & known)[0]:
                ref_a = np.nan
                if j is not None:
                    c = [price_ for oi in opn.get((clss[p], gpus[p]), []) for price_ in [price[o][oi, q, j]] if not np.isnan(price_)]
                    if c:
                        oi_m = [med[o][oi, j] for oi in opn[(clss[p], gpus[p])] if not np.isnan(price[o][oi, q, j])]
                        ref_a = float(np.median(c)); scale = float(Md[p, t - 1] / np.median(oi_m))
                ob = (gpus != gpus[p]) & pr[:, q, t - 1]
                ratio = np.nan
                if ob.any():
                    ratio = float(np.mean(np.log(A[ob, q, t - 1] / Md[ob, t - 1])))
                ent_ev.append(dict(src=s, cls=clss[p], day=d[t], p=p, q=q, actual=A[p, q, t], med0=Md[p, t - 1],
                                   ref_a=ref_a, scale=scale if not np.isnan(ref_a) else np.nan, ratio_b=ratio))
names = list(fl.keys())
R = pd.DataFrame(rows, columns=["kind", "src", "panel", "prov", "day", "event"] + names)
R.to_parquet(OUT / "events.parquet")
E = pd.DataFrame(ent_ev)

lines = []
def lift(kind, sub, flagcol):
    s = sub[sub[flagcol]]; n = sub[~sub[flagcol]]
    r1, r0 = s.event.mean() if len(s) else np.nan, n.event.mean() if len(n) else np.nan
    ud = np.unique(sub.day); idx = {x: i for i, x in enumerate(ud)}
    di = sub.day.map(idx).to_numpy(); ev = sub.event.to_numpy(); fg = sub[flagcol].to_numpy()
    cnt = np.zeros((len(ud), 4))  # at-risk flagged, events flagged, at-risk all, events all
    np.add.at(cnt[:, 0], di, fg); np.add.at(cnt[:, 1], di, fg & ev); np.add.at(cnt[:, 2], di, 1); np.add.at(cnt[:, 3], di, ev)
    base = cnt[:, 3].sum() / cnt[:, 2].sum()
    ratios = []
    for _ in range(500):
        b = cnt[rng.integers(0, len(ud), len(ud))].sum(0)
        if b[0] > 0 and b[2] > 0 and b[3] > 0:
            ratios.append((b[1] / b[0]) / (b[3] / b[2]))
    lo, hi = np.quantile(ratios, [0.05, 0.95]) if ratios else (np.nan, np.nan)
    return (f"{kind:11s} {flagcol:34s} at-risk flagged {len(s):7d} events {int(s.event.sum()):4d} rate {r1:.4f} | "
            f"uncond {base:.5f} ({int(sub.event.sum())}/{len(sub)}) | lift {r1 / base:6.1f} [{lo:.1f},{hi:.1f}] "
            f"| precision {r1:.3f}")
for kind in ("entry", "exit"):
    for src in (None,) + P.SOURCES:
        sub = R[(R.kind == kind) & ((R.src == src) if src else True)]
        lines.append(f"--- {kind} {src or 'both'} at-risk {len(sub)} events {int(sub.event.sum())}")
        for c in names:
            lines.append(lift(kind, sub, c))
nov = R[R.kind == "novel_entry"]
lines.append(f"novel-provider entries (never seen on either collector before): {len(nov)}; entries by known providers: {int(R[(R.kind=='entry')].event.sum())}")
(OUT / "lift.txt").write_text("\n".join(lines)); print("\n".join(lines))

pl = []
E = E.dropna(subset=["actual", "med0"]).sort_values("day")
E["lr"] = np.log(E.actual / E.med0)
pool = []
for i, r in E.iterrows():
    prev = E[(E.src == r.src) & (E.day < r.day)].lr
    pool.append(float(prev.median()) if len(prev) >= 5 else 0.0)
E["pool_pred"] = pool
E["e_pool"] = np.abs(E.lr - E.pool_pred)
E["e_a_raw"] = np.abs(np.log(E.actual / E.ref_a))
E["e_a_scaled"] = np.abs(np.log(E.actual / (E.ref_a * E.scale)))
E["e_b"] = np.abs(E.lr - E.ratio_b)
pl.append(f"entries by known providers with price: {len(E)}")
for nm, m in (("a: same-GPU price on other collector", E.ref_a.notna()), ("b: ratio on other GPUs same collector", E.ratio_b.notna())):
    x = E[m]
    pl.append(f"{nm}: n={len(x)}  pooled err {x.e_pool.mean():.3f} (med {x.e_pool.median():.3f})")
    for c in ("e_a_raw", "e_a_scaled") if nm[0] == "a" else ("e_b",):
        d = (x[c] - x.e_pool).to_numpy()
        bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(1000)]
        pl.append(f"   {c}: mean abs log err {x[c].mean():.3f} (median {x[c].median():.3f}); diff vs pooled {d.mean():+.3f} [{np.quantile(bs,.05):+.3f},{np.quantile(bs,.95):+.3f}]; within 5% of actual: {(x[c]<0.05).mean():.2f} vs pooled {(x.e_pool<0.05).mean():.2f}")
(OUT / "price.txt").write_text("\n".join(pl)); print("\n".join(pl))
E.to_parquet(OUT / "entry_prices.parquet")
