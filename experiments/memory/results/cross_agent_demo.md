# Cross-agent use of the shared memory (live output)

Every block below is the unedited stdout of `python -m gpuf.memory ...` against past.dev, or a table computed from it.

## (a) `scout` reads what `autopsy` wrote

`python -m gpuf.memory recall --as scout "big median moves caused by one provider repricing or entering the panel, with no news explanation yet" --top 40` returned 36 sources; authors: ['autopsy'].

```json
{
 "identity": "scout",
 "query": "big median moves caused by one provider repricing or entering the panel, with no news explanation yet",
 "as_of": null,
 "offline": false,
 "count": 36,
 "pending": null,
 "results": [
  {
   "rank": 1,
   "source_id": "autopsy-mode-composition_entry_exit",
   "author": "autopsy",
   "occurred_at": "2026-10-13T23:59:59Z",
   "label": "Failure mode: Provider enters or leaves the panel (composition)",
   "kind": "source",
   "excerpt": "Autopsy failure mode 1: Provider enters or leaves the panel (composition) (written by autopsy)\nid: composition_entry_exit\ndefinition: The median moves because one provider's offer(s) appear or disappear near the middle of a 3-17 offer panel, with no surviving offer repriced.\nn_blend_cells: 331\nn_one_day_events: 60\nshare_of_blend_loss: 0.321\nshare_of_blend_loss_from_cells_outside_q10_q90: 0.301\nshare_of_last_value_loss: 0.299\nblend_loss_over_last_value_loss: 0.879\nshare_of_cells_with_truth_above_"
  },
  {
   "rank": 2,
   "source_id": "autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-06",
   "author": "autopsy",
   "occurred_at": "2026-08-06T23:59:59Z",
   "label": "Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median",
   "kind": "source",
   "excerpt": "Autopsy event 2026-08-06 on series gpurentalprices.marketplace_ask.H100_80GB.spot.median (written by autopsy)\nSeries: gpurentalprices.marketplace_ask.H100_80GB.spot.median\nDate of the move: 2026-08-05 -> 2026-08-06\nMedian: 1.46 -> 2.1 USD per GPU-hour (log change +0.3635, +43.8%)\nCause: repricing (repricing part +0.3635, composition part +0.0000; Shapley cause repricing)\nPivotal provider: spheron\nProviders that raised: spheron\nProviders that cut: sfcompute\nProviders that entered the panel: none\n"
  },
  {
   "rank": 3,
   "source_id": "autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-21",
   "author": "autopsy",
   "occurred_at": "2026-09-21T23:59:59Z",
   "label": "Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median",
   "kind": "source",
   "excerpt": "Autopsy event 2026-09-21 on series gpurentalprices.marketplace_ask.H100_80GB.spot.median (written by autopsy)\nSeries: gpurentalprices.marketplace_ask.H100_80GB.spot.median\nDate of the move: 2026-09-20 -> 2026-09-21\nMedian: 1.5 -> 1.8704105073255506 USD per GPU-hour (log change +0.2207, +24.7%)\nCause: repricing (repricing part +0.2207, composition part +0.0000; Shapley cause repricing)\nPivotal provider: sfcompute\nProviders that raised: sfcompute\nProviders that cut: none\nProviders that entered the"
  }
 ]
}
```
(first 3 of the rows shown)

Autopsy cases returned, and what scout should search next (an autopsy event whose provider has no scout evidence in memory):

| autopsy source id | date | provider | scout evidence for provider in memory? | search next |
|---|---|---|---|---|
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-06` | 2026-08-06 | spheron | no | Exa: spheron price change news 2026-08-06 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-21` | 2026-09-21 | sfcompute | no | Exa: sfcompute price change news 2026-09-21 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-21` | 2026-08-21 | sfcompute | no | Exa: sfcompute price change news 2026-08-21 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-15` | 2026-09-15 | sfcompute | no | Exa: sfcompute price change news 2026-09-15 |
| `autopsy-fastgpu_daily.neocloud_rate_card.B200.on_demand.median-2026-10-03` | 2026-10-03 | together,verda | no | Exa: together,verda price change news 2026-10-03 |
| `autopsy-afhubbard.hyperscaler_spot.V100.spot.median-2026-05-07` | 2026-05-07 | gcp | no | Exa: gcp price change news 2026-05-07 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-10` | 2026-09-10 | sfcompute | no | Exa: sfcompute price change news 2026-09-10 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-10-06` | 2026-10-06 | (case, no single provider) | n/a | see text of record |
| `autopsy-afhubbard.hyperscaler_spot.V100.spot.median-2026-09-29` | 2026-09-29 | oci,gcp | no | Exa: oci,gcp price change news 2026-09-29 |
| `autopsy-fastgpu_daily.neocloud_rate_card.B200.on_demand.median-2026-10-02` | 2026-10-02 | fal,modal | no | Exa: fal,modal price change news 2026-10-02 |
| `autopsy-fastgpu_daily.neocloud_rate_card.B300.on_demand.median-2026-10-02` | 2026-10-02 | nebius,modal | no | Exa: nebius,modal price change news 2026-10-02 |
| `autopsy-fastgpu_daily.neocloud_rate_card.A100_40GB.on_demand.median-2026-10-12` | 2026-10-12 | northflank | no | Exa: northflank price change news 2026-10-12 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-07` | 2026-09-07 | sfcompute | no | Exa: sfcompute price change news 2026-09-07 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-09` | 2026-09-09 | sfcompute | no | Exa: sfcompute price change news 2026-09-09 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-22` | 2026-08-22 | sfcompute | no | Exa: sfcompute price change news 2026-08-22 |
| `autopsy-afhubbard.hyperscaler_spot.V100.spot.median-2026-01-13` | 2026-01-13 | gcp | no | Exa: gcp price change news 2026-01-13 |
| `autopsy-gpurentalprices.neocloud_rate_card.H100_80GB.on_demand.median-2026-10-04` | 2026-10-04 | daytona | no | Exa: daytona price change news 2026-10-04 |
| `autopsy-gpurentalprices.neocloud_rate_card.B300.on_demand.median-2026-10-03` | 2026-10-03 | together,digitalocean,verda | no | Exa: together,digitalocean,verda price change news 2026-10-03 |
| `autopsy-gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand.median-2026-10-03` | 2026-10-03 | lambdalabs | no | Exa: lambdalabs price change news 2026-10-03 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-05` | 2026-08-05 | spheron | no | Exa: spheron price change news 2026-08-05 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-19` | 2026-08-19 | sfcompute | no | Exa: sfcompute price change news 2026-08-19 |
| `autopsy-fastgpu_daily.hyperscaler_spot.T4.spot.median-2026-09-22` | 2026-09-22 | aws | no | Exa: aws price change news 2026-09-22 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-17` | 2026-08-17 | sfcompute | no | Exa: sfcompute price change news 2026-08-17 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-07` | 2026-08-07 | sfcompute | no | Exa: sfcompute price change news 2026-08-07 |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-13` | 2026-08-13 | sfcompute | no | Exa: sfcompute price change news 2026-08-13 |
| `autopsy-fastgpu_daily.neocloud_spot.RTX_PRO_6000.spot.median-2026-10-05` | 2026-10-05 | (case, no single provider) | n/a | see text of record |
| `autopsy-gpurentalprices.neocloud_rate_card.RTX_PRO_6000.on_demand.median-2026-10-04` | 2026-10-04 | jarvislabs,daytona,verda | no | Exa: jarvislabs,daytona,verda price change news 2026-10-04 |
| `autopsy-afhubbard.hyperscaler_spot.A100_40GB.spot.median-2026-01-13` | 2026-01-13 | gcp | no | Exa: gcp price change news 2026-01-13 |
| `autopsy-fastgpu_daily.hyperscaler_spot.T4.spot.median-2026-09-30` | 2026-09-30 | aws | no | Exa: aws price change news 2026-09-30 |
| `autopsy-fastgpu_daily.neocloud_rate_card.A100_80GB.on_demand.median-2026-10-05` | 2026-10-05 | (case, no single provider) | n/a | see text of record |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-14` | 2026-08-14 | sfcompute | no | Exa: sfcompute price change news 2026-08-14 |

## (b) `proposer` briefs itself

`python -m gpuf.memory brief --as proposer "upper tail under-covered at 7 days" --top 4`, briefing text:

```
BRIEFING for proposer on: upper tail under-covered at 7 days

## Refuted or not significant hypotheses (do not re-test blindly)
- [exp-H10] by experimenter, 2026-11-14: Experiment: H10 (not_significant) | Claim: A burst of dated price-increase headlines (Exa, one published day per search) precedes upward jumps. | Prediction: +0.005 to +0.02 pooled skill at h=7. | Result: g=0.5: +0.0096 against the base, 90% CI [-0.004,+0.015]; 13 origins helped, 21 hurt; nearly all gain from 5 origins in one episode (dev headline, 4,278 cells).
- [exp-H7b] by experimenter, 2026-11-14: Experiment: H7b (refuted) | Claim: The share of a collector's series that changed recently predicts how far each series moves next. | Prediction: +0.005 to +0.02 pooled skill. | Result: Every variant at or below the base mix (dev headline, 4,278 cells).
- [exp-H14] by experimenter, 2026-11-14: Experiment: H14 (refuted) | Claim: The upper-tail gap at h=7 is a stable miscalibration that online recalibration fixes. | Prediction: not recorded | Result: The upper-tail gap at h=7 is one multi-week regime, not a stable bias: above-q90 rate 0.110 in the first half of dev and 0.330 in the second (weekly 0.13, 0.02, 0.08, 0.24, 0.38, 0.38, 0.29, 0.08; lag-1 autocorrelation of the daily rate 0.93). Conformal q90 correction on mix: +0.023 [+0.008,+0.031] overall but -0.006 in the first half and +0.030 in the second; on the three-mix ensemble +0.008 [-0.003,+0.014]. Adaptive conformal inference loses (-0.017 to -0.025). Lower-tail correction adds nothing. Not nominated.
- [exp-H26] by experimenter, 2026-11-14: experimenter: The policy-label result was refuted: as a prior under 14 days of history, constant zero beat both the label and the pooled rate (outcome).

## Failure modes and dated failure cases of the median forecast
- [autopsy-all-2026-10-04] by autopsy, 2026-10-04: Autopsy: all series, busiest day | 6 of 37 series moved more than 5% on 2026-10-04. Days with 5 or more big moves: 2026-10-02 (5), 2026-10-03 (5), 2026-10-04 (6), 2026-10-06 (5) (runs/failure/events.txt). | The 5 busiest days carry 34.8% of big moves.
- [autopsy-mode-repricing_verda_staircase] by autopsy, 2026-10-13: Failure mode: Verda small upward reprices accumulating (repricing) | definition: Provider verda raises a posted rate by about 1% (median one-day move of the median 0.5%), many days in a row, on up to 17 fastgpu and 10 gpurentalprices series; when verda is the median or adjacent, the median climbs in small steps. | share_of_blend_loss: 0.175 | share_of_last_value_loss: 0.203
- [autopsy-mode-mixed_reprice_plus_entry_exit] by autopsy, 2026-10-13: autopsy: mixed one-day events reversion interval h=7 upper bound: 1.74.
- [autopsy-mode-composition_entry_exit] by autopsy, 2026-10-13: Failure mode: Provider enters or leaves the panel (composition) | definition: The median moves because one provider's offer(s) appear or disappear near the middle of a 3-17 offer panel, with no surviving offer repriced. | share_of_blend_loss: 0.321 | share_of_last_value_loss: 0.299

## Dated web evidence
(nothing found)
```

| section | source id | author | occurred |
|---|---|---|---|
| refuted | `exp-H10` | experimenter | 2026-11-14T19:49:16Z |
| refuted | `exp-H7b` | experimenter | 2026-11-14T19:49:16Z |
| refuted | `exp-H14` | experimenter | 2026-11-14T20:19:17Z |
| refuted | `exp-H26` | experimenter | 2026-11-14T20:19:17Z |
| failures | `autopsy-all-2026-10-04` | autopsy | 2026-10-04T23:59:59Z |
| failures | `autopsy-mode-repricing_verda_staircase` | autopsy | 2026-10-13T23:59:59Z |
| failures | `autopsy-mode-mixed_reprice_plus_entry_exit` | autopsy | 2026-10-13T23:59:59Z |
| failures | `autopsy-mode-composition_entry_exit` | autopsy | 2026-10-13T23:59:59Z |

Check: refuted section authors {'experimenter'}, failures {'autopsy'}, evidence set(). Contains autopsy failure modes, scout evidence and experimenter hypotheses: False.

## (c) `forecaster` at forecast origin 2026-10-06

`python -m gpuf.memory recall --as forecaster --as-of 2026-10-06 "announced price increases effective soon" --top 10`

| rank | source id | author | occurred | label |
|---|---|---|---|---|
| 1 | `scout-03849b87` | scout | 2026-09-16T07:00:00Z | Evidence: thefivenines.com |
| 2 | `scout-228cdc44` | scout | 2026-09-17T16:12:34Z | Evidence: reuters.com |
| 3 | `scout-3d7d1259` | scout | 2026-09-01T23:29:16Z | Evidence: blog.salad.com |
| 5 | `scout-7a73cd32` | scout | 2026-10-04T23:59:59Z | Evidence: usagepricing.com |
| 7 | `scout-12d5cf4c` | scout | 2026-09-02T23:59:59Z | Evidence: linkedin.com |
| 12 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-06` | autopsy | 2026-08-06T23:59:59Z | Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median |
| 16 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-13` | autopsy | 2026-08-13T23:59:59Z | Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median |
| 17 | `autopsy-afhubbard.hyperscaler_spot.A100_40GB.spot.median-2026-01-13` | autopsy | 2026-01-13T23:59:59Z | Autopsy: afhubbard.hyperscaler_spot.A100_40GB.spot.median |
| 18 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-16` | autopsy | 2026-08-16T23:59:59Z | Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median |
| 19 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-14` | autopsy | 2026-08-14T23:59:59Z | Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median |

Anything dated after 2026-10-06: none. Evidence rows returned: scout-03849b87, scout-228cdc44, scout-3d7d1259, scout-7a73cd32, scout-12d5cf4c.

Same question at as-of 2026-10-31 (for contrast; the askgpu Nebius page, timed 2026-10-18, may now appear):

| rank | source id | author | occurred |
|---|---|---|---|
| 1 | `scout-03849b87` | scout | 2026-09-16T07:00:00Z |
| 2 | `scout-228cdc44` | scout | 2026-09-17T16:12:34Z |
| 3 | `scout-3d7d1259` | scout | 2026-09-01T23:29:16Z |
| 5 | `scout-7a73cd32` | scout | 2026-10-04T23:59:59Z |
| 7 | `scout-12d5cf4c` | scout | 2026-09-02T23:59:59Z |
| 12 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-06` | autopsy | 2026-08-06T23:59:59Z |
| 16 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-16` | autopsy | 2026-08-16T23:59:59Z |
| 17 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-14` | autopsy | 2026-08-14T23:59:59Z |
| 19 | `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-17` | autopsy | 2026-08-17T23:59:59Z |
| 20 | `scout-c520a7d6` | scout | 2026-09-01T10:35:30Z |

The page `scout-f4c32699` (askgpu, Nebius, timed 2026-10-18) is see tables.
