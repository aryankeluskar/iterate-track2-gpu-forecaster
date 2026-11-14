"""analog: forecast from the h-day log changes that followed the K most similar past (series, day) situations.

A state vector is computed for every (series, day) row from rows dated on or before that day. For an origin d and
horizon h the candidate neighbours are the situations (s, t) with t + h <= d, so their outcome is known at d. The
state table is built once per process from the series file (cut at `cap`, default the dev cap 2026-10-13) and each
origin filters it by date. Standardisation uses only situations dated <= d - h.

params
  pool     "self" | "cc" (collector, class) | "class" (class on any collector) | "all" (everything in the table)
  k        neighbours (30 to 300)
  kern     "tricube" (weight falls to 0 at the (k+1)-th distance) or "uniform"
  hl       half-life in days for recency weights on the neighbour's outcome day (0 = off)
  centre   "median" | "last" | float c: q50 = last * exp(c * weighted median)
  scale    multiplier on the log offsets of q10 and q90 from the centre
  rescale  scale neighbours' changes by clip(own mad30 / neighbour mad30)
  drop     list of feature groups to switch off: since n7 n14 mad7 mad30 size sign nprov pos
  min_n    below this many candidates fall back to `fallback` pool (then to a flat forecast)
  aws      include the AWS spot ticks table in the pool
  cap      last date the table may hold (ISO). Dev runs must keep the default.
  table    a prebuilt AnalogTable (tests)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from gpuf.methods import register

DEV_CAP = "2026-10-13"
CAP_SINCE = 30.0
HORIZONS = (1, 3, 7)
GROUPS = {"since": [0], "n7": [1], "n14": [2], "mad7": [3], "mad30": [4], "size": [5], "sign": [6, 7, 8],
          "nprov": [9], "pos": [10]}
NF = 11


def _wquantile(x, w, qs):
    o = np.argsort(x, kind="stable")
    x, w = x[o], w[o]
    cw = np.cumsum(w)
    p = (cw - 0.5 * w) / cw[-1]
    return np.interp(qs, p, x)


def _series_features(days, vals, nprov):
    """(n, NF) feature rows; row i uses only rows <= i."""
    n = len(vals)
    lv = np.log(vals)
    dl = np.r_[0.0, np.diff(lv)]
    chg = np.r_[False, vals[1:] != vals[:-1]]
    idx = np.arange(n)
    lastc = np.maximum.accumulate(np.where(chg, idx, -1))
    since = np.where(lastc >= 0, days - days[np.maximum(lastc, 0)], days - days[0])
    since = np.minimum(since, CAP_SINCE)
    cs = np.cumsum(chg)
    ab = np.cumsum(np.abs(dl))

    def win(w):
        p = np.searchsorted(days, days - w, side="right")  # first row with day > t - w
        return p

    def count(w):
        p = win(w)
        return cs - np.where(p > 0, cs[np.maximum(p - 1, 0)], 0)

    def mad(w):
        p = win(w)
        s = ab - np.where(p > 0, ab[np.maximum(p - 1, 0)], 0)
        first = np.where(p == 0, 1, 0)
        s = s - first * 0.0
        return s / w

    chi = np.nonzero(chg)[0]
    sg = np.sign(dl[chi]) if len(chi) else np.empty(0)
    sz = np.abs(dl[chi]) if len(chi) else np.empty(0)
    sign = np.zeros((n, 3))
    size = np.zeros(n)
    if len(chi):
        for k in range(3):
            j = cs - 1 - k
            ok = j >= 0
            sign[ok, k] = sg[j[ok]]
        ok = cs >= 1
        size[ok] = sz[cs[ok] - 1]
    s = pd.Series(lv, index=pd.to_datetime(days - 719163, unit="D"))
    lo = s.rolling("30D").min().to_numpy()
    hi = s.rolling("30D").max().to_numpy()
    rng = hi - lo
    pos = np.where(rng > 1e-12, (lv - lo) / np.where(rng > 1e-12, rng, 1.0), 0.5)
    F = np.empty((n, NF))
    F[:, 0] = since
    F[:, 1] = count(7)
    F[:, 2] = count(14)
    F[:, 3] = np.log(mad(7) + 1e-3)
    F[:, 4] = np.log(mad(30) + 1e-3)
    F[:, 5] = np.log1p(100 * size)
    F[:, 6:9] = sign
    F[:, 9] = np.log(np.maximum(nprov, 1.0))
    F[:, 10] = pos
    return F


def _outcomes(days, vals, h):
    lv = np.log(vals)
    j = np.searchsorted(days, days + h)
    jc = np.minimum(j, len(days) - 1)
    ok = (j < len(days)) & (days[jc] == days + h)
    out = np.full(len(days), np.nan)
    out[ok] = lv[jc[ok]] - lv[ok]
    return out


class AnalogTable:
    def __init__(self, df: pd.DataFrame, meta: dict, horizons=HORIZONS):
        """df: series_id, day, value, n_providers (rows past the cap already removed). meta: sid -> (collector, class)."""
        self.horizons = tuple(horizons)
        self.series = {}
        rows = []
        for sid, g in df.groupby("series_id", sort=True):
            g = g.sort_values("day")
            days = g["day"].to_numpy(np.int64)
            vals = g["value"].to_numpy(np.float64)
            if len(days) < 2 or not (vals > 0).all():
                continue
            npv = np.nan_to_num(g["n_providers"].to_numpy(np.float64), nan=1.0)
            F = _series_features(days, vals, npv)
            outs = {h: _outcomes(days, vals, h) for h in self.horizons}
            self.series[sid] = (days, vals, F)
            rows.append((sid, days, F, outs))
        self.sids = [r[0] for r in rows]
        code = {s: i for i, s in enumerate(self.sids)}
        self.meta = {s: meta.get(s, (None, None)) for s in self.sids}
        self.day = np.concatenate([r[1] for r in rows])
        self.F = np.vstack([r[2] for r in rows])
        self.sid_code = np.concatenate([np.full(len(r[1]), code[r[0]]) for r in rows])
        self.out = {h: np.concatenate([r[3][h] for r in rows]) for h in self.horizons}
        o = np.argsort(self.day, kind="stable")
        self.day, self.F, self.sid_code = self.day[o], self.F[o], self.sid_code[o]
        self.out = {h: v[o] for h, v in self.out.items()}
        self.cs = np.vstack([np.zeros(NF), np.cumsum(self.F, axis=0)])
        self.cs2 = np.vstack([np.zeros(NF), np.cumsum(self.F ** 2, axis=0)])
        self._pools = {}
        self._sd = {}

    def sd(self, upto_day):
        """Per-feature std over situations dated <= upto_day."""
        p = int(np.searchsorted(self.day, upto_day, side="right"))
        if p not in self._sd:
            n = max(p, 1)
            m = self.cs[p] / n
            v = self.cs2[p] / n - m ** 2
            s = np.sqrt(np.maximum(v, 0))
            self._sd[p] = np.where(s > 1e-9, s, 1.0)
        return self._sd[p]

    def pool(self, kind, sid, h):
        """Arrays (day, F, out, mad30) of candidate situations with a known h-day outcome, day-sorted."""
        c, cl = self.meta[sid]
        key = {"self": sid, "cc": (c, cl), "class": cl, "all": None}[kind]
        ck = (kind, key, h)
        if ck not in self._pools:
            if kind == "self":
                m = self.sid_code == self.sids.index(sid)
            elif kind == "cc":
                m = np.array([self.meta[s] == (c, cl) for s in self.sids])[self.sid_code]
            elif kind == "class":
                m = np.array([self.meta[s][1] == cl for s in self.sids])[self.sid_code]
            else:
                m = np.ones(len(self.day), bool)
            m = m & np.isfinite(self.out[h])
            self._pools[ck] = (self.day[m], self.F[m], self.out[h][m])
        return self._pools[ck]


_TABLES = {}


def load_table(cap=DEV_CAP, aws=False):
    key = (cap, aws)
    if key in _TABLES:
        return _TABLES[key]
    from gpuf import data
    cat = data.load_catalog()
    ok = cat[cat["table"].isin(["daily_statistics"] + (["aws_spot_ticks"] if aws else []))]
    meta = {r.series_id: (r.source_id, r.instrument_class) for r in ok.itertuples()}
    df = pd.read_csv(data.series_path(), usecols=["series_id", "date", "value", "n_providers"], low_memory=False)
    df = df[df["series_id"].isin(meta) & (df["date"] <= cap)].dropna(subset=["value"]).copy()
    df["day"] = pd.to_datetime(df["date"]).map(pd.Timestamp.toordinal).astype(np.int64)
    _TABLES[key] = AnalogTable(df, meta)
    return _TABLES[key]


@register("analog")
def make(pool="cc", k=100, kern="tricube", hl=0.0, centre="median", scale=1.0, rescale=False, drop=(), min_n=10,
         fallback="cc", aws=False, cap=DEV_CAP, table=None, lo=0.1, hi=0.9, w=None):
    wt = np.ones(NF)
    for g in drop:
        wt[GROUPS[g]] = 0.0
    for g, x in (w or {}).items():
        wt[GROUPS[g]] = float(x)
    tab = [table]

    def neigh(T, sid, f, origin_day, h, kind):
        d, F, out = T.pool(kind, sid, h)
        p = int(np.searchsorted(d, origin_day - h, side="right"))
        if p < min_n:
            return None
        sd = T.sd(origin_day - h)
        z = (F[:p] - f) * (wt / sd)
        d2 = np.einsum("ij,ij->i", z, z)
        kk = min(int(k), p)
        if kk < p:
            sel = np.argpartition(d2, kk)[: kk + 1]
            sel = sel[np.argsort(d2[sel])]
            dist = np.sqrt(d2[sel])
            dk = dist[-1]
            sel, dist = sel[:kk], dist[:kk]
        else:
            sel = np.arange(p)
            dist = np.sqrt(d2)
            dk = dist.max() * 1.0001 + 1e-9
        wts = np.ones(len(sel)) if kern == "uniform" else np.clip(1 - (dist / (dk + 1e-9)) ** 3, 0, 1) ** 3 + 1e-6
        if hl:
            wts = wts * 0.5 ** ((origin_day - (d[sel] + h)) / hl)
        x = out[sel]
        if rescale:
            m30 = np.exp(F[sel, 4]) - 1e-3
            x = x * np.clip((np.exp(f[4]) - 1e-3 + 1e-4) / (m30 + 1e-4), 0.25, 4.0)
        return x, wts

    def f(sid, days, vals, origin_day, horizons, ctx):
        T = tab[0] if tab[0] is not None else load_table(cap, aws)
        tab[0] = T
        last = float(vals[-1])
        row = T.series.get(sid)
        if row is None:
            return {h: (last, last, last) for h in horizons}
        sd_, sv_, SF = row
        pos = int(np.searchsorted(sd_, days[-1], side="right")) - 1
        if pos < 0 or sd_[pos] != days[-1] or abs(sv_[pos] - last) > 1e-12 * max(1.0, abs(last)):
            return {h: (last, last, last) for h in horizons}
        ft = SF[pos]
        res = {}
        for h in horizons:
            r = None
            for kind in dict.fromkeys([pool, fallback]):
                r = neigh(T, sid, ft, origin_day, h, kind)
                if r is not None:
                    break
            if r is None:
                res[h] = (last, last, last)
                continue
            x, wts = r
            a, b, c = _wquantile(x, wts, [lo, 0.5, hi])
            mid = b if centre == "median" else 0.0 if centre == "last" else float(centre) * b
            res[h] = (last * np.exp(mid + scale * (a - b)), last * np.exp(mid), last * np.exp(mid + scale * (c - b)))
        return res

    return f
