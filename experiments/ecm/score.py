"""Score ecm variants on dev headline against the base (mix reference params) and drift. Dev only."""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, 'src')
from gpuf import compare, harness, methods

REF = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
VARIANTS = json.load(open(sys.argv[1]))
OUT = sys.argv[2]


def ev(name, params):
    return harness.evaluate(methods.get(name, **params), 'dev', 'rental_headline', name=name, params=params).cells


def q50_ratio(c, reps=1000, seed=0):
    num = c.loss_q50.to_numpy(); den = (0.5 * (c.y - c.baseline).abs()).to_numpy()
    wk = c.origin_week.to_numpy(); u, idx = np.unique(wk, return_inverse=True)
    sn = np.bincount(idx, weights=num); sd = np.bincount(idx, weights=den)
    rng = np.random.default_rng(seed); r = []
    for _ in range(reps):
        w = rng.integers(0, len(u), len(u)); r.append(sn[w].sum() / sd[w].sum())
    return num.sum() / den.sum(), np.percentile(r, [5, 95])


base = ev(*REF)
drift = ev('drift', {})
den_all = (0.5 * (base.y - base.baseline).abs()).sum()
print(f"base mix skill {1-base.loss.sum()/base.baseline_loss.sum():+.4f}  q50 ratio {q50_ratio(base)[0]:.4f}  drift skill {1-drift.loss.sum()/drift.baseline_loss.sum():+.4f}")
rows = []
for name, params in VARIANTS:
    p = dict(params); p['base'] = REF
    c = ev('ecm', p)
    sk = 1 - c.loss.sum() / c.baseline_loss.sum()
    pb = compare.paired(c, base)
    pdr = compare.paired(c, drift)
    r, (lo, hi) = q50_ratio(c)
    cov = float(((c.y >= c.q10) & (c.y <= c.q90)).mean())
    rec = dict(variant=name, params=params, skill=sk, d_vs_base=pb['d_pooled_skill'], ci_base=pb['ci90_d_pooled_skill'],
               d_vs_drift=pdr['d_pooled_skill'], ci_drift=pdr['ci90_d_pooled_skill'], q50_ratio=r, q50_ci=[lo, hi], cov=cov, n=len(c))
    m = c.merge(base[compare.KEY + ['loss', 'loss_q50']], on=compare.KEY, suffixes=('', '_b'))
    tot = m.baseline_loss.sum()
    rec['d_vs_base_by_source'] = {k: round(float((v.loss_b.sum() - v.loss.sum()) / tot), 5) for k, v in m.groupby('source_id')}
    rec['d_vs_base_by_h'] = {int(k): round(float((v.loss_b.sum() - v.loss.sum()) / tot), 5) for k, v in m.groupby('horizon_days')}
    den = lambda v: (0.5 * (v.y - v.baseline).abs()).sum()
    rec['q50_ratio_by_source'] = {k: round(float(v.loss_q50.sum() / den(v)), 4) for k, v in m.groupby('source_id')}
    rec['q50_ratio_by_h'] = {int(k): round(float(v.loss_q50.sum() / den(v)), 4) for k, v in m.groupby('horizon_days')}
    rec['q50_base_ratio_by_h'] = {int(k): round(float(v.loss_q50_b.sum() / den(v)), 4) for k, v in m.groupby('horizon_days')}
    rows.append(rec)
    print(f"{name:34s} skill {sk:+.4f} d_base {pb['d_pooled_skill']:+.4f} [{pb['ci90_d_pooled_skill'][0]:+.4f},{pb['ci90_d_pooled_skill'][1]:+.4f}] "
          f"d_drift {pdr['d_pooled_skill']:+.4f} q50ratio {r:.4f} [{lo:.4f},{hi:.4f}] cov {cov:.3f}", flush=True)
    print('    by source', rec['d_vs_base_by_source'], 'by h', rec['d_vs_base_by_h'], 'q50 by h', rec['q50_ratio_by_h'], flush=True)
json.dump(rows, open(OUT, 'w'), indent=1, default=float)
