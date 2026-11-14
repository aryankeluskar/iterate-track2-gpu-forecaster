"""hyper: simulate the afhubbard offer panel (gpuf.panel_hyper, rows truncated at the origin) forward with
provider-level repricing waves drawn from that provider's own recent history, and read q10/q50/q90 from the
simulated medians. Other series go to `base`.

Dynamics per (instrument class, provider), pooled over the provider's offers on every afhubbard GPU series of that
class: for each provider-day in the trailing `W` days (a change on day d compares the offer's last snapshot of d-1
with that of d, both on or before the origin) the share of offers repriced and the list of nonzero log changes.
A simulated path picks provider-days in blocks of `L` consecutive days (block starts recency-weighted, half-life
`hl`); on each simulated day every offer of the provider reprices with that day's share, by a size drawn from that
day's own changes (so a gcp wave day keeps its sign and size mix, and an aws day its small two-sided steps).
The panel is the unique offers of the origin's last day at their last price; the simulated median is rescaled so
that the panel median equals the last value.

params
  W, L, hl, n_paths, seed   as above
  list    "zero": hyperscaler_list series get (last, last, last) when the series has not moved in `gate_days`
          days, else base; "base": base; "sim": simulate like the other classes
  sim_cls classes simulated (others -> base)
  centre  "sim" or "last" (q50 = last value, q10/q90 kept on either side)
  w       weight of hyper in a log-quantile blend with base where it applies
  base    [name, params]
"""
from __future__ import annotations

import warnings
import zlib

import numpy as np

from gpuf import panel_hyper as P
from gpuf.methods import get, register

DEFAULT_BASE = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]


def _prep():
    """{(cls, prov): (days, n, k, offsets, changes)}: per provider-day counts and the concatenated nonzero log
    changes of that day. Every entry is labelled with the day it is observed on."""
    L = P.load()
    rows = L["rows"]
    inv = {v: k[0] for k, v in L["series"].items()}
    od = rows.groupby(["ser", "key", "day"], sort=True).agg(prov=("prov", "first"), price=("price", "last")).reset_index()
    g = od.groupby(["ser", "key"], sort=False)
    m = ((od["day"] - g["day"].shift(1)) == 1).to_numpy()
    r = np.log(od["price"].to_numpy() / g["price"].shift(1).to_numpy())
    t = od.loc[m, ["ser", "prov", "day"]].assign(r=r[m])
    t["cls"] = t["ser"].map(inv)
    out = {}
    for (cls, pv), x in t.groupby(["cls", "prov"]):
        x = x.sort_values("day", kind="stable")
        days, first, n = np.unique(x["day"].to_numpy(), return_index=True, return_counts=True)
        rr = x["r"].to_numpy()
        nz = rr != 0
        dd = np.repeat(np.arange(len(days)), n)
        k = np.bincount(dd[nz], minlength=len(days))
        ch = rr[nz]
        off = np.r_[0, np.cumsum(k)[:-1]]
        out[(cls, int(pv))] = (days, n.astype(float), k.astype(float), off, ch)
    return out


@register("hyper")
def make(W=21, L=1, hl=0.0, n_paths=500, seed=0, list="zero", gate_days=14,
         sim_cls=("hyperscaler_spot", "neocloud_spot", "neocloud_rate_card"), centre="sim", w=1.0, base=None):
    base_spec = base or DEFAULT_BASE
    base_f = get(base_spec[0], **base_spec[1])
    st = {}

    def simulate(cls, o, provs, H, rng):
        N, m = n_paths, len(provs)
        R = np.zeros((N, m, H))
        for pv in np.unique(provs):
            x = st["dyn"].get((cls, int(pv)))
            if x is None:
                continue
            days, n, k, off, ch = x
            sel = np.nonzero((days <= o) & (days > o - W))[0]
            if not len(sel) or k[sel].sum() == 0:
                continue
            nd = len(sel)
            rw = 0.5 ** ((o - days[sel]) / hl) if hl else np.ones(nd)
            nbk = -(-H // L)
            starts = rng.choice(nd, size=(N, nbk), p=rw / rw.sum())
            pi = sel[((starts[:, :, None] + np.arange(L)[None, None, :]) % nd).reshape(N, -1)[:, :H]]
            share = k[pi] / n[pi]
            cols = np.nonzero(provs == pv)[0]
            U = rng.random((N, len(cols), H))
            mv = U < share[:, None, :]
            j = off[pi][:, None, :] + np.floor(rng.random((N, len(cols), H)) * np.maximum(k[pi], 1)[:, None, :]).astype(int)
            step = ch[np.minimum(j, len(ch) - 1)] if len(ch) else 0.0
            R[:, cols, :] = np.where(mv, step, 0.0)
        return np.cumsum(R, axis=2)

    def f(sid, days, vals, origin_day, horizons, ctx):
        if not P.supported(sid):
            return base_f(sid, days, vals, origin_day, horizons, ctx)
        cls = P.parse_sid(sid)[1]
        last = float(vals[-1])
        if cls == "hyperscaler_list" and list != "sim":
            if list == "zero":
                recent = vals[days > origin_day - gate_days]
                if len(recent) and np.all(recent == last) and days[0] <= origin_day - gate_days:
                    return {h: (last, last, last) for h in horizons}
            return base_f(sid, days, vals, origin_day, horizons, ctx)
        if cls not in sim_cls and cls != "hyperscaler_list":
            return base_f(sid, days, vals, origin_day, horizons, ctx)
        o_rows = P.offers(sid, origin_day)
        if len(o_rows) == 0:
            return base_f(sid, days, vals, origin_day, horizons, ctx)
        if not st:
            st["dyn"] = _prep()
        d_last = int(o_rows["day"].iat[-1])
        cur = o_rows[o_rows["day"] == d_last].groupby("key", sort=True).agg(prov=("prov", "first"), price=("price", "last"))
        px, provs = cur["price"].to_numpy(), cur["prov"].to_numpy()
        gap = int(origin_day - d_last)
        rng = np.random.default_rng(zlib.crc32(f"{sid}|{origin_day}".encode()) + int(seed))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            C = simulate(cls, origin_day, provs, max(horizons) + gap, rng)
        scale = last / float(np.median(px))
        res = {}
        for h in horizons:
            meds = np.median(px[None, :] * np.exp(C[:, :, h + gap - 1]), axis=1)
            q10, q50, q90 = (float(x) * scale for x in np.quantile(meds, [0.1, 0.5, 0.9]))
            if centre == "last":
                q10, q50, q90 = min(q10, last), last, max(q90, last)
            res[h] = (q10, q50, q90)
        if w < 1.0:
            b = base_f(sid, days, vals, origin_day, horizons, ctx)
            res = {h: tuple(float(np.exp(w * np.log(res[h][i]) + (1 - w) * np.log(b[h][i]))) for i in range(3))
                   for h in horizons}
        return res

    return f
