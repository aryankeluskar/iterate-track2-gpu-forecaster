import sys
import numpy as np, pandas as pd
from scipy.stats import spearmanr
sys.path.insert(0, 'src')
from gpuf import data
from gpuf.data import starter_common as sc

P = 'data/pack/gpu-price-pack-v0.1.1-handover/'
D0 = sc.day_of(sc.parse_date('2026-07-01'))
DEV0 = sc.day_of(sc.parse_date('2026-08-18'))
DEV1 = sc.day_of(sc.parse_date('2026-10-06'))
CAP = sc.day_of(sc.parse_date('2026-10-13'))
H = (1, 3, 7)
ORIGINS = np.arange(DEV0, DEV1 + 1)


def iso(day):
    return str(sc.date_of(day)) if hasattr(sc, 'date_of') else day


def load():
    st = data.load_store()
    cat = data.load_catalog()
    cat = cat[cat.table == 'daily_statistics'].set_index('series_id')
    days = np.arange(D0, CAP + 1)
    L = {}
    for s in cat.index:
        d, v = st.history(s, CAP)
        m = (d >= D0) & (d <= CAP)
        if m.sum() < 15:
            continue
        g = np.full(len(days), np.nan)
        g[d[m] - D0] = v[m]
        L[s] = np.log(pd.Series(g).ffill().to_numpy())
    return st, cat, days, L


def target(L, s, t, h):
    return L[s][t + h - D0] - L[s][t - D0]


def _block_idx(weeks, rng):
    u = np.unique(weeks)
    groups = {w: np.where(weeks == w)[0] for w in u}
    return np.concatenate([groups[w] for w in rng.choice(u, len(u))])


def stats(x, y, weeks):
    x = np.asarray(x, float); y = np.asarray(y, float)
    b = (x * y).sum() / (x * x).sum()
    r = spearmanr(x, y)[0]
    return b, r


def screen(df, name, xcol='x', ycol='y', reps=600, seed=0, null=True, absmode=False, within=True):
    """df columns: sid, t, h, x, y, (week). Reports per horizon slope (through origin on demeaned-free x), spearman,
    90% week-block bootstrap CIs and two nulls: shuffled dates and circular shift of dates."""
    rows = []
    rng = np.random.default_rng(seed)
    for h in H:
        d = df[df.h == h].dropna(subset=[xcol, ycol])
        if len(d) < 25:
            rows.append(dict(signal=name, h=h, n=len(d), note='n<25'))
            continue
        d = d.copy()
        if absmode:
            d[xcol] = d[xcol].abs(); d[ycol] = d[ycol].abs()
        if within:
            d[xcol] = d[xcol] - d.groupby('sid')[xcol].transform('mean'); d[ycol] = d[ycol] - d.groupby('sid')[ycol].transform('mean')
        x = d[xcol].to_numpy(); y = d[ycol].to_numpy(); wk = (d.t.to_numpy() // 7)
        absmode_local = False
        b, r = stats(x, y, wk)
        bs, rs = [], []
        for _ in range(reps):
            ix = _block_idx(wk, rng)
            if np.ptp(x[ix]) == 0 or np.ptp(y[ix]) == 0:
                continue
            bb, rr = stats(x[ix], y[ix], wk[ix]); bs.append(bb); rs.append(rr)
        rec = dict(signal=name, h=h, n=len(d), n_series=d.sid.nunique(), n_dates=d.t.nunique(), n_weeks=len(np.unique(wk)),
                   slope=b, slope_lo=np.percentile(bs, 5), slope_hi=np.percentile(bs, 95),
                   rho=r, rho_lo=np.percentile(rs, 5), rho_hi=np.percentile(rs, 95))
        if null:
            piv = d.pivot_table(index='t', columns='sid', values=xcol if not absmode else xcol, aggfunc='first')
            ypv = d.pivot_table(index='t', columns='sid', values=ycol, aggfunc='first')
            dates = piv.index.to_numpy(); X = piv.to_numpy(); Y = ypv.reindex(index=piv.index, columns=piv.columns).to_numpy()
            T = len(dates)
            sh, cs = [], []
            for _ in range(300):
                for mode, out in (('shuffle', sh), ('circ', cs)):
                    if mode == 'shuffle':
                        Xp = X[rng.permutation(T)]
                    else:
                        if T < 16:
                            continue
                        Xp = np.roll(X, int(rng.integers(5, T - 5)), axis=0)
                    m = np.isfinite(Xp) & np.isfinite(Y)
                    if m.sum() > 10 and np.ptp(Xp[m]) > 0:
                        out.append(spearmanr(Xp[m], Y[m])[0])
            if sh:
                rec['rho_null_shuf_lo'], rec['rho_null_shuf_hi'] = np.percentile(sh, [2.5, 97.5])
                rec['p_shuf'] = float((np.abs(sh) >= abs(r)).mean())
            if cs:
                rec['rho_null_circ_lo'], rec['rho_null_circ_hi'] = np.percentile(cs, [2.5, 97.5])
                rec['p_circ'] = float((np.abs(cs) >= abs(r)).mean())
        rows.append(rec)
    return rows


def fmt(rows):
    out = []
    for r in rows:
        if 'note' in r:
            out.append(f"{r['signal']:42s} h={r['h']} n={r['n']} (too few)")
            continue
        s = (f"{r['signal']:42s} h={r['h']} n={r['n']:5d} ser={r['n_series']:2d} dates={r['n_dates']:2d} wk={r['n_weeks']:2d} "
             f"slope={r['slope']:+.3f} [{r['slope_lo']:+.3f},{r['slope_hi']:+.3f}] rho={r['rho']:+.3f} [{r['rho_lo']:+.3f},{r['rho_hi']:+.3f}]")
        if 'rho_null_shuf_lo' in r:
            s += f" | null shuf [{r['rho_null_shuf_lo']:+.2f},{r['rho_null_shuf_hi']:+.2f}] p={r['p_shuf']:.2f}"
        if 'rho_null_circ_lo' in r:
            s += f" circ [{r['rho_null_circ_lo']:+.2f},{r['rho_null_circ_hi']:+.2f}] p={r['p_circ']:.2f}"
        out.append(s)
    return '\n'.join(out)
