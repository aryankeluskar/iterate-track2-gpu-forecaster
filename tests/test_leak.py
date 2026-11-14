"""Acceptance C: a forecaster cannot see rows dated after its origin."""
import numpy as np
import pytest

from gpuf import baselines, data, harness, splits

ORIGINS = [splits.DEV[0], splits.DEV[60], splits.DEV[-1], splits.STARTER15[-1]]


def _cross(sid, days, vals, origin_day, horizons, ctx):
    """Drift, shifted by the mean last value of every other series (so ctx leaks would show up)."""
    lv = [ctx.history(s)[1][-1] for s in ctx.ids()]
    shift = 1.0 + 1e-3 * float(np.tanh(np.mean(lv)))
    return {h: tuple(x * shift for x in q) for h, q in baselines.drift(sid, days, vals, origin_day, horizons, ctx).items()}


def test_cheater_sees_nothing_after_origin():
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    violations = []

    def cheat(sid, days, vals, origin_day, horizons, ctx):
        if len(days) and days.max() > origin_day:
            violations.append(("own", sid))
        if days.base is not None or vals.base is not None:
            violations.append(("base", sid))
        try:
            vals[0] = 0.0
            violations.append(("writeable", sid))
        except ValueError:
            pass
        for other in store.ids():  # ask for every series, including ones that start later
            d, v = ctx.history(other)
            if len(d) and d.max() > origin_day:
                violations.append(("ctx.history", other))
            if d.base is not None:
                violations.append(("ctx.base", other))
        for d, v in ctx._hist.values():  # even the private storage holds only truncated copies
            if len(d) and d.max() > origin_day:
                violations.append(("ctx._hist", sid))
        if set(ctx.meta(sid)) & set(harness.AS_OF_FIELDS):
            violations.append(("meta", sid))
        return {}

    sids = data.universe("rental_all")[:40] + data.universe("rental_headline")
    fc, _ = harness.forecast(cheat, ORIGINS, sids, (1, 3, 7), store, meta)
    assert len(fc) > 0
    assert violations == []
    with pytest.raises(AttributeError):
        harness.OriginContext(0, {}, {}).store = store  # __slots__: nothing can be attached


def test_perturbing_the_future_leaves_forecasts_unchanged():
    store = data.load_store(data.series_path())
    meta = harness.static_meta(data.load_catalog())
    sids = data.universe("rental_all")
    rng = np.random.default_rng(0)
    for o in ORIGINS:
        pert = data.SeriesStore.__new__(data.SeriesStore)
        pert._d = {}
        for sid in store.ids():
            d, v = store.arrays(sid)
            v2 = v.copy()
            after = d > o
            v2[after] = v2[after] * rng.uniform(0.2, 5.0, after.sum())
            pert._d[sid] = (d, v2)
        for f in (baselines.drift, _cross):
            a, _ = harness.forecast(f, [o], sids, (1, 3, 7), store, meta)
            b, _ = harness.forecast(f, [o], sids, (1, 3, 7), pert, meta)
            assert len(a) > 0
            assert a.equals(b), (f.__name__, o)


def test_test_split_is_locked():
    with pytest.raises(splits.LockedSplit):
        harness.evaluate(baselines.drift, "test")
    with pytest.raises(splits.LockedSplit):
        harness.evaluate(baselines.drift, [splits.TEST[3]])
