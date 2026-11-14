"""External signal tables, each dated under its own day basis. Used by screen_ext.py (analysis) and ecm.py (never, unless a
signal passes the screen). Returns dict name -> {family: (days array, values array, known_from array)} where
`known_from` is the first origin day on which the value may be used."""
import duckdb
import numpy as np, pandas as pd
from lib import P, sc

dd = lambda s: sc.day_of(sc.parse_date(str(s)[:10]))

FAM = {'A100 40GB': 'A100_40', 'A100 80GB': 'A100_80', 'A100 SXM 80GB': 'A100_80', 'A100 PCIe 80GB': 'A100_80',
       'H100 SXM 80GB': 'H100', 'H100 PCIe 80GB': 'H100', 'H100 80GB': 'H100', 'H100 NVL': 'H100',
       'H200': 'H200', 'H200 NVL': 'H200', 'B200': 'B200', 'B300': 'B300', 'L40S': 'L40S', 'T4': 'T4', 'V100': 'V100',
       'RTX A6000': 'A6000', 'RTX 6000 Ada': 'RTX6000Ada', 'RTX PRO 6000': 'PRO6000', 'L4': 'L4', 'A10': 'A10', 'A100 (memory unspecified)': 'A100_any'}


def gix():
    ip = pd.read_csv(P + 'index_prints.csv')
    ip = ip[(ip.source_id == 'gix') & ip.value_usd_per_gpu_hour.notna()]
    m = {'GIX_H100': ['H100'], 'GIX_H200': ['H200'], 'GIX_B200': ['B200'], 'GIX_A100': ['A100_40', 'A100_80']}
    out = {}
    for ix, fams in m.items():
        s = ip[ip.index_id == ix].sort_values('print_date')
        d = np.array([dd(x) for x in s.print_date]); v = np.log(s.value_usd_per_gpu_hour.to_numpy())
        for f in fams:
            out[f] = (d, v, d + 1)  # print of day D usable from D+1 (published 18:00-ish UTC on D; conservative)
    return out


def gpueconomy():
    ip = pd.read_csv(P + 'index_prints.csv')
    s = ip[ip.source_id.str.startswith('gpueconomy') & ip.value_usd_per_gpu_hour.notna()].sort_values('print_date')
    d = np.array([dd(x) for x in s.print_date]); v = np.log(s.value_usd_per_gpu_hour.to_numpy())
    return {'H100': (d, v, d + 7)}  # ISO week dated by Monday, known after the week ends (Monday + 7)


def getdeploying(mode):
    am = pd.read_csv(P + 'aggregator_medians.csv')
    am = am[(am.pricing_mode == mode) & am.median_usd_per_gpu_hour.notna()]
    m = {'NVIDIA H100': ['H100'], 'NVIDIA H200': ['H200'], 'NVIDIA B200': ['B200'], 'NVIDIA B300': ['B300'], 'NVIDIA L40S': ['L40S'],
         'NVIDIA A100': ['A100_40', 'A100_80', 'A100_any'], 'NVIDIA A6000': ['A6000'], 'NVIDIA V100': ['V100'], 'NVIDIA T4': ['T4'],
         'NVIDIA L4': ['L4'], 'NVIDIA A10': ['A10']}
    out = {}
    for g, fams in m.items():
        s = am[am.gpu_model == g].sort_values('week_start')
        if len(s) < 3:
            continue
        d = np.array([dd(x) for x in s.week_start]); v = np.log(s.median_usd_per_gpu_hour.to_numpy())
        for f in fams:
            out[f] = (d, v, d + 7)
    return out


AWS = {'p4d': 'A100_40', 'p4de': 'A100_80', 'p5': 'H100', 'p5e': 'H200', 'p5en': 'H200', 'p6-b200': 'B200', 'p6-b300': 'B300',
       'g4dn': 'T4', 'p3': 'V100', 'g6e': 'L40S'}


def aws_daily(last_day):
    """Median across (AZ, instance type) of the last Linux/UNIX per-GPU price on or before the end of each UTC day <= last_day."""
    files = [P + f'aws_spot_ticks/aws_spot_ticks_2026-{m:02d}.parquet' for m in (7, 8, 9, 10)]
    fams = ",".join(f"'{f}'" for f in AWS)
    q = f"""select family, instance_type, az_global_id, cast(ts_utc as date) d, arg_max(usd_per_gpu_hour, ts_utc) p
            from read_parquet({files}) where usd_per_gpu_hour is not null and family in ({fams})
            and cast(ts_utc as date) <= date '{last_day}' group by all"""
    t = duckdb.sql(q).df()
    t['d'] = t.d.map(dd)
    out = {}
    for fam, g in t.groupby('family'):
        pv = g.pivot_table(index='d', columns=['instance_type', 'az_global_id'], values='p', aggfunc='last')
        full = pv.reindex(np.arange(pv.index.min(), dd(last_day) + 1)).ffill()
        med = np.log(full.median(axis=1).to_numpy())
        d = full.index.to_numpy()
        out.setdefault(AWS[fam], []).append((d, med))
    res = {}
    for f, lst in out.items():
        start = max(x[0][0] for x in lst)
        v = np.mean([x[1][start - x[0][0]:] for x in lst], axis=0)
        d = np.arange(start, dd(last_day) + 1)
        res[f] = (d, v, d)  # tick at ts_utc on day D usable on origin D (end-of-day state; ticks carry their own timestamp)
    return res
