"""Read-only practice-store verification and collector/calendar support analysis.

Protocol is in review_maturity.md. Prints results; writes nothing, imports no
project forecaster, and reads no file except runs/maturity/cells.parquet.
"""
import datetime as dt

import numpy as np
import pandas as pd

START = dt.date(2026, 8, 18).toordinal()
END = dt.date(2026, 10, 6).toordinal()
OCT = dt.date(2026, 10, 1).toordinal()
MEMBERS = ("mix", "gbm", "chronos", "analog", "prov", "fm2", "fragility")
Q = ("q10", "q50", "q90")
TAUS = np.array([0.1, 0.5, 0.9])
D = pd.read_parquet(
    "runs/maturity/cells.parquet",
    filters=[("origin_day", ">=", START), ("origin_day", "<=", END)],
)
KEY = ["series_id", "origin_day", "horizon_days"]
assert not D.duplicated(KEY).any()
assert D.origin_day.between(START, END).all()
assert D.horizon_days.isin([1, 3, 7]).all()
D["src"] = D.series_id.str.split(".").str[0]
D["date"] = D.origin_day.map(lambda o: dt.date.fromordinal(int(o)).isoformat())
D["week"] = D.origin_day.map(
    lambda o: (dt.date.fromordinal(int(o)) - dt.timedelta(
        days=dt.date.fromordinal(int(o)).weekday())).isoformat()
)
D["target"] = D.origin_day + D.horizon_days
D["mature"] = D.rows >= 60
D["change_group"] = np.where(D.chg14 == 1, "one", "multiple")


def quantiles(members, clean=True):
    a = np.stack([D[[f"{m}_{q}" for q in Q]].to_numpy(float) for m in members])
    present = np.isfinite(a)
    assert np.array_equal(present[:, :, 0], present[:, :, 1])
    assert np.array_equal(present[:, :, 1], present[:, :, 2])
    assert not np.isinf(a).any()
    count = present[:, :, 0].sum(axis=0)
    logs = np.log(np.maximum(a, 1e-9))
    out = np.exp(np.nansum(logs, axis=0) / np.maximum(count, 1)[:, None])
    if clean:
        single = count == 1
        out[single] = np.nansum(a, axis=0)[single]
    out[count == 0] = D["last"].to_numpy()[count == 0, None]
    if clean:
        out[:, 0] = np.minimum(out[:, 0], out[:, 1])
        out[:, 2] = np.maximum(out[:, 2], out[:, 1])
        out[out <= 0] = 1e-6
    return out


def loss(q):
    error = D.y.to_numpy()[:, None] - q
    return np.maximum(TAUS * error, (TAUS - 1) * error).mean(axis=1)


for name in ("drift",) + MEMBERS:
    D["L_" + name] = loss(quantiles((name,)))
D["L_final"] = loss(quantiles(MEMBERS))
D["L_raw"] = loss(quantiles(MEMBERS, clean=False))
D["L_submitted"] = np.where(
    ~D.in37 & D.gate14, D.baseline_loss, D.L_final
)
assert np.allclose(D.baseline_loss, np.abs(D.y - D["last"]) / 2, atol=1e-12)
error = np.abs(D.L_final - D.final_loss)
assert error.max() < 1e-10, error.max()


def show(label, g, models=("drift", "mix", "final", "chronos", "fm2")):
    base = g.baseline_loss.sum()
    scores = " ".join(
        f"{m}={1 - g['L_' + m].sum() / base:+.6f}" if base > 0 else f"{m}=NA"
        for m in models
    )
    print(f"{label}: cells={len(g)} series={g.series_id.nunique()} "
          f"origins={g.origin_day.nunique()} base={base:.6f} {scores}")


print("SOURCE runs/maturity/cells.parquet")
print(f"store cells={len(D)} series={D.series_id.nunique()} "
      f"origins={D.date.min()}..{D.date.max()} targets_max={D.target.max()}")
print(f"clean_reblend_max_error={error.max():.16g}; "
      f"raw_max_error={np.abs(D.L_raw - D.final_loss).max():.16g}; "
      f"raw_changed_cells={(np.abs(D.L_raw - D.final_loss) > 1e-12).sum()}")
bad = D[np.abs(D.L_raw - D.final_loss) > 1e-12]
print("raw_discrepancy_collectors", bad.groupby("src").size().to_dict())
print("raw_discrepancy_in37", int(bad.in37.sum()))
D["L_fragility_raw"] = loss(quantiles(("fragility",), clean=False))
for member in MEMBERS:
    a = D[[f"{member}_{q}" for q in Q]].to_numpy(float)
    crossing = (a[:, 0] > a[:, 1]) | (a[:, 2] < a[:, 1])
    if crossing.any():
        print(f"crossed_member {member}: {int(crossing.sum())}")

head = D[D.in37]
show("fixed37", head)
show("tier", D[D.tier])
show("all_ungated_and_submitted", D, ("final", "submitted"))
print("tier_not_fixed37", int((D.tier & ~D.in37).sum()))
print("tier_composition", D[D.tier].groupby("src").agg(
    cells=("series_id", "size"), series=("series_id", "nunique"),
    origins=("origin_day", "nunique"), rows_min=("rows", "min"),
    rows_max=("rows", "max")).to_dict("index"))
print("rows60_composition", head[head.mature].groupby("src").agg(
    cells=("series_id", "size"), series=("series_id", "nunique"),
    origins=("origin_day", "nunique")).to_dict("index"))
gain = (head.L_drift - head.L_final).sum()
base = head.baseline_loss.sum()
for label, mask in (
    ("tier", head.tier), ("not_tier", ~head.tier),
    ("rows_lt60", ~head.mature), ("rows_ge60", head.mature),
    ("certain_insufficient_pairs", head.rows - head.horizon_days < 20),
    ("exact_drift_flat", (head.drift_q10 == head["last"]) &
     (head.drift_q50 == head["last"]) & (head.drift_q90 == head["last"])),
):
    g = head[mask]
    improvement = (g.L_drift - g.L_final).sum()
    print(f"gain_contribution {label}: cells={len(g)} baseline_share="
          f"{g.baseline_loss.sum()/base:.6f} skill_points={improvement/base:.6f} "
          f"gain_share={improvement/gain:.6f}")

print("collector_labels", sorted(D.src.unique()))
print("not_gated_but_no_change", int((~D.gate14 & (D.chg14 == 0)).sum()))
for label, g in head.groupby("src"):
    show("head_collector " + label, g)
show("gpurentalprices_rows60_fragility_cleanup",
     head[head.mature & (head.src == "gpurentalprices")],
     ("fragility", "fragility_raw"))

rate = D[(D.cls == "neocloud_rate_card") & (D.chg14 > 0)]
print("RATE_CARD_ANALYSIS actual chg14>0")
for (src, mature), g in rate.groupby(["src", "mature"]):
    show(f"all src={src} mature={mature}", g)
    show(f"before_oct_including_targets src={src} mature={mature}",
         g[g.target < OCT])
    print(f"rate_support {src} mature={mature} weeks={sorted(g.week.unique())}")
for src, g in rate[rate.mature].groupby("src"):
    before = g[g.target < OCT]
    after = g[g.target >= OCT]
    cohort = set(before.series_id) & set(after.series_id)
    show(f"fixed_series_cohort before_oct {src}",
         before[before.series_id.isin(cohort)])
    show(f"fixed_series_cohort october_targets {src}",
         after[after.series_id.isin(cohort)])
    extra = after[~after.series_id.isin(cohort)]
    if len(extra):
        print(f"october_only_active_cohort {src}: cells={len(extra)} "
              f"series={extra.series_id.nunique()} baseline={extra.baseline_loss.sum():.6f} "
              + " ".join(f"{m}_loss={extra['L_' + m].sum():.6f}"
                         for m in ("mix", "final", "chronos", "fm2")))

strata = ["src", "origin_day", "horizon_days", "change_group"]
support = rate.groupby(strata).mature.nunique()
keys = support[support == 2].index
matched = rate.set_index(strata)
matched = matched[matched.index.isin(keys)].reset_index()
print(f"exact_common_support strata={len(keys)} cells={len(matched)} "
      f"collectors={sorted(matched.src.unique())}")
if len(keys):
    agg = matched.groupby(strata + ["mature"])[
        ["baseline_loss", "L_drift", "L_final"]
    ].mean().unstack("mature")
    den = (agg[("baseline_loss", False)] + agg[("baseline_loss", True)]) / 2
    paired = ((agg[("L_drift", True)] - agg[("L_final", True)]) -
              (agg[("L_drift", False)] - agg[("L_final", False)]))
    valid = den > 0
    print("common_support_positive_baseline_both_sides",
          int(((agg[("baseline_loss", False)] > 0) &
               (agg[("baseline_loss", True)] > 0)).sum()))
    for (src, mature), g in matched.groupby(["src", "mature"]):
        show(f"matched_support {src} mature={mature}", g)
    print("common_support_mean_stratum_normalized_maturity_gap",
          float((paired[valid] / den[valid]).mean()),
          "valid_strata", int(valid.sum()))

print("RATE_CARD_WEEKLY same collector and actual prior activity")
for (src, week, mature), g in rate.groupby(["src", "week", "mature"]):
    show(f"{src} {week} mature={mature}", g)
