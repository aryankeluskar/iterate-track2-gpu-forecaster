# Failure attribution with Exa: were provider repricings announced before they showed up in the price data?

Dev rows only (<= 2026-10-13); every search had endPublishedDate <= 2026-11-06. BEFORE = D-21..D-1, AFTER = D..min(D+14, 11-06). Size = how far the series median moved that day (log). Loss weight = |median move| x the series' share of dev last-value loss (merged duplicates summed).

## Headline

```json
{
 "n_events": 37,
 "n_announced_before": 2,
 "share_events_announced": 0.054,
 "share_loss_announced_of_selected": 0.013,
 "selected_cover_of_all_event_score": 0.218,
 "lower_bound_share_of_all_event_score": 0.003,
 "n_reported_after": 1,
 "n_no_trace": 34,
 "rate_card_events": 12,
 "rate_card_announced": 2,
 "rate_card_share_loss_announced": 0.109,
 "marketplace_events": 23,
 "median_lead_days": 12.5,
 "leads": [
  15.0,
  10.0
 ],
 "v2_fired_on_events": 21,
 "v2_true_among_fired": 2,
 "control_pairs": 10,
 "control_false_alarms_v2": 4,
 "control_false_alarm_rate": 0.4,
 "control_ci90": [
  0.19,
  0.65
 ],
 "control_fired_ids": [
  3,
  4,
  7,
  9
 ],
 "spend_usd": 1.564
}
```

## Events

| id | provider | GPU | date | price old>new | median move | label | lead (d) | source (published) | quoted sentence |
|---|---|---|---|---|---|---|---|---|---|
| 0 | spheron | H100 80GB | 2026-08-05 | 2.2>1.46 | -0.406 | NO_TRACE |  |  |  |
| 1 | spheron | H100 80GB | 2026-08-06 | 1.46>2.1 | +0.363 | NO_TRACE |  |  |  |
| 2 | sfcompute | H100 80GB | 2026-08-06 | 2.19>2.1 | +0.363 | NO_TRACE |  |  |  |
| 3 | sfcompute | H100 80GB | 2026-08-13 | 1.97>1.2 | -0.496 | NO_TRACE |  |  |  |
| 4 | sfcompute | H100 80GB | 2026-08-21 | 1.27>1.5 | +0.166 | NO_TRACE |  |  |  |
| 5 | spheron | H100 80GB | 2026-08-21 | 2.2>2.04 | +0.166 | NO_TRACE |  |  |  |
| 6 | sfcompute | H100 80GB | 2026-08-22 | 1.5>1.81 | +0.188 | NO_TRACE |  |  |  |
| 7 | spheron | H100 80GB | 2026-08-31 | 2.04>2.2 | -0.143 | NO_TRACE |  |  |  |
| 8 | sfcompute | H100 80GB | 2026-08-31 | 1.64>1.42 | -0.143 | NO_TRACE |  |  |  |
| 9 | spheron | H100 80GB | 2026-09-01 | 2.2>2.05 | +0.172 | NO_TRACE |  |  |  |
| 10 | sfcompute | H100 80GB | 2026-09-01 | 1.42>1.69 | +0.172 | NO_TRACE |  |  |  |
| 11 | sfcompute | H100 80GB | 2026-09-02 | 1.69>1.23 | -0.315 | NO_TRACE |  |  |  |
| 12 | spheron | H100 80GB | 2026-09-02 | 2.05>2.2 | -0.315 | NO_TRACE |  |  |  |
| 13 | sfcompute | H100 80GB | 2026-09-06 | 1.28>1.69 | +0.276 | NO_TRACE |  |  |  |
| 14 | sfcompute | H100 80GB | 2026-09-07 | 1.69>1.41 | -0.179 | NO_TRACE |  |  |  |
| 15 | sfcompute | H100 80GB | 2026-09-09 | 1.47>1.75 | +0.175 | NO_TRACE |  |  |  |
| 16 | spheron | H100 80GB | 2026-09-09 | 2.04>2.1 | +0.175 | NO_TRACE |  |  |  |
| 17 | verda | A100 40GB | 2026-09-13 | 1.29>1.25 | -0.012 | NO_TRACE |  |  |  |
| 18 | sfcompute | H100 80GB | 2026-09-15 | 1.61>1.83 | +0.129 | NO_TRACE |  |  |  |
| 19 | spheron | H100 80GB | 2026-09-18 | 2.07>2.13 | -0.191 | NO_TRACE |  |  |  |
| 20 | sfcompute | H100 80GB | 2026-09-18 | 1.82>1.5 | -0.191 | NO_TRACE |  |  |  |
| 21 | verda | B300 | 2026-09-19 | 7.65>7.88 | +0.026 | NO_TRACE |  |  |  |
| 22 | sfcompute | H100 80GB | 2026-09-19 | 1.5>1.72 | +0.135 | NO_TRACE |  |  |  |
| 23 | sfcompute | H100 80GB | 2026-09-20 | 1.72>1.5 | -0.135 | NO_TRACE |  |  |  |
| 24 | sfcompute | H100 80GB | 2026-09-21 | 1.5>1.87 | +0.221 | NO_TRACE |  |  |  |
| 25 | massedcompute | H100 SXM 80GB | 2026-09-30 | 2.89>3.14 | -0.054 | NO_TRACE |  |  |  |
| 26 | nebius | B300 | 2026-10-01 | 7.85>9.5 | +0.061 | ANNOUNCED_BEFORE | 15 | [Nebius raises GPU prices 20% as supply tightens | ](https://www.thefivenines.com/data-ai/nebius-raises-gpu-prices-20-as-supply-tightens) (2026-09-16) | BigGo Finance reported that Nebius said it will raise GPU cloud prices by an average of 20 percent from October 1, covering H100, H200, B200 and B300 chips, with B300 rising from $7.85 to $9.50 per GPU-hour. |
| 27 | fal | B300 | 2026-10-02 | 8.5>13 | +0.133 | REPORTED_AFTER |  | [Fal price change: fal reprices GPU fleet upward an](https://www.usagepricing.com/blueprint/activity/fal-ai-2026-10-04-gpu-fleet-repricing) (2026-10-01) | Every negotiated "as low as" floor rose, by 32% (H100) to 81% (RTX PRO 6000), and every list price rose except the H100's, which had already gone up in August. |
| 28 | lambdalabs | H100 SXM 80GB | 2026-10-03 | 3.99>4.14 | +0.129 | NO_TRACE |  |  |  |
| 29 | jarvislabs | RTX PRO 6000 | 2026-10-04 | 1.89>2.19 | +0.069 | ANNOUNCED_BEFORE | 10 | [New GPU rates from October 5, 2026 | Jarvislabs Up](https://jarvislabs.ai/updates/gpu-pricing-october-2026) (2026-09-24) | From October 5, 2026 at 00:00 IST, new rates apply to NVIDIA H200, H100 and RTX PRO 6000 GPUs. / NVIDIA RTX PRO 6000 / $1.89/hr / $2.19/hr |
| 30 | spheron | H100 80GB | 2026-10-06 | 2.2>2.43 | +0.071 | NO_TRACE |  |  |  |
| 31 | spheron | H100 80GB | 2026-10-07 | 2.43>2.2 | -0.071 | NO_TRACE |  |  |  |
| 32 | gmi | B200 | 2026-10-08 | 4>5 | +0.010 | NO_TRACE |  |  |  |
| 33 | quantacloud | H100 PCIe 80GB | 2026-10-09 | 2.59>2.69 | +0.038 | NO_TRACE |  |  |  |
| 34 | quantacloud | H100 PCIe 80GB | 2026-10-11 | 2.69>2.59 | -0.038 | NO_TRACE |  |  |  |
| 35 | verda | H100 SXM 80GB | 2026-10-11 | 3.93>4.01 | +0.008 | NO_TRACE |  |  |  |
| 36 | verda | B200 | 2026-10-12 | 7.42>7.56 | -0.040 | NO_TRACE |  |  |  |

## Notes per labelled event

- **26 nebius B300 2026-10-01 (ANNOUNCED_BEFORE)**: Customer pricing notice, relayed by Bloomberg and Reuters. Exa's publishedDate for each page is its own article date; the Nebius price page itself is undated in Exa. 2026-09-17 Reuters: "Cloud provider Nebius said on Thursday it will raise pay-as-you-go prices for leasing selected Nvidia chips from October 1, marking the company's second price hike" https://www.reuters.com/technology/nebius-hikes-ai-cloud-prices-again-demand-computing-power-soars-2026-09-17/
- **27 fal B300 2026-10-02 (REPORTED_AFTER)**: Exa dates the page 2026-10-01, the URL slug says 2026-10-04 and the text lists the new B300 list price of $12.99/h that the data first shows on 10-02. It is a report of a change already made, not a notice. Another page (withorb.com, published 2026-09-18) contains text dated 'October 26, 2026', so Exa's published date does not bound the text. PricingSaaS Pulse (published 2026-10-01): "GPU rates were untouched as well." https://pricingsaas.com/news/article/fal-rebuilds-its-model-api-pricing-into-per-endpoint-table
- **29 jarvislabs RTX PRO 6000 2026-10-04 (ANNOUNCED_BEFORE)**: Provider's own changelog page. 00:00 IST on Oct 5 is 18:30 UTC on Oct 4, which is the day the series shows the move. 

## Control (10 provider-GPU-date pairs with no repricing in D-21..D+7)

| id | provider | GPU | date | rule v2 fired | hand check |
|---|---|---|---|---|---|
| 0 | lambdalabs | A100 SXM 80GB | 2026-09-26 | False |  |
| 1 | massedcompute | A100 SXM 80GB | 2026-09-25 | False |  |
| 2 | jarvislabs | RTX PRO 6000 | 2026-09-19 | False |  |
| 3 | jarvislabs | A100 40GB | 2026-10-03 | True | provider-wide hike announced for other GPUs (H200/H100/RTX PRO 6000 from Oct 5), not A100 40GB |
| 4 | lambdalabs | A100 80GB | 2026-09-30 | True | pricing-guide page, no change stated |
| 5 | gmi | H100 80GB | 2026-09-23 | False |  |
| 6 | fal | B200 | 2026-09-19 | False |  |
| 7 | nebius | RTX PRO 6000 | 2026-10-02 | True | Nebius Oct 1 hike covers H100-B300, not RTX PRO 6000 |
| 8 | massedcompute | RTX 6000 Ada | 2026-09-23 | False |  |
| 9 | nebius | L40S | 2026-09-14 | True | page published 09-10 whose text was updated 10-01; no change for L40S |
