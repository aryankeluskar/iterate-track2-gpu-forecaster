import numpy as np
import pandas as pd
import pytest

from gpuf import data, final_build, harness, methods
from gpuf.data import starter_common
from gpuf.methods.final import blend

SUB = data.ROOT / "submissions"


def _ctx(series, origin):
    hist = {s: (np.asarray(d, np.int64), np.asarray(v, float)) for s, (d, v) in series.items()}
    meta = {s: {"series_id": s, "table": "daily_statistics", "source_id": "src", "instrument_class": "cls"} for s in series}
    return harness.OriginContext(origin, hist, meta)


def _toy():
    days = np.arange(1000, 1060)
    rng = np.random.default_rng(0)
    active = 2.0 * np.exp(np.cumsum(np.where(rng.random(60) < 0.4, rng.normal(0, 0.03, 60), 0.0)))
    flat = np.r_[np.full(30, 3.0), np.full(30, 3.3)]  # last change 30 days before the origin
    return {"x.active": (days, active), "x.flat": (days, flat)}, int(days[-1])


def test_blend_of_one_member_equals_that_member():
    q = {1: (0.9, 1.0, 1.2), 3: (0.8, 1.0, 1.3), 7: (0.7, 1.01, 1.5)}
    res, used = blend({"mix": q}, (1, 3, 7), 1.0)
    assert res == q and all(u == ("mix",) for u in used.values())
    series, o = _toy()
    ctx = _ctx(series, o)
    fin, mix = methods.get("final", members=["mix"]), methods.get("mix", pool="cc", k=20, state="chgk", sk=3, hl=30)
    for s, (d, v) in series.items():
        assert fin(s, d, v, o, (1, 3, 7), ctx) == mix(s, d, v, o, (1, 3, 7), ctx)


def test_missing_member_is_left_out_of_that_series_average():
    a = {1: (0.8, 1.0, 1.25), 7: (0.5, 1.0, 2.0)}
    b = {1: (0.9, 1.0, 1.1)}  # cannot forecast h=7
    res, used = blend({"a": a, "b": b, "c": None}, (1, 7), 1.0)
    assert used == {1: ("a", "b"), 7: ("a",)}
    assert res[7] == a[7]
    assert np.allclose(res[1], np.sqrt(np.array(a[1]) * np.array(b[1])))
    res, used = blend({"c": None}, (1,), 4.0)
    assert res[1] == (4.0, 4.0, 4.0) and used[1] == ()


def test_pretrained_file_missing_or_lacking_a_cell_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr(final_build, "OUT", tmp_path)
    with pytest.raises(FileNotFoundError):
        methods.get("final", members=["mix", "chronos"], tag="toy", universe="u")
    series, o = _toy()
    pd.DataFrame({"series_id": ["x.active"] * 3, "origin_day": [o] * 3, "horizon_days": [1, 3, 7],
                  "q10": 1.0, "q50": 2.0, "q90": 3.0}).to_parquet(final_build.path("chronos", "toy", "u"))
    fin = methods.get("final", members=["mix", "chronos"], tag="toy", universe="u")
    ctx = _ctx(series, o)
    d, v = series["x.active"]
    fin("x.active", d, v, o, (1, 3, 7), ctx)
    assert fin.used[("x.active", o)][7] == ("mix", "chronos")
    with pytest.raises(KeyError):  # eligible series (>= 8 rows) without a cell
        fin("x.flat", *series["x.flat"], o, (1, 3, 7), ctx)
    with pytest.raises(KeyError):  # origin not in the file
        fin("x.active", d[:-1], v[:-1], o - 1, (1, 3, 7), _ctx({s: (x[:-1], y[:-1]) for s, (x, y) in series.items()}, o - 1))
    short = {"x.short": (np.arange(o - 4, o + 1), np.full(5, 2.0))}  # fewer than 8 rows: chronos left out
    fin("x.short", *short["x.short"], o, (1, 3, 7), _ctx({**series, **short}, o))
    assert fin.used[("x.short", o)][1] == ("mix",)


def test_activity_gate():
    series, o = _toy()
    ctx = _ctx(series, o)
    off = methods.get("final", members=["mix"])
    on = methods.get("final", members=["mix"], gate=[14, 1])
    d, v = series["x.flat"]
    assert on("x.flat", d, v, o, (1, 3, 7), ctx) == {h: (3.3, 3.3, 3.3) for h in (1, 3, 7)} and on.gated[("x.flat", o)]
    d, v = series["x.active"]
    assert on("x.active", d, v, o, (1, 3, 7), ctx) == off("x.active", d, v, o, (1, 3, 7), ctx)
    assert not on.gated[("x.active", o)]
    on30 = methods.get("final", members=["mix"], gate=[31, 1])  # the change 30 days back is inside 31 days
    on30("x.flat", *series["x.flat"], o, (1,), ctx)
    assert not on30.gated[("x.flat", o)]
    short = {"x.new": (np.arange(o - 9, o + 1), np.full(10, 2.0))}  # flat but under 14 days of history: not gated
    on("x.new", *short["x.new"], o, (1,), _ctx({**series, **short}, o))
    assert not on.gated[("x.new", o)]


@pytest.mark.skipif(not (SUB / "forecast_final_all.csv").exists(), reason="run bash reproduce.sh final first")
def test_sunday_files_pass_starter_validation():
    for name in ("forecast_final_all.csv", "forecast_final_headline.csv"):
        raw = pd.read_csv(SUB / name, dtype=str, keep_default_na=False)
        clean, problems = starter_common.validate_forecast(raw, [1, 3, 7])
        assert not problems and len(clean) == len(raw)
        assert set(raw["origin_date"]) == {"2026-11-06"} and set(raw["horizon_days"]) == {"1", "3", "7"}
    a = pd.read_csv(SUB / "forecast_final_all.csv", dtype=str, keep_default_na=False)
    h = pd.read_csv(SUB / "forecast_final_headline.csv", dtype=str, keep_default_na=False)
    heads = data.universe("rental_headline")
    assert set(h["series_id"]) == set(heads) and len(h) == 3 * len(heads)
    pd.testing.assert_frame_equal(a[a["series_id"].isin(heads)].reset_index(drop=True), h)
