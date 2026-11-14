"""H1 pair gap and H2 own-panel position. Dev origins only; every feature uses days <= origin."""
import sys, json
sys.path.insert(0, 'experiments/ecm')
from lib import *

st, cat, days, L = load()
c = cat.loc[list(L)]
ds = pd.read_csv(P + 'daily_statistics.csv', parse_dates=['date'])
ds = ds[ds.date <= pd.Timestamp('2026-10-13')]
ds['day'] = ds.date.map(lambda d: sc.day_of(sc.parse_date(str(d.date()))))
ds['sid'] = ds.source_id + '.' + ds.instrument_class + '.' + ds.gpu_model.str.replace(' ', '_') + '.' + ds.pricing_tier + '.median'
headline = set(c.index[c.tier == 'headline'])

MINPER, WIN = 10, 30


def gapz(a, b, t, floor=0.01):
    i = t - D0
    g = L[a] - L[b]
    w = g[max(0, i - WIN):i]
    w = w[np.isfinite(w)]
    if len(w) < MINPER or not np.isfinite(g[i]):
        return np.nan, np.nan
    sd = max(w.std(ddof=1), floor)
    return (g[i] - w.mean()) / sd, g[i] - w.mean()


f = c[c.source_id == 'fastgpu_daily']; g = c[c.source_id == 'gpurentalprices']
norm = lambda x: {'A100 SXM 80GB': 'A100 80GB'}.get(x, x)
fk = {(r.instrument_class, r.gpu_model, r.pricing_tier): s for s, r in f.iterrows()}
gk = {(r.instrument_class, norm(r.gpu_model), r.pricing_tier): s for s, r in g.iterrows()}
exact = {(k): (fk[k], gk[k]) for k in fk if k in gk and k[1] != 'A100 80GB'}
alias = {k: (fk[k], gk[k]) for k in fk if k in gk and k[1] == 'A100 80GB'}
print('pairs exact', len(exact), 'alias', len(alias))

rows = []
for kind, pairs in (('exact', exact), ('alias', alias)):
    for k, (a, b) in pairs.items():
        for t in ORIGINS:
            z, graw = gapz(a, b, t)
            if not np.isfinite(z):
                continue
            for h in H:
                rows.append(dict(sid=a, side='fastgpu', kind=kind, cls=k[0], t=t, h=h, x=-z, y=target(L, a, t, h), raw=-graw, z=z))
                rows.append(dict(sid=b, side='gprice', kind=kind, cls=k[0], t=t, h=h, x=z, y=target(L, b, t, h), raw=graw, z=z))
R = pd.DataFrame(rows)
R['headline'] = R.sid.isin(headline)
R.to_pickle('runs/ecm/pair_rows.pkl')
print('origins with z:', R.t.nunique(), 'first', R.t.min(), 'series', R.sid.nunique(), 'headline series', R[R.headline].sid.nunique())
out = []
for lab, sel in [('H1 all pairs (closing signal)', R.kind == 'exact'),
                 ('H1 exact, fastgpu side', (R.kind == 'exact') & (R.side == 'fastgpu')),
                 ('H1 exact, gprice side', (R.kind == 'exact') & (R.side == 'gprice')),
                 ('H1 exact, headline series only', (R.kind == 'exact') & R.headline),
                 ('H1 exact, rate-card/list classes', (R.kind == 'exact') & R.cls.isin(['neocloud_rate_card', 'hyperscaler_list'])),
                 ('H1 exact, spot classes', (R.kind == 'exact') & R.cls.isin(['hyperscaler_spot', 'neocloud_spot'])),
                 ('H1 alias A100_80GB/SXM_80GB', R.kind == 'alias')]:
    out += screen(R[sel], lab)
# |z| vs |y|
for lab, sel in [('H1 |z| vs |y| exact all', R.kind == 'exact'), ('H1 |z| vs |y| exact headline', (R.kind == 'exact') & R.headline)]:
    out += screen(R[sel], lab, absmode=True)
# |z| > 2 subset
for thr in (1.0, 2.0):
    out += screen(R[(R.kind == 'exact') & (R.z.abs() > thr)], f'H1 exact |z|>{thr}', null=False)

# H2 own panel position
P25 = ds.pivot_table(index='day', columns='sid', values='p25_usd_per_gpu_hour', aggfunc='first')
P75 = ds.pivot_table(index='day', columns='sid', values='p75_usd_per_gpu_hour', aggfunc='first')
rows = []
for s in L:
    if s not in P25.columns:
        continue
    a = P25[s].reindex(np.arange(D0, CAP + 1)).ffill().to_numpy(); b = P75[s].reindex(np.arange(D0, CAP + 1)).ffill().to_numpy()
    for t in ORIGINS:
        i = t - D0
        med = np.exp(L[s][i]); lo, hi = a[i], b[i]
        w = L[s][max(0, i - WIN):i]; w = w[np.isfinite(w)]
        if len(w) < MINPER or not (lo > 0 and hi > lo and lo <= med <= hi) or not np.isfinite(L[s][i]):
            pos = np.nan
        else:
            pos = np.log(hi / med) - np.log(med / lo)
        dev = L[s][i] - np.median(w) if len(w) >= MINPER else np.nan
        # panel width as scale
        wid = np.log(hi / lo) if (lo > 0 and hi > lo) else np.nan
        for h in H:
            rows.append(dict(sid=s, t=t, h=h, y=target(L, s, t, h), pos=pos, dev=dev, wid=wid, headline=s in headline,
                             src=c.loc[s, 'source_id']))
Q = pd.DataFrame(rows)
Q.to_pickle('runs/ecm/own_rows.pkl')
for lab, sel in [('all', Q.src != ''), ('headline', Q.headline), ('fastgpu', Q.src == 'fastgpu_daily'), ('gprice', Q.src == 'gpurentalprices')]:
    d = Q[sel]
    out += screen(d.assign(x=d.dev), f'H2 level dev vs own 30d median [{lab}]')
    out += screen(d.assign(x=d.pos), f'H2 position asymmetry p75/p25 [{lab}]')
out += screen(Q.assign(x=Q.dev.abs()), 'H2 |dev| vs |y| [all]', absmode=True)
out += screen(Q.assign(x=Q.wid), 'H2 panel width log(p75/p25) vs |y| [all]', absmode=True)
out += screen(Q[Q.headline].assign(x=Q[Q.headline].wid), 'H2 panel width vs |y| [headline]', absmode=True)
txt = fmt(out)
print(txt)
open('experiments/ecm/results_own.txt', 'w').write(txt + '\n')
