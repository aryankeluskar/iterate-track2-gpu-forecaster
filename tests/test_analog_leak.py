"""analog: changing data dated after the origin leaves the forecast unchanged."""
import numpy as np
import pandas as pd

from gpuf import data, harness, splits
from gpuf.methods import analog

ORIGIN_IDX = (5, 25)


def _frame():
    cat = data.load_catalog()
    cat = cat[cat["table"] == "daily_statistics"]
    meta = {r.series_id: (r.source_id, r.instrument_class) for r in cat.itertuples()}
    df = pd.read_csv(data.series_path(), usecols=["series_id", "date", "value", "n_providers"], low_memory=False)
    df = df[df["series_id"].isin(meta) & (df["date"] <= analog.DEV_CAP)].dropna(subset=["value"]).copy()
    df["day"] = pd.to_datetime(df["date"]).map(pd.Timestamp.toordinal).astype(np.int64)
    return df, meta


def test_future_rows_do_not_change_forecast():
    df, meta = _frame()
    store = data.load_store(data.series_path())
    smeta = harness.static_meta(data.load_catalog())
    heads = data.universe("rental_headline")[:12]
    base = analog.AnalogTable(df, meta)
    for oi in ORIGIN_IDX:
        o = splits.DEV[oi]
        pert = df.copy()
        late = pert["day"] > o
        rng = np.random.default_rng(oi)
        pert.loc[late, "value"] = pert.loc[late, "value"] * rng.uniform(0.2, 5.0, late.sum())
        pert.loc[late, "n_providers"] = 99
        extra = pert[late].copy()
        extra["day"] += 400
        pert = pd.concat([pert, extra])
        t2 = analog.AnalogTable(pert, meta)
        assert (t2.day > o).sum() != (base.day > o).sum()
        ctx = harness.make_context(store, o, smeta)
        for params in ({"pool": "all", "k": 300}, {"pool": "cc", "k": 100, "rescale": True, "hl": 30},
                       {"pool": "self", "k": 100, "fallback": "class"}, {"pool": "class", "k": 50, "centre": "last"}):
            fa = analog.make(table=base, **params)
            fb = analog.make(table=t2, **params)
            n = 0
            for sid in heads:
                d, v = ctx.history(sid)
                if len(d) < 5:
                    continue
                a, b = fa(sid, d, v, o, (1, 3, 7), ctx), fb(sid, d, v, o, (1, 3, 7), ctx)
                assert a == b, (sid, params, a, b)
                n += 1
            assert n > 0


def test_deleting_rows_after_the_origin_changes_nothing():
    """Added after the audit (experiments/audit/results/audit.md, item 1b): the earlier tests changed values after the
    origin but never deleted rows, and missed that a young series' later rows decided whether it entered the table."""
    import datetime as dt

    import numpy as np
    import pandas as pd

    from gpuf import data
    from gpuf.methods import get
    from gpuf.methods.analog import AnalogTable

    cat = data.load_catalog()
    ok = cat[cat["table"] == "daily_statistics"]
    meta = {r.series_id: (r.source_id, r.instrument_class) for r in ok.itertuples()}
    df = pd.read_csv(data.series_path(), usecols=["series_id", "date", "value", "n_providers"], low_memory=False)
    df = df[df["series_id"].isin(meta)].dropna(subset=["value"]).copy()
    df["day"] = pd.to_datetime(df["date"]).map(pd.Timestamp.toordinal).astype(np.int64)
    origin = dt.date(2026, 10, 21).toordinal()
    full, cut = AnalogTable(df, meta), AnalogTable(df[df["day"] <= origin], meta)
    sids = data.universe("rental_headline") + [s for s in sorted(meta) if s.startswith("tanod.")][:20]
    n = 0
    for sid in sids:
        g = df[(df["series_id"] == sid) & (df["day"] <= origin)].sort_values("day")
        if len(g) == 0:
            continue
        days, vals = g["day"].to_numpy(np.int64), g["value"].to_numpy(np.float64)
        p = {"pool": "all", "k": 600, "drop": ["n14", "sign"]}
        a = get("analog", table=full, **p)(sid, days, vals, origin, (1, 3, 7), None)
        b = get("analog", table=cut, **p)(sid, days, vals, origin, (1, 3, 7), None)
        assert a == b, sid
        n += 1
    assert n >= 40
