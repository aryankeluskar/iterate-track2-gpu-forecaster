"""gpuf.index reads offer rows directly: rows after day t must not change any published value up to t."""
import numpy as np
import pandas as pd
import pytest

from gpuf import index, panel

END = index.ordinal("2026-11-06")
CUTS = [index.ordinal(d) for d in ("2026-09-20", "2026-10-01", "2026-10-06")]
PANELS = [("gpurentalprices", "H100 80GB"), ("fastgpu_daily", "B200"), ("gpurentalprices", "A100 40GB"),
          ("fastgpu_daily", "H100 SXM 80GB")]


def _alt(full, t, mode, rng):
    late = full["day"] > t
    if mode == "delete":
        return full[~late].reset_index(drop=True)
    alt = full.assign(price=np.where(late, full["price"] * rng.uniform(0.3, 3.0, len(full)), full["price"]))
    fake = full[late].drop_duplicates(["src", "cls", "gpu", "tier", "day"])
    extra = pd.concat([fake.assign(key="fakeprov|||#0", provider="fakeprov", price=50.0),
                       fake.assign(key="lambdalabs|zz||#0", provider="lambdalabs", price=0.01)])
    return pd.concat([alt, extra], ignore_index=True)


@pytest.mark.parametrize("mode", ["delete", "corrupt"])
@pytest.mark.parametrize("src,gpu", PANELS)
def test_later_rows_do_not_change_index(src, gpu, mode, monkeypatch):
    ref = index.compute(src, gpu, to_day=END)
    ref_paths = index.paths(src, gpu, to_day=END, exclude="verda")
    full = panel.load()
    rng = np.random.default_rng(7)
    for t in CUTS:
        alt = _alt(full, t, mode, rng)
        monkeypatch.setattr(panel, "load", lambda alt=alt: alt)
        got = index.compute(src, gpu, to_day=END)
        got_paths = index.paths(src, gpu, to_day=END, exclude="verda")
        monkeypatch.undo()
        pd.testing.assert_frame_equal(ref[ref["day"] <= t].reset_index(drop=True),
                                      got[got["day"] <= t].reset_index(drop=True), check_exact=True)
        pd.testing.assert_frame_equal(ref_paths.loc[:t], got_paths.loc[:t], check_exact=True)


def test_rules_on_toy_panel(monkeypatch):
    def row(day, prov, price, k="#0"):
        return dict(src="s", cls=index.CLS, gpu="G", tier=index.TIER, day=day, key=f"{prov}|||{k}", provider=prov, price=price)
    rs = [row(1, p, 1.0) for p in "abc"] + [row(1, "a", 1.0, "#1")]
    rs += [row(2, "a", 2.0), row(2, "a", 1.0, "#1"), row(2, "b", 1.0), row(2, "c", 1.0)]  # a: offers +log2 and 0
    rs += [row(3, "a", 2.0), row(3, "b", 1.1)]  # only 2 matched providers: carry and flag
    toy = pd.DataFrame(rs)
    monkeypatch.setattr(panel, "load", lambda: toy)
    t = index.compute("s", "G", to_day=3)
    assert t["anchor"].tolist() == [True, False, False]
    assert np.isclose(t["daily_change"].iloc[1], np.log(2) / 2 / 3)  # a's median change log2/2, equal weight over 3
    assert t["valid"].tolist() == [False, True, False] and t["daily_change"].iloc[2] == 0.0
    assert np.isclose(t["index_level"].iloc[2], np.exp(np.log(2) / 6))
    assert np.isclose(t["largest_provider_share"].iloc[1], 1.0) and t["largest_provider"].iloc[1] == "a"
    assert np.isclose(t["one_provider_removal"].iloc[1], np.log(2) / 6)  # dropping a: 2 providers left, invalid, 0
