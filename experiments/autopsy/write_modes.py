"""Writes results/failure_modes.json from runs/autopsy/modes_raw.json + step3/probe summaries (numbers copied from those files)."""
import json
raw = json.load(open("runs/autopsy/modes_raw.json"))
T = {r["mode"]: r for r in raw["table"]}
E = {r["mode"]: r for r in raw["event_level"]}
S = raw["top_series"]; X = raw["examples"]
COMMON = ("Scope: 37 rental_headline series, dev blend cells (origins 2026-08-18..2026-10-06, h=1,3,7, n=4266 with panel), "
          "one-day events 2026-08-04..2026-10-13 (n=579). Blend = mix+gbm+chronos_last, runs/failure/blend_dev_cells.parquet. "
          "Cause of an h-day move: counterfactual median of origin-day offers at target-day prices (repricing) vs the rest (composition); "
          "label needs >=80% of |effect| in one part, else mixed. Offer key: fastgpu provider; gpurentalprices provider+sku_raw; afhubbard provider+region+sku+gpu_count.")
def entry(rank, mode, name, definition, reverts, visible, examples, extra):
    t, e = T[mode], E.get(mode, {})
    return dict(rank=rank, id=mode, name=name, definition=definition, n_blend_cells=t["n_cells"], n_one_day_events=e.get("n_events"),
                share_of_blend_loss=t["loss_share"], share_of_blend_loss_from_cells_outside_q10_q90=t["miss_loss_share"],
                share_of_last_value_loss=t["lv_loss_share"], blend_loss_over_last_value_loss=t["blend_vs_lv"],
                share_of_cells_with_truth_above_q90=t["share_above_q90"], share_of_one_day_abs_log_change=round(e.get("abs_dlog_share", 0), 3),
                reverts=reverts, visible_in_panel_at_origin=visible, top_series_by_blend_loss_share=S[mode], dated_examples=examples, notes=extra, scope=COMMON)
modes = [
 entry(1, "composition_entry_exit", "Provider enters or leaves the panel (composition)",
  "The median moves because one provider's offer(s) appear or disappear near the middle of a 3-17 offer panel, with no surviving offer repriced.",
  "Weakly. Exited offers came back within 7 days in 5.6% of 162 fastgpu exits and 0% of 118 gpurentalprices exits. Regressing the next change on the jump: slope -0.01 (h=1), -0.24 [90% CI -0.27,-0.04] (h=3), -0.16 [-0.30,-0.14] (h=7), n=56-60; only 5% of jumps fully undo within 7 days.",
  "Size yes, timing no. The jump equals the one-offer 'fragility' of the origin panel (largest median change from dropping one offer): correlation 0.88, median ratio 1.00, n=60. The new value is an origin order statistic or midpoint (k=1) in 79% of h=1 and 54% of h=7 composition moves. Timing is not foreseeable from fragility: median fragility on composition days 0.047 vs 0.074 on all days. Events cluster: 60 events on 19 dates; one provider changes its listings across 4-7 series on one day (modal 2026-10-02 and 10-04, daytona 2026-09-29, quantacloud 2026-10-06, nebius 2026-10-05).",
  X["composition_entry_exit"],
  "Kinds (one-day, n=60): entry 35, exit 20, sku relabel 5 (same provider exits and re-enters under new sku_raw; 0.82 of 2.83 total abs log change from composition). 10% of one-day changes but 28% of their abs log change. Misses split evenly by side (40% of cells above q90; 14.6% of total blend loss from below-q10 composition misses). Largest single series: gpurentalprices A100_40GB, 2026-10-03, lambdalabs listings 1->5 offers, median 1.294->1.990, 5.2% of all blend loss."),
 entry(2, "mixed_reprice_plus_entry_exit", "Repricing and entry/exit in the same window (mixed)",
  "Within the horizon both a surviving offer is repriced and offers enter or leave, each carrying >20% of the median's move; mostly B200/B300 rate cards in the late-September/early-October repricing wave.",
  "No evidence of reversion (one-day mixed events n=23, slope +0.30 [0.03,0.38] at h=1; h=7 interval [-0.45,1.74], n=18).",
  "Partly: the repricing part is the Verda/Nebius/fal upward wave already under way at the origin; the entry/exit part (modal exit 2026-10-02, together entry) is not.",
  X["mixed_reprice_plus_entry_exit"],
  "54% of mixed cells have truth above q90. Worst cells: fastgpu B300 origin 2026-09-30/10-01, last value 7.625, truth 9.06-9.15 against q90 7.79-7.92 (nebius, fal, verda up; modal out; together in). Small n; one episode dominates."),
 entry(3, "repricing_verda_staircase", "Verda small upward reprices accumulating (repricing)",
  "Provider verda raises a posted rate by about 1% (median one-day move of the median 0.5%), many days in a row, on up to 17 fastgpu and 10 gpurentalprices series; when verda is the median or adjacent, the median climbs in small steps.",
  "No. Verda reprices return to the previous price within 7 days 1.1% (fastgpu, n=352) and 0.5% (gpurentalprices, n=219); 96.8% of median-moving verda events are up. fastgpu repricing events show momentum: slope +0.18 [0.02,0.30] at h=1, +0.40 [0.19,0.77] at h=3 (n=134, 124).",
  "Yes. 97.6% of the 247 median-moving verda events were preceded by another verda reprice in the same collector within 7 days; verda repriced something on 75% of fastgpu days and 35% of gpurentalprices days.",
  ["2026-09-12..09-14 origins, fastgpu B300 rate card: last value 7.50-7.575, all blend quantiles at the last value, truth 7.85 at h=7 after verda reprices up (loss 0.175 per cell).", X["repricing_verda_staircase"][0]],
  "Verda does 84% of fastgpu reprices on 13.8% of its offer-days and 39% of gpurentalprices reprices on 12.4%. Loss is mostly h=7 (0.110 of 0.175). The blend often has zero width here (q10=q50=q90=last value)."),
 entry(4, "repricing_sfcompute_marketplace_ask", "sfcompute marketplace ask swings (repricing)",
  "On gpurentalprices H100_80GB marketplace_ask (3 offers), the sfcompute ask is the median and moves by a median 5.6% per change; together with spheron it produces the largest one-day swings.",
  "Partly. gpurentalprices repricing events revert: slope -0.33 [-0.58,-0.01] at h=1 and -0.46 [-0.69,-0.19] at h=7 (n=292, 256). spheron's reprices return to the previous price within 7 days 66% of the time (n=41); sfcompute's 6% (n=48).",
  "Volatility yes (sfcompute repriced on 48 of ~70 days), direction no.",
  X["repricing_sfcompute_marketplace_ask"],
  "One series; 32% of one-day abs log change in the set but 8.9% of blend loss, because the blend is already wide here (blend/last-value loss 0.63; only 12% of cells above q90)."),
 entry(5, "repricing_hyperscaler_spot", "Hyperscaler spot repricing (gcp, aws)",
  "Spot prices of surviving hyperscaler offers change (afhubbard ~450 offers per series-day, fastgpu 3 offers); gcp and aws do 63% and 35% of afhubbard reprices.",
  "afhubbard repricing slope ~0 at h=1 and h=3 (-0.003, -0.011, n=51, 48), -0.33 [-0.54,-0.14] at h=7 (n=44).",
  "Partly: afhubbard's new median is an origin order statistic in 67% of h=1 moves (n=42) because the panel is dense.",
  X["repricing_hyperscaler_spot"],
  "Per-offer daily reprice chance 0.20 on afhubbard (n=124k offer-days), strongly clustered by provider and day (given one offer of a provider repriced that day, 89% of its others did too)."),
 entry(6, "repricing_other_provider", "Other single-provider reprices (spheron, nebius, quantacloud, ...)",
  "A surviving offer of a provider other than verda, sfcompute or scaleway is repriced and is pivotal for the median.",
  "Mixed: spheron 66% back within 7 days; nebius/fal moves in the October wave persist.",
  "No.", X["repricing_other_provider"], "56% of cells above q90; B300 rate cards top."),
 entry(7, "repricing_scaleway_small_drift", "Scaleway sub-percent drift",
  "scaleway's posted USD rates move by a median 0.2% per change (230 reprices, 5 series), consistent with currency conversion; it moves the median when scaleway is the middle offer (L4, H100_80GB, B300 on gpurentalprices).",
  "No (2.2% back to previous price within 7 days).", "Yes, it is continuous small drift.",
  X["repricing_scaleway_small_drift"], "120 one-day events but only 1.6% of abs log change and 1.7% of blend loss. Not worth modelling."),
]
json.dump(dict(description="Ranked failure modes of the dev blend, by physical cause of the move in the posted-offer median. Each entry stands alone.",
               modes=modes), open("experiments/autopsy/results/failure_modes.json", "w"), indent=1)
print(sum(m["share_of_blend_loss"] for m in modes))
