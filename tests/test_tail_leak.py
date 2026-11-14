"""tail recomputes the base method's past forecasts inside the call; changing rows after the origin must not move any output."""
import numpy as np
import pytest

from gpuf import data, harness, methods, splits

MIX = ["mix", {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}]
ORIGINS = [splits.DEV[5], splits.DEV[25]]
VARIANTS = [dict(mode="conf", pool="all"), dict(mode="conf", pool="cc", hl=30, pw=1),
            dict(mode="aci", pool="all", gamma=0.02), dict(mode="scale", pool="cc")]


def _perturbed(store, o, rng):
    pert = data.SeriesStore.__new__(data.SeriesStore)
    pert._d = {}
    for sid in store.ids():
        d, v = store.arrays(sid)
        v2 = v.copy()
        after = d > o
        v2[after] = v2[after] * rng.uniform(0.2, 5.0, after.sum())
        pert._d[sid] = (d, v2)
    return pert


@pytest.mark.parametrize("params", VARIANTS)
def test_future_rows_do_not_change_tail(params):
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    sids = data.universe("rental_headline")
    rng = np.random.default_rng(1)
    for o in ORIGINS:
        pert = _perturbed(store, o, rng)
        # fresh instances, sequential origins up to o, so the online state is built from scratch on each store
        for scope in ("headline",):
            a = methods.get("tail", base=MIX, scope=scope, **params)
            b = methods.get("tail", base=MIX, scope=scope, **params)
            og = [x for x in ORIGINS if x <= o][-1:]
            fa, _ = harness.forecast(a, og, sids, (1, 3, 7), store, meta)
            fb, _ = harness.forecast(b, og, sids, (1, 3, 7), pert, meta)
            assert len(fa) > 0 and fa.equals(fb), (params, o, scope)


def test_tail_actually_changes_the_base():
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    sids = data.universe("rental_headline")
    t = methods.get("tail", base=MIX, mode="conf")
    m = methods.get(MIX[0], **MIX[1])
    ft, _ = harness.forecast(t, [splits.DEV[-1]], sids, (7,), store, meta)
    fm, _ = harness.forecast(m, [splits.DEV[-1]], sids, (7,), store, meta)
    assert not np.allclose(ft.q90, fm.q90)
    assert np.allclose(ft.q50, fm.q50)
