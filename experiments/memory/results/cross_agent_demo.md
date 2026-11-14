# Cross-agent use of the shared memory (live output)

Every block below is the unedited stdout of `python -m gpuf.memory ...` against past.dev, or a table computed from it.

## (a) `scout` reads what `autopsy` wrote

`python -m gpuf.memory recall --as scout "Autopsy event: one-day move of the median caused by a provider repricing or entering the panel, pivotal provider" --top 40` returned 40 sources; authors: ['autopsy']. First 2 rows:

```json
[
 {
  "rank": 1,
  "source_id": "autopsy-fastgpu_daily.neocloud_rate_card.A100_40GB.on_demand.median-2026-10-12",
  "author": "autopsy",
  "occurred_at": "2026-10-12T23:59:59Z",
  "label": "Autopsy: fastgpu_daily.neocloud_rate_card.A100_40GB.on_demand.median",
  "kind": "source",
  "excerpt": "Autopsy event 2026-10-12 on series fastgpu_daily.neocloud_rate_card.A100_40GB.on_demand.median (written by autopsy)\nSeries: fastgpu_daily.neocloud_rate_card.A100_40GB.on_demand.median\nDate of the move: 2026-10-11 -> 2026-10-12\nMedian: 1.6815 -> 1.42 USD per GPU-hour (log change -0.1690, -15.6%)\nCause: composition (repricing part +0.0080, composition part -0.1770; Shapley cause composition)\nPivotal provider: northflank\nProviders that raised: verda\nProviders that cut: none\nProviders that entered t"
 },
 {
  "rank": 2,
  "source_id": "autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-15",
  "author": "autopsy",
  "occurred_at": "2026-09-15T23:59:59Z",
  "label": "Autopsy: gpurentalprices.marketplace_ask.H100_80GB.spot.median",
  "kind": "source",
  "excerpt": "Autopsy event 2026-09-15 on series gpurentalprices.marketplace_ask.H100_80GB.spot.median (written by autopsy)\nSeries: gpurentalprices.marketplace_ask.H100_80GB.spot.median\nDate of the move: 2026-09-14 -> 2026-09-15\nMedian: 1.6105072032035928 -> 1.8325934108634239 USD per GPU-hour (log change +0.1292, +13.8%)\nCause: repricing (repricing part +0.1292, composition part +0.0000; Shapley cause repricing)\nPivotal provider: sfcompute\nProviders that raised: sfcompute\nProviders that cut: spheron\nProvider"
 }
]
```

`python -m gpuf.memory recall --as scout "Web evidence: provider announced GPU price increase, quoted sentence, URL" --top 40` returned 10 scout evidence sources already in memory: `scout-03849b87` (thefivenines.com, 2026-09-16), `scout-c520a7d6` (theweightedaverage.com, 2026-09-01), `scout-f4c32699` (askgpu.com, 2026-10-18), `scout-7a73cd32` (usagepricing.com, 2026-10-04), `scout-228cdc44` (reuters.com, 2026-09-17), `scout-12d5cf4c` (linkedin.com, 2026-09-02), `scout-3d7d1259` (blog.salad.com, 2026-09-01), `scout-c73fc813` (prweb.com, 2024-08-02), `scout-0c8538d1` (jarvislabs.ai, 2026-09-24), `scout-f319e5f7` (pricingsaas.com, 2026-10-01).

Autopsy events returned, with whether scout evidence for the provider exists within 45 days before the move (or 14 days after):

| autopsy source id | date | pivotal / involved providers | scout evidence in memory | search next |
|---|---|---|---|---|
| `autopsy-fastgpu_daily.neocloud_rate_card.A100_40GB.on_demand.median-2026-10-12` | 2026-10-12 | northflank | none | Exa: `northflank price change 2026-10-12` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-15` | 2026-09-15 | sfcompute | none | Exa: `sfcompute price change 2026-09-15` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-21` | 2026-09-21 | sfcompute | none | Exa: `sfcompute price change 2026-09-21` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-16` | 2026-08-16 | sfcompute | none | Exa: `sfcompute price change 2026-08-16` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-10` | 2026-09-10 | sfcompute | none | Exa: `sfcompute price change 2026-09-10` |
| `autopsy-gpurentalprices.neocloud_rate_card.H100_80GB.on_demand.median-2026-10-04` | 2026-10-04 | daytona | none | Exa: `daytona price change 2026-10-04` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-10-06` | 2026-10-06 | spheron | none | Exa: `spheron price change 2026-10-06` |
| `autopsy-afhubbard.hyperscaler_spot.V100.spot.median-2026-09-29` | 2026-09-29 | oci, gcp | none | Exa: `oci, gcp price change 2026-09-29` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-31` | 2026-08-31 | sfcompute | none | Exa: `sfcompute price change 2026-08-31` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-05` | 2026-08-05 | spheron | none | Exa: `spheron price change 2026-08-05` |
| `autopsy-fastgpu_daily.neocloud_spot.RTX_PRO_6000.spot.median-2026-09-29` | 2026-09-29 | daytona | none | Exa: `daytona price change 2026-09-29` |
| `autopsy-fastgpu_daily.neocloud_rate_card.B200.on_demand.median-2026-10-02` | 2026-10-02 | fal, modal | fal: scout-7a73cd32 | Exa: `modal price change 2026-10-02` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-19` | 2026-08-19 | sfcompute | none | Exa: `sfcompute price change 2026-08-19` |
| `autopsy-gpurentalprices.neocloud_rate_card.RTX_PRO_6000.on_demand.median-2026-10-04` | 2026-10-04 | jarvislabs, daytona, verda | jarvislabs: scout-0c8538d1 | Exa: `daytona, verda price change 2026-10-04` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-22` | 2026-08-22 | sfcompute | none | Exa: `sfcompute price change 2026-08-22` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-06` | 2026-08-06 | spheron | none | Exa: `spheron price change 2026-08-06` |
| `autopsy-fastgpu_daily.neocloud_rate_card.B300.on_demand.median-2026-10-02` | 2026-10-02 | nebius, modal | nebius: scout-03849b87 | Exa: `modal price change 2026-10-02` |
| `autopsy-fastgpu_daily.neocloud_rate_card.A100_40GB.on_demand.median-2026-10-04` | 2026-10-04 | modal | none | Exa: `modal price change 2026-10-04` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-07` | 2026-09-07 | sfcompute | none | Exa: `sfcompute price change 2026-09-07` |
| `autopsy-fastgpu_daily.neocloud_rate_card.B200.on_demand.median-2026-10-03` | 2026-10-03 | together, verda | none | Exa: `together, verda price change 2026-10-03` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-07` | 2026-08-07 | sfcompute | none | Exa: `sfcompute price change 2026-08-07` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-09-09` | 2026-09-09 | sfcompute | none | Exa: `sfcompute price change 2026-09-09` |
| `autopsy-fastgpu_daily.neocloud_spot.RTX_PRO_6000.spot.median-2026-10-05` | 2026-10-05 | nebius | nebius: scout-03849b87 | - |
| `autopsy-fastgpu_daily.neocloud_rate_card.RTX_PRO_6000.on_demand.median-2026-09-29` | 2026-09-29 | daytona | none | Exa: `daytona price change 2026-09-29` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-13` | 2026-08-13 | sfcompute | none | Exa: `sfcompute price change 2026-08-13` |
| `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot.median-2026-08-14` | 2026-08-14 | sfcompute | none | Exa: `sfcompute price change 2026-08-14` |
| `autopsy-fastgpu_daily.neocloud_rate_card.A100_80GB.on_demand.median-2026-10-05` | 2026-10-05 | cudo | none | Exa: `cudo price change 2026-10-05` |
| `autopsy-fastgpu_daily.hyperscaler_spot.T4.spot.median-2026-09-22` | 2026-09-22 | aws | none | Exa: `aws price change 2026-09-22` |
| `autopsy-fastgpu_daily.hyperscaler_spot.T4.spot.median-2026-09-30` | 2026-09-30 | aws | none | Exa: `aws price change 2026-09-30` |
| `autopsy-fastgpu_daily.neocloud_rate_card.A100_80GB.on_demand.median-2026-10-06` | 2026-10-06 | quantacloud | none | Exa: `quantacloud price change 2026-10-06` |
| `autopsy-afhubbard.hyperscaler_spot.A100_40GB.spot.median-2026-01-13` | 2026-01-13 | gcp | none | Exa: `gcp price change 2026-01-13` |
| `autopsy-afhubbard.hyperscaler_spot.V100.spot.median-2026-01-13` | 2026-01-13 | gcp | none | Exa: `gcp price change 2026-01-13` |
| `autopsy-afhubbard.hyperscaler_spot.A100_40GB.spot.median-2026-08-03` | 2026-08-03 | gcp | none | Exa: `gcp price change 2026-08-03` |

Next searches for scout (distinct provider, first date): aws 2026-09-22; cudo 2026-10-05; daytona 2026-09-29; gcp 2026-01-13; modal 2026-10-02; northflank 2026-10-12; oci 2026-09-29; quantacloud 2026-10-06; sfcompute 2026-08-07; spheron 2026-08-05; together 2026-10-03; verda 2026-10-03.

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
- [scout-03849b87] by scout, 2026-09-16: Evidence: thefivenines.com | URL: https://www.thefivenines.com/data-ai/nebius-raises-gpu-prices-20-as-supply-tightens | Quoted sentence: "BigGo Finance reported that Nebius said it will raise GPU cloud prices by an average of 20 percent from October 1, covering H100, H200, B200 and B300 chips, with B300 rising from $7.85 to $9.50 per GPU-hour." | Explains: nebius B300 repricing seen in the data on 2026-10-01 (attribution label ANNOUNCED_BEFORE, lead 15 days). Customer pricing notice, relayed by Bloomberg and Reuters. Exa's publishedDate for each page is its own article date; the Nebius price page itself is undated in Exa.
- [scout-c520a7d6] by scout, 2026-09-01: Evidence: theweightedaverage.com | URL: https://theweightedaverage.com/notes/2026-09-01-fireworks-gpu-rate-increase/ | Quoted sentence: "Fireworks’ current on-demand price table raises H100/H200 from $7 to $8 per GPU-hour, B200 from $10 to $13, B300 from $12 to $15, and GB300 from $18 to $20 starting September 1—an 11%–30% increase." | Explains: Fireworks on-demand GPU rate increase effective 2026-09-01.
- [scout-0c8538d1] by scout, 2026-09-24: Evidence: jarvislabs.ai | URL: https://jarvislabs.ai/updates/gpu-pricing-october-2026 | Quoted sentence: "From October 5, 2026 at 00:00 IST, new rates apply to NVIDIA H200, H100 and RTX PRO 6000 GPUs. | NVIDIA RTX PRO 6000 | $1.89/hr | $2.19/hr" | Explains: jarvislabs RTX PRO 6000 repricing seen in the data on 2026-10-04 (attribution label ANNOUNCED_BEFORE, lead 10 days). Provider's own changelog page. 00:00 IST on Oct 5 is 18:30 UTC on Oct 4, which is the day the series shows the move.
- [scout-f4c32699] by scout, 2026-10-18: Evidence: askgpu.com | URL: https://askgpu.com/updates/nebius-raises-on-demand-gpu-prices/ | Quoted sentence: "From October 1, 2026, a Nebius H100 costs $4.50 per GPU-hour on demand instead of $3.85, and a B300 $9.50 instead of $7.85." | Explains: Nebius on-demand repricing effective 2026-10-01. Exa's published date is 2026-10-01 but the page text says "Published Oct 18, 2026", so it is timed 2026-10-18.
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
| evidence | `scout-03849b87` | scout | 2026-09-16T07:00:00Z |
| evidence | `scout-c520a7d6` | scout | 2026-09-01T10:35:30Z |
| evidence | `scout-0c8538d1` | scout | 2026-09-24T16:33:04Z |
| evidence | `scout-f4c32699` | scout | 2026-10-18T23:59:59Z |

Check: refuted section authors {'experimenter'}, failures {'autopsy'}, evidence {'scout'}. Contains autopsy failure modes, scout evidence and experimenter hypotheses: True.

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
