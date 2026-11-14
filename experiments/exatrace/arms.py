"""Task 1: controlled arms of the calendar switch on cached practice episodes (protocol.yaml). No network, no trajectory/ledger rows.

PYTHONPATH=src .venv/bin/python experiments/exatrace/arms.py
Writes experiments/exatrace/results/arms_cells.parquet (one row per arm x cell) and arms_summary.json.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import pathlib
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "2")
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "calendar"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import numpy as np
import pandas as pd

import calendar_lib as CL
from gpuf import harness, loop, methods, panel as P
import sources as SRC

RES = pathlib.Path(__file__).parent / "results"
ORIGINS = [str(dt.date(2026, 9, 16) + dt.timedelta(days=i)) for i in range(21)]
assert ORIGINS[-1] == "2026-10-06"
PRV = loop.PRV[1]
K = ["series_id", "origin_day", "horizon_days"]


def base_entries() -> list[dict]:
    return [json.loads(l) for l in (ROOT / "data_out/repricing_calendar.jsonl").read_text().splitlines() if l.strip()]


def key(e):
    return f"{e['provider']} {e['effective_date']}"


def run(entries: list[dict] | None, lag: bool = False) -> pd.DataFrame:
    """prov on the 21 origins with the calendar replaced by `entries` (None = switch off)."""
    params = dict(PRV, cal=entries is not None, cal_lag=lag)
    if entries is not None:
        frozen = tuple(copy.deepcopy(entries))
        CL.load = lambda path=None: frozen        # scheduled_changes() reads load(); the file itself is untouched
    try:
        c = harness.evaluate(methods.get("prov", **params), ORIGINS, "rental_headline", name="prov", params=params).cells
    finally:
        CL.load = ORIG_LOAD
    return c[K + ["q10", "q50", "q90", "y", "baseline", "loss", "baseline_loss"]]


ORIG_LOAD = CL.load


def affected(entries, origins=ORIGINS, horizons=(1, 3, 7), lag=False) -> pd.DataFrame:
    """Cells where an entry usable at the origin (published <= o, conf A/B) with effective day E in (o, o+h] matches an offer of
    the announcing provider in the series' panel at the origin (same GPU/tier, old price within 3%): calendar_lib's rule."""
    sids = [s for s in harness.data.universe("rental_headline") if P.supported(s)]
    rows = []
    for o in origins:
        od = loop._day(o)
        for e in entries:
            if loop._day(e["published"]) > od or e["confidence"] > "B":
                continue
            E = CL.effective_day(e)
            if E <= od:
                continue
            for sid in sids:
                src, cls, gpu, tier = P.parse_sid(sid)
                A = E + (CL.COLLECTOR_LAG[src] if lag else 0)
                for c in e["changes"]:
                    if not (gpu in c["panel_gpus"] and tier in CL.TIER_MAP.get(c["tier"], set()) and c["new"] is not None):
                        continue
                    ofr = P.offers(sid, od)
                    last = ofr.sort_values("day").groupby("key").tail(1)
                    m = last.provider == e["provider"]
                    if c["old"] is not None:
                        m &= np.isclose(last.price, c["old"], rtol=0.03)
                    if not m.any():
                        continue
                    for h in horizons:
                        if od + h >= E:
                            rows.append({"series_id": sid, "origin_day": od, "horizon_days": h, "event": key(e), "E": E, "A": A,
                                         "reaches_arrival": od + h >= A})
    return pd.DataFrame(rows, columns=["series_id", "origin_day", "horizon_days", "event", "E", "A", "reaches_arrival"])


def skill(c) -> float:
    return float(1 - c.loss.sum() / c.baseline_loss.sum()) if len(c) else float("nan")


def same(a: pd.DataFrame, b: pd.DataFrame) -> pd.Series:
    m = a[K].merge(b[K], on=K, validate="one_to_one")
    assert len(m) == len(a) == len(b)
    return (a[["q10", "q50", "q90"]].to_numpy() == b[["q10", "q50", "q90"]].to_numpy()).all(axis=1)


def main():
    t0 = time.time()
    RES.mkdir(parents=True, exist_ok=True)
    ents = base_entries()
    E_ = {key(e): e for e in ents}
    arms = {}

    def nopair(es):
        es = copy.deepcopy(es)
        for e in es:
            for c in e["changes"]:
                c["old"] = c["new"] = None
        return es

    def zero(es):
        es = copy.deepcopy(es)
        for e in es:
            for c in e["changes"]:
                if c["old"] is not None:
                    c["new"] = c["old"]
        return es

    def deferred(es):
        es = copy.deepcopy(es)
        for e in es:
            e["published"] = str(dt.date.fromordinal(CL.effective_day(e) + 8))
        return es

    specs = {"i_off": (None, False), "ii_valid": (ents, False), "ii_lag": (ents, True), "iii_nopair": (nopair(ents), False),
             "iii_zero": (zero(ents), False), "iv_deferred": (deferred(ents), False)}
    for name, (es, lag) in specs.items():
        t = time.time()
        arms[name] = run(es, lag)
        print(f"{name}: {skill(arms[name]):.4f} ({time.time() - t:.0f}s)", flush=True)
    off = arms["i_off"]
    changed = ~same(arms["ii_valid"], off)
    aff = affected(ents)
    aff_lag = affected(ents, lag=True)
    acting = sorted(aff.event.unique())
    notes = {}
    # one event removed in turn; earliest source removed in turn (entry rebuilt from the remaining sources' cached text)
    for k in acting:
        arms[f"minus_{k.replace(' ', '_')}"] = run([e for e in ents if key(e) != k], False)
        print(f"minus {k}: {skill(arms[f'minus_{k.replace(chr(32), chr(95))}']):.4f}", flush=True)
        first = SRC.sources_of(E_[k])[0]["url"]
        for tag, drop in (("first", first), ("primary", E_[k]["url"])):   # earliest source (protocol); the cited source (added)
            if tag == "primary" and drop == first:
                continue
            rebuilt, note = SRC.rebuild_without_first_source(E_[k], drop)
            arms[f"minus_{tag}_source_{k.replace(' ', '_')}"] = run([e for e in ents if key(e) != k] + (rebuilt or []), False)
            notes[f"minus_{tag}_source_{k}"] = {"note": note, "entries": rebuilt}
    cells = pd.concat([a.assign(arm=n) for n, a in arms.items()], ignore_index=True)
    cells.to_parquet(RES / "arms_cells.parquet")
    aff.to_csv(RES / "affected_cells.csv", index=False)
    (RES / "source_deletion.json").write_text(json.dumps(notes, indent=1))

    # ---------- summary
    akeys = aff[K].drop_duplicates()
    def sub(c, keys):
        return c.merge(keys, on=K, how="inner")
    out = {"origins": [ORIGINS[0], ORIGINS[-1]], "n_origins": len(ORIGINS), "n_cells": int(len(off)), "prov_params": PRV,
           "calendar_entries": [key(e) for e in ents], "events_with_affected_cells": acting,
           "n_affected_cells": int(len(akeys)), "affected_by_event": aff.groupby("event").size().to_dict(),
           "arms": {}}
    for n, a in arms.items():
        d = ~same(a, off)
        a_aff = sub(a, akeys)
        out["arms"][n] = {"skill_all": round(skill(a), 4), "skill_affected": round(skill(a_aff), 4),
                          "loss_affected": round(float(a_aff.loss.sum()), 4), "cells_changed_vs_off": int(d.sum()),
                          "bit_identical_to_off": bool(not d.any())}
        out["arms"][n]["per_event_affected"] = {k: round(skill(sub(a, aff[aff.event == k][K].drop_duplicates())), 4) for k in acting}
    out["last_value_loss_affected"] = round(float(sub(off, akeys).baseline_loss.sum()), 4)
    # A1..A4
    chg = off[K][changed]
    inside = chg.merge(akeys, on=K, how="left", indicator=True)
    only = {k: aff[aff.event == k][K].drop_duplicates().merge(aff[aff.event != k][K].drop_duplicates(), on=K, how="left", indicator=True)
            .query("_merge == 'left_only'")[K] for k in acting}
    a3 = {}
    for k in acting:
        m = arms[f"minus_{k.replace(' ', '_')}"]
        keys = only[k]
        a3[k] = {"cells_only_this_event": int(len(keys)),
                 "identical_to_off_on_them": bool(same(sub(m, keys).sort_values(K).reset_index(drop=True),
                                                       sub(off, keys).sort_values(K).reset_index(drop=True)).all()),
                 "cells_changed_by_removal_vs_valid": int((~same(m, arms["ii_valid"])).sum())}
    out["acceptance"] = {
        "A1_deferred_bit_identical_to_off": out["arms"]["iv_deferred"]["bit_identical_to_off"],
        "A2_changed_cells_all_inside_affected": bool((inside["_merge"] == "both").all()), "A2_changed_cells": int(changed.sum()),
        "A3_event_removed": a3,
        "A4_nopair_bit_identical_to_off": out["arms"]["iii_nopair"]["bit_identical_to_off"],
    }
    d_valid = out["arms"]["ii_valid"]["skill_affected"] - out["arms"]["i_off"]["skill_affected"]
    d_zero = out["arms"]["iii_zero"]["skill_affected"] - out["arms"]["i_off"]["skill_affected"]
    out["gate_opening_share_of_gain_affected"] = round(d_zero / d_valid, 3) if d_valid else None
    out["affected_cells_reaching_lagged_arrival"] = int(aff_lag[K + ["reaches_arrival"]].groupby(K).reaches_arrival.any().sum())
    out["wall_s"] = round(time.time() - t0)
    (RES / "arms_summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["acceptance"], indent=1))


if __name__ == "__main__":
    main()
