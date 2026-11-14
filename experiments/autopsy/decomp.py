"""Offer panel, median reproduction and repricing/composition decomposition of median moves (dev rows only)."""
import numpy as np, pandas as pd

KEYS = {"fastgpu_daily": ["provider"], "gpurentalprices": ["provider", "sku_raw"],
        "afhubbard": ["provider", "region_raw", "sku_raw", "gpu_count"]}
TOL = 1e-9


def offer_panel(rows):
    """Adds an `offer` key column; one row per posted offer (afhubbard: per snapshot)."""
    out = []
    for src, g in rows.groupby("source_id"):
        g = g.copy()
        k = g[KEYS[src][0]].astype(object).fillna("").astype(str)
        for c in KEYS[src][1:]:
            k = k + "|" + g[c].astype(object).fillna("").astype(str)
        g["offer"] = k
        out.append(g)
    return pd.concat(out, ignore_index=True)


def day_tables(panel):
    """{series_id: {date: DataFrame(offer, provider, price)}}"""
    d = {}
    for (sid, dt), g in panel.groupby(["series_id", "dt"], sort=True):
        d.setdefault(sid, {})[dt] = g[["offer", "provider", "usd_per_gpu_hour"]].rename(columns={"usd_per_gpu_hour": "p"})
    return d


def label(rep, comp, tol=0.2):
    a, b = abs(rep), abs(comp)
    if a + b < TOL:
        return "none"
    s = a / (a + b)
    return "repricing" if s >= 1 - tol else "composition" if s <= tol else "mixed"


def decompose(A, B):
    """A, B: day tables (offer, provider, p). Returns dict of effects (log) and responsible providers."""
    ma, mb = float(np.median(A.p)), float(np.median(B.p))
    pa, pb = A.groupby("offer").p.mean(), B.groupby("offer").p.mean()
    both = pa.index.intersection(pb.index)
    # yesterday's rows at today's price where the offer survives (repricing first)
    cf = A.p.where(~A.offer.isin(both), A.offer.map(pb))
    mcf = float(np.median(cf))
    # reverse order: today's rows at yesterday's price where the offer existed (composition first)
    cf2 = B.p.where(~B.offer.isin(both), B.offer.map(pa))
    mcf2 = float(np.median(cf2))
    rep, comp = np.log(mcf / ma), np.log(mb / mcf)
    comp2, rep2 = np.log(mcf2 / ma), np.log(mb / mcf2)
    dp = (pb[both] - pa[both])
    rp = dp[dp.abs() > TOL]
    prov = A.drop_duplicates("offer").set_index("offer").provider.combine_first(B.drop_duplicates("offer").set_index("offer").provider)
    entered = pb.index.difference(pa.index)
    exited = pa.index.difference(pb.index)
    rep_up = sorted(set(prov[rp.index[rp > 0]]))
    rep_dn = sorted(set(prov[rp.index[rp < 0]]))
    return dict(m_a=ma, m_b=mb, m_cf=mcf, dlog=np.log(mb / ma), rep=rep, comp=comp,
                rep_shapley=(rep + rep2) / 2, comp_shapley=(comp + comp2) / 2,
                cause=label(rep, comp), cause_shapley=label((rep + rep2) / 2, (comp + comp2) / 2),
                n_a=len(A), n_b=len(B), n_offers_a=len(pa), n_offers_b=len(pb), n_both=len(both),
                n_repriced=len(rp), n_entered=len(entered), n_exited=len(exited),
                prov_reprice_up=",".join(rep_up), prov_reprice_down=",".join(rep_dn),
                prov_entered=",".join(sorted(set(prov[entered]))), prov_exited=",".join(sorted(set(prov[exited]))),
                pivotal=pivotal(A, B, pa, pb, both, ma, mb, prov))


def pivotal(A, B, pa, pb, both, ma, mb, prov):
    """Providers whose single action (reprice/entry/exit of their offers), applied alone to day A, moves A's median
    in the direction of the observed move; ranked by size."""
    res = []
    for pv in sorted(set(prov[pa.index.union(pb.index)])):
        offs = set(prov.index[prov == pv])
        a_rest = A[~A.offer.isin(offs)]
        b_mine = B[B.offer.isin(offs)]
        x = pd.concat([a_rest.p, b_mine.p])
        if not len(x):
            continue
        m = float(np.median(x))
        eff = np.log(m / ma)
        if abs(eff) > TOL and np.sign(eff) == np.sign(np.log(mb / ma)):
            res.append((abs(eff), pv))
    return ",".join(p for _, p in sorted(res, reverse=True)[:3])
