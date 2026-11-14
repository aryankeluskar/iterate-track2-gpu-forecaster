"""The scientist: research iterations on the practice dates with no human choice between steps.

  python -m gpuf.scientist run --checkpoint 2026-09-25 --iterations 8 --memory none|ledger|pastdev --rep r1 [--offline]
  python -m gpuf.scientist walkforward [--offline]       checkpoints 2026-09-18, 09-25, 10-02 (K=6), then 10-13 (K=8)
  python -m gpuf.scientist compare [--offline]           memory comparison at 2026-09-25, K=8, 3 conditions x 3 replicates
  python -m gpuf.scientist report                        tables from the journal -> experiments/scientist/results/
  python -m gpuf.scientist replay --run RUN_ID [--max-iter N]   offline replay of a recorded run, compared with its journal rows
  python -m gpuf.scientist validate SPEC.json            strict check of a candidate spec

A system is a base blend (equal-weight mean of log quantiles over the members available in a cell, as
gpuf.methods.final.blend) plus an ordered list of rules. A rule is {"when": condition, "do": action}; see GRAMMAR.
Each iteration: observe (failure report on selection cells), inspect (the model may ask for 3 breakdowns), recall
(--memory), prior (one Exa search, end published date = checkpoint), hypothesise (the model returns a claim, a
mechanism and a spec), dedupe, test (the gate of experiments/scientist/protocol.yaml), decide and record (journal row in
data_out/scientist_journal.jsonl, one memory record auto-<run>-i<k> as `experimenter`).

Selection cells at checkpoint C are the dev cells with origin + 7 <= C; the controller builds them as a separate store
(Store.subset) before anything else, so no cell with a later origin can reach the model, the report or the gate.
--offline sets GPUF_LLM_OFFLINE=1 PAST_OFFLINE=1 LOOP_OFFLINE=1: model replies, recalls and searches come from caches.
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "2")

import argparse
import copy
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
import time

import numpy as np

from . import data
from .store import ALL_MEMBERS, FACTS, MEMBERS, Store

ROOT = data.ROOT
JOURNAL = ROOT / "data_out/scientist_journal.jsonl"
OUTDIR = ROOT / "experiments/scientist/results"
RECALL_CACHE = ROOT / "experiments/scientist/cache/recall"
LEDGER = ROOT / "data_out/ledger.jsonl"
TAUS = (0.1, 0.5, 0.9)
MAX_CHECKPOINT = dt.date(2026, 10, 13)
EXA_CAP = 0.50
WRITE_WAIT = 20   # seconds to wait for a memory write to complete (the walk-forward of 14 Nov used 180)
WALK = ["2026-09-18", "2026-09-25", "2026-10-02"]
DEV_END = "2026-10-06"
BASE_SYSTEM = {
    "name": "final (submitted)",
    "base": {"members": list(MEMBERS)},
    "rules": [{"id": "gate14-nonhead", "claim": "the submitted system's 14-day zero-width gate on non-headline series (EVAL_PROTOCOL.md Amendment 3)",
               "when": {"all": [{"fact": "in37", "op": "==", "value": False}, {"fact": "gate14", "op": "==", "value": True}]},
               "do": {"action": "last_zero"}}],
}
MEMBER_TEXT = {
    "mix": "pooled empirical change quantiles conditioned on the series' recent-change state",
    "gbm": "gradient-boosted quantile regression on series features",
    "chronos": "pretrained time-series model (Chronos-Bolt-small, long context, centre = last value)",
    "analog": "nearest-neighbour analog windows across series",
    "prov": "simulation of the provider offers behind the published median",
    "fm2": "pretrained time-series model with 16 days of context, centre = last value",
    "fragility": "mix with tails moved to the one-offer-out and one-offer-in medians of the panel",
    "drift": "the organisers' baseline: last value times empirical quantiles of the series' own h-day log changes (not in the base blend)",
}


# ============================================================================= grammar
ACTIONS = {   # name: {param: (lo, hi) for numbers | "members"}
    "members_only": {"members": "members"},
    "drop_members": {"members": "members"},
    "add_drift": {},
    "last_zero": {},
    "scale_width": {"lo": (0.0, 3.0), "hi": (0.0, 3.0)},
    "centre_last": {},
    "cover_last": {},
    "shrink_to_last": {"w": (0.0, 1.0)},
}
ACTION_TEXT = {
    "members_only": "recompute the blend from only these members (cells where none of them gives a forecast keep the current forecast)",
    "drop_members": "recompute the blend without these members (from the members currently in the cell's blend)",
    "add_drift": "add drift as a member of the cell's blend and recompute it",
    "last_zero": "replace the forecast by the last value with zero width (q10 = q50 = q90 = last)",
    "scale_width": "multiply the log distance of q10 below q50 by lo and of q90 above q50 by hi (0..3; 1 = unchanged)",
    "centre_last": "move the whole forecast so q50 equals the last value, keeping its log distances",
    "cover_last": "widen the interval just enough to contain the last value (q10 = min(q10, last), q90 = max(q90, last))",
    "shrink_to_last": "move every quantile toward the last value in log: q = exp((1 - w) log q + w log last), w in 0..1",
}
MEMBER_ACTIONS = ("members_only", "drop_members", "add_drift")
NUM_OPS, BOOL_OPS, CAT_OPS = ("<", "<=", ">", ">=", "==", "!="), ("==", "!="), ("==", "!=", "in")
MAX_CMP, MAX_DEPTH = 6, 3


class SpecError(ValueError):
    pass


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v)


def validate_cond(c, cats: dict, depth: int = 0, count: list | None = None) -> None:
    count = [0] if count is None else count
    if not isinstance(c, dict):
        raise SpecError(f"a condition must be an object, got {type(c).__name__}")
    if depth > MAX_DEPTH:
        raise SpecError(f"conditions nest at most {MAX_DEPTH} levels")
    if set(c) in ({"all"}, {"any"}):
        k = next(iter(c))
        if not isinstance(c[k], list) or not c[k]:
            raise SpecError(f"'{k}' needs a non-empty list of conditions")
        for x in c[k]:
            validate_cond(x, cats, depth + 1, count)
        return
    if set(c) == {"not"}:
        return validate_cond(c["not"], cats, depth + 1, count)
    if set(c) != {"fact", "op", "value"}:
        raise SpecError(f"a comparison has exactly the keys fact, op, value (or all/any/not); got {sorted(c)}")
    f, op, v = c["fact"], c["op"], c["value"]
    if f not in FACTS:
        raise SpecError(f"unknown fact {f!r}; known: {', '.join(FACTS)}")
    kind = FACTS[f][0]
    count[0] += 1
    if count[0] > MAX_CMP:
        raise SpecError(f"at most {MAX_CMP} comparisons per condition")
    if kind == "num":
        if op not in NUM_OPS or not _num(v):
            raise SpecError(f"numeric fact {f!r} takes ops {NUM_OPS} and a finite number, got {op!r} {v!r}")
    elif kind == "bool":
        if op not in BOOL_OPS or not isinstance(v, bool):
            raise SpecError(f"boolean fact {f!r} takes ops {BOOL_OPS} and true/false, got {op!r} {v!r}")
    else:
        vals = v if op == "in" else [v]
        if op not in CAT_OPS or (op == "in" and (not isinstance(v, list) or not v)) or not all(isinstance(x, str) for x in vals):
            raise SpecError(f"category fact {f!r} takes ops {CAT_OPS} with a string (a non-empty list for 'in'), got {op!r} {v!r}")
        bad = [x for x in vals if x not in cats.get(f, [])]
        if bad:
            raise SpecError(f"unknown value(s) {bad} for {f!r}; known: {cats.get(f)}")


def validate_action(a) -> None:
    if not isinstance(a, dict) or "action" not in a:
        raise SpecError("'do' must be an object with an 'action' key")
    name = a["action"]
    if name not in ACTIONS:
        raise SpecError(f"unknown action {name!r}; allowed: {', '.join(ACTIONS)}")
    want = ACTIONS[name]
    extra, missing = set(a) - {"action"} - set(want), set(want) - set(a)
    if extra or missing:
        raise SpecError(f"action {name!r} takes exactly {sorted(want) or 'no parameters'}; extra {sorted(extra)}, missing {sorted(missing)}")
    for k, r in want.items():
        v = a[k]
        if r == "members":
            if not isinstance(v, list) or not v or len(set(v)) != len(v):
                raise SpecError(f"{name}.{k} must be a non-empty list of distinct members")
            bad = [m for m in v if m not in ALL_MEMBERS]
            if bad:
                raise SpecError(f"unknown member(s) {bad}; known: {', '.join(ALL_MEMBERS)}")
        elif not _num(v) or not r[0] <= v <= r[1]:
            raise SpecError(f"{name}.{k} must be a number in [{r[0]}, {r[1]}], got {v!r}")


def validate_spec(spec, cats: dict) -> None:
    if not isinstance(spec, dict) or set(spec) != {"when", "do"}:
        raise SpecError(f"a spec has exactly the keys when and do; got {sorted(spec) if isinstance(spec, dict) else type(spec).__name__}")
    validate_cond(spec["when"], cats)
    validate_action(spec["do"])


def canon_cond(c):
    if "fact" in c:
        f, op, v = c["fact"], c["op"], c["value"]
        if op == "in":
            vals = sorted(set(v))
            return {"fact": f, "op": "==", "value": vals[0]} if len(vals) == 1 else {"fact": f, "op": "in", "value": vals}
        if isinstance(v, bool):
            return {"fact": f, "op": "==", "value": v if op == "==" else not v}
        return {"fact": f, "op": op, "value": round(float(v), 6) if _num(v) else v}
    if "not" in c:
        inner = canon_cond(c["not"])
        if "not" in inner:
            return inner["not"]
        if "fact" in inner and isinstance(inner["value"], bool):
            return {**inner, "value": not inner["value"]}
        return {"not": inner}
    k = "all" if "all" in c else "any"
    kids = []
    for x in (canon_cond(y) for y in c[k]):
        kids.extend(x[k] if k in x else [x])
    uniq = {json.dumps(x, sort_keys=True): x for x in kids}
    kids = [uniq[s] for s in sorted(uniq)]
    return kids[0] if len(kids) == 1 else {k: kids}


def canon(spec: dict) -> dict:
    a = {k: (sorted(v) if isinstance(v, list) else round(float(v), 4) if _num(v) else v) for k, v in spec["do"].items()}
    return {"when": canon_cond(spec["when"]), "do": a}


def spec_hash(spec: dict) -> str:
    return hashlib.sha256(json.dumps(canon(spec), sort_keys=True).encode()).hexdigest()[:12]


# ============================================================================= evaluator
def cond_mask(S: Store, c) -> np.ndarray:
    if "all" in c:
        m = np.ones(S.n, bool)
        for x in c["all"]:
            m &= cond_mask(S, x)
        return m
    if "any" in c:
        m = np.zeros(S.n, bool)
        for x in c["any"]:
            m |= cond_mask(S, x)
        return m
    if "not" in c:
        return ~cond_mask(S, c["not"])
    x, op, v = S.facts[c["fact"]], c["op"], c["value"]
    if op == "in":
        return np.isin(x, list(v))
    if FACTS[c["fact"]][0] == "num":
        ok = np.isfinite(x)
        xx = np.where(ok, x, 0.0)
        r = {"<": xx < v, "<=": xx <= v, ">": xx > v, ">=": xx >= v, "==": xx == v, "!=": xx != v}[op]
        return r & ok
    return (x == v) if op == "==" else (x != v)


def _blend(S: Store, W: np.ndarray, rows: np.ndarray):
    use = W & S.avail[rows]
    cnt = use.sum(1)
    L = (S.Lq[rows] * use[:, :, None]).sum(1) / np.maximum(cnt, 1)[:, None]
    return np.exp(L), cnt > 0


def _mono(F: np.ndarray) -> np.ndarray:
    """starter _common.monotone, as the harness applies it: q10 = min(q10, q50), q90 = max(q90, q50); then the positive floor."""
    F = np.stack([np.minimum(F[:, 0], F[:, 1]), F[:, 1], np.maximum(F[:, 2], F[:, 1])], 1)
    return np.maximum(F, 1e-6)


def init_state(S: Store, system: dict) -> dict:
    W = np.zeros((S.n, len(ALL_MEMBERS)), bool)
    W[:, [ALL_MEMBERS.index(m) for m in system["base"]["members"]]] = True
    F, ok = _blend(S, W, np.arange(S.n))
    F[~ok] = S.lastv[~ok, None]
    return {"W": W, "F": _mono(F)}


def apply_rule(S: Store, st: dict, rule: dict) -> dict:
    """The state after one rule: member actions recompute the blend in their cells (overriding earlier value actions
    there); value actions transform the current quantiles. The harness's monotone fix is applied after every rule."""
    W, F = st["W"].copy(), st["F"].copy()
    idx = np.nonzero(cond_mask(S, rule["when"]))[0]
    a = rule["do"]
    name = a["action"]
    if len(idx) == 0:
        return {"W": W, "F": F}
    last = S.lastv[idx, None]
    if name in MEMBER_ACTIONS:
        W2 = W[idx].copy()
        if name == "members_only":
            W2[:] = False
            W2[:, [ALL_MEMBERS.index(m) for m in a["members"]]] = True
        elif name == "drop_members":
            W2[:, [ALL_MEMBERS.index(m) for m in a["members"]]] = False
        else:
            W2[:, ALL_MEMBERS.index("drift")] = True
        F2, ok = _blend(S, W2, idx)
        W[idx[ok]], F[idx[ok]] = W2[ok], F2[ok]
    else:
        q = F[idx]
        if name == "last_zero":
            q = np.repeat(last, 3, 1)
        elif name == "scale_width":
            c = q[:, 1:2]
            q = np.concatenate([c * np.exp(a["lo"] * np.log(q[:, :1] / c)), c, c * np.exp(a["hi"] * np.log(q[:, 2:] / c))], 1)
        elif name == "centre_last":
            q = q * (last / q[:, 1:2])
        elif name == "cover_last":
            q = np.concatenate([np.minimum(q[:, :1], last), q[:, 1:2], np.maximum(q[:, 2:], last)], 1)
        elif name == "shrink_to_last":
            q = np.exp((1 - a["w"]) * np.log(q) + a["w"] * np.log(last))
        F[idx] = q
    F[idx] = _mono(F[idx])
    return {"W": W, "F": F}


def run_system(S: Store, system: dict, upto: int | None = None) -> dict:
    st = init_state(S, system)
    for r in system["rules"][:upto]:
        st = apply_rule(S, st, r)
    return st


def cell_loss(S: Store, F: np.ndarray) -> np.ndarray:
    from .scoring import pinball
    return sum(pinball(S.y, F[:, i], t) for i, t in enumerate(TAUS)) / 3.0


def skill(S: Store, L: np.ndarray, m=None) -> float:
    m = np.ones(S.n, bool) if m is None else m
    b = S.bl[m].sum()
    return float(1 - L[m].sum() / b) if b > 0 else float("nan")


def week_boot(S: Store, L0, L1, m=None, reps=2000, seed=0):
    """ISO-week block bootstrap of d pooled skill (L0 -> L1), as gpuf.compare.paired: (share > 0, 5%, 95%)."""
    m = np.ones(S.n, bool) if m is None else m
    weeks, wi = np.unique(S.week[m], return_inverse=True)
    W = len(weeks)
    s0, s1, sb = (np.bincount(wi, weights=x[m], minlength=W) for x in (L0, L1, S.bl))
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, W, size=(reps, W))
    M = np.zeros((reps, W))
    np.add.at(M, (np.repeat(np.arange(reps), W), draws.ravel()), 1.0)
    ds = (M @ s0 - M @ s1) / (M @ sb)
    return float((ds > 0).mean()), float(np.quantile(ds, 0.05)), float(np.quantile(ds, 0.95)), int(W)


def gate(S: Store, F0: np.ndarray, F1: np.ndarray) -> dict:
    """The gate of protocol.yaml on the selection store S (current system F0, candidate F1)."""
    L0, L1 = cell_loss(S, F0), cell_loss(S, F1)
    o = np.unique(S.origin)
    first = S.origin < o[len(o) // 2]
    d = lambda m: float((L0[m].sum() - L1[m].sum()) / S.bl[m].sum()) if S.bl[m].sum() > 0 else 0.0
    h37 = S.facts["in37"]
    ch = (np.abs(F1 - F0) > 1e-9 * np.abs(F0)).any(1)
    share, lo, hi, nw = week_boot(S, L0, L1)
    g = {"d_all": d(np.ones(S.n, bool)), "d_first": d(first), "d_second": d(~first), "d37": d(h37),
         "changed_cells": int(ch.sum()), "changed_series": int(len(set(S.sid[ch]))), "boot_share_pos": share, "boot_ci90": [lo, hi], "weeks": nw,
         "skill_before": skill(S, L0), "skill_after": skill(S, L1), "skill37_before": skill(S, L0, h37), "skill37_after": skill(S, L1, h37),
         "halves": [str(dt.date.fromordinal(int(o[0]))), str(dt.date.fromordinal(int(o[len(o) // 2]))), str(dt.date.fromordinal(int(o[-1])))]}
    g["checks"] = {"halves_positive": g["d_first"] > 0 and g["d_second"] > 0, "all_positive": g["d_all"] > 0,
                   "changed_200_cells_5_series": g["changed_cells"] >= 200 and g["changed_series"] >= 5,
                   "headline37_not_lower": g["d37"] >= -1e-9, "bootstrap_90pct_positive": share >= 0.90}
    g["pass"] = all(g["checks"].values())
    return {k: (round(v, 6) if isinstance(v, float) else [round(x, 6) for x in v] if k == "boot_ci90" else v) for k, v in g.items()}


# ============================================================================= selection view
def _o(s: str) -> int:
    return dt.date.fromisoformat(s).toordinal()


def selection(S: Store, checkpoint: str) -> Store:
    """Dev cells whose origin is at least 7 days before the checkpoint, as a separate store."""
    if dt.date.fromisoformat(checkpoint) > MAX_CHECKPOINT:
        raise PermissionError(f"REFUSED: checkpoint {checkpoint} is after 2026-10-13 (the last day of dev outcomes)")
    idx = np.nonzero(S.origin + 7 <= _o(checkpoint))[0]
    if not len(idx):
        raise SystemExit(f"error: no selection origins at checkpoint {checkpoint}")
    return S.subset(idx)


def window(S: Store, a: str, b: str) -> Store:
    return S.subset(np.nonzero((S.origin >= _o(a)) & (S.origin <= _o(b)))[0])


# ============================================================================= failure report and breakdowns
def _bins(x: np.ndarray, name: str):
    ok = np.isfinite(x)
    if not ok.any():
        return [(f"{name} missing", ~ok)]
    lo0 = x[ok].min()
    e = [v for v in np.unique(np.round(np.nanquantile(x[ok], [0.25, 0.5, 0.75]), 4)) if v > lo0]
    if len(e) < 2 and (x[ok] > lo0).sum() > 1:   # mass at the minimum (e.g. no change): cut the rest at its terciles
        e = sorted(set(e) | {v for v in np.unique(np.round(np.nanquantile(x[ok][x[ok] > lo0], [0.34, 0.67]), 4)) if v > lo0})
    out, lo = [], None
    for v in e + [None]:
        m = ok & (x >= lo if lo is not None else True) & (x < v if v is not None else True)
        lab = (f"{name} < {v:g}" if lo is None else f"{lo:g} <= {name}" if v is None else f"{lo:g} <= {name} < {v:g}") if (lo is not None or v is not None) else f"{name} all"
        out.append((lab, m))
        lo = v
    if (~ok).any():
        out.append((f"{name} missing", ~ok))
    return out


def groups(S: Store, name: str):
    if name == "cause":
        x = S.cause
        return [(f"cause={v}", x == v) for v in sorted({v for v in x if isinstance(v, str)})]
    kind = FACTS[name][0]
    x = S.facts[name]
    if kind == "num" and len(np.unique(x[np.isfinite(x)])) > 6:
        return _bins(x, name)
    vals = sorted({v for v in x if not (isinstance(v, float) and np.isnan(v))}, key=str)
    out = [(f"{name}={v:g}" if isinstance(v, float) else f"{name}={v}", x == v) for v in vals]
    if kind == "num" and (~np.isfinite(x)).any():
        out.append((f"{name} missing", ~np.isfinite(x)))
    return out


class Report:
    def __init__(self, S: Store, F: np.ndarray):
        self.S, self.F = S, F
        self.L = cell_loss(S, F)
        self.Lm = {}
        for j, m in enumerate(ALL_MEMBERS):
            Fm = np.where(S.avail[:, j:j + 1], np.exp(S.Lq[:, j]), F)
            self.Lm[m] = cell_loss(S, Fm)
        self.LV, self.TL = S.bl.sum(), self.L.sum()

    def row(self, lab: str, m: np.ndarray) -> str:
        S = self.S
        if not m.any():
            return f"{lab:<38}{0:>6}"
        b = S.bl[m].sum()
        sk = lambda L: f"{1 - L[m].sum() / b:+.3f}" if b > 0 else "  n/a"
        cov = ((S.y[m] >= self.F[m, 0]) & (S.y[m] <= self.F[m, 2])).mean()
        return (f"{lab[:38]:<38}{int(m.sum()):>6}{len(set(S.sid[m])):>5}{b / self.LV:>7.3f}{self.L[m].sum() / max(self.TL, 1e-12):>7.3f}"
                f"{sk(self.L):>8}{cov:>6.2f} " + " ".join(f"{sk(self.Lm[k]):>7}" for k in ALL_MEMBERS))

    def head(self) -> str:
        return (f"{'slice':<38}{'cells':>6}{'ser':>5}{'LV sh':>7}{'sys sh':>7}{'skill':>8}{'cov':>6} " + " ".join(f"{k[:7]:>7}" for k in ALL_MEMBERS))

    def table(self, title: str, parts) -> str:
        parts = sorted(parts, key=lambda p: -self.S.bl[p[1]].sum())[:15]
        return f"\n{title}\n{self.head()}\n" + "\n".join(self.row(l, m) for l, m in parts)


SLICES = ["cls", "collector", "horizon", "in37", "has_panel", "rows", "chg14", "days_since_change", "cause"]


def failure_report(S: Store, F: np.ndarray, system: dict, checkpoint: str) -> str:
    R = Report(S, F)
    o = np.unique(S.origin)
    h37 = S.facts["in37"]
    first = S.origin < o[len(o) // 2]
    t = [f"SELECTION DATA at checkpoint {checkpoint}: {len(o)} daily origins {dt.date.fromordinal(int(o[0]))}..{dt.date.fromordinal(int(o[-1]))} "
         f"(every outcome known by the checkpoint), {S.n} cells (series x origin x horizon 1/3/7), {len(set(S.sid))} posted rental series.",
         f"Current system pooled skill: all series {skill(S, R.L):+.4f} (first half {skill(S, R.L, first):+.4f}, second half {skill(S, R.L, ~first):+.4f}); "
         f"the 37 headline series {skill(S, R.L, h37):+.4f}. Interval [q10,q90] coverage {((S.y >= F[:, 0]) & (S.y <= F[:, 2])).mean():.3f} (target 0.80).",
         "Columns: cells, series, LV sh = share of all last-value loss, sys sh = share of the current system's loss, skill = current system's pooled "
         "skill in the slice, cov = coverage, then the skill if that member alone replaced the system in the slice (cells where the member gives "
         "no forecast keep the system's). 'cause' labels exist for the 37 only and use the realised outcome: they describe what happened, "
         "they are not origin-time facts and cannot be used in a rule."]
    for f in SLICES:
        t.append(R.table(f"by {f}", groups(S, f)))
    return "\n".join(t)


def breakdown(S: Store, F: np.ndarray, req: dict) -> str:
    """One requested table: {"by": [fact] or [fact, fact], "where": condition or null}."""
    try:
        if not isinstance(req, dict) or set(req) - {"by", "where"} or not isinstance(req.get("by"), list) or not 1 <= len(req["by"]) <= 2:
            raise SpecError('a breakdown is {"by": [one or two facts], "where": condition or null}')
        for f in req["by"]:
            if f not in FACTS and f != "cause":
                raise SpecError(f"unknown fact {f!r}")
        m0 = np.ones(S.n, bool)
        if req.get("where") is not None:
            validate_cond(req["where"], S.cats)
            m0 = cond_mask(S, req["where"])
        R = Report(S, F)
        g = groups(S, req["by"][0])
        if len(req["by"]) == 2:
            g = [(f"{a} & {b}", ma & mb) for a, ma in g for b, mb in groups(S, req["by"][1])]
        g = [(l, m & m0) for l, m in g if (m & m0).any()]
        return R.table(f"breakdown by {' x '.join(req['by'])}" + (f" where {json.dumps(req['where'])}" if req.get("where") else "") +
                       f" ({int(m0.sum())} cells)", g)
    except SpecError as e:
        return f"\nbreakdown {json.dumps(req)[:200]} refused: {e}"


def facts_text(S: Store) -> str:
    out = []
    for k, (kind, desc) in FACTS.items():
        x = S.facts[k]
        if kind == "num":
            ok = x[np.isfinite(x)]
            rng = (f"selection quartiles min {ok.min():g}, {np.quantile(ok, .25):g}, {np.median(ok):g}, {np.quantile(ok, .75):g}, max {ok.max():g}"
                   + (f"; missing in {(~np.isfinite(x)).mean():.0%} of cells" if (~np.isfinite(x)).any() else "")) if len(ok) else "always missing"
        elif kind == "bool":
            rng = f"true in {x.mean():.0%} of cells"
        else:
            rng = "values: " + ", ".join(S.cats[k])
        out.append(f"- {k} ({kind}): {desc}. {rng}")
    return "\n".join(out)


GRAMMAR = """A candidate rule is a JSON object {"when": CONDITION, "do": ACTION}.
CONDITION is one of:
  {"fact": NAME, "op": OP, "value": V}   numeric facts: op < <= > >= == != with a number; a missing value makes every comparison false
                                        boolean facts: op == != with true or false
                                        category facts: op == != with a string, or "in" with a list of strings
  {"all": [CONDITION, ...]}   {"any": [CONDITION, ...]}   {"not": CONDITION}
  at most 6 comparisons and 3 levels of nesting. Only the facts listed above exist; unknown facts, values, members or actions are errors.
ACTION is one of (applied to the current system's forecast in the cells where the condition holds; rules apply in order, the new rule last):
""" + "\n".join(f'  {{"action": "{k}"' + "".join(f', "{p}": ' + ("[MEMBER, ...]" if r == "members" else f"number in [{r[0]}, {r[1]}]") for p, r in v.items())
                 + f"}}  {ACTION_TEXT[k]}" for k, v in ACTIONS.items()) + f"""
MEMBER is one of: {', '.join(ALL_MEMBERS)}.
Format example only (it selects no cell and changes nothing): {{"when": {{"all": [{{"fact": "horizon", "op": "==", "value": 3}}, {{"fact": "rows", "op": "<", "value": 0}}]}}, "do": {{"action": "scale_width", "lo": 1.0, "hi": 1.0}}}}"""

GATE_TEXT = """The test (fixed before any run): the candidate is the current system plus your rule appended last, scored on the selection data only.
It is kept only if all hold: (1) pooled skill on all posted rental series rises in the first half and in the second half of the selection
origins, and overall; (2) it changes at least 200 cells in at least 5 series; (3) pooled skill on the 37 headline series does not fall;
(4) at least 90% of 2000 ISO-week block bootstrap resamples show a rise. Otherwise it is rejected and recorded as refuted."""


def system_text(system: dict) -> str:
    t = [f"Base: equal-weight blend (mean of log quantiles) of the members available in each cell: {', '.join(system['base']['members'])}.",
         "Members: " + "; ".join(f"{m} = {MEMBER_TEXT[m]}" for m in ALL_MEMBERS) + "."]
    t += [f"Rule {i} ({r['id']}): {json.dumps(r['when'])} -> {json.dumps(r['do'])}" + (f"  [{r['claim'][:160]}]" if r.get("claim") else "")
          for i, r in enumerate(system["rules"])]
    return "\n".join(t)


CONTEXT = """You are the proposer in an automated research loop on a GPU rental price forecaster. Each target is a published daily
median of provider offers (USD per GPU-hour) from public collectors; the forecaster gives q10, q50 and q90 at 1, 3 and 7 days.
Loss is pinball loss averaged over the three quantiles; skill = 1 - loss / loss of the last value (flat forecast, zero width);
pooled skill sums losses over cells. You change the system only through one rule in the grammar below, and a fixed test decides."""


def prompt_inspect(ctx: dict) -> str:
    return f"""{CONTEXT}

CURRENT SYSTEM
{ctx['system']}

FAILURE REPORT
{ctx['report']}

ORIGIN-TIME FACTS (each computed only from data dated on or before the origin)
{ctx['facts']}

RULE GRAMMAR
{GRAMMAR}

STEP 1 OF 2. Before proposing a rule you may ask for up to three further breakdowns of the selection data, each by one or two facts
(numeric facts are cut at their quartiles; "cause" is also allowed), optionally restricted by a condition in the grammar above.
Also write one web search query for prior work on the mechanism you suspect (it searches sources published on or before {ctx['checkpoint']}).
Reply with JSON only: {{"breakdowns": [{{"by": ["FACT"], "where": null}}], "search_query": "...", "focus": "one sentence on what you will look at"}}"""


def prompt_hypothesis(ctx: dict) -> str:
    return f"""{CONTEXT}

CURRENT SYSTEM
{ctx['system']}

FAILURE REPORT
{ctx['report']}

BREAKDOWNS YOU ASKED FOR
{ctx['breakdowns']}

ORIGIN-TIME FACTS (each computed only from data dated on or before the origin)
{ctx['facts']}

RULE GRAMMAR
{GRAMMAR}

{GATE_TEXT}

MEMORY
{ctx['memory']}

PRIOR WORK (one web search, sources published on or before {ctx['checkpoint']})
{ctx['prior']}

STEP 2 OF 2. Propose exactly one candidate rule: a hypothesis about what moves these published medians, with its mechanism, written as
a spec in the grammar. Do not repeat a rule already in the system or an idea recorded in MEMORY as tested.
Reply with JSON only:
{{"claim": "...", "mechanism": "why this should move a published median, in one or two sentences", "spec": {{"when": ..., "do": ...}},
 "falsification": "what result would refute it, in words", "prior_ids_used": ["ids of MEMORY records or URLs of PRIOR WORK you used, or empty"],
 "expects": "what you expect the test to show"}}"""


# ============================================================================= memory, recall, prior work
def _secs(t0):
    return round(time.time() - t0, 3)


def record_text(r: dict) -> str:
    g = r.get("gate") or {}
    gt = (f"Gate on selection origins {g['halves'][0]}..{g['halves'][2]}: d_all {g['d_all']:+.4f} (halves {g['d_first']:+.4f}, {g['d_second']:+.4f}), "
          f"d37 {g['d37']:+.4f}, changed {g['changed_cells']} cells in {g['changed_series']} series, bootstrap share positive {g['boot_share_pos']:.2f}"
          if g else "Gate: not run")
    h = r.get("hypothesis") or {}
    return (f"Automatic experiment {r['mem_id']} (written by experimenter via gpuf.scientist), checkpoint {r['checkpoint']}, verdict {r['verdict']}\n"
            f"Claim: {h.get('claim', '')}\nMechanism: {h.get('mechanism', '')}\n"
            f"Spec: {json.dumps(r['canonical']) if r.get('canonical') else 'none'}\nFalsification: {h.get('falsification', '')}\n{gt}\n"
            f"Status: {'supported' if r['verdict'] == 'kept' else 'refuted' if r['verdict'] == 'rejected' else r['verdict']}"
            + (f"\nDuplicate of: {r['dedupe']['duplicate_of']}" if (r.get('dedupe') or {}).get('duplicate_of') else ""))


def write_memory(r: dict) -> dict:
    from . import memory
    t0 = time.time()
    st = {"verdict": r["verdict"], "kept": "supported", "rejected": "refuted"}.get(r["verdict"], r["verdict"])
    item = {"id": r["mem_id"], "audience": "gpuf-experiments", "identity": "experimenter", "timestamp": f"{r['checkpoint']}T23:59:59Z",
            "label": f"Experiment: {r['mem_id']}", "content": record_text(r),
            "metadata": {"agent": "experimenter", "kind": "experiment", "hypothesis": r["mem_id"], "status": st, "auto": True,
                         "checkpoint": r["checkpoint"], "spec_hash": r.get("spec_hash"), "spec": json.dumps(r.get("canonical")) if r.get("canonical") else None,
                         "source": "gpuf.scientist"}}
    try:
        res = memory.ingest([item], agent="experimenter")
        try:
            w = memory.wait(res["ingestionId"], timeout=WRITE_WAIT)
        except memory.PastError as e:   # still queued: ingestion finishes server-side; this run's verdicts reach the prompt directly
            return {"id": r["mem_id"], "status": "submitted, not completed within the wait", "detail": str(e)[:160], "offline": memory.offline(), "seconds": _secs(t0)}
        return {"id": r["mem_id"], "status": w.get("status"), "offline": memory.offline(), "seconds": _secs(t0)}
    except memory.PastError as e:
        return {"id": r["mem_id"], "error": str(e), "seconds": _secs(t0)}


def ledger_snapshot(sha: str | None = None) -> tuple[str, str]:
    """The ledger text a run gives the model, frozen at run start under cache/ledger/<sha>.txt (other agents edit the ledger)."""
    d = RECALL_CACHE.parent / "ledger"
    if sha:
        return sha, (d / f"{sha}.txt").read_text()
    text = LEDGER.read_text() if LEDGER.exists() else ""
    sha = hashlib.sha256(text.encode()).hexdigest()[:12]
    d.mkdir(parents=True, exist_ok=True)
    if not (d / f"{sha}.txt").exists():
        (d / f"{sha}.txt").write_text(text)
    return sha, text


def recall_block(mode: str, run_id: str, it: int, query: str, checkpoint: str, own: list[dict], ledger_sha: str | None = None) -> dict:
    """The MEMORY block of the hypothesis prompt, the specs it carries (for dedupe) and its timing."""
    own_txt = "\n".join(f"- [{r['mem_id']}] {record_text(r)}".replace("\n", " | ") for r in own)
    own_specs = [{"id": r["mem_id"], "verdict": r["verdict"], "spec": r["canonical"]} for r in own if r.get("canonical")]
    if mode == "none":
        return {"text": "(no memory is given in this condition)", "specs": [], "ids": [], "seconds": 0.0, "query": None}
    if mode == "ledger":
        led = ledger_snapshot(ledger_sha)[1]
        return {"text": "Hypothesis ledger of this project (every line, verbatim; written by earlier research, results on all practice dates):\n"
                        + led.strip() + "\n\nThis run's earlier verdicts:\n" + (own_txt or "(none yet)"),
                "specs": own_specs, "ids": [r["mem_id"] for r in own], "seconds": 0.0, "query": None}
    from . import memory
    t0 = time.time()
    key = hashlib.sha256(json.dumps([run_id, it, query, checkpoint]).encode()).hexdigest()[:20]
    p = RECALL_CACHE / f"{key}.json"
    err, cached = None, p.exists()
    if cached:
        resp = json.loads(p.read_text())
        err = resp.get("_error")
    else:
        try:
            resp = memory.recall(query, "proposer", agent="proposer", as_of=checkpoint, limit=40)
        except memory.PastError as e:
            resp, err = {"results": [], "_error": str(e)}, str(e)
        if not memory.offline():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(resp))
    rows = memory._dedupe(resp, 12)
    own_ids = {r["mem_id"] for r in own}
    rows = [x for x in rows if x["source_id"] not in own_ids]
    lines, specs = [], list(own_specs)
    for x in rows:
        body = (x.get("text") or x.get("excerpt") or "").replace("\n", " | ")[:700]
        lines.append(f"- [{x['source_id']}] by {x.get('author')}, {str(x.get('occurred_at'))[:10]}: {body}")
        md = x.get("metadata") or {}
        sp = md.get("spec")
        if not sp:
            mm = re.search(r"Spec: (\{.*?\})(?: \||\n|$)", x.get("text") or "")
            sp = mm.group(1) if mm else None
        try:
            if sp:
                specs.append({"id": x["source_id"], "verdict": md.get("status"), "spec": json.loads(sp)})
        except ValueError:
            pass
    text = (f"past.dev recall as `proposer`, as of {checkpoint}, query: \"{query}\" ({len(rows)} records):\n" + ("\n".join(lines) or "(no records)")
            + "\n\nThis run's earlier verdicts (the records it wrote to memory):\n" + (own_txt or "(none yet)"))
    return {"text": text, "specs": specs, "ids": [x["source_id"] for x in rows] + [r["mem_id"] for r in own], "seconds": _secs(t0),
            "query": query, "cache_key": key, "cache_hit": cached, "error": err}


def exa_spent() -> float:
    from . import scout
    return round(sum(float(json.loads(p.read_text()).get("cost") or 0) for p in scout.CACHE.glob("scientist_*.json")), 4)


def prior_block(query: str, checkpoint: str) -> dict:
    from . import loop
    _, PV, _ = loop._calsys()
    spent = exa_spent()
    b = loop.Budget(max(0.0, EXA_CAP - spent))
    body = {"query": str(query)[:300], "type": "auto", "numResults": 5, "endPublishedDate": f"{checkpoint}T23:59:59.000Z",
            "contents": {"highlights": True}, "excludeDomains": PV.TRACKERS}
    rec = loop._exa("search", body, b, lookup=("scientist",), tag="scientist")
    res, dropped = [], {}
    for x in ((rec or {}).get("response") or {}).get("results", []):
        pub, url = (x.get("publishedDate") or "")[:10], x.get("url") or ""
        why = "no_date" if not pub else "after_checkpoint" if pub > checkpoint else "tracker" if any(t in url for t in PV.TRACKERS) else None
        if why:
            dropped[why] = dropped.get(why, 0) + 1
            continue
        res.append({"date": pub, "title": (x.get("title") or "")[:160], "url": url, "highlight": re.sub(r"\s+", " ", " ".join(x.get("highlights") or []))[:300]})
    skipped = "offline_uncached" if b.skipped_offline["search"] else "over_budget" if b.skipped_budget["search"] else None
    text = ("\n".join(f"- {r['date']} {r['title']} {r['url']}\n  \"{r['highlight']}\"" for r in res) if res else
            f"(no usable source: {'the search was skipped' if skipped else 'none dated on or before the checkpoint'})")
    return {"query": body["query"], "results": res, "dropped": dropped, "skipped": skipped, "budget": b.report(), "exa_spent_before": spent, "text": text}


# ============================================================================= dedupe
def same_idea(S: Store, a: dict, b: dict) -> bool:
    """protocol.yaml same_idea_definition."""
    ca, cb = canon(a), canon(b)
    if ca == cb:
        return True
    da, db = ca["do"], cb["do"]
    if da["action"] != db["action"] or set(da) != set(db):
        return False
    for k in da:
        if k == "action":
            continue
        if isinstance(da[k], list):
            if da[k] != db[k]:
                return False
        elif abs(da[k] - db[k]) > 0.05 + 1e-12:
            return False
    ma, mb = cond_mask(S, ca["when"]), cond_mask(S, cb["when"])
    u = (ma | mb).sum()
    return bool(u == 0 or (ma & mb).sum() / u >= 0.9)


def find_duplicate(S: Store, spec: dict, known: list[dict]) -> dict | None:
    for k in known:
        try:
            validate_spec(k["spec"], S.cats)
        except SpecError:
            continue
        if same_idea(S, spec, k["spec"]):
            return k
    return None


# ============================================================================= controller
def journal_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("SCI_JOURNAL") or JOURNAL)


def _append(row: dict) -> None:
    p = journal_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def read_journal(path=None) -> list[dict]:
    p = pathlib.Path(path) if path else journal_path()
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _ask(prompt: str, tag: str, salt: str) -> tuple[object, dict]:
    from . import llm
    rec = llm.ask(prompt, tag=tag, salt=salt)
    meta = {"key": rec.get("key") or llm._key(rec.get("model") or os.environ.get("GPUF_LLM_MODEL", llm.DEFAULT_MODEL), prompt, salt),
            "cached": rec["cached"], "seconds": rec.get("seconds"), "prompt_tokens_est": rec["prompt_tokens_est"],
            "completion_tokens": rec.get("completion_tokens"), "reply": rec["text"]}
    try:
        return llm.parse_json(rec["text"]), meta
    except ValueError as e:
        return None, {**meta, "parse_error": str(e)}


def _query_from(S: Store, F: np.ndarray) -> str:
    R = Report(S, F)
    parts = []
    for f in ("cls", "collector", "horizon"):
        g = max(groups(S, f), key=lambda p: R.L[p[1]].sum())
        parts.append(g[0])
    return ("Tested rules and hypotheses about where the GPU rental price forecast loses most: " + ", ".join(parts)
            + "; experiment verdicts, rule specs and failure cases")


def iterate(S: Store, system: dict, ctx0: dict, it: int, own: list[dict]) -> tuple[dict, dict]:
    """One iteration on the selection store S. Returns (journal row, system after)."""
    t0 = time.time()
    run_id, cp, mode = ctx0["run_id"], ctx0["checkpoint"], ctx0["memory"]
    # "iteration": every model call of an iteration is a fresh draw (salt run:iteration). "run" (the walk-forward of
    # 14 Nov, kept for replay): salt = run id, so an unchanged prompt in a later iteration replayed the earlier reply.
    salt = run_id if ctx0.get("salt_mode") == "run" else f"{run_id}:i{it}"
    st = run_system(S, system)
    F0 = st["F"]
    rep = failure_report(S, F0, system, cp)
    ctx = {"system": system_text(system), "report": rep, "facts": facts_text(S), "checkpoint": cp}
    row = {"type": "iteration", "run_id": run_id, "exec_id": ctx0["exec_id"], "checkpoint": cp, "memory": mode, "rep": ctx0["rep"], "iteration": it,
           "mem_id": f"auto-{run_id}-i{it}", "system_before": {"rules": [r["id"] for r in system["rules"]], "hash": _sha(system)},
           "report_sha": _sha(rep), "human_interventions": 0, "calls": []}
    obj, m1 = _ask(prompt_inspect(ctx), "scientist-inspect", salt)
    row["calls"].append({"step": "inspect", **m1})
    reqs = (obj or {}).get("breakdowns") if isinstance(obj, dict) else None
    reqs = [r for r in reqs if isinstance(r, dict)][:3] if isinstance(reqs, list) else []
    bd = "\n".join(breakdown(S, F0, r) for r in reqs) or "(none asked)"
    row["breakdowns"] = {"asked": reqs, "sha": _sha(bd)}
    sq = (obj or {}).get("search_query") if isinstance(obj, dict) else None
    row["focus"] = (obj or {}).get("focus") if isinstance(obj, dict) else None
    mem = recall_block(mode, run_id, it, _query_from(S, F0), cp, own, ctx0.get("ledger_sha"))
    row["recall"] = {k: v for k, v in mem.items() if k not in ("text", "specs")} | {"tokens_est": len(mem["text"]) // 4, "n_specs": len(mem["specs"])}
    pr = prior_block(sq or "posted GPU rental price median forecasting", cp)
    row["prior"] = {k: v for k, v in pr.items() if k != "text"}
    ctx.update(breakdowns=bd, memory=mem["text"], prior=pr["text"])
    hp = prompt_hypothesis(ctx)
    known = [{"id": r["mem_id"], "verdict": r["verdict"], "spec": r["canonical"]} for r in own if r.get("canonical")] + mem["specs"]
    hyp, spec, err, dup = None, None, None, None
    refused = []
    for attempt in range(2):
        hyp, m2 = _ask(hp, "scientist-hypothesis" if attempt == 0 else "scientist-repair", salt)
        row["calls"].append({"step": "hypothesis" if attempt == 0 else "repair", **m2})
        err, dup, spec = None, None, None
        try:
            if not isinstance(hyp, dict):
                raise SpecError(m2.get("parse_error") or "the reply is not a JSON object")
            spec = hyp.get("spec")
            validate_spec(spec, S.cats)
        except SpecError as e:
            err = str(e)
        if err is None:
            dup = find_duplicate(S, spec, known)
        if err is None and dup is None:
            break
        refused.append({"attempt": attempt, "reason": "invalid" if err else "duplicate", "error": err, "spec": spec if err is None else None,
                        "duplicate_of": dup["id"] if dup else None, "duplicate_verdict": dup["verdict"] if dup else None})
        if attempt == 0:
            note = (f"Your spec was refused: {err}. Reply again with a valid spec." if err else
                    f"Your candidate is the same idea as {dup['id']} (verdict {dup['verdict']}) under the fixed rule: equal canonical spec, or "
                    f"same action and parameters within 0.05 and a condition selecting at least 90% of the same selection cells. "
                    f"Propose a different candidate.")
            hp = hp + "\n\nCONTROLLER NOTE\n" + note
    row["hypothesis"] = hyp if isinstance(hyp, dict) else None
    row["validation_error"] = err
    row["dedupe"] = {"duplicate_of": dup["id"], "duplicate_verdict": dup["verdict"]} if dup else {"duplicate_of": None}
    row["refused"] = refused
    row["candidates_proposed"] = sum(c["step"] in ("hypothesis", "repair") for c in row["calls"])
    row["duplicates_avoided"] = sum(r["reason"] == "duplicate" for r in refused)
    row["invalid_specs"] = sum(r["reason"] == "invalid" for r in refused)
    new_system = system
    if err is None and dup is None:
        row["canonical"], row["spec_hash"] = canon(spec), spec_hash(spec)
        rule = {"id": row["mem_id"], "claim": hyp.get("claim", ""), **canon(spec)}
        F1 = apply_rule(S, st, rule)["F"]
        g = gate(S, F0, F1)
        row["gate"], row["verdict"] = g, "kept" if g["pass"] else "rejected"
        if g["pass"]:
            new_system = {**copy.deepcopy(system), "rules": system["rules"] + [rule]}
    else:
        row["canonical"] = canon(spec) if err is None and spec else None
        row["spec_hash"] = spec_hash(spec) if err is None and spec else None
        row["gate"], row["verdict"] = None, "duplicate" if dup else "invalid"
    row["memory_write"] = write_memory(row)
    row["prompt_tokens_est"] = sum(c["prompt_tokens_est"] for c in row["calls"])
    row["model_seconds"] = round(sum(c.get("seconds") or 0 for c in row["calls"]), 2)
    row["memory_seconds"] = round(mem["seconds"] + row["memory_write"].get("seconds", 0), 3)
    row["seconds"], row["utc"] = _secs(t0), _now()
    return row, new_system


def _sha(o) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _file_sha(p: pathlib.Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.exists() else None


def run(checkpoint: str, iterations: int, memory: str, rep: str, start: dict | None = None, out: pathlib.Path | None = None,
        store: Store | None = None, max_iter: int | None = None, ledger_sha: str | None = None, salt_mode: str = "iteration") -> dict:
    from . import store as stmod
    if memory not in ("none", "ledger", "pastdev"):
        raise SystemExit(f"error: --memory must be none, ledger or pastdev, got {memory!r}")
    S_all = store or stmod.load()
    S = selection(S_all, checkpoint)
    del S_all   # nothing below reads a cell with origin > checkpoint - 7
    system = copy.deepcopy(start or BASE_SYSTEM)
    run_id = f"c{checkpoint[5:7]}{checkpoint[8:10]}-{memory}-{rep}"
    lsha = ledger_snapshot(ledger_sha)[0] if memory == "ledger" else None
    ctx0 = {"run_id": run_id, "checkpoint": checkpoint, "memory": memory, "rep": rep, "exec_id": f"{run_id}@{_now()}", "ledger_sha": lsha,
            "salt_mode": salt_mode}
    usage0 = _usage()
    o = np.unique(S.origin)
    head = {"type": "run_start", "run_id": run_id, "exec_id": ctx0["exec_id"], "checkpoint": checkpoint, "memory": memory, "rep": rep,
            "iterations": iterations, "start_system": system, "selection": {"first": str(dt.date.fromordinal(int(o[0]))), "last": str(dt.date.fromordinal(int(o[-1]))),
                                                                              "n_origins": int(len(o)), "n_cells": S.n},
            "ledger_sha": lsha, "salt_mode": salt_mode, "store_sha": {"cells": _file_sha(stmod.CELLS), "facts": _file_sha(stmod.FACTS_PATH)},
            "model": os.environ.get("GPUF_LLM_MODEL", "gpt-6-astra-medium"), "offline": _offline(), "utc": _now(), "past_usage_before": usage0}
    _append(head)
    own, rows = [], []
    for it in range(1, (max_iter or iterations) + 1):
        row, system = iterate(S, system, ctx0, it, own)
        _append(row)
        rows.append(row)
        own.append(row)
        print(f"[{run_id}] i{it} {row['verdict']:<9} {row.get('spec_hash') or '-':<12} "
              + (f"d_all {row['gate']['d_all']:+.4f} d37 {row['gate']['d37']:+.4f} boot {row['gate']['boot_share_pos']:.2f} cells {row['gate']['changed_cells']}"
                 if row.get("gate") else (row.get("validation_error") or f"dup of {row['dedupe']['duplicate_of']}"))[:160], file=sys.stderr)
    end = {"type": "run_end", "run_id": run_id, "exec_id": ctx0["exec_id"], "final_system": system, "kept": [r["mem_id"] for r in rows if r["verdict"] == "kept"],
           "verdicts": [r["verdict"] for r in rows], "utc": _now(), "past_usage_after": _usage(), "complete": max_iter is None or max_iter >= iterations}
    _append(end)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({**system, "name": f"scientist {run_id}, frozen at checkpoint {checkpoint}"}, indent=1) + "\n")
    return {"run_id": run_id, "rows": rows, "system": system, "end": end}


def _offline() -> bool:
    return os.environ.get("GPUF_LLM_OFFLINE") == "1"


def _usage():
    from . import memory
    if memory.offline() or os.environ.get("PAST_ALLOW_WRITES") != "1":
        return None
    try:
        u = memory.usage()
        return {"credits": u["project"]["credits"], "ingestions": u["project"]["ingestions"], "recalls": u["project"]["recalls"]}
    except Exception as e:  # noqa: BLE001 - usage is informational
        return {"error": str(e)[:200]}


# ============================================================================= later origins (never seen by the controller)
def _cells(W: Store, F: np.ndarray, m=None):
    import pandas as pd
    m = np.ones(W.n, bool) if m is None else m
    return pd.DataFrame({"series_id": W.sid[m], "origin_day": W.origin[m], "horizon_days": W.h[m], "origin_week": W.week[m],
                         "loss": cell_loss(W, F)[m], "baseline_loss": W.bl[m], "in37": W.facts["in37"][m]})


def _paired(new, ref) -> dict:
    from . import compare
    out = {}
    for lab, f in (("all", lambda d: d), ("37", lambda d: d[d.in37])):
        a, b = f(new).reset_index(drop=True), f(ref).reset_index(drop=True)
        p = compare.paired(a, b)
        out[lab] = {"d": round(p["d_pooled_skill"], 4), "ci90": [round(x, 4) for x in p["ci90_d_pooled_skill"]], "n_cells": p["n_cells"],
                    "n_origins": p["n_origins"], "n_weeks": p["n_weeks"],
                    "skill_new": round(float(1 - a.loss.sum() / a.baseline_loss.sum()), 4), "skill_ref": round(float(1 - b.loss.sum() / b.baseline_loss.sum()), 4)}
    return out


def later_frames(S_all: Store, sys_new: dict, sys_ref: dict, a: str, b: str):
    W = window(S_all, a, b)
    return _cells(W, run_system(W, sys_new)["F"]), _cells(W, run_system(W, sys_ref)["F"])


# ============================================================================= drivers
def walkforward(S: Store | None = None) -> dict:
    from . import store as stmod
    S = S or stmod.load()
    cur, out = copy.deepcopy(BASE_SYSTEM), []
    for c in WALK:
        r = run(c, 6, "pastdev", "wf", start=cur, out=OUTDIR / "systems" / f"c{c[5:7]}{c[8:10]}-pastdev-wf.json", store=S, salt_mode="run")
        cur = r["system"]
        out.append({"run_id": r["run_id"], "kept": r["end"]["kept"]})
    r = run("2026-10-13", 8, "pastdev", "wf", start=cur, out=OUTDIR / "system_final.json", store=S, salt_mode="run")
    out.append({"run_id": r["run_id"], "kept": r["end"]["kept"], "system_final": str(OUTDIR / "system_final.json")})
    return {"runs": out}


def compare_memory(S: Store | None = None, reps=("r1", "r2", "r3"), modes=("none", "ledger", "pastdev")) -> dict:
    from . import store as stmod
    S = S or stmod.load()
    out = []
    for rep in reps:
        for mode in modes:
            r = run("2026-09-25", 8, mode, rep, start=BASE_SYSTEM, out=OUTDIR / "systems" / f"c0925-{mode}-{rep}.json", store=S)
            out.append({"run_id": r["run_id"], "verdicts": r["end"]["verdicts"]})
    return {"runs": out}


# ============================================================================= report
def executions(rows: list[dict]) -> dict:
    """The latest complete live execution of each run id: {run_id: {"start", "end", "iters"}} in start order."""
    by = {}
    for r in rows:
        by.setdefault(r["exec_id"], []).append(r)
    out = {}
    for ex, rs in by.items():
        st = [r for r in rs if r["type"] == "run_start"]
        en = [r for r in rs if r["type"] == "run_end"]
        if not st or not en or not en[-1].get("complete") or st[0].get("offline"):
            continue
        rid = st[0]["run_id"]
        if rid not in out or st[0]["utc"] > out[rid]["start"]["utc"]:
            out[rid] = {"start": st[0], "end": en[-1], "iters": sorted([r for r in rs if r["type"] == "iteration"], key=lambda r: r["iteration"])}
    return dict(sorted(out.items(), key=lambda kv: kv[1]["start"]["utc"]))


def wasted_tests(execs: dict, S_all: Store) -> dict:
    """protocol.yaml wasted_test_definition, per run id."""
    out = {}
    for rid, e in execs.items():
        sel = selection(S_all, e["start"]["checkpoint"])
        ref = [(r["canonical"], r["mem_id"]) for e2 in execs.values() if e2["end"]["utc"] < e["start"]["utc"]
               for r in e2["iters"] if r["verdict"] == "rejected"]
        wasted, seen = [], []
        for r in e["iters"]:
            if r["verdict"] in ("kept", "rejected"):
                hit = next((i for s, i in ref + seen if same_idea(sel, r["canonical"], s)), None)
                if hit:
                    wasted.append({"iteration": r["iteration"], "same_idea_as": hit})
                if r["verdict"] == "rejected":
                    seen.append((r["canonical"], r["mem_id"]))
        out[rid] = wasted
    return out


def _f(x, n=4):
    return "n/a" if x is None else f"{x:+.{n}f}"


def _short(s, n=110):
    s = re.sub(r"\s+", " ", str(s or ""))
    return s if len(s) <= n else s[:n - 1] + "…"


def iteration_table(e: dict) -> str:
    t = ["| it | verdict | claim | mechanism | spec | d all (halves) | d 37 | cells / series | boot | dedupe |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in e["iters"]:
        h, g = r.get("hypothesis") or {}, r.get("gate")
        sp = json.dumps(r.get("canonical"), separators=(",", ":")) if r.get("canonical") else (r.get("validation_error") or "")[:120]
        gd = f"{_f(g['d_all'])} ({_f(g['d_first'])}, {_f(g['d_second'])})" if g else "-"
        dd = (f"refused {r['duplicates_avoided']} dup, {r.get('invalid_specs', 0)} invalid" if r["refused"] else "") + \
             (f"; dup of {r['dedupe']['duplicate_of']}" if r["dedupe"]["duplicate_of"] else "")
        cells = f"{g['changed_cells']} / {g['changed_series']}" if g else "-"
        boot = f"{g['boot_share_pos']:.2f}" if g else "-"
        t.append(f"| {r['iteration']} | {r['verdict']} | {_short(h.get('claim'))} | {_short(h.get('mechanism'))} | `{sp.replace('|', '/')}` | {gd} | "
                 f"{_f(g['d37']) if g else '-'} | {cells} | {boot} | {dd or '-'} |")
    return "\n".join(t)


def report() -> dict:
    import pandas as pd
    from . import store as stmod
    S = stmod.load()
    rows = read_journal()
    execs = executions(rows)
    waste = wasted_tests(execs, S)
    summary = {"runs": {}, "walkforward": {}, "memory": {}}
    md = ["# scientist: tables generated by `python -m gpuf.scientist report` from data_out/scientist_journal.jsonl", ""]
    for rid, e in execs.items():
        it = e["iters"]
        summary["runs"][rid] = {"checkpoint": e["start"]["checkpoint"], "memory": e["start"]["memory"], "rep": e["start"]["rep"],
                                "selection": e["start"]["selection"], "verdicts": [r["verdict"] for r in it],
                                "candidates_proposed": sum(r["candidates_proposed"] for r in it), "duplicates_avoided": sum(r["duplicates_avoided"] for r in it),
                                "invalid_specs": sum(r.get("invalid_specs", 0) for r in it), "tests": sum(r["verdict"] in ("kept", "rejected") for r in it),
                                "kept": sum(r["verdict"] == "kept" for r in it), "wasted_tests": waste[rid],
                                "prompt_tokens_per_iteration": round(float(np.mean([r["prompt_tokens_est"] for r in it])), 0),
                                "model_seconds": round(sum(r["model_seconds"] for r in it), 1), "memory_seconds": round(sum(r["memory_seconds"] for r in it), 1),
                                "model_calls": sum(len(r["calls"]) for r in it), "human_interventions": sum(r["human_interventions"] for r in it),
                                "exa_new_searches": sum(r["prior"]["budget"]["new_calls"]["search"] for r in it),
                                "exa_skipped": sum(bool(r["prior"]["skipped"]) for r in it), "recall_errors": sum(bool((r["recall"] or {}).get("error")) for r in it),
                                "memory_write_errors": sum("error" in r["memory_write"] for r in it)}
        u0, u1 = e["start"].get("past_usage_before") or {}, e["end"].get("past_usage_after") or {}
        summary["runs"][rid]["past_credits_delta_projectwide"] = (u1["credits"] - u0["credits"]) if "credits" in u0 and "credits" in u1 else None
        # 1 credit per recall, 1 per 350 bytes written (rounded up per record): literature/pastdev-api.md, README_memory.md
        summary["runs"][rid]["past_credits_est_by_price_rule"] = (sum(1 for r in it if r["recall"].get("query"))
                                                                  + sum(-(-len(record_text(r).encode()) // 350) for r in it))
        md += [f"## run {rid} (checkpoint {e['start']['checkpoint']}, memory {e['start']['memory']}, selection origins "
               f"{e['start']['selection']['first']}..{e['start']['selection']['last']}, {e['start']['selection']['n_origins']} origins, "
               f"{e['start']['selection']['n_cells']} cells)", "", iteration_table(e), ""]
    # walk-forward
    wf = [execs.get(f"c{c[5:7]}{c[8:10]}-pastdev-wf") for c in WALK]
    if all(wf):
        ends = WALK[1:] + [None]
        news, refs, blocks = [], [], []
        for c, e, nxt in zip(WALK, wf, ends):
            a = str(dt.date.fromisoformat(c) + dt.timedelta(days=1))
            b = str(dt.date.fromisoformat(nxt) - dt.timedelta(days=1)) if nxt else DEV_END
            n, r = later_frames(S, e["end"]["final_system"], BASE_SYSTEM, a, b)
            news.append(n), refs.append(r)
            blocks.append({"checkpoint": c, "window": [a, b], "rules_added_at_checkpoint": e["end"]["kept"],
                           "rules_in_system": [x["id"] for x in e["end"]["final_system"]["rules"]], **_paired(n, r)})
        pooled = _paired(pd.concat(news, ignore_index=True), pd.concat(refs, ignore_index=True))
        final_sys = wf[-1]["end"]["final_system"]
        rule_rows = []
        jr = {r["mem_id"]: r for e in execs.values() for r in e["iters"]}
        for j, rule in enumerate(final_sys["rules"]):
            if j == 0:
                continue
            src = jr.get(rule["id"], {})
            cp = src.get("checkpoint")
            a = str(dt.date.fromisoformat(cp) + dt.timedelta(days=1))
            with_r = {**final_sys, "rules": final_sys["rules"][:j + 1]}
            without = {**final_sys, "rules": final_sys["rules"][:j]}
            n, r = later_frames(S, with_r, without, a, DEV_END)
            rule_rows.append({"rule": rule["id"], "spec": {"when": rule["when"], "do": rule["do"]}, "claim": rule.get("claim"), "checkpoint": cp,
                              "selection": {"d_all": src["gate"]["d_all"], "d37": src["gate"]["d37"], "changed_cells": src["gate"]["changed_cells"]},
                              "later": {"window": [a, DEV_END], **_paired(n, r)}})
        summary["walkforward"] = {"blocks": blocks, "pooled": pooled, "kept_rules": rule_rows}
        md += ["## walk-forward: self-modified system minus the frozen submitted system, later origins only", "",
               "| checkpoint | later origins | origins | cells all / 37 | rules kept so far | d all [90% week-block range] | d 37 [range] | skill all new / start | skill 37 new / start |",
               "|---|---|---|---|---|---|---|---|---|"]
        for bk in blocks + [{"checkpoint": "pooled", "window": [blocks[0]["window"][0], DEV_END], "rules_in_system": ["-"], **pooled}]:
            md.append(f"| {bk['checkpoint']} | {bk['window'][0]}..{bk['window'][1]} | {bk['all']['n_origins']} | {bk['all']['n_cells']} / {bk['37']['n_cells']} | "
                      f"{len(bk['rules_in_system']) - 1 if bk['checkpoint'] != 'pooled' else '-'} | {_f(bk['all']['d'])} [{_f(bk['all']['ci90'][0], 3)}, {_f(bk['all']['ci90'][1], 3)}] ({bk['all']['n_weeks']} wk) | "
                      f"{_f(bk['37']['d'])} [{_f(bk['37']['ci90'][0], 3)}, {_f(bk['37']['ci90'][1], 3)}] | {bk['all']['skill_new']:.4f} / {bk['all']['skill_ref']:.4f} | "
                      f"{bk['37']['skill_new']:.4f} / {bk['37']['skill_ref']:.4f} |")
        md += ["", "### every kept rule: gain on selection data when kept, and marginal gain on later dev origins", "",
               "| rule | checkpoint | spec | selection d all / d 37 | later origins | later d all [range] | later d 37 |", "|---|---|---|---|---|---|---|"]
        for x in rule_rows:
            md.append(f"| {x['rule']} | {x['checkpoint']} | `{json.dumps(x['spec'], separators=(',', ':')).replace('|', '/')}` | {_f(x['selection']['d_all'])} / {_f(x['selection']['d37'])} | "
                      f"{x['later']['window'][0]}..{x['later']['window'][1]} ({x['later']['all']['n_origins']}) | {_f(x['later']['all']['d'])} [{_f(x['later']['all']['ci90'][0], 3)}, "
                      f"{_f(x['later']['all']['ci90'][1], 3)}] | {_f(x['later']['37']['d'])} |")
        md.append("")
    fin = execs.get("c1013-pastdev-wf")
    if fin:
        summary["final_run"] = {"kept": fin["end"]["kept"], "rules": [r["id"] for r in fin["end"]["final_system"]["rules"]],
                                "file": "experiments/scientist/results/system_final.json", "evaluated_after_2026_10_06": False}
    # memory comparison
    mem_rows = []
    for mode in ("none", "ledger", "pastdev"):
        for rep in ("r1", "r2", "r3"):
            e = execs.get(f"c0925-{mode}-{rep}")
            if not e:
                continue
            n, r = later_frames(S, e["end"]["final_system"], BASE_SYSTEM, "2026-09-26", DEV_END)
            s = summary["runs"][f"c0925-{mode}-{rep}"]
            mem_rows.append({"memory": mode, "rep": rep, **{k: s[k] for k in ("candidates_proposed", "duplicates_avoided", "invalid_specs", "tests", "kept",
                                                                             "prompt_tokens_per_iteration", "model_seconds", "memory_seconds", "model_calls",
                                                                             "past_credits_delta_projectwide", "past_credits_est_by_price_rule")},
                             "wasted_tests": len(s["wasted_tests"]), "later": _paired(n, r)})
    if mem_rows:
        summary["memory"] = mem_rows
        md += ["## memory comparison: checkpoint 2026-09-25, K = 8, start = submitted system; later origins 2026-09-26..2026-10-06", "",
               "| memory | rep | proposed | dup avoided | invalid | tests | wasted | kept | later d all [range] | later d 37 | tokens / it | model s | memory s | past.dev credits (project-wide delta; price-rule estimate) |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for x in mem_rows:
            md.append(f"| {x['memory']} | {x['rep']} | {x['candidates_proposed']} | {x['duplicates_avoided']} | {x['invalid_specs']} | {x['tests']} | {x['wasted_tests']} | {x['kept']} | "
                      f"{_f(x['later']['all']['d'])} [{_f(x['later']['all']['ci90'][0], 3)}, {_f(x['later']['all']['ci90'][1], 3)}] | {_f(x['later']['37']['d'])} | "
                      f"{x['prompt_tokens_per_iteration']:.0f} | {x['model_seconds']:.0f} | {x['memory_seconds']:.1f} | "
                      f"{x['past_credits_delta_projectwide'] if x['past_credits_delta_projectwide'] is not None else 'not measured'}; {x['past_credits_est_by_price_rule'] if x['memory'] == 'pastdev' else '-'} |")
        md.append("")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "tables.md").write_text("\n".join(md) + "\n")
    (OUTDIR / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    return {"runs": list(execs), "tables": str(OUTDIR / "tables.md"), "summary": str(OUTDIR / "summary.json")}


# ============================================================================= replay
VOLATILE = {"utc", "seconds", "exec_id", "memory_seconds", "memory_write"}


def stable(row: dict) -> dict:
    r = {k: v for k, v in copy.deepcopy(row).items() if k not in VOLATILE}
    for c in r.get("calls", []):
        c.pop("cached", None)
    if r.get("recall"):
        for k in ("seconds", "cache_hit"):
            r["recall"].pop(k, None)
    if r.get("prior"):
        r["prior"].pop("budget", None), r["prior"].pop("exa_spent_before", None)
        r["prior"]["skipped"] = bool(r["prior"]["skipped"])
    return r


def replay(run_id: str, max_iter: int | None = None, store: Store | None = None) -> dict:
    import tempfile
    e = executions(read_journal()).get(run_id)
    if not e:
        raise SystemExit(f"error: no complete recorded run {run_id!r} in {journal_path()}")
    s = e["start"]
    keep = {k: os.environ.get(k) for k in ("GPUF_LLM_OFFLINE", "PAST_OFFLINE", "LOOP_OFFLINE", "SCI_JOURNAL", "PAST_JOURNAL")}
    with tempfile.TemporaryDirectory(prefix="sci_replay_") as tmp:
        os.environ.update(GPUF_LLM_OFFLINE="1", PAST_OFFLINE="1", LOOP_OFFLINE="1", SCI_JOURNAL=str(pathlib.Path(tmp) / "j.jsonl"),
                          PAST_JOURNAL=str(pathlib.Path(tmp) / "mj.jsonl"))
        try:
            res = run(s["checkpoint"], s["iterations"], s["memory"], s["rep"], start=s["start_system"], store=store, max_iter=max_iter, ledger_sha=s.get("ledger_sha"),
                      salt_mode=s.get("salt_mode", "run"))
        finally:
            for k, v in keep.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    n = len(res["rows"])
    diffs = [i + 1 for i in range(n) if stable(res["rows"][i]) != stable(e["iters"][i])]
    same_sys = res["system"] == e["end"]["final_system"] if max_iter is None or max_iter >= s["iterations"] else None
    return {"run_id": run_id, "iterations_compared": n, "identical_rows": not diffs, "differing_iterations": diffs, "same_final_system": same_sys,
            "store_sha_recorded": s.get("store_sha")}


# ============================================================================= CLI
def _set_offline():
    os.environ.update(GPUF_LLM_OFFLINE="1", PAST_OFFLINE="1", LOOP_OFFLINE="1")


def main(argv=None) -> int:
    P = argparse.ArgumentParser(prog="python -m gpuf.scientist", description=__doc__.split("\n\n")[0],
                                epilog=__doc__.split("\n\n", 1)[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = P.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="research iterations at one checkpoint")
    r.add_argument("--checkpoint", required=True); r.add_argument("--iterations", type=int, required=True)
    r.add_argument("--memory", required=True, choices=["none", "ledger", "pastdev"]); r.add_argument("--rep", required=True)
    r.add_argument("--offline", action="store_true"); r.add_argument("--start", help="system JSON to start from (default: the submitted system)")
    r.add_argument("--out", help="where to write the frozen system (default results/systems/<run id>.json)")
    for name in ("walkforward", "compare"):
        x = sub.add_parser(name)
        x.add_argument("--offline", action="store_true")
    sub.add_parser("report")
    x = sub.add_parser("replay"); x.add_argument("--run", required=True); x.add_argument("--max-iter", type=int)
    x = sub.add_parser("validate"); x.add_argument("spec")
    a = P.parse_args(argv)
    if getattr(a, "offline", False):
        _set_offline()
    try:
        if a.cmd == "run":
            start = json.loads(pathlib.Path(a.start).read_text()) if a.start else None
            rid = f"c{a.checkpoint[5:7]}{a.checkpoint[8:10]}-{a.memory}-{a.rep}"
            res = run(a.checkpoint, a.iterations, a.memory, a.rep, start=start, out=pathlib.Path(a.out) if a.out else OUTDIR / "systems" / f"{rid}.json")
            out = {"run_id": res["run_id"], "verdicts": res["end"]["verdicts"], "kept": res["end"]["kept"],
                   "rules": [x["id"] for x in res["system"]["rules"]], "human_interventions": 0}
        elif a.cmd == "walkforward":
            out = walkforward()
        elif a.cmd == "compare":
            out = compare_memory()
        elif a.cmd == "report":
            out = report()
        elif a.cmd == "replay":
            out = replay(a.run, a.max_iter)
        else:
            from . import store as stmod
            S = stmod.load()
            validate_spec(json.loads(pathlib.Path(a.spec).read_text()), S.cats)
            out = {"valid": True}
    except PermissionError as e:
        print(json.dumps({"refused": str(e)}))
        return 2
    except SpecError as e:
        print(json.dumps({"valid": False, "error": str(e)}))
        return 1
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
