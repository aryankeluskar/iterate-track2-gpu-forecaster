"""hyper reads afhubbard rental_observations directly: changing or deleting offer rows after the origin must not
change any forecast at or before it."""
import numpy as np
import pandas as pd
import pytest

from gpuf import data, harness, methods, panel_hyper, splits

ORIGINS = [splits.DEV[5], splits.DEV[-1]]
SIDS = [s for s in data.universe("rental_headline") if s.startswith("afhubbard.")] + \
       ["afhubbard.hyperscaler_spot.L4.spot.median", "afhubbard.neocloud_rate_card.H100_SXM_80GB.on_demand.median"]
PARAMS = {"W": 21, "L": 1, "n_paths": 200, "sim_cls": ["hyperscaler_spot", "neocloud_rate_card"]}


def _run():
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    fc, _ = harness.forecast(methods.get("hyper", **PARAMS), ORIGINS, SIDS, (1, 3, 7), store, meta)
    return fc


@pytest.mark.parametrize("mode", ["perturb", "delete"])
def test_future_offer_rows_do_not_change_forecasts(mode, monkeypatch):
    ref = _run()
    full = panel_hyper.load()
    rows = full["rows"]
    rng = np.random.default_rng(1)
    for o in ORIGINS:
        late = (rows["day"] > o).to_numpy()
        if mode == "perturb":
            alt = rows.assign(price=np.where(late, rows["price"] * rng.uniform(0.3, 3.0, len(rows)), rows["price"]))
        else:
            alt = rows[~late].reset_index(drop=True)
        assert late.any()
        panel_hyper._index.cache_clear()
        monkeypatch.setattr(panel_hyper, "load", lambda alt=alt: {**full, "rows": alt})
        got = _run()
        monkeypatch.undo()
        panel_hyper._index.cache_clear()
        a = ref[ref.origin_day <= o].reset_index(drop=True)
        b = got[got.origin_day <= o].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)
