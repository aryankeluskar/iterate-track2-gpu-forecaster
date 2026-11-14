"""Acceptance A (reference) and B (FAST == OFFICIAL)."""
import json

import numpy as np
import pandas as pd
import pytest

from gpuf import baselines, data, harness

ROOT = data.ROOT
DEMO = ROOT / "demo_out"
TOL = 1e-9


def _check_agree(res, workdir):
    off = res.official(workdir)
    assert off["returncode"] == 0, off["stderr"]
    s, rep = res.summary, off["report"]
    assert off["n_cells"] == s["n_cells"] == rep["cells"]["scored"]
    assert abs(off["pooled_loss"] - s["pooled_loss"]) < TOL
    assert abs(off["baseline_loss"] - s["baseline_loss"]) < TOL
    assert abs(off["pooled_skill"] - s["pooled_skill"]) < TOL
    for k in ("missing_truth", "missing_baseline"):
        assert rep["cells"][k] == s["counts"][k], k
    for k in ("skill_mean_of_series", "skill_median_of_series", "skill_geomean", "share_series_positive_skill",
              "n_series_with_skill", "n_series_baseline_degenerate"):
        assert rep["overall"][k] == s[k], k
    for h, bh in rep["by_horizon"].items():
        assert bh["n_cells"] == s["by_horizon"][h]["n_cells"]
        if bh["skill_pooled"] is not None:
            assert abs(bh["skill_pooled"] - s["by_horizon"][h]["pooled_skill"]) <= 5e-7
        assert bh["skill_median_of_series"] == s["by_horizon"][h]["skill_median_of_series"]
    cov = rep["overall"]["coverage"]["within_q10_q90"]
    assert abs(cov - s["coverage"]["within_q10_q90"]) <= 5e-7
    return off


@pytest.fixture(scope="module")
def ref_sids():
    return data.catalog_ids(data.load_catalog(str(DEMO / "catalog_2026-10-24.csv")), "headline")


def test_reference_drift_matches_demo_both_scorers(ref_sids, tmp_path):
    assert len(ref_sids) == 97
    res = harness.evaluate(baselines.drift, "starter15", ref_sids, (1, 3, 7), name="drift")
    demo = json.loads((DEMO / "backtest/report_drift_h137.json").read_text())
    assert res.summary["n_cells"] == demo["cells"]["scored"] == 4209
    assert round(res.summary["pooled_skill"], 6) == demo["overall"]["skill_pooled"] == 0.183267
    for k in ("skill_mean_of_series", "skill_median_of_series", "skill_geomean"):
        assert res.summary[k] == demo["overall"][k], k
    off = _check_agree(res, tmp_path)
    assert off["report"]["overall"]["skill_pooled"] == 0.183267


def test_drift_forecasts_byte_identical_to_starter(ref_sids):
    """Our drift wrapper, run through the harness, reproduces the starter's forecast_drift.csv quantiles."""
    store = data.load_store(data.series_path())
    fc, _ = harness.forecast(baselines.drift, harness.splits.STARTER15, ref_sids, (1, 3, 7, 30), store, {})
    demo = pd.read_csv(DEMO / "backtest/forecast_drift.csv", dtype=str, keep_default_na=False)
    ours = fc.assign(origin_date=fc["origin_day"].map(data.starter_common.iso),
                     horizon_days=fc["horizon_days"].astype(str))
    for q in ("q10", "q50", "q90"):
        ours[q] = ours[q].map(lambda x: "%.10g" % x)
    key = ["series_id", "origin_date", "horizon_days"]
    m = demo.merge(ours, on=key, suffixes=("_demo", "_ours"), validate="one_to_one")
    assert len(m) == len(demo) == len(ours)
    for q in ("q10", "q50", "q90"):
        assert (m[f"{q}_demo"] == m[f"{q}_ours"]).all(), q


@pytest.mark.parametrize("universe", ["rental_headline", "rental_all"])
def test_fast_equals_official_drift_dev(universe, tmp_path):
    res = harness.evaluate(baselines.drift, "dev", universe, name="drift")
    assert res.summary["n_cells"] > 0
    _check_agree(res, tmp_path)


def test_fast_equals_official_with_fill_and_monotone(ref_sids, tmp_path):
    """A forecaster that skips h=3 and returns crossed quantiles: harness fill + monotone agree with OFFICIAL."""
    def odd(sid, days, vals, origin_day, horizons, ctx):
        out = baselines.drift(sid, days, vals, origin_day, horizons, ctx)
        out.pop(3, None)
        return {h: (q90 * 1.01, q50, q10 * 0.99) for h, (q10, q50, q90) in out.items()}

    res = harness.evaluate(odd, "starter15", ref_sids, (1, 3, 7), name="odd")
    assert res.summary["counts"]["filled_from_baseline"] > 0
    f = res.forecasts
    assert (f["q10"] <= f["q50"]).all() and (f["q50"] <= f["q90"]).all() and (f["q10"] > 0).all()
    _check_agree(res, tmp_path)


def test_pack_has_no_pycache():
    assert not list(data.PACK.rglob("__pycache__"))
