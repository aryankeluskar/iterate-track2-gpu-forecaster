"""ecm reads daily_statistics.csv directly (p25/p75 for the `pos` feature): rows dated after the origin must not matter."""
import numpy as np
import pytest

from gpuf import data, harness, methods, splits
from gpuf.methods import ecm

REF = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
PARAMS = {"base": REF, "feats": ["pos", "dev"], "kappa": 0.5, "skew": 1.0}
ORIGINS = [splits.DEV[10], splits.DEV[30], splits.DEV[-1]]


def _run(store, meta, sids, origin):
    fc, _ = harness.forecast(methods.get("ecm", **PARAMS), [origin], sids, (1, 3, 7), store, meta)
    return fc.sort_values(["series_id", "horizon_days"]).reset_index(drop=True)


def test_future_rows_of_daily_statistics_and_store_do_not_change_forecasts():
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    sids = data.universe("rental_headline")
    base_df = ecm._ds().copy()
    rng = np.random.default_rng(0)
    try:
        for o in ORIGINS:
            ecm._DS["df"] = base_df
            a = _run(store, meta, sids, o)
            assert len(a) > 0 and (a.q10 != a.q90).any()
            pert = base_df.copy()
            m = (pert.day > o).to_numpy()
            pert.loc[m, "p25_usd_per_gpu_hour"] *= rng.uniform(0.2, 5.0, m.sum())
            pert.loc[m, "p75_usd_per_gpu_hour"] *= rng.uniform(0.2, 5.0, m.sum())
            ecm._DS["df"] = pert
            pstore = data.SeriesStore.__new__(data.SeriesStore)
            pstore._d = {}
            for sid in store.ids():
                d, v = store.arrays(sid)
                v2 = v.copy()
                v2[d > o] *= rng.uniform(0.2, 5.0, (d > o).sum())
                pstore._d[sid] = (d, v2)
            b = _run(pstore, meta, sids, o)
            np.testing.assert_array_equal(a[["q10", "q50", "q90"]].to_numpy(), b[["q10", "q50", "q90"]].to_numpy())
    finally:
        ecm._DS["df"] = base_df


def test_control_perturbing_rows_before_the_origin_does_change_forecasts():
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    sids = data.universe("rental_headline")
    base_df = ecm._ds().copy()
    o = ORIGINS[1]
    try:
        a = _run(store, meta, sids, o)
        pert = base_df.copy()
        m = ((pert.day <= o) & (pert.day > o - 60)).to_numpy()
        pert.loc[m, "p25_usd_per_gpu_hour"] *= 0.5
        ecm._DS["df"] = pert
        b = _run(store, meta, sids, o)
        assert not np.array_equal(a[["q10", "q50", "q90"]].to_numpy(), b[["q10", "q50", "q90"]].to_numpy())
    finally:
        ecm._DS["df"] = base_df
