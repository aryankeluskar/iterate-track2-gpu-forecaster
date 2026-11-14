# past.dev shared memory: plan for owner approval

Status: nothing has been sent to past.dev. The only call made was `GET /api/v1/usage` (key accepted; project `default-project`; 550,000 credits left). `gpuf.memory` refuses live writes and recalls until `PAST_ALLOW_WRITES=1`; offline mode (`PAST_OFFLINE=1`) is journal-only. API details and unknowns: [literature/pastdev-api.md](../../literature/pastdev-api.md).

## What I ask you to approve

1. Use the existing project `default-project` (the plan appears to allow one project; no project is created).
2. Create three audiences and five identities (below).
3. Send the 12 test records and run the 6 test recalls (about 30 to 45 credits of 550,000).

## Audiences (slugs)

| slug | kind | holds | members (fixed) |
|---|---|---|---|
| `gpuf-failures` | fixed | dated failure cases written by `autopsy` | autopsy, scout, experimenter, proposer, forecaster |
| `gpuf-evidence` | fixed | dated web evidence written by `scout` | autopsy, scout, experimenter, proposer, forecaster |
| `gpuf-experiments` | fixed | hypothesis tests written by `experimenter` | autopsy, experimenter, proposer |

No project-visible data points: every record names one audience. The forecaster is deliberately absent from `gpuf-experiments` (experiment records are timed at run time, after every forecast origin, and describe dev-period results).

## Identities (agents, no traits needed)

`autopsy` writes `gpuf-failures`; reads failures and evidence (to attach a cause to a move) and experiments (so it does not re-diagnose a refuted cause).
`scout` writes `gpuf-evidence`; reads `gpuf-failures` (it searches Exa for the provider and date of an autopsy case, so autopsy output steers scout) and evidence (to skip duplicates).
`experimenter` writes `gpuf-experiments`; reads failures, evidence, experiments.
`proposer` writes nothing; reads all three audiences.
`forecaster` writes nothing; reads `gpuf-failures` and `gpuf-evidence` only.

Cross-agent use that the challenge asks for: `proposer` uses all three writers' data; `scout` uses `autopsy`'s cases; `forecaster` uses `scout`'s and `autopsy`'s data. Author goes in the data point's `identity` and in `metadata.agent` (recall results show no author field; see UNKNOWN list).

## Records to data points, and the date each carries

| record | one data point is | `id` | `timestamp` | audience |
|---|---|---|---|---|
| autopsy case | one provider repricing or panel exit seen in the median of one series, with date, size of the median move and whether the forecast missed | `autopsy-<series>-<yyyy-mm-dd>` | the date the miss is known: event date for h=1, event date + h when the text states a miss at horizon h | `gpuf-failures` |
| scout evidence | one dated web hit: url, title, published date, quoted sentence, event it explains | `scout-<sha8 of url>` | the later of Exa `publishedDate` and any date the page text states about itself (e.g. "Published Oct 18") | `gpuf-evidence` |
| experiment | one hypothesis test: claim, failure mode, prediction, result with interval, verdict | `exp-<hypothesis>-<yyyy-mm-dd>` | run time (UTC) | `gpuf-experiments` |

Text format follows the docs: one header line (source and day), then raw complete fields, no summaries. Labels: `Autopsy: <series>`, `Evidence: <domain>`, `Experiment: <H-id>`.

## Where each agent recalls, and leak control

- `proposer`: before proposing, one recall per failure mode (`query` = the failure mode in words), no date bound (it works at "now", all three audiences).
- `forecaster`: at forecast origin `d`, recall as `forecaster` with `as_of=d` (sends `queryTimestamp` and `occurredTo` = end of day d, UTC). `gpuf.memory.recall` also drops any returned result with `occurredAt` after `d`, so a docs gap cannot leak.
- Leak-free by date: (a) every data point is timed when its information became known, not when the event it describes happened (the scout rule above and the autopsy rule above); (b) the forecaster cannot read experiments; (c) a test perturbs journalled records dated after the origin and checks recall is unchanged (offline path now, live path after approval). Residual risk, UNKNOWN in docs: a derived memory (`claim`, `observation`) that merges an early and a late data point may carry the late fact under an early date. Mitigation in the live check: recall as the forecaster at an origin before the Nebius article date and confirm no result mentions "Oct 18" content.
- A concrete leak in our own data: the cached Exa hit `https://askgpu.com/updates/nebius-raises-on-demand-gpu-prices/` has `publishedDate` 2026-10-01 but its text says "Published Oct 18, 2026". Under the rule it is timed 2026-10-18, so a forecaster at origin 2026-10-06 does not see it.

## 12 test records

Numbers come from `runs/failure/decomp.txt`, `runs/failure/events.txt`, `experiments/failure/protocol.yaml`, `research-log.md`, and the Exa cache. Items marked (pack) need the exact median move read from the pack at write time; nothing is invented.

**autopsy (4)**
1. `autopsy-gpurentalprices.marketplace_ask.H100_80GB.spot-2026-10-06`, timed 2026-10-06, `gpuf-failures`: largest-loss series on dev; 13.6% of last-value loss; blend skill 0.346 against drift 0.130; moves are marketplace asks, not rate-card repricing.
2. `autopsy-fastgpu_daily.neocloud_rate_card.B300-2026-10-06`, timed 2026-10-06: 13.1% of last-value loss (cumulative 0.267 after 0.136); same B300 class on gpurentalprices carries 9.6%; both collectors moved together (same-day correlation 0.25 over 9 shared GPUs).
3. `autopsy-all-2026-10-04`, timed 2026-10-04: busiest day on dev, 6 of 37 series moved more than 5%; days with 5 or more big moves: 10-02, 10-03, 10-04, 10-06; blend upper tail under-covered at h=7 (27 to 33% of truths above q90).
4. `autopsy-gpurentalprices.neocloud_rate_card.H100_SXM_80GB-2026-10-01`, timed 2026-10-08 (h=7 miss known 7 days later): on-demand H100 repriced by Nebius on 2026-10-01; median move (pack); forecast missed on the upside at h=7.

**scout (4)** (Exa cache, `data_out/exa_cache`)
5. `scout-<askgpu nebius>`: url above; title "Nebius raises on-demand GPU prices by up to 21% | AskGPU"; quote "From October 1, 2026, a Nebius H100 costs $4.50 per GPU-hour on demand instead of $3.85, and a B300 $9.50 instead of $7.85"; explains the 2026-10-01 repricing; timed 2026-10-18.
6. `scout-<salad>`: https://blog.salad.com/saladcloud-price-changes-september-2026/; "SaladCloud GPU and vCPU pricing is changing on September 12, 2026: 15 GPU classes drop 25% on average, while RTX 5090 and 4090 prices increase."; explains a September down-move on the marketplace class; timed 2026-09-01.
7. `scout-<fireworks>`: https://theweightedaverage.com/notes/2026-09-01-fireworks-gpu-rate-increase/; title "Fireworks raises GPU rates up to 30%"; the quoted sentence is read from the cached highlight at write time; timed 2026-09-01.
8. `scout-<linkedin>`: https://www.linkedin.com/feed/update/urn:li:activity:7501005054821253121 ; quote "In the last 3 months, GPU prices have risen across all SKUs."; timed 2026-09-02; context for the 17 Sep onward burst.

**experimenter (4)**
9. `exp-H7_breadth-2026-11-14`: claim "share of a collector's series that changed in the last b days predicts how much each series moves next"; targets the 10 busy days carrying 56% of loss; prediction +0.005 to +0.02, mostly h=7 and fastgpu_daily; result: every variant at or below the base (mix +0.0805 over drift); verdict refuted.
10. `exp-H8_lead-2026-11-14`: gpurentalprices leads fastgpu by a day as a centre shift; prediction +0.003 to +0.01 at fastgpu h=1 and h=3; result at or below base; refuted.
11. `exp-H9_reversal-2026-11-14`: reversal after a >5% one-day move (about 69 jumps); result at or below base; refuted.
12. `exp-H10_news-2026-11-14`: Exa dated "price increase" headline count widens q90; prediction +0.005 to +0.02 at h=7; result +0.0096 skill, 90% interval [-0.004, +0.015], one episode (Nebius repricing); verdict not significant.

Identities and audiences are created first, then records 1 to 12 go in as three batches (one per writer, own `idempotencyKey`), each polled to `completed`.

## Six recall questions

| # | identity | question | what a pass looks like |
|---|---|---|---|
| Q1 | proposer | "Which hypotheses on failure modes of the median have been refuted, and what was the evidence?" | returns records 9 to 12 with `sourceId`s |
| Q2 | proposer | "What is the largest unexplained source of last-value loss?" | returns records 1, 2 and 3 |
| Q3 | forecaster, `as_of` 2026-10-06 | "Which providers announced price increases before this date?" | returns records 6 to 8; not record 5 (timed 10-18) |
| Q4 | forecaster, `as_of` 2026-10-31 | "Nebius H100 on-demand price change" | returns record 5 and 4 |
| Q5 | scout | "Which dates and providers had big median moves that still lack a news explanation?" | returns records 3 and 4 (autopsy data used by scout) |
| Q6 | forecaster | "What did the experiments conclude about breadth?" | returns nothing from `gpuf-experiments` (access check) |

Each question is run once live and once offline (replay from the journal) and the results compared.

## Estimated credit cost

Sends: 1 credit per 350 bytes, minimum 1; the records are about 400 to 900 bytes each, so 2 to 3 credits each, 24 to 36 in total. Recalls: 1 credit each on Pay as you go, 6 to 12 with reruns. Polls, audiences and identities cost nothing. Total about 30 to 50 credits, under 0.01% of the 550,000 balance. The plan name is not in the usage response, so recall might be free; I assumed the worse case.

## What I will not do without a second approval

Create or change a project, key, MCP server or webhook; call `ingest/estimate`; send anything beyond these 12 records.
