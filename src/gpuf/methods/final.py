"""final: the submitted forecaster (EVAL_PROTOCOL.md Amendment 2, rule 4): the equal-weight blend, mean of log
quantiles, of the validated members and every kept direction.

Members (exact params)
  mix        {"pool":"cc","k":20,"state":"chgk","sk":3,"hl":30}
  gbm        {"mode":"full","train":"all","save_importance":false}
  chronos    Chronos-Bolt-small, default context, centre = last          (file from gpuf.final_build)
  analog     {"pool":"all","k":600,"drop":["n14","sign"],"cap":cap}
  prov       {"L":1,"W":21,"gate":"dyn"}
  fm2        Chronos-Bolt-small, 16 days of context, centre = last, lo = 0.15 (grid file from gpuf.final_build)
  fragility  {"mode":"mix","boost":20,"bkind":"any"} (wraps the reference mix)

chronos and fm2 need torch, which cannot share a process with LightGBM here, so they are read from
runs/final/<member>_<tag>_<universe>.parquet (`python -m gpuf.final_build`). A missing file, origin or cell
raises. A member that cannot forecast a series is left out of that series' average:
  mix        fewer than 2 rows          gbm        fewer than 9 rows (returns no horizon)
  chronos/fm2 fewer than 8 rows         analog     no row of the series at the origin's last day in its table
  prov       no offer panel (afhubbard, tanod, cheapest) or no offers on or before the origin
  fragility  no offer panel, or the last value is more than 3 days old (where it would return plain mix)
prov's own dynamic gate (base = mix where no repricing provider sits near the middle) is kept: that is the
validated method. Members used per (series, origin, horizon) are recorded in `f.used`.

Membership and gate were fixed on dev by EVAL_PROTOCOL.md Amendment 3 (experiments/final/score.py,
results/dev.txt): no member's removal raises pooled skill in both halves on both universes, so all seven are
kept (the default); the gate [14, 1] is applied to non-headline series only (gate_scope "nonhead"), which is
what `bash reproduce.sh final` passes. prov's later switches `cal` and `ret_mkt` stay at their defaults.

params
  members     subset of MEMBERS (leave-one-out); one member returns that member's quantiles unchanged
  gate        [n, m]: last value with zero width when the series changed fewer than m times in the last n days
              and has at least n days of history (gpuf.methods.allrental.gated); null = off
  gate_scope  "all" or "nonhead" (gate only series outside the rental_headline universe)
  cap         analog table cap (ISO); must be on or after every origin. Dev: 2026-10-13. Sunday: 2026-11-06
  tag         file tag of the pretrained members: "dev" or the origin's ISO date
  universe    universe the pretrained files were built on (rental_all covers rental_headline)
  record      keep every member's output in f.outs (experiments)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from gpuf import panel
from gpuf.methods import get, register
from gpuf.methods.allrental import gated

MEMBERS = ("mix", "gbm", "chronos", "analog", "prov", "fm2", "fragility")
REF_MIX = {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}
SPECS = {
    "mix": ("mix", REF_MIX),
    "gbm": ("gbm", {"mode": "full", "train": "all", "save_importance": False}),
    "analog": ("analog", {"pool": "all", "k": 600, "drop": ["n14", "sign"]}),
    "prov": ("prov", {"L": 1, "W": 21, "gate": "dyn"}),
    "fragility": ("fragility", {"mode": "mix", "boost": 20, "bkind": "any"}),
}
FILE_MEMBERS = ("chronos", "fm2")
FM2_LO = 0.15
MIN_PRETRAINED = 8
DEV_CAP = "2026-10-13"


def _day(iso: str) -> int:
    import datetime as dt
    return dt.date.fromisoformat(iso).toordinal()


class _FileMember:
    """Read-back of one pretrained member; raises on a missing origin or cell for an eligible series."""

    def __init__(self, name, path):
        if not path.exists():
            raise FileNotFoundError(f"final: {name} file {path} missing; run python -m gpuf.final_build")
        self.name, self.path = name, path
        if name == "chronos":
            df = pd.read_parquet(path)
            self.tab = {(s, int(o), int(h)): (float(a), float(b), float(c)) for s, o, h, a, b, c in
                        df[["series_id", "origin_day", "horizon_days", "q10", "q50", "q90"]].itertuples(index=False)}
            self.origins = set(df["origin_day"].astype(int))
        else:
            self.origins = set(pd.read_parquet(path, columns=["origin_day"])["origin_day"].astype(int))
            self.f = get("fm2", grids=[str(path)], lo=FM2_LO, centre="last")

    def __call__(self, sid, days, vals, origin_day, horizons, ctx):
        o = int(origin_day)
        if o not in self.origins:
            raise KeyError(f"final: origin {o} not in {self.path}")
        if self.name == "chronos":
            out = {h: self.tab[(sid, o, h)] for h in horizons if (sid, o, h) in self.tab}
        else:
            out = self.f(sid, days, vals, origin_day, horizons, ctx)
        miss = [h for h in horizons if h not in out]
        if miss:
            raise KeyError(f"final: {self.name} has no cell for {sid} origin {o} horizons {miss} in {self.path}")
        return out


def can_forecast(name, sid, days, vals, origin_day, analog_table=None) -> bool:
    n = len(vals)
    if name == "mix":
        return n >= 2 and bool((vals > 0).all())
    if name in FILE_MEMBERS:
        return n >= MIN_PRETRAINED and bool((vals > 0).all())
    if name == "analog":
        row = analog_table.series.get(sid)
        if row is None:
            return False
        d, v, _ = row
        p = int(np.searchsorted(d, days[-1], side="right")) - 1
        return p >= 0 and d[p] == days[-1] and abs(v[p] - vals[-1]) <= 1e-12 * max(1.0, abs(float(vals[-1])))
    if name == "prov":
        return panel.supported(sid) and len(panel.offers(sid, origin_day)) > 0
    if name == "fragility":
        return panel.supported(sid) and origin_day - int(days[-1]) <= 3
    return True  # gbm: leaves horizons out itself


def blend(outs: dict, horizons, last: float) -> tuple[dict, dict]:
    """Equal-weight mean of log quantiles over the members that returned horizon h. One member: unchanged."""
    res, used = {}, {}
    for h in horizons:
        qs = [(m, o[h]) for m, o in outs.items() if o is not None and h in o]
        used[h] = tuple(m for m, _ in qs)
        if not qs:
            res[h] = (last, last, last)
        elif len(qs) == 1:
            res[h] = tuple(float(x) for x in qs[0][1])
        else:
            lq = np.log(np.maximum(np.array([q for _, q in qs], float), 1e-9)).mean(0)
            res[h] = tuple(float(x) for x in np.exp(lq))
    return res, used


@register("final")
def make(members=MEMBERS, gate=None, gate_scope="all", cap=DEV_CAP, tag="dev", universe="rental_all",
         record=False):
    from gpuf import data, final_build
    members = tuple(members)
    bad = set(members) - set(MEMBERS)
    if bad or not members:
        raise ValueError(f"final: unknown members {sorted(bad)}")
    if gate_scope not in ("all", "nonhead"):
        raise ValueError(gate_scope)
    fs, table = {}, None
    for m in members:
        if m in FILE_MEMBERS:
            fs[m] = _FileMember(m, final_build.path(m, tag, universe))
        else:
            name, p = SPECS[m]
            fs[m] = get(name, **({**p, "cap": cap} if m == "analog" else p))
    if "analog" in members:
        from gpuf.methods.analog import load_table
        table = load_table(cap)
    cap_day = _day(cap)
    head = set(data.universe("rental_headline")) if gate and gate_scope == "nonhead" else set()

    def f(sid, days, vals, origin_day, horizons, ctx):
        if "analog" in members and origin_day > cap_day:
            raise ValueError(f"final: origin {origin_day} after the analog cap {cap}; pass cap")
        last = float(vals[-1])
        g = bool(gate) and sid not in head and gated(days, vals, origin_day, int(gate[0]), int(gate[1]))
        f.gated[(sid, origin_day)] = g
        if g and not record:
            f.used[(sid, origin_day)] = {h: () for h in horizons}
            return {h: (last, last, last) for h in horizons}
        outs = {m: fs[m](sid, days, vals, origin_day, horizons, ctx) if can_forecast(m, sid, days, vals, origin_day, table)
                else None for m in members}
        res, used = blend(outs, horizons, last)
        if record:
            f.outs[(sid, origin_day)] = outs
        if g:
            used = {h: () for h in horizons}
            res = {h: (last, last, last) for h in horizons}
        f.used[(sid, origin_day)] = used
        return res

    f.used, f.gated, f.outs = {}, {}, {}
    return f
