"""v2 step 1: panel-robust within-chip change and per-unit comparison from static rate-card offers (gpuf.panel).

Neocloud rate cards, on-demand, gpurentalprices (2026-08-04..11-06) and fastgpu_daily (2026-09-08..11-06). An offer is a
gpuf.panel key. Provider reprice rate = share of its offer-days whose price differs from the same offer's previous day;
static < 0.02, dynamic >= 0.15 (insight.md thresholds). Balanced = offers present on the first and the last day."""
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
UNITS = {"A100": 1.0, "H100": 2.464960, "H200": 2.716192, "B200": 7.914753, "B300": 8.767422}
D1 = dt.date(2026, 11, 6).toordinal()
D0 = {"gpurentalprices": dt.date(2026, 8, 4).toordinal(), "fastgpu_daily": dt.date(2026, 9, 8).toordinal()}


def main() -> dict:
    df = panel.load()
    df = df[(df.cls == "neocloud_rate_card") & (df.tier == "on_demand")].copy()
    df = df.sort_values(["src", "gpu", "key", "day"])
    prev = df.groupby(["src", "gpu", "key"]).price.shift()
    prevday = df.groupby(["src", "gpu", "key"]).day.shift()
    ok = prevday == df.day - 1
    df["chg"] = np.where(ok, (df.price != prev).astype(float), np.nan)
    rate = df.groupby(["src", "provider"]).chg.mean().rename("reprice_rate").reset_index()
    rate["kind"] = np.where(rate.reprice_rate < 0.02, "static", np.where(rate.reprice_rate >= 0.15, "dynamic", "intermediate"))
    df = df.merge(rate, on=["src", "provider"])
    rows, levels = [], []
    for chip, models in CHIPS.items():
        for src, d0 in D0.items():
            for gm in models + ["__chip__"]:
                g = df[(df.src == src) & (df.gpu.isin(models if gm == "__chip__" else [gm]))]
                a, b = g[g.day == d0].set_index(["gpu", "key"]), g[g.day == D1].set_index(["gpu", "key"])
                if len(a) == 0 or len(b) == 0:
                    continue
                both = a.join(b[["price"]].rename(columns={"price": "price_1"}), how="inner")
                both["dl"] = np.log(both.price_1 / both.price)
                st = both[both.kind == "static"]
                dy = both[both.kind == "dynamic"]
                rows.append({"chip": chip, "series": gm if gm != "__chip__" else f"{chip} (all SKUs)", "src": src,
                             "from": dt.date.fromordinal(d0), "to": dt.date.fromordinal(D1),
                             "posted_median_dlog": float(np.log(b.price.median() / a.price.median())),
                             "n_offers_d0": len(a), "n_offers_d1": len(b), "n_balanced": len(both),
                             "balanced_mean_dlog": float(both.dl.mean()) if len(both) else np.nan,
                             "n_static": len(st), "static_mean_dlog": float(st.dl.mean()) if len(st) else np.nan,
                             "static_up": int((st.dl > 0.005).sum()), "static_down": int((st.dl < -0.005).sum()),
                             "n_dynamic": len(dy), "dynamic_mean_dlog": float(dy.dl.mean()) if len(dy) else np.nan})
        # panel-robust level on 6 Nov: one price per static provider (median over its offers), both collectors pooled
        last = df[(df.day == D1) & df.gpu.isin(models) & (df.kind == "static")]
        pp = last.groupby(["src", "provider"]).price.median()
        allp = df[(df.day == D1) & df.gpu.isin(models)].groupby(["src", "provider"]).price.median()
        bs = [np.median(pp.values[RNG.integers(0, len(pp), len(pp))]) for _ in range(1000)]
        levels.append({"chip": chip, "n_static_providers": len(pp), "static_median_usd": float(pp.median()),
                       "ci90": [float(np.percentile(bs, 5)), float(np.percentile(bs, 95))],
                       "all_providers_median_usd": float(allp.median()), "n_all_providers": len(allp)})
    t = pd.DataFrame(rows)
    t["panel_effect_dlog"] = t.posted_median_dlog - t.static_mean_dlog
    t.round(4).to_csv(RES / "v2_t1_panel_decomposition.csv", index=False)
    lv = pd.DataFrame(levels).set_index("chip")
    lv["usd_per_unit_static"] = lv.static_median_usd / pd.Series(UNITS)
    front = lv.loc[["B200", "B300"], "usd_per_unit_static"].min()
    lv["premium_vs_frontier_static"] = lv.usd_per_unit_static / front
    lv["premium_vs_frontier_all"] = (lv.all_providers_median_usd / pd.Series(UNITS)) / (lv.loc[["B200", "B300"], "all_providers_median_usd"] / pd.Series(UNITS)[["B200", "B300"]]).min()
    lv.round(4).to_csv(RES / "v2_t1b_static_levels_per_unit.csv")
    # GetDeploying weekly on-demand over the same window (cannot be decomposed)
    ag = pd.read_csv(ROOT / "data/pack/gpu-price-pack-v0.1.1-handover/aggregator_medians.csv", parse_dates=["week_start"])
    ag = ag[(ag.pricing_mode == "on_demand")]
    gd = {}
    for chip in CHIPS:
        s = ag[ag.gpu_model == f"NVIDIA {chip}"].set_index("week_start").median_usd_per_gpu_hour
        gd[chip] = {"aug03_to_oct26_dlog": float(np.log(s[pd.Timestamp("2026-10-26")] / s[pd.Timestamp("2026-08-03")])),
                    "sep07_to_oct26_dlog": float(np.log(s[pd.Timestamp("2026-10-26")] / s[pd.Timestamp("2026-09-07")])),
                    "nov03_2025_to_oct26_2026_dlog": float(np.log(s[pd.Timestamp("2026-10-26")] / s.sort_index().iloc[0]))}
    out = {"getdeploying": gd, "levels": lv.round(4).reset_index().to_dict("records"),
           "n_providers_by_kind": rate.groupby(["src", "kind"]).size().to_dict()}
    out["n_providers_by_kind"] = {f"{k[0]}|{k[1]}": int(v) for k, v in out["n_providers_by_kind"].items()}
    json.dump(out, open(RES / "v2_panel_summary.json", "w"), indent=1, default=str)
    print(t[t.series.str.contains("all SKUs") | t.chip.isin(["H200", "B200", "B300"])].round(3).to_string())
    print(lv.round(3).to_string())
    print(json.dumps(gd, indent=1))
    return out


if __name__ == "__main__":
    main()
