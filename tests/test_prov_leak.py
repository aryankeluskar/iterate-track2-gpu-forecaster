"""prov reads rental_observations directly (all providers of a collector): rows after the origin must not matter."""
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gpuf import data, harness, methods, panel, splits

ORIGINS = [splits.DEV[5], splits.DEV[-1]]
SIDS = [s for s in data.universe("rental_headline") if panel.supported(s)]


def _run(params):
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    fc, _ = harness.forecast(methods.get("prov", **params), ORIGINS, SIDS, (1, 3, 7), store, meta)
    return fc


@pytest.mark.parametrize("params", [{"L": 1, "W": 21, "gate": "dyn", "n_paths": 300},
                                    {"L": 1, "W": 21, "gate": "dyn", "cal": True, "ret_mkt": False, "n_paths": 300},
                                    {"L": 7, "sizes": "sym", "n_paths": 300}])
@pytest.mark.parametrize("mode", ["perturb", "delete"])
def test_future_offer_rows_do_not_change_forecasts(params, mode, monkeypatch):
    ref = _run(params)
    full = panel.load()
    rng = np.random.default_rng(1)
    for o in ORIGINS:
        late = full["day"] > o
        if mode == "perturb":
            alt = full.assign(price=np.where(late, full["price"] * rng.uniform(0.3, 3.0, len(full)), full["price"]))
            extra = full[late].drop_duplicates(["src", "cls", "gpu", "tier"]).assign(key="FAKE#0", provider="verda", price=99.0)
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


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "calendar"))
import calendar_lib  # noqa: E402

CAL_PARAMS = {"L": 1, "W": 21, "gate": "dyn", "cal": True, "n_paths": 300}
GPUS = sorted({panel.parse_sid(s)[2] for s in SIDS})


def _fake_entry(published_day, origin):
    iso = lambda d: dt.date.fromordinal(int(d)).isoformat()
    return {"provider": "verda", "effective_date": iso(origin + 3), "effective_utc": iso(origin + 3) + "T00:00Z",
            "published": iso(published_day), "confidence": "A",
            "changes": [{"gpu": "all", "panel_gpus": GPUS, "tier": "on_demand", "old": None, "new": 100.0, "pct": None}]}


@pytest.mark.parametrize("lead", [1, 0])
def test_calendar_entry_published_after_origin_is_ignored(lead, monkeypatch):
    """An entry published the day after the origin leaves every forecast unchanged; the same entry published on
    the origin (positive control, lead=0) must change some forecast, so the test can fail."""
    o = splits.DEV[-1]
    ref = _run(CAL_PARAMS)
    real = calendar_lib.load()
    monkeypatch.setattr(calendar_lib, "load", lambda *a, **k: tuple(real) + (_fake_entry(o + lead, o),))
    got = _run(CAL_PARAMS)
    a = ref[ref.origin_day == o].reset_index(drop=True)
    b = got[got.origin_day == o].reset_index(drop=True)
    if lead > 0:
        pd.testing.assert_frame_equal(a, b)
    else:
        assert not a.equals(b)
