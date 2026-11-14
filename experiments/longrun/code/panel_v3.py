"""v3 step 1: base levels under two provider definitions, and the same-offer change on the two collectors with offer rows.

Definitions are frozen in experiments/longrun/protocol_v3.yaml (task1). The same-offer decomposition repeats panel_v2.py's
code path unchanged; only the level aggregation is new.
  v2 units:      one price per (collector, provider): a provider quoted by both collectors counts twice.
  v3 unique:     one price per provider: geometric mean of its two collector prices when both collectors quote it.
Run: OMP_NUM_THREADS=2 .venv/bin/python experiments/longrun/code/panel_v3.py"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from gpuf import panel  # noqa: E402

RES = ROOT / "experiments/longrun/results"
RNG = np.random.default_rng(7)
CHIPS = {"A100": ["A100 80GB", "A100 SXM 80GB"], "H100": ["H100 SXM 80GB", "H100 80GB"], "H200": ["H200"], "B200": ["B200"], "B300": ["B300"]}
UNITS = pd.Series({"A100": 1.0, "H100": 2.464960, "H200": 2.716192, "B200": 7.914753, "B300": 8.767422})
D1 = dt.date(2026, 11, 6).toordinal()
D0 = {"gpurentalprices": dt.date(2026, 8, 4).toordinal(), "fastgpu_daily": dt.date(2026, 9, 8).toordinal()}


def boot_median(v: np.ndarray) -> list[float]:
    bs = [np.median(v[RNG.integers(0, len(v), len(v))]) for _ in range(1000)]
    return [float(np.percentile(bs, 5)), float(np.percentile(bs, 95))]


def main() -> dict:
    df = panel.load()
    df = df[(df.cls == "neocloud_rate_card") & (df.tier == "on_demand") & (df.day <= D1)].copy()
    df = df.sort_values(["src", "gpu", "key", "day"])
    prev = df.groupby(["src", "gpu", "key"]).price.shift()
    prevday = df.groupby(["src", "gpu", "key"]).day.shift()
    df["chg"] = np.where(prevday == df.day - 1, (df.price != prev).astype(float), np.nan)
    rate = df.groupby(["src", "provider"]).chg.mean().rename("reprice_rate").reset_index()
    rate["kind"] = np.where(rate.reprice_rate < 0.02, "static", np.where(rate.reprice_rate >= 0.15, "dynamic", "intermediate"))
    df = df.merge(rate, on=["src", "provider"])

    rows, levels, shared = [], [], []
    for chip, models in CHIPS.items():
        # ---- same-offer change (panel_v2 code path, unchanged)
        for src, d0 in D0.items():
            g = df[(df.src == src) & df.gpu.isin(models)]
            a, b = g[g.day == d0].set_index(["gpu", "key"]), g[g.day == D1].set_index(["gpu", "key"])
            if len(a) == 0 or len(b) == 0:
                continue
            both = a.join(b[["price"]].rename(columns={"price": "price_1"}), how="inner")
            both["dl"] = np.log(both.price_1 / both.price)
            st = both[both.kind == "static"]
            rows.append({"chip": chip, "src": src, "from": dt.date.fromordinal(d0), "to": dt.date.fromordinal(D1),
                         "posted_median_dlog": float(np.log(b.price.median() / a.price.median())),
                         "n_offers_d0": len(a), "n_offers_d1": len(b), "n_same_offers": len(both),
                         "same_offers_mean_dlog": float(both.dl.mean()),
                         "n_static_same": len(st), "static_same_mean_dlog": float(st.dl.mean()) if len(st) else np.nan,
                         "static_up": int((st.dl > 0.005).sum()), "static_down": int((st.dl < -0.005).sum())})
        # ---- levels on 6 Nov
        last = df[(df.day == D1) & df.gpu.isin(models) & (df.kind == "static")]
        units = last.groupby(["src", "provider"]).price.median()                     # v2 definition
        wide = units.unstack("src")
        both_c = wide.dropna()
        uniq = np.exp(np.log(wide).mean(axis=1, skipna=True))                        # v3 primary: geometric mean
        uniq_grp = wide["gpurentalprices"].fillna(wide.get("fastgpu_daily")) if "gpurentalprices" in wide else wide["fastgpu_daily"]
        uniq_fg = wide["fastgpu_daily"].fillna(wide.get("gpurentalprices")) if "fastgpu_daily" in wide else wide["gpurentalprices"]
        levels.append({"chip": chip,
                       "v2_units_n": len(units), "v2_units_median": float(units.median()), "v2_units_ci90": boot_median(units.values),
                       "v3_unique_n": len(uniq), "v3_unique_median": float(uniq.median()), "v3_unique_ci90": boot_median(uniq.values),
                       "v3_rule_grp_first_median": float(uniq_grp.median()), "v3_rule_fg_first_median": float(uniq_fg.median()),
                       "n_providers_in_both": len(both_c),
                       "median_abs_log_gap_shared": float(np.median(np.abs(np.log(both_c.gpurentalprices / both_c.fastgpu_daily)))) if len(both_c) else np.nan})
        for p, r in both_c.iterrows():
            shared.append({"chip": chip, "provider": p, "gpurentalprices": r.gpurentalprices, "fastgpu_daily": r.fastgpu_daily,
                           "log_gap": float(np.log(r.gpurentalprices / r.fastgpu_daily))})

    t = pd.DataFrame(rows)
    t["posted_minus_static_same_dlog"] = t.posted_median_dlog - t.static_same_mean_dlog
    t.round(4).to_csv(RES / "v3_t1_same_offer_change.csv", index=False)
    lv = pd.DataFrame(levels).set_index("chip")
    for k in ["v2_units_median", "v3_unique_median", "v3_rule_grp_first_median", "v3_rule_fg_first_median"]:
        per = lv[k] / UNITS
        lv[k.replace("_median", "_ratio_vs_frontier")] = per / per[["B200", "B300"]].min()
    lv["level_change_v3_vs_v2_pct"] = 100 * (lv.v3_unique_median / lv.v2_units_median - 1)
    lv.round(4).to_csv(RES / "v3_t1b_levels_two_definitions.csv")
    pd.DataFrame(shared).round(4).to_csv(RES / "v3_t1c_shared_providers.csv", index=False)
    out = {"levels": lv.round(4).reset_index().to_dict("records"),
           "n_collector_provider_units_by_kind": {f"{k[0]}|{k[1]}": int(v) for k, v in rate.groupby(["src", "kind"]).size().items()}}
    json.dump(out, open(RES / "v3_panel_summary.json", "w"), indent=1, default=str)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(t.round(3).to_string())
    print(lv.round(3).to_string())
    print(pd.DataFrame(shared).round(3).to_string())
    return out


if __name__ == "__main__":
    main()
