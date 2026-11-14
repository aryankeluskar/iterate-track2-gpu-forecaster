import csv
import numpy as np

from gpuf.harness import OriginContext
from gpuf.methods.wsp import Features, adjust, qnet, zero_weights


def test_zero_identity_and_ordering():
    base = np.array([[1., 2., 4.], [3., 3., 3.], [.9, 1., 1.]])
    x = np.random.default_rng(0).normal(size=(3, 20))
    np.testing.assert_array_equal(adjust(base, qnet(x, zero_weights())), base)
    q = adjust(base, np.array([[2., -2., .5], [-2., 2., -.5], [0., 1., .1]]))
    assert np.all(np.isfinite(q)) and np.all(q > 0)
    assert np.all(q[:, 0] <= q[:, 1]) and np.all(q[:, 1] <= q[:, 2])


def test_future_panel_perturbation_does_not_change_forecast(tmp_path):
    from gpuf.data import starter_common as common
    origin = common.day_of(common.parse_date("2026-09-01"))
    days, vals = np.arange(origin - 20, origin + 1), np.linspace(1, 2, 21)
    meta = {"source_id": "afhubbard", "instrument_class": "hyperscaler_spot",
            "gpu_model": "test", "pricing_tier": "spot", "table": "daily_statistics"}
    context = OriginContext(origin, {"s": (days, vals), "p": (days, vals + 1)},
                            {"s": meta, "p": meta})
    header = ["date", "source_id", "instrument_class", "gpu_model", "pricing_tier",
              "n_providers", "median_usd_per_gpu_hour", "p25_usd_per_gpu_hour", "p75_usd_per_gpu_hour"]
    path = tmp_path / "panel.csv"

    def write(future):
        with path.open("w") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerow(["2026-09-01", "afhubbard", "hyperscaler_spot", "test", "spot", 5, 2, 1, 3])
            w.writerow(["2026-09-02", "afhubbard", "hyperscaler_spot", "test", "spot", future, future, 1, future])

    write(100)
    before = Features(path).cell("s", days, vals, origin, 7, context)
    write(1000000)
    after = Features(path).cell("s", days, vals, origin, 7, context)
    np.testing.assert_array_equal(before, after)
    weights = zero_weights()
    weights["w1"][:, 0] = np.arange(20) / 20
    weights["w2"][0] = [.1, .2, -.01]
    np.testing.assert_array_equal(adjust([1, 2, 3], qnet(before, weights)),
                                  adjust([1, 2, 3], qnet(after, weights)))


def test_literal_zero_hidden_gradients():
    import torch
    torch.set_num_threads(2)
    weights = {k: torch.tensor(v, requires_grad=True) for k, v in zero_weights().items()}
    x = torch.ones((2, 20), dtype=torch.float64)
    out = torch.relu(x @ weights["w1"] + weights["b1"]) @ weights["w2"] + weights["b2"]
    out.sum().backward()
    for k in ("w1", "b1", "w2"):
        assert torch.count_nonzero(weights[k].grad) == 0
    assert torch.count_nonzero(weights["b2"].grad) == 3
