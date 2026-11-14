"""H3: other instruments as signals. Dev origins only; signal dated under its own day basis (signals.py)."""
import sys
sys.path.insert(0, 'experiments/ecm')
from lib import *
import signals as S

st, cat, days, L = load()
c = cat.loc[list(L)]
headline = set(c.index[c.tier == 'headline'])
LAST = '2026-10-13'
cand = [s for s in L if c.loc[s, 'source_id'] != 'gpurentalprices_cheapest' and c.loc[s, 'gpu_model'] in S.FAM]
fam = {s: S.FAM[c.loc[s, 'gpu_model']] for s in cand}
mode = {s: ('spot' if c.loc[s, 'pricing_tier'] == 'spot' else 'on_demand') for s in cand}

SIG = {'GIX': S.gix(), 'gpueconomy_H100': S.gpueconomy(), 'GetDeploying_on_demand': S.getdeploying('on_demand'),
       'GetDeploying_spot': S.getdeploying('spot'), 'AWS_spot': S.aws_daily(LAST)}
# cheapest from the store
cheap = {}
for s in L:
    if c.loc[s, 'source_id'] == 'gpurentalprices_cheapest' and c.loc[s, 'pricing_tier'] == 'on_demand' and c.loc[s, 'gpu_model'] in S.FAM:
        cheap.setdefault(S.FAM[c.loc[s, 'gpu_model']], s)


def change(data, f, t, span=7, tol=3, stale=4):
    if f not in data:
        return np.nan
    d, v, kf = data[f]
    ok = np.where(kf <= t)[0]
    if len(ok) == 0:
        return np.nan
    i = ok[-1]
    if d[i] < t - stale:
        return np.nan
    j = np.where((d <= d[i] - span) & (d >= d[i] - span - tol))[0]
    if len(j) == 0:
        return np.nan
    return v[i] - v[j[-1]]


def x_for(name, s, t):
    f = fam[s]
    if name == 'GIX':
        return change(SIG['GIX'], f, t, 7, 3, 5)
    if name == 'gpueconomy_H100':
        return change(SIG['gpueconomy_H100'], f, t, 7, 0, 13)
    if name == 'GetDeploying':
        data = SIG['GetDeploying_' + mode[s]]
        return change(data, f, t, 7, 0, 13)
    if name == 'AWS_spot':
        return change(SIG['AWS_spot'], f, t, 7, 0, 3)
    if name == 'cheapest':
        k = cheap.get(f) or (cheap.get('A100_any') if f in ('A100_40', 'A100_80') else None)
        if k is None:
            return np.nan
        i = t - D0
        return L[k][i] - L[k][i - 7]
    return np.nan


# Compute Screener: documented zero overlap with dev
cs = pd.read_csv(P + 'index_prints.csv'); cs = cs[cs.source_id == 'computescreener']
print('Compute Screener first print', cs.print_date.min(), 'dev last origin', sc.date_of(DEV1), 'last target day', sc.date_of(CAP), '-> dev overlap rows:', int((cs.print_date <= '2026-10-13').sum()))

rows = []
for name in ['GIX', 'gpueconomy_H100', 'GetDeploying', 'AWS_spot', 'cheapest']:
    for s in cand:
        for t in ORIGINS:
            x = x_for(name, s, t)
            if not np.isfinite(x):
                continue
            for h in H:
                rows.append(dict(signal=name, sid=s, t=t, h=h, x=x, y=target(L, s, t, h), headline=s in headline,
                                 hs=c.loc[s, 'instrument_class'] == 'hyperscaler_spot', src=c.loc[s, 'source_id'], fam=fam[s]))
R = pd.DataFrame(rows)
R.to_pickle('runs/ecm/ext_rows.pkl')
out = []
cov = []
for name in R.signal.unique():
    d = R[R.signal == name]
    d1 = d[d.h == 7]
    cov.append(f"{name}: cells(h=7)={len(d1)} series={d1.sid.nunique()} origins={d1.t.nunique()} distinct x values={d1.x.round(6).nunique()} share x==0 {np.mean(d1.x.abs() < 1e-9):.2f} headline cells={int(d1.headline.sum())} headline series={d1[d1.headline].sid.nunique()}")
    out += screen(d, f'H3 {name} 7d change -> signed [all series]')
    if d.headline.sum() > 40:
        out += screen(d[d.headline], f'H3 {name} 7d change -> signed [headline]')
    out += screen(d, f'H3 {name} |7d change| -> |y| [all series]', absmode=True)
    if name == 'AWS_spot':
        out += screen(d[d.hs], f'H3 {name} -> signed [hyperscaler_spot targets]')
    for src in ['fastgpu_daily', 'gpurentalprices']:
        e = d[d.src == src]
        if len(e) > 60:
            out += screen(e, f'H3 {name} signed [{src}]', null=False)
txt = '\n'.join(cov) + '\n' + fmt(out)
print(txt)
open('experiments/ecm/results_ext.txt', 'w').write(txt + '\n')
