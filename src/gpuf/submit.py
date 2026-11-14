"""python -m gpuf.submit --method drift [--params JSON] [--universe rental_headline] [--out PATH] [--headline-out PATH]

Builds the history truncated at 2026-11-06 with the starter, forecasts origin 2026-11-06 at
horizons 1, 3, 7 through the harness, writes the starter-schema CSV to runs/submission/ (or --out) and
validates it as the organisers will: starter schema check, then starter/scorer.py in
frozen-cutoff mode (no truth exists yet, so it must score zero cells without refusing).
--headline-out also writes the rows of the headline series only (identical rows) and validates that file.
A forecaster that records `used` (as `final` does) also gets a sidecar <out>_members.csv.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from . import data, harness, methods
from .data import starter_common
from .scoring import forecast_csv_frame, score_official

CUTOFF = data.AS_OF
HORIZONS = (1, 3, 7)
OUT = data.ROOT / "runs/submission"


def history():
    """(history path, history catalog path, store) truncated at the cutoff, members from the full catalog."""
    full_series, full_catalog = data.build_series()
    hist_path, hist_cat = data.build_series(CUTOFF, OUT / "history", members_from=full_catalog)
    store = data.load_store(str(hist_path))
    if store.max_day() > starter_common.day_of(starter_common.parse_date(CUTOFF)):
        raise RuntimeError("history holds rows after the cutoff")
    return hist_path, hist_cat, store


def validate(path: Path, fc: pd.DataFrame, sids: list[str], hist_path, workdir: Path) -> dict:
    """Starter schema check, then starter/scorer.py in frozen-cutoff mode on the file as written."""
    sub = pd.read_csv(path, dtype=str, keep_default_na=False)
    clean, problems = starter_common.validate_forecast(sub, list(HORIZONS))
    off = score_official(fc, sids, HORIZONS, hist_path, workdir, history_path=hist_path,
                         frozen_cutoff=CUTOFF, forecast_path=path)
    rep = off["report"] or {}
    fv = rep.get("forecast_validation", {})
    q = sub[["q10", "q90"]].astype(float)
    zero = (q["q10"] == q["q90"]).groupby(sub["series_id"]).all()
    v = {"path": str(path), "rows": len(sub), "series": int(sub["series_id"].nunique()),
         "series_zero_width": int(zero.sum()),
         "schema_problems": len(problems), "rows_valid": len(clean),
         "scorer_exit": off["returncode"], "scorer_status": rep.get("status"), "scorer_refusals": rep.get("refusals"),
         "scorer_rows_in": fv.get("rows_in"), "scorer_rows_valid": fv.get("rows_valid"),
         "scorer_n_problems": fv.get("n_problems"), "scorer_cells": rep.get("cells"),
         "sha256": starter_common.sha256_file(str(path))}
    v["ok"] = (v["schema_problems"] == 0 and v["rows_valid"] == v["rows"] and v["scorer_exit"] == 0
               and v["scorer_status"] != "refused" and v["scorer_rows_valid"] == v["rows"]
               and not v["scorer_refusals"] and (v["scorer_cells"] or {}).get("scored", 0) == 0)
    return v


def submit(method: str, params: dict | None = None, universe: str = "rental_headline", out: str | None = None,
           headline_out: str | None = None) -> dict:
    params = params or {}
    hist_path, hist_cat, store = history()
    sids = data.universe(universe)  # protocol catalog as of the cutoff
    meta = harness.static_meta(data.load_catalog(str(hist_cat)))
    origin = starter_common.day_of(starter_common.parse_date(CUTOFF))
    f = methods.get(method, **params)
    fc, counts = harness.forecast(f, [origin], sids, HORIZONS, store, meta)
    sub = forecast_csv_frame(fc).assign(method=method, method_note=json.dumps(params, sort_keys=True))
    path = Path(out) if out else OUT / f"forecast_{method}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    sub.to_csv(path, index=False)

    v = validate(path, fc, sids, hist_path, OUT / "frozen_check")
    v.update({"universe": universe, "universe_size": len(sids),
              "series_without_history": len(set(sids) - set(sub["series_id"])),
              "filled_from_baseline": counts["filled_from_baseline"], "quantiles_clipped": counts["quantiles_clipped"]})
    used = getattr(f, "used", None)
    if used:
        side = path.with_name(path.stem + "_members.csv")
        pd.DataFrame([(s, h, "+".join(m), int(f.gated.get((s, o), False))) for (s, o), hm in used.items()
                      for h, m in sorted(hm.items())],
                     columns=["series_id", "horizon_days", "members_used", "gated"]).to_csv(side, index=False)
        v["members_sidecar"] = str(side)
    if headline_out:
        hs = data.universe("rental_headline")
        hpath = Path(headline_out)
        sub[sub["series_id"].isin(hs)].to_csv(hpath, index=False)
        hv = validate(hpath, fc[fc["series_id"].isin(hs)], hs, hist_path, OUT / "frozen_check_headline")
        hv["headline_series_missing"] = len(set(hs) - set(sub["series_id"]))
        v["headline"] = hv
        v["ok"] = v["ok"] and hv["ok"] and hv["headline_series_missing"] == 0
    (OUT / f"validation_{path.stem if out else method}.json").write_text(json.dumps(v, indent=2, default=str) + "\n")
    return v


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--method", required=True)
    ap.add_argument("--params", default="{}")
    ap.add_argument("--universe", default="rental_headline", choices=list(data.UNIVERSES))
    ap.add_argument("--out", help="CSV path (default runs/submission/forecast_<method>.csv)")
    ap.add_argument("--headline-out", help="also write and validate the headline series' rows here")
    a = ap.parse_args()
    v = submit(a.method, json.loads(a.params), a.universe, a.out, a.headline_out)
    print(json.dumps(v))
    return 0 if v["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
