import numpy as np

from gpuf.methods.fm2 import covariates, load_daily_statistics


def test_covariates_ignore_rows_after_origin():
    ds = load_daily_statistics()
    r = ds[(ds.source_id == "fastgpu_daily") & (ds.instrument_class == "neocloud_rate_card")].iloc[0]
    key = (r.source_id, r.instrument_class, r.gpu_model, r.pricing_tier)
    sel = (ds.source_id == key[0]) & (ds.instrument_class == key[1]) & (ds.gpu_model == key[2]) & (ds.pricing_tier == key[3])
    days = np.sort(ds.loc[sel, "day"].to_numpy())
    origin = int(days[len(days) // 2])
    gdays = np.arange(days[0], origin + 1)
    a = covariates(ds, *key, gdays, origin)
    pert = ds.copy()
    late = sel & (pert.day > origin)
    pert.loc[late, ["n_providers", "lp25", "lp75"]] = [999, 5.0, -5.0]
    b = covariates(pert, *key, gdays, origin)
    assert late.any()
    for k in a:
        np.testing.assert_array_equal(a[k], b[k])
