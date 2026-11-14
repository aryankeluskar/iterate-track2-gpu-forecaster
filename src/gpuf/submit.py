"""python -m gpuf.submit --method drift [--params JSON] [--universe rental_headline]

Builds the history truncated at 2026-11-06 with the starter, forecasts origin 2026-11-06 at
horizons 1, 3, 7 through the harness, writes the starter-schema CSV to runs/submission/ and
validates it as the organisers will: starter schema check, then starter/scorer.py in
frozen-cutoff mode (no truth exists yet, so it must score zero cells without refusing).
"""
from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

from . import data, harness, methods
from .data import starter_common
from .scoring import forecast_csv_frame, score_official

CUTOFF = data.AS_OF
HORIZONS = (1, 3, 7)
OUT = data.ROOT / "runs/submission"


def submit(method: str, params: dict | None = None, universe: str = "rental_headline") -> dict:
    params = params or {}
    full_series, full_catalog = data.build_series()
    hist_path, hist_cat = data.build_series(CUTOFF, OUT / "history", members_from=full_catalog)
    store = data.load_store(str(hist_path))
    if store.max_day() > starter_common.day_of(starter_common.parse_date(CUTOFF)):
        raise RuntimeError("history holds rows after the cutoff")
    sids = data.universe(universe)  # protocol catalog as of the cutoff
    meta = harness.static_meta(data.load_catalog(str(hist_cat)))
    origin = starter_common.day_of(starter_common.parse_date(CUTOFF))
    fc, counts = harness.forecast(methods.get(method, **params), [origin], sids, HORIZONS, store, meta)
    sub = forecast_csv_frame(fc).assign(method=method, method_note=json.dumps(params, sort_keys=True))
    path = OUT / f"forecast_{method}.csv"
    sub.to_csv(path, index=False)

    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    clean, problems = starter_common.validate_forecast(raw, list(HORIZONS))
    off = score_official(fc, sids, HORIZONS, hist_path, OUT / "frozen_check", history_path=hist_path,
                         frozen_cutoff=CUTOFF, forecast_path=path)
    rep = off["report"] or {}
    fv = rep.get("forecast_validation", {})
    v = {"path": str(path), "rows": len(sub), "series": int(sub["series_id"].nunique()), "universe": universe,
         "universe_size": len(sids), "series_without_history": len(set(sids) - set(sub["series_id"])),
         "filled_from_baseline": counts["filled_from_baseline"], "quantiles_clipped": counts["quantiles_clipped"],
         "schema_problems": len(problems), "rows_valid": len(clean),
         "scorer_exit": off["returncode"], "scorer_status": rep.get("status"), "scorer_refusals": rep.get("refusals"),
         "scorer_rows_in": fv.get("rows_in"), "scorer_rows_valid": fv.get("rows_valid"),
         "scorer_n_problems": fv.get("n_problems"), "scorer_cells": rep.get("cells"),
         "sha256": starter_common.sha256_file(str(path))}
    v["ok"] = (v["schema_problems"] == 0 and v["rows_valid"] == v["rows"] and v["scorer_exit"] == 0
               and v["scorer_status"] != "refused" and v["scorer_rows_valid"] == v["rows"])
    (OUT / f"validation_{method}.json").write_text(json.dumps(v, indent=2, default=str) + "\n")
    return v


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--method", required=True)
    ap.add_argument("--params", default="{}")
    ap.add_argument("--universe", default="rental_headline", choices=list(data.UNIVERSES))
    a = ap.parse_args()
    v = submit(a.method, json.loads(a.params), a.universe)
    print(json.dumps(v))
    return 0 if v["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
