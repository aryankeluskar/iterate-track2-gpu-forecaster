"""Writes results/failure_modes_iter2.json from the labelled cells (same schema as experiments/autopsy/results/failure_modes.json)."""
import json, pandas as pd
b = pd.read_parquet("runs/autopsy2/cells_labelled.parquet")
s = json.load(open("experiments/autopsy2/results/summary.json"))
LV, T3 = b.baseline_loss.sum(), b.S3_loss.sum()
SCOPE = ("Scope: 37 rental_headline series, dev cells (origins 2026-08-18..2026-10-06, h=1,3,7, n=4,278), offer panel rows <= 2026-10-13. "
         "S3 = ens of mix, gbm, chronos_last replay, fm2 bs16, analog k600, prov L1 W21 dyn (dev skill 0.2036). Cause of an h-day move from the "
         "origin->target panel decomposition of experiments/autopsy (Shapley split for mixed cells); dynamic = pivotal provider repriced on >15% "
         "of its observed days in the 21 days to the origin (headline offers on that collector); announced = calendar entry for that provider and GPU "
         "published <= origin with effective day (+collector lag) in (origin, target].")
TEXT = {
 "entry": ("Offer enters the panel", "The median moves because a provider's offer appears near the middle of the panel and composition outweighs repricing.",
   "Partly. A provider listing the same GPU and tier on the other collector but absent here raises the chance of an entry cell from 0.041 to 0.090 (lift 2.2; fires on 47% of panel cells). A calendar announcement for any provider in the panel lifts it 3.9x (entries cluster in the Nebius repricing week). A thin panel (one-offer-out fragility > 5%) does not lift it (0.69x).",
   ["2026-10-02 h=1 gpurentalprices.neocloud_rate_card.A100_40GB.on_demand: 3-offer panel, lambdalabs adds listings, median 1.294 -> 1.990; S3 q50 1.296, q90 1.302.",
    "2026-09-30 h=3 fastgpu_daily.neocloud_rate_card.B300.on_demand: together enters while nebius, fal and verda raise prices, median 7.625 -> 9.148; S3 q90 7.790."]),
 "dynamic_reprice": ("Repricing by a dynamic provider", "The pivotal provider reprices often (>15% of days in the trailing 21) and the move is mostly repricing of surviving offers.",
   "Yes: the provider's own trailing reprice rate and signed drift, which prov already uses. This is the cause iteration 2 fixed most.",
   ["2026-09-13 h=7 fastgpu_daily.neocloud_rate_card.B300.on_demand: verda staircase, 7.50 -> 7.85; S3 q10=q50=q90=7.50 (prov gate closed, every member flat).",
    "2026-09-21 h=7 gpurentalprices.neocloud_rate_card.B300.on_demand: verda up, scaleway down, 8.239 -> 8.502; S3 q90 8.297."]),
 "announced_oneoff": ("Announced one-off repricing by a static provider", "A provider that rarely reprices raises a price on a date published in the repricing calendar before the origin.",
   "Yes, fully: date and size are in data_out/repricing_calendar.jsonl. The calendar fires on 3.8% of panel cells with 47% precision for an up-move >5% (base rate 6.3%), and flags 54% of S3's up-move loss. S3 does not use it.",
   ["2026-10-01 h=7 fastgpu_daily.neocloud_rate_card.B300.on_demand: nebius +21% effective 2026-10-01 (published 2026-09-16), median 7.625 -> 9.153; S3 q90 7.920.",
    "2026-09-27 h=7 gpurentalprices.neocloud_rate_card.B300.on_demand: same nebius change, 8.460 -> 9.500; S3 q90 8.683."]),
 "unannounced_oneoff": ("Unannounced one-off repricing", "A provider that was static in the trailing 21 days reprices without a calendar entry.",
   "Weakly. 61% of the up-move cells in this class sit in panels where another provider has an announced change (the 2026-10-01 B200/B300 week: fal, verda, gmi move with nebius). The provider having raised this GPU on the other collector in the last 7 days has precision 0.38 but fires on 0.6% of cells. Verda's staircase after a 3-week pause lands here (rate21 = 0).",
   ["2026-09-30 h=3 fastgpu_daily.neocloud_rate_card.B200.on_demand: fal raises with nebius and verda in the same week, 6.470 -> 7.522; S3 q90 6.544.",
    "2026-09-12 h=7 fastgpu_daily.neocloud_rate_card.B300.on_demand: verda resumes its staircase after no reprice in 21 days, 7.50 -> 7.85; S3 interval zero width."]),
 "exit": ("Offer leaves the panel", "The median moves because a provider's offer disappears from the panel and composition outweighs repricing.",
   "Size yes (the one-offer-out median of the origin panel), timing no. No system improved it: loss/last value 0.97 (S0) to 0.94 (S3). At h=7, 67% of exit cells fall below S3's q10.",
   ["2026-09-29 h=7 fastgpu_daily.neocloud_rate_card.H100_PCIe_80GB.on_demand: thundercompute leaves (quantacloud enters lower), 3.20 -> 2.59; S3 q10=q90=3.20.",
    "2026-10-01 h=1 fastgpu_daily.neocloud_rate_card.A100_40GB.on_demand: modal leaves a 4-offer panel, 1.642 -> 1.294; S3 q10 1.639."]),
 "marketplace_ask": ("Marketplace ask noise", "The single marketplace ask series (gpurentalprices H100_80GB spot: sfcompute, spheron) moves daily.",
   "Volatility yes (recent volatility; fm2 and chronos track it), direction no. S1 -> S2 fixed most of it (0.71 -> 0.62); S3 adds nothing.",
   ["2026-08-18 h=7 gpurentalprices.marketplace_ask.H100_80GB.spot: sfcompute ask up, 1.090 -> 1.760; S3 q90 1.516.",
    "2026-10-05 h=1 gpurentalprices.marketplace_ask.H100_80GB.spot: spheron up, 1.570 -> 1.685; S3 q90 1.625."]),
 "hyperscaler_spot": ("Hyperscaler spot (afhubbard)", "Moves in the four afhubbard spot series (aws, azure, gcp, oci regional spot snapshots).",
   "Little. Changes cluster in time (afhubbard EDA) but no member exploits it beyond that; S3 is slightly worse than S2 here (0.695 vs 0.682).",
   ["2026-09-03 h=7 afhubbard.hyperscaler_spot.A100_40GB.spot: aws and gcp regional spot moves, 2.248 -> 2.135; S3 q10 2.235.",
    "2026-09-28 h=1 afhubbard.hyperscaler_spot.V100.spot: gcp spot up, 1.375 -> 1.475; S3 q90 1.388."]),
 "none": ("Width cost on cells that did not move", "Loss on cells whose value is unchanged at the target; all of it is interval width.",
   "Partly: whether a series moves is predictable (AUC 0.83, H16), and prov's gate already zeroes width on static panels.",
   ["2026-08-18 h=7 afhubbard.hyperscaler_spot.A100_40GB.spot: unchanged at 2.248, S3 interval 2.17-2.38.",
    "dev-wide: 2,211 no-move cells carry 4.2% of S3 loss (2.5% at h=7)."]),
}
modes = []
for c, g in b.groupby("cause2"):
    h7 = g[g.horizon_days == 7]
    name, dfn, vis, ex = TEXT[c]
    modes.append(dict(id=c, name=name, definition=dfn, n_cells=int(len(g)), share_of_S3_loss=round(g.S3_loss.sum() / T3, 3),
        share_of_last_value_loss=round(g.baseline_loss.sum() / LV, 3),
        S3_loss_over_last_value_loss=round(g.S3_loss.sum() / g.baseline_loss.sum(), 3) if g.baseline_loss.sum() else None,
        S2_loss_over_last_value_loss=round(g.S2_loss.sum() / g.baseline_loss.sum(), 3) if g.baseline_loss.sum() else None,
        S2_to_S3_drop_points_of_last_value_loss=round(s["S2_to_S3_drop_points_of_lv"][c], 4),
        h7_share_above_q90=round(float((h7.y > h7.S3_q90 + 1e-12).mean()), 3), h7_share_below_q10=round(float((h7.y < h7.S3_q10 - 1e-12).mean()), 3),
        top_providers_by_S3_loss_share=(g.groupby("provider").S3_loss.sum() / T3).sort_values(ascending=False).head(3).round(4).to_dict(),
        visible_in_panel_at_origin=vis, dated_examples=ex, scope=SCOPE))
modes.sort(key=lambda m: -m["share_of_S3_loss"])
for i, m in enumerate(modes, 1):
    m["rank"] = i
json.dump({"description": "Iteration 2: ranked failure modes of the current blend S3 on dev, by physical cause of the move in the posted-offer median. Each entry stands alone.",
           "modes": [{"rank": m.pop("rank"), **m} for m in modes]}, open("experiments/autopsy2/results/failure_modes_iter2.json", "w"), indent=1)
print([(m["id"], m["share_of_S3_loss"]) for m in modes])
