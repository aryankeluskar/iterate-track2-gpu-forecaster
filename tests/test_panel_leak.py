"""The panel method reads rental_observations directly: rows dated after the origin must not matter."""
import numpy as np
import pandas as pd
import pytest

from gpuf import data, harness, methods, panel, splits

ORIGINS = [splits.DEV[5], splits.DEV[-1]]
SIDS = [s for s in data.universe("rental_headline") if panel.supported(s)]


def _run(params):
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    fc, _ = harness.forecast(methods.get("panel", **params), ORIGINS, SIDS, (1, 3, 7), store, meta)
    return fc


@pytest.mark.parametrize("params", [{"variant": "v1", "hl": 14, "n_paths": 400}, {"variant": "v0"}])
@pytest.mark.parametrize("mode", ["perturb", "delete"])
def test_future_offer_rows_do_not_change_forecasts(params, mode, monkeypatch):
    ref = _run(params)
    full = panel.load()
    cut = min(ORIGINS)  # everything after the earliest origin is altered; later origins see their own future change
    rng = np.random.default_rng(1)
    for o in ORIGINS:
        late = full["day"] > o
        if mode == "perturb":
            alt = full.assign(price=np.where(late, full["price"] * rng.uniform(0.3, 3.0, len(full)), full["price"]))
            # also add a fake future offer to every panel
            extra = full[late].drop_duplicates(["src", "cls", "gpu", "tier"]).assign(key="FAKE#0", price=99.0)
            alt = pd.concat([alt, extra], ignore_index=True)
        else:
            alt = full[~late].reset_index(drop=True)
        panel._index.cache_clear()
        monkeypatch.setattr(panel, "load", lambda alt=alt: alt)
        got = _run(params)
        monkeypatch.undo()
        panel._index.cache_clear()
        a = ref[ref.origin_day <= o].reset_index(drop=True)
        b = got[got.origin_day <= o].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)
    assert cut in ref.origin_day.values
