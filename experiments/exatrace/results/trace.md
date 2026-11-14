# exatrace: what Exa search changes, cell by cell

Protocol frozen before any result: `experiments/exatrace/protocol.yaml`. Practice dates only (origins 2026-09-16 to 2026-10-06, targets to 2026-10-13). No row added to the trajectory or the ledger. The calendar switch stays off in the submission; nothing here changes `submissions/`.

## Top line for the orchestrator: the scored week

**No announcement found.** No dated public announcement published on or before 2026-11-06 of a price change taking effect 7 to 13 November was found for any of the 29 providers that hold the middle offer, or an offer next to it, of the 37 scored series on 6 November (87 searches, 117 kept pages, 40 stored-copy fetches, $0.243 of new Exa spend; `results/forward.json`). Nothing is flagged.

The only eligible hits effective near the week are two GPUJournal reports on Verda (effective 2 and 4 November, published the same day, lead 0 days). Verda is a daily repricer, about +1% every two days: the 6 November rows already show two further steps past the 2 November prices and the 4 November prices exactly (fastgpu). Moving only Verda's offer to either announced price changes no scored median (0.0% on every series). Lambda's 16 November rise (already in the calendar) takes effect after the last target date. It is already reflected on gpurentalprices on 6 November, and on fastgpu Lambda is not at the middle, so it has no pass-through.

Not appended to `data_out/repricing_calendar.jsonl`: the two Verda reports are same-day descriptions of moves that already happened, not announcements. Changing the calendar file would also change its hash, and the shipped cause labels (`experiments/loop/cause_labels.json`) are keyed on that hash, so the existing loop test would fail.

## 1. Controlled arms on the cached practice episodes

Setting: prov in its submitted configuration {L 1, W 21, gate dyn}, 37 scored series × 21 origins × horizons 1/3/7 = 2,331 cells (`arms.py`, `results/arms_summary.json`, cells in `results/arms_cells.parquet`). Skill = 1 − pinball loss / last-value loss. The calendar is substituted in memory per arm; the file is not edited.

| arm | what it is | skill, all 2,331 cells | skill, 142 affected cells | cells changed vs off |
|---|---|---|---|---|
| i off | no calendar | 0.2160 | 0.1539 | 0 |
| ii valid, lag 0 (primary) | the extracted calendar, collector lag fixed at 0 | **0.3083** | **0.4756** | 101 |
| ii valid, fitted lag (IN-SAMPLE) | fastgpu +1 day, read off these same two episodes | 0.3121 | 0.4888 | 100 |
| iii no price pair | announcement known, size not | 0.2160 | 0.1539 | 0 (bit-identical) |
| iii size zero | date known, new price = old price | 0.2109 | 0.1361 | 23 |
| iv deferred | every entry published at its effective date + 8 days | 0.2160 | 0.1539 | 0 (bit-identical) |
| minus Nebius | entry deleted | 0.2436 | 0.2499 | 53 |
| minus Jarvislabs | entry deleted (its only source) | 0.2769 | 0.3658 | 56 |
| minus Longbridge (Nebius's cited source) | entry rebuilt from the remaining 3 sources' cached text | 0.3071 | 0.4712 | 89 |
| minus thefivenines (Nebius's earliest source) | rebuilt from the remaining 3 | 0.3083 | 0.4756 | 101 |

"Affected cells" means the origin falls between an entry's usable date and its effective day, the target is on or after the effective day, and the announcing provider has an offer at the old price in that series' list: 88 cells for Nebius and 66 for Jarvislabs, 142 distinct (12 cells are touched by both). Of the 142, 124 had a price move. Of the 101 changed cells, 81 lose less, 20 lose more, and total loss falls by 6.28 (last-value loss on the 142 is 19.53).

By horizon, all cells, lag 0: h=1 0.140 → 0.173, h=3 0.207 → 0.274, h=7 0.237 → 0.355.

### Acceptance (thresholds fixed in the protocol)

| test | result |
|---|---|
| A1 deferred arm bit-identical to off on every cell | **passed** (0 of 2,331 cells differ) |
| A2 every changed cell lies inside the affected set | **passed** (101 of 101) |
| A3 deleting an event restores off on the cells only it touches | **passed**: Nebius 76 of 76 cells, Jarvislabs 54 of 54 |
| A4 no-price arm bit-identical to off | **passed** (prov cannot use an announcement without a price) |
| A5 each acting event has a cached source stating its GPU, old and new price and the effective date | **passed**: Nebius via Longbridge (4/4 prices, 16 Sep) and gpucloudadvisors (4/4, 28 Sep); Jarvislabs via its own page (3/3, 24 Sep) |

None of the three drop conditions holds. Deleting the source changes the forecasts, the deferred control does nothing, and the cached text justifies each price mapping. The causal claim therefore stands, but only as a retrospective mechanism demonstration on two practice events.

### What the controls show

- **Where the gain comes from.** It comes from the announced price, not from the switch opening prov's gate. With the date known and the size zero, skill on the affected cells falls from 0.154 to 0.136. Opening the gate alone is slightly harmful (share of the gain: −0.055). Without the price pair, nothing changes at all.
- **The fitted lag adds little.** Zero lag gets 0.3083; the lag read off the same two episodes gets 0.3121. The earlier full-dev figure (0.2089 → 0.2827, research-log 12:34) used the fitted lag and is in-sample. The window here is 21 origins, so the numbers differ from that figure.
- **Sources are redundant in one case and not in the other.** Deleting thefivenines changes nothing, because Longbridge states all four Nebius prices the same day. Deleting Longbridge delays H100, H200 and B200 to 28 September (gpucloudadvisors), which reduces 101 changed cells to 89 and the affected-cell skill from 0.476 to 0.471. Jarvislabs has a single source; deleting it deletes the effect.
- **Monte Carlo note.** The thefivenines-deleted arm carries the same information as the valid arm, but its loss on the affected cells is 10.2425 against 10.2418. The rebuilt line sits in a different place in the list, so the calendar's random arrival-day draws come in a different order. This is simulation noise, not information.
- **Sample size.** Two events. The 21 origins span 3 calendar weeks, so no interval is given. This is not a validation of H27 and says nothing about the calendar in general.

## 2. The trace

Rows are reproducible offline from `data_out/exa_cache` with `LOOP_OFFLINE=1` (`trace.py`, `sources.py`; test `tests/test_loop.py::test_trace_sources_reproduce_from_cache` runs with the network disabled). Full columns: `results/trace_sources.csv` (one row per source), `results/trace_events.json` (one per calendar entry), `results/trace_series.csv` (one per entry × scored series). The tables below are generated by `render.py`.

How to read them:
- `states_prices` counts the entry's (GPU, old, new) triples that the cached text names, with the GPU first, then the old price and the new price within 160 characters, plus the effective date anywhere in the text.
- `quote_found_in_cached_text` checks the calendar's quoted sentence verbatim. It is False for Reuters and gpucloudadvisors, whose calendar quotes are paraphrases. Reuters states no prices at all.
- `first_observed_new_price` is the first day, per collector, on which the provider's offer rows show the new price after not showing it the day before. It reads rows up to 10 days after the effective date for practice-date entries, and up to 6 November otherwise.
- `position` is where the provider's offer at the old price sits in the scored list on the last practice origin before the change. For entries outside the window it is taken on the publication day or the day before the change.

Entries that correctly do nothing, and why:
- **Too late.** DigitalOcean 1 Aug (reported 2 Aug) and the auto-added Nebius 1 Jun (reported 22 Aug) are confidence C, reported after the change. DigitalOcean is also in no scored list before August.
- **Wrong contract.** AWS 7 Oct covers capacity blocks, which are in no panel. Salad 12 Sep and 1 Nov cover priority tiers (high, medium, low), and no scored series has those GPUs in a matching tier. The calendar's part B also found that Salad's old prices were not in the community panel.
- **Outside the window or not in the list.** Fireworks 1 Sep took effect before the first origin, and Fireworks has no offer in any of the five scored lists its GPUs map to.
- **Already reflected in the collector.** Lambda 16 Nov: on gpurentalprices on 6 November, Lambda's B200 offer is already at the new $7.69. On H100 SXM there is no offer at the old $3.99.
- **No pass-through to the median.** Lambda 16 Nov on fastgpu: 0.0% on all four lists (B200 next to the middle, H100 SXM 2 ranks away, A100 80GB 4 ranks away; A100 40GB has old = new). Inside the window, Nebius sits 2 ranks from the middle on fastgpu B200 and gpurentalprices H100 80GB, and all 22 cells of those two series stay unchanged. Counting the partly changed B200 and H200 lists on gpurentalprices, 32 of Nebius's 88 cells stay unchanged. Nebius has no offer on gpurentalprices H100 SXM.
- **Changed but worse.** On Jarvislabs fastgpu H200, Jarvislabs sits 3 ranks from the middle, with a static pass-through of 1.10%, and its loss rises from 0.096 to 0.137. On Nebius gpurentalprices B200, its loss rises from 0.126 to 0.127.

## 3. Fix: the scout's memory-write path now uses the calendar's eligibility

Before the fix, `step_scout` wrote a `gpuf-evidence` record for every kept hit that had effective-date language and a title that was not evergreen. It skipped the calendar's checks: whether a dated old → new price passage exists, whether the passage names a panel provider, and whether the text carries a date later than `--as-of` (the "edited later" rule). It also timed each record by Exa's publication date. An earnings-preview page (`scout-8f1956d9`, edelbridge.substack.com) is an example of what that let through.

What changed in `src/gpuf/loop.py`:
- `assess()` is now the one eligibility decision for both calendar lines and evidence records.
- `evidence_items()` writes a record only for hits that pass `assess`. Each record is timed by its availability date (the later of the publication date and any later date in the text) and carries separate fields: `published`, `latest_date_in_text`, `effective_date`, `usable_from` and `first_observed` (per collector, from offer rows up to the as-of date).
- `later_dates()`, `latest_date()` and `first_observed()` are new helpers.
- Calendar decisions are unchanged: candidates are processed in the same order with the same contents budget, and sources already in the calendar are judged afterwards, for evidence only.

On the cached searches (dry run, journals redirected; `results/scout_2026-10-06.json`, `results/scout_2026-11-06.json`):

| as of | hits with effective-date language | evidence eligible after the fix | eligible before (all non-evergreen) |
|---|---|---|---|
| 2026-10-06 | 106 | 10 | 102 |
| 2026-11-06 | 133 | 15 | 127 |

Writes were capped at 15 a run before and after. Rejections at 2026-10-06: 82 have no dated price passage, 7 name no panel provider, 4 are evergreen, and 3 carry a date after the as-of date.

Fixture test (`tests/test_loop.py::test_scout_eligibility_rejects_later_dated_content`): a page Exa dates 20 September, saying the H100 goes from $3.85 to $4.50 effective 1 October, with an "Updated November 2" line. As of 25 September it is rejected and nothing is written. As of 6 November it is accepted, and the record carries published 2026-09-20, latest date in text 2026-11-02, effective 2026-10-01, usable from 2026-11-02, and the H100 first observed on fastgpu on 2 October and on gpurentalprices on 1 October.

Not fixed, reported:
- Records already in the shared memory from before this fix stay there. The records above (scout-8f1956d9 an earnings preview, and scout-f4c32699 from askgpu.com, a tracker domain that the orchestrator wrote by hand) would not pass now.
- Defect found in `subject_provider` (task scope was two defects, so this is not fixed): at as-of 2026-11-06 the scout would add a "verda 2026-10-01" line built from a GPUJournal passage that names Verda first but quotes RunPod's prices. It is confidence C, so `calendar_lib` would never use it, but the line would be wrong.

## 4. Fix: `prior --as-of`

`python -m gpuf.loop prior --claim ... --as-of YYYY-MM-DD` takes a date that defaults to 2026-11-06 and is refused if later.
- It sets the Exa `endPublishedDate` and drops results published after that date.
- Before the default it also bounds the memory recall (end of that day UTC) and the ledger: entries updated after the as-of date are ignored, because research records are timed by when they were written.
- At the default the request bodies are byte-identical to before (cache hits, same recommendation), and recall stays unbounded as before.
- The output gains `as_of` and `bounded_recall_and_ledger`.
- Test: `tests/test_loop.py::test_prior_as_of_bounds_search_and_recall`. As of 2026-09-25 offline, the bodies end 2026-09-25T23:59:59Z, no new Exa call is made, the recalled rows are all dated on or before that day, and no ledger entry is used. A date of 2026-11-07 is refused.

## 5. Paragraph for the README: what breaks if Exa is removed?

> **What breaks if Exa is removed.** The submitted forecast does not: `bash reproduce.sh final` reads no Exa output. prov's calendar switch (`cal` in `src/gpuf/methods/prov.py`) is off, and no member calls Exa. What breaks is the research loop's evidence path. `python -m gpuf.loop scout` can no longer find dated price announcements, so no new calendar lines and no new evidence records are made. `prior` can no longer check a claim against dated outside sources. The recorded traces stay checkable because every response is cached in `data_out/exa_cache` and replays with `LOOP_OFFLINE=1`. Run with the calendar switch on, on the two practice episodes that had dated announcements (Nebius 1 Oct, Jarvislabs 5 Oct; origins 16 Sep to 6 Oct), deleting the sources changes the forecasts. Skill on the 142 cells between announcement and effect falls from 0.476 to 0.154, and on all 2,331 cells from 0.308 to 0.216, with the collector lag fixed at zero. Moving the same sources to after the target date gives forecasts bit-identical to no calendar (`experiments/exatrace/results/trace.md`). That is two events on practice dates, a mechanism demonstration and not a validated forecasting gain, which is why the switch stays off. Forward search found no dated announcement of a change taking effect in the scored week (7 to 13 November) by any provider at or next to the middle of a scored list. Exa call sites: [`src/gpuf/scout.py:130`](src/gpuf/scout.py) (`exa_call`, the single cached client for `search` and `contents`, request on line 130; `search_day` at line 59 served the retired news signal H10); [`src/gpuf/loop.py:184`](src/gpuf/loop.py) (`_exa`, the loop's only route, calling `scout.exa_call` at line 203), used at `loop.py:631` (scout search), `loop.py:660` (scout contents, Exa's stored copy) and `loop.py:751` (prior search); `src/gpuf/scientist.py:684` (through `loop._exa`). Offline experiment scripts: `experiments/calendar/search.py:49`, `experiments/calendar/fetch.py:61`, `experiments/exa_attrib/run_search.py:36`, `experiments/exa_attrib/fetch.py:20`, `experiments/exatrace/forward.py:107,130`, and two direct clients, `experiments/policy/search.py:33` and `experiments/longrun/code/exa_resale.py:43`.

(Line numbers as of this report. `src/gpuf/scientist.py` belongs to another agent.)

## 6. Task 4 details: forward-looking search

Twenty-nine providers hold the middle offer, or one next to it, of a scored series on 6 November (list below; the four afhubbard hyperscaler-spot series have no offer panel). For each one, `forward.py` ran three searches, all in the window 2026-10-01 to 2026-11-06 with trackers excluded: the scout's two queries (58 of them were cache hits from the calendar agent's identical requests) and one new query for changes effective 7 to 13 November (29 new).

What happened to the results:
- 150 were dropped as trackers and 456 as not a price change by that provider; 117 were kept.
- 40 kept pages had their stored copy fetched.
- Through `assess` with as-of 2026-11-06: 103 have no dated price passage, 3 are evergreen, and 1 names no panel provider.
- Ten were eligible. Two are effective in 30 Oct to 13 Nov (the Verda reports above). The other eight are effective earlier: Nebius 1 Oct (4 sources), Nebius 24 Oct, AWS 7 Oct, Jarvislabs 5 Oct, and the mis-attributed "Verda 1 Oct" GPUJournal passage, which quotes RunPod's prices (section 3).

The pass-through tolerance for the announced old price is min(3%, half the step). An earlier run used a fixed 3% and flagged a spurious −1% Verda A100 pass-through, caused by an offer one 1% step past the old price. That flag was a false positive; the fix is in `forward.py`. Spend: $0.243 of new requests, against a cap of $1.50.

## Limitations

- Exa's publication date is not a historical snapshot. Cached text could include edits made after that date. The later-date rule catches dated edits, not silent ones.
- Two events, 21 origins in 3 calendar weeks: no interval is given, and the gain is not general.
- The source-support check (GPU, then old and new price within 160 characters) is a heuristic. It misses the "new (from old)" order, so the Lambda page scores 1/4.
- The trace's "position" is a static, one-day view. prov's simulated median can move when the static pass-through is zero (Jarvislabs fastgpu H100 SXM: 4 of 11 cells changed at 4 ranks from the middle).

# Generated tables (render.py)

## Arms (origins 2026-09-16..2026-10-06, prov {L 1, W 21, gate dyn})

| arm | skill, all 2,331 cells | skill, 142 affected cells | Nebius cells (88) | Jarvislabs cells (66) | cells changed vs off | bit-identical to off |
|---|---|---|---|---|---|---|
| i_off | 0.216 | 0.1539 | 0.106 | 0.3076 | 0 | True |
| ii_valid | 0.3083 | 0.4756 | 0.4002 | 0.7135 | 101 | False |
| ii_lag | 0.3121 | 0.4888 | 0.4204 | 0.7029 | 100 | False |
| iii_nopair | 0.216 | 0.1539 | 0.106 | 0.3076 | 0 | True |
| iii_zero | 0.2109 | 0.1361 | 0.0841 | 0.2754 | 23 | False |
| iv_deferred | 0.216 | 0.1539 | 0.106 | 0.3076 | 0 | True |
| minus_jarvislabs_2026-10-05 | 0.2769 | 0.3658 | 0.3861 | 0.3008 | 56 | False |
| minus_first_source_jarvislabs_2026-10-05 | 0.2769 | 0.3658 | 0.3861 | 0.3008 | 56 | False |
| minus_nebius_2026-10-01 | 0.2436 | 0.2499 | 0.102 | 0.6688 | 53 | False |
| minus_first_source_nebius_2026-10-01 | 0.3083 | 0.4756 | 0.4001 | 0.7132 | 101 | False |
| minus_primary_source_nebius_2026-10-01 | 0.3071 | 0.4712 | 0.3944 | 0.7018 | 89 | False |

## Sources (all read from data_out/exa_cache)

| event | url | exa_published | title | quoted_sentence | quote_found_in_cached_text | states_effective_date | states_prices | latest_date_in_text |
|---|---|---|---|---|---|---|---|---|
| digitalocean 2026-08-01 | https://theweightedaverage.com/notes/2026-08-02-digitalocean-gpu-price-hike/ | 2026-08-02T16:24:00 | DigitalOcean raises H100 rental prices 30% • The Weighted Av | DigitalOcean raised on-demand H100 GPU Droplet pricing 30%, from $3.39 to $4.41 per GPU-hour, while H200 pricing climbed from $3.44 to $4.47 | True | True | 2/2 | 2026-08-02 |
| fireworks 2026-09-01 | https://modelswar.com/change/fireworks-h200-141gb-gpu-price-increases-effective-sep-1-26510/ | 2026-08-13T00:02:29 | Fireworks: H200 141GB GPU price increases effective Sep 1 —  | H200 141 GB GPU ... upto Aug 31: $7.00 ... from Sep 1: $8.00 |  | True | 1/3 | 2026-09-01 |
| fireworks 2026-09-01 | https://modelswar.com/change/fireworks-h100-80gb-gpu-price-increases-effective-sep-1-26509/ | 2026-08-13T00:02:30 | Fireworks: H100 80GB GPU price increases effective Sep 1 — M | GPU Type: H100 80 GB GPU + Price ($) per hour - upto Aug 31: $7.00 + Price ($) per hour - from Sep 1: $8.00 | True | True | 1/3 | 2026-09-01 |
| fireworks 2026-09-01 | https://modelswar.com/change/fireworks-b200-180gb-gpu-price-increases-effective-sep-1-26506/ | 2026-08-13T00:02:30 | Fireworks: B200 180GB GPU price increases effective Sep 1 —  | Price ($) per hour - upto Aug 31: $10.00 + Price ($) per hour - from Sep 1: $13.00 | True | True | 1/3 | 2026-09-01 |
| salad 2026-09-12 | https://blog.salad.com/saladcloud-price-changes-september-2026/ | 2026-09-01T00:00:00 | Upcoming SaladCloud Price Changes: September 12, 2026 - Sala | These changes take effect Saturday, September 12, 2026 at 00:00 UTC ... At High Priority, the RTX 5090 moves from $0.450 to $0.500 and the R | True | True | 52/52 | 2026-09-12 |
| nebius 2026-10-01 | https://www.thefivenines.com/data-ai/nebius-raises-gpu-prices-20-as-supply-tightens | 2026-09-16T07:00:00 | Nebius raises GPU prices 20% as supply tightens | Five Nines | Nebius said it will raise GPU cloud prices by an average of 20 percent from October 1, covering H100, H200, B200 and B300 chips, with B300 r | True | True | 1/4 | 2026-10-01 |
| nebius 2026-10-01 | https://longbridge.com/en/topics/100000000903151 | 2026-09-16T21:10:10 | $Nebius(NBIS.US) INCREASE ON-DEMAND GPU RATES EFFECTIVE OCTO | $Nebius(NBIS.US) INCREASE ON-DEMAND GPU RATES EFFECTIVE OCTOBER 1. H100: $3.85 per GPU-hour -> $4.50 H200: $4.50 per GPU-hour -> $5.40 B200: | True | True | 4/4 | 2026-10-01 |
| nebius 2026-10-01 | https://www.reuters.com/technology/nebius-hikes-ai-cloud-prices-again-demand-computing-power-soars-2026-09-17/ | 2026-09-17T16:12:34 | Nebius hikes AI cloud prices again as demand for computing p | Cloud provider Nebius (NBIS.O) said on Thursday it will raise pay-as-you-go prices for leasing selected Nvidia chips from October 1 | False | True | 0/4 | 2026-10-01 |
| nebius 2026-10-01 | https://gpucloudadvisors.com/news/nebius-october-gpu-price-increase/ | 2026-09-28T07:54:45 | Nebius raises GPU prices again October 1; H100 to $4.50, B30 | HGX H100, per GPU hour $3.85 now, $4.50 from October 1 ... HGX B300, per GPU hour $7.85 now, $9.50 from October 1. RTX PRO 6000 stays at $1. | False | True | 4/4 | 2026-10-01 |
| jarvislabs 2026-10-05 | https://jarvislabs.ai/updates/gpu-pricing-october-2026 | 2026-09-24T16:33:04 | New GPU rates from October 5, 2026 | Jarvislabs Updates | From October 5, 2026 at 00:00 IST, new rates apply to NVIDIA H200, H100 and RTX PRO 6000 GPUs. ... NVIDIA H200 SXM / $3.99/hr / $4.59/hr / N | True | True | 3/3 | 2026-10-05 |
| aws 2026-10-07 | https://cryptobriefing.com/aws-gpu-capacity-block-price-increase/ | 2026-09-30T18:20:10 | AWS reportedly lifts GPU capacity prices again, with a 15% h | A post on X claims AWS is lifting reserved compute prices for a fourth quarter, with a 15% increase set to begin October 7. | True | True | 0/6 | 2026-10-07 |
| aws 2026-10-07 | https://fourweekmba.com/ai-aws-ec2-capacity-block-rates-october-2026/ | 2026-10-01T11:01:21 | AWS EC2 Capacity Block Rates, Effective October 7 - FourWeek | P6-B300 at $16.146, P6-B200 at $14.208, P5en at $7.895, P5e at $6.866, and P5 at $5.970, P4de at $2.546 and P4d at $1.696. ... all other Cap | True | True | 0/6 | 2026-10-07 |
| salad 2026-11-01 | https://blog.salad.com/saladcloud-price-changes-november-2026 | 2026-11-01T00:00:00 | Upcoming SaladCloud Price Changes: November 1, 2026 | These changes take effect Sunday, November 1, 2026 at 00:00 UTC ... High Priority prices are increasing on 21 GPU classes, by 10% to 20% on  | True | True | 63/63 | 2026-11-01 |
| lambdalabs 2026-11-16 | https://gpujournal.ai/story/lambda-announced-rises-nov-16 | 2026-11-06T18:09:31 | Lambda announces GPU price rises of about 15% — B200, H100 a | 'These prices take effect November 16, 2026, at 00:00 UTC. Until then, log in to your Lambda Cloud account to see current pricing.' The prin | True | True | 1/4 | 2026-11-16 |
| nebius 2026-06-01 | https://startupfortune.com/nvidia-warns-hyperscalers-its-ai-server-prices-are-jumping-more-than-15/ | 2026-08-22T19:44:51 | Nvidia Warns Hyperscalers Its AI Server Prices Are Jumping M | The pain is already showing up further down the chain. Nebius raised on-demand GPU rental prices by roughly 30% from June 1, with H100 prici | True | True | 2/2 | 2026-08-22 |

## Events

| event | published_usable_from | effective_utc | confidence | changes | n_changes | first_observed_new_price | scored_series_touched | affected_cells | does_nothing_because |
|---|---|---|---|---|---|---|---|---|---|
| digitalocean 2026-08-01 | 2026-08-02 | 2026-08-01T00:00Z | C | H100 [on_demand] 3.39->4.41; H200 [on_demand] 3.44->4.47 | 2 | fastgpu None, gpurentalprices 2026-08-04 | 5 | 0 | too late: confidence C (published 2026-08-02, effective 2026-08-01: reported after the change) |
| fireworks 2026-09-01 | 2026-08-13 | 2026-09-01T00:00Z | B | H100 80GB [on_demand_deployment] 7.0->8.0; H200 [on_demand_deployment] 7.0->8.0; B200 [on_demand_deployment] 10.0->13.0 | 3 | fastgpu None, gpurentalprices 2026-09-01 | 5 | 0 | outside the origin window: effective 2026-09-01 before the first origin 2026-09-16 |
| salad 2026-09-12 | 2026-09-01 | 2026-09-12T00:00Z | A | RTX 5090 [high] 0.45->0.5; RTX 5090 [medium] 0.38->0.417; RTX 5090 [low] 0.31->0.333; RTX 4090 [high] 0.3->0.33 ... | 52 | fastgpu None, gpurentalprices 2026-09-10 | 0 | 0 | wrong contract: no scored series has an announced GPU in a matching tier (announced tiers ['high', 'low', 'lowest', 'medium']; calendar_lib.TIER_MAP) |
| nebius 2026-10-01 | 2026-09-16 | 2026-10-01T00:00Z | A | H100 [on_demand] 3.85->4.5; H200 [on_demand] 4.5->5.4; B200 [on_demand] 7.15->8.5; B300 [on_demand] 7.85->9.5 | 4 | fastgpu 2026-10-02, gpurentalprices 2026-10-01 | 9 | 88 |  |
| jarvislabs 2026-10-05 | 2026-09-24 | 2026-10-04T18:30Z | A | H200 [on_demand] 3.99->4.59; H100 SXM [on_demand] 2.69->3.49; RTX PRO 6000 [on_demand] 1.89->2.19 | 3 | fastgpu 2026-10-05, gpurentalprices 2026-10-04 | 6 | 66 |  |
| aws 2026-10-07 | 2026-09-30 | 2026-10-07T00:00Z | B | B300 [capacity_block] None->16.146; B200 [capacity_block] None->14.208; H200 (P5en) [capacity_block] None->7.895; H100 (P5) [capacity_block] None->5.97 ... | 6 | fastgpu None, gpurentalprices None | 0 | 0 | wrong contract: no scored series has an announced GPU in a matching tier (announced tiers ['capacity_block']; calendar_lib.TIER_MAP) |
| salad 2026-11-01 | 2026-11-01 | 2026-11-01T00:00Z | A | RTX 5090 [high] 0.5->0.6; RTX 5090 [medium] 0.417->0.483; RTX 5090 [low] 0.333->0.367; RTX 4090 [high] 0.33->0.44 ... | 63 | fastgpu 2026-10-28, gpurentalprices None | 0 | 0 | wrong contract: no scored series has an announced GPU in a matching tier (announced tiers ['high', 'low', 'medium']; calendar_lib.TIER_MAP) |
| lambdalabs 2026-11-16 | 2026-11-06 | 2026-11-16T00:00Z | B | B200 [on_demand] 6.69->7.69; H100 SXM [on_demand] 3.99->4.59; A100 80GB [on_demand] 2.79->3.19; A100 40GB [on_demand] 1.99->1.99 | 4 | fastgpu None, gpurentalprices 2026-11-06 | 8 | 0 | outside the origin window: published 2026-11-06 after the last practice origin 2026-10-06 |
| nebius 2026-06-01 | 2026-08-22 | 2026-06-01T00:00Z | C | H100 [on_demand] 2.95->3.85; B200 [on_demand] 5.5->7.15 | 2 | fastgpu None, gpurentalprices 2026-08-04 | 5 | 0 | too late: confidence C (published 2026-08-22, effective 2026-06-01: reported after the change) |

## Series rows of the two events that change forecasts (q50 and loss over the affected cells of that series)

| event | series | old | new | position_day | n_offers | rank | position | static_pass_through_pct | affected_cells | cells_changed | last_value_mean | q50_before_mean | q50_after_mean | truth_mean | loss_before | loss_after | outcome |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nebius 2026-10-01 | fastgpu_daily.B200.on_demand | 7.15 | 8.5 | 2026-09-30 | 10 | [8] | 2 ranks from middle | 0.0 | 11 | 0.0 | 6.4695 | 6.47 | 6.47 | 6.9903 | 2.8141 | 2.8141 | no change: no pass-through to the median |
| nebius 2026-10-01 | fastgpu_daily.B300.on_demand | 7.85 | 9.5 | 2026-09-30 | 8 | [5] | middle | 4.26 | 11 | 11.0 | 7.7477 | 7.7616 | 8.2343 | 8.5722 | 4.7771 | 3.3587 | forecast changed, loss down |
| nebius 2026-10-01 | fastgpu_daily.H100_SXM_80GB.on_demand | 3.85 | 4.5 | 2026-09-30 | 16 | [8] | middle | 1.28 | 11 | 11.0 | 3.875 | 3.875 | 3.9245 | 3.9155 | 0.2009 | 0.1059 | forecast changed, loss down |
| nebius 2026-10-01 | fastgpu_daily.H200.on_demand | 4.5 | 5.4 | 2026-09-30 | 13 | [8] | next to middle | 0.0 | 11 | 11.0 | 4.4918 | 4.5277 | 4.5055 | 4.525 | 0.1088 | 0.1087 | forecast changed, loss down |
| nebius 2026-10-01 | gpurentalprices.B200.on_demand | 7.15 | 8.5 | 2026-09-30 | 6 | [5] | next to middle | 0.0 | 11 | 5.0 | 6.7593 | 6.8487 | 6.8487 | 6.8663 | 0.1259 | 0.1266 | forecast changed, loss up |
| nebius 2026-10-01 | gpurentalprices.B300.on_demand | 7.85 | 9.5 | 2026-09-30 | 6 | [2] | next to middle | 5.77 | 11 | 11.0 | 8.4685 | 8.5534 | 9.0682 | 9.3528 | 4.1907 | 1.4306 | forecast changed, loss down |
| nebius 2026-10-01 | gpurentalprices.H100_80GB.on_demand | 3.85 | 4.5 | 2026-09-30 | 11 | [8] | 2 ranks from middle | 0.0 | 11 | 0.0 | 3.2629 | 3.248 | 3.248 | 3.4111 | 0.8795 | 0.8795 | no change: no pass-through to the median |
| nebius 2026-10-01 | gpurentalprices.H100_SXM_80GB.on_demand | 3.85 | 4.5 | 2026-09-30 | 7 |  | provider not in list |  | 0 |  |  |  |  |  |  |  | no change: provider not in list |
| nebius 2026-10-01 | gpurentalprices.H200.on_demand | 4.5 | 5.4 | 2026-09-30 | 9 | [6] | next to middle | 0.0 | 11 | 7.0 | 4.47 | 4.4705 | 4.5136 | 4.5045 | 0.1191 | 0.0437 | forecast changed, loss down |
| jarvislabs 2026-10-05 | fastgpu_daily.H100_SXM_80GB.on_demand | 2.69 | 3.49 | 2026-10-03 | 18 | [5] | 4 ranks from middle | 0.0 | 11 | 4.0 | 3.893 | 3.8997 | 3.9177 | 3.949 | 0.2313 | 0.1334 | forecast changed, loss down |
| jarvislabs 2026-10-05 | fastgpu_daily.H200.on_demand | 3.99 | 4.59 | 2026-10-03 | 13 | [4] | 3 ranks from middle | 1.1 | 11 | 11.0 | 4.5091 | 4.5356 | 4.5427 | 4.5445 | 0.0959 | 0.137 | forecast changed, loss up |
| jarvislabs 2026-10-05 | fastgpu_daily.RTX_PRO_6000.on_demand | 1.89 | 2.19 | 2026-10-03 | 7 | [3] | next to middle | 7.14 | 11 | 11.0 | 2.097 | 2.1856 | 2.2745 | 2.3496 | 0.7034 | 0.3686 | forecast changed, loss down |
| jarvislabs 2026-10-05 | gpurentalprices.H100_SXM_80GB.on_demand | 2.69 | 3.49 | 2026-10-03 | 10 | [1] | 4 ranks from middle | 0.0 | 11 | 9.0 | 3.3674 | 3.3846 | 3.5557 | 3.6865 | 1.6375 | 0.7008 | forecast changed, loss down |
| jarvislabs 2026-10-05 | gpurentalprices.H200.on_demand | 3.99 | 4.59 | 2026-10-03 | 11 | [3] | 3 ranks from middle | 2.68 | 11 | 11.0 | 4.47 | 4.47 | 4.59 | 4.565 | 0.3876 | 0.139 | forecast changed, loss down |
| jarvislabs 2026-10-05 | gpurentalprices.RTX_PRO_6000.on_demand | 1.89 | 2.19 | 2026-10-03 | 7 | [3] | next to middle | 7.14 | 11 | 11.0 | 2.0041 | 2.0676 | 2.19 | 2.19 | 0.5396 | 0.0087 | forecast changed, loss down |

## Lambda 16 Nov on 6 Nov (already reflected / no pass-through)

| series | old | new | position_day | n_offers | rank | position | static_pass_through_pct |
|---|---|---|---|---|---|---|---|
| fastgpu_daily.A100_40GB.on_demand | 1.99 | 1.99 | 2026-11-06 | 4 | [3] | middle | 0.0 |
| fastgpu_daily.A100_80GB.on_demand | 2.79 | 3.19 | 2026-11-06 | 13 | [11] | 4 ranks from middle | 0.0 |
| fastgpu_daily.B200.on_demand | 6.69 | 7.69 | 2026-11-06 | 11 | [7] | next to middle | 0.0 |
| fastgpu_daily.H100_SXM_80GB.on_demand | 3.99 | 4.59 | 2026-11-06 | 17 | [11] | 2 ranks from middle | 0.0 |
| gpurentalprices.A100_40GB.on_demand | 1.99 | 1.99 | 2026-11-06 | 7 | [3, 4, 5, 6, 7] | middle | 0.0 |
| gpurentalprices.A100_SXM_80GB.on_demand | 2.79 | 3.19 | 2026-11-06 | 4 |  | provider not in list |  |
| gpurentalprices.B200.on_demand | 6.69 | 7.69 | 2026-11-06 | 11 |  | already at the new price (reflected in the collector) |  |
| gpurentalprices.H100_SXM_80GB.on_demand | 3.99 | 4.59 | 2026-11-06 | 9 |  | no offer at the old price |  |

## Scored series on 2026-11-06: middle and adjacent offers

| series | offers | middle | next to middle | note |
|---|---|---|---|---|
| afhubbard.hyperscaler_spot.A100_40GB.spot |  |  |  | no offer panel in gpuf.panel (afhubbard hyperscaler spot) |
| afhubbard.hyperscaler_spot.A100_SXM_80GB.spot |  |  |  | no offer panel in gpuf.panel (afhubbard hyperscaler spot) |
| afhubbard.hyperscaler_spot.T4.spot |  |  |  | no offer panel in gpuf.panel (afhubbard hyperscaler spot) |
| afhubbard.hyperscaler_spot.V100.spot |  |  |  | no offer panel in gpuf.panel (afhubbard hyperscaler spot) |
| fastgpu_daily.hyperscaler_spot.A100_80GB.spot | 3 | aws 1.757 | azure 0.679, gcp 1.882 |  |
| fastgpu_daily.hyperscaler_spot.T4.spot | 3 | aws 0.089 | azure 0.068, gcp 0.1 |  |
| fastgpu_daily.neocloud_rate_card.A100_40GB.on_demand | 4 | verda 1.641, lambdalabs 1.99 | northflank 1.42, modal 2.099 |  |
| fastgpu_daily.neocloud_rate_card.A100_80GB.on_demand | 13 | verda 2.293 | northflank 1.76, vultr 2.397 |  |
| fastgpu_daily.neocloud_rate_card.B200.on_demand | 11 | openrelay 6.3 | modal 6.25, lambdalabs 6.69 |  |
| fastgpu_daily.neocloud_rate_card.B300.on_demand | 9 | openrelay 8.49 | hyperstack 7.4, nebius 9.5 |  |
| fastgpu_daily.neocloud_rate_card.H100_PCIe_80GB.on_demand | 4 | quantacloud 2.59, ovhcloud 2.99 | hyperstack 2.5, lambdalabs 3.29 |  |
| fastgpu_daily.neocloud_rate_card.H100_SXM_80GB.on_demand | 17 | daytona 3.949 | novita 3.39, modal 3.949 |  |
| fastgpu_daily.neocloud_rate_card.H200.on_demand | 14 | daytona 4.54, modal 4.54 | paperspace 4.47, nebius 5.4 |  |
| fastgpu_daily.neocloud_rate_card.L40S.on_demand | 10 | vultr 1.671, ovhcloud 1.8 | paperspace 1.57, verda 1.939 |  |
| fastgpu_daily.neocloud_rate_card.RTX_6000_Ada.on_demand | 3 | verda 1.528 | quantacloud 0.79, paperspace 1.57 |  |
| fastgpu_daily.neocloud_rate_card.RTX_A6000.on_demand | 5 | hyperstack 0.5 | quantacloud 0.48, verda 0.844 |  |
| fastgpu_daily.neocloud_rate_card.RTX_PRO_6000.on_demand | 12 | exoscale 2.153, quantacloud 2.17 | cloudrift 1.95, coreweave 2.5 |  |
| fastgpu_daily.neocloud_spot.A100_80GB.spot | 3 | verda 1.147 | hyperstack 1.08, coreweave 1.189 |  |
| fastgpu_daily.neocloud_spot.B200.spot | 4 | together 4.09, coreweave 4.264 | vultr 3.2, verda 4.524 |  |
| fastgpu_daily.neocloud_spot.B300.spot | 4 | coreweave 4.48, together 4.99 | daytona 4.08, verda 5.785 |  |
| fastgpu_daily.neocloud_spot.H100_SXM_80GB.spot | 6 | daytona 2.27, vultr 2.3 | together 1.99, coreweave 2.439 |  |
| fastgpu_daily.neocloud_spot.H200.spot | 4 | daytona 2.61, together 2.99 | coreweave 2.58, verda 3.188 |  |
| fastgpu_daily.neocloud_spot.L40S.spot | 3 | verda 0.97 | nebius 0.749, coreweave 0.985 |  |
| fastgpu_daily.neocloud_spot.RTX_PRO_6000.spot | 4 | verda 1.349, hyperstack 1.48 | coreweave 1.195, daytona 1.74 |  |
| gpurentalprices.marketplace_ask.H100_80GB.spot | 6 | lium 1.7, lium 2.05 | lium 1.55, spheron 2.2 |  |
| gpurentalprices.neocloud_rate_card.A100_40GB.on_demand | 7 | lambdalabs 1.99 | lambdalabs 1.99, lambdalabs 1.99 |  |
| gpurentalprices.neocloud_rate_card.A100_SXM_80GB.on_demand | 4 | hyperstack 1.6, crusoe 2.3 | massedcompute 1.38, verda 2.316 |  |
| gpurentalprices.neocloud_rate_card.B200.on_demand | 11 | lambdalabs 7.89 | lambdalabs 7.79, lambdalabs 7.99 |  |
| gpurentalprices.neocloud_rate_card.B300.on_demand | 10 | nebius 9.5, together 9.99 | crusoe 8.96, digitalocean 11.19 |  |
| gpurentalprices.neocloud_rate_card.H100_80GB.on_demand | 16 | runcrate 3.87, crusoe 3.9 | latitude 3.37, daytona 3.95 |  |
| gpurentalprices.neocloud_rate_card.H100_SXM_80GB.on_demand | 9 | scaleway 3.5539 | jarvislabs 3.49, lambdalabs 4.69 |  |
| gpurentalprices.neocloud_rate_card.H200.on_demand | 13 | jarvislabs 4.59 | daytona 4.54, runcrate 5.25 |  |
| gpurentalprices.neocloud_rate_card.L4.on_demand | 3 | scaleway 0.8839 | jarvislabs 0.44, ovhcloud 1.0 |  |
| gpurentalprices.neocloud_rate_card.L40S.on_demand | 10 | digitalocean 1.57, scaleway 1.6498 | crusoe 1.5, vultr 1.671 |  |
| gpurentalprices.neocloud_rate_card.RTX_6000_Ada.on_demand | 4 | runcrate 0.96, verda 1.543 | massedcompute 0.79, digitalocean 1.57 |  |
| gpurentalprices.neocloud_rate_card.RTX_A6000.on_demand | 8 | runcrate 0.57, verda 0.852 | massedcompute 0.57, lambdalabs 1.09 |  |
| gpurentalprices.neocloud_rate_card.RTX_PRO_6000.on_demand | 10 | massedcompute 2.19, runcrate 2.41 | jarvislabs 2.19, coreweave 2.5 |  |

## Forward search hits (eligible, effective 2026-10-30..2026-11-13)

| provider | published | effective | url | quote | new price already in 6 Nov rows | max abs pass-through % | flag (non-zero, not in rows) |
|---|---|---|---|---|---|---|---|
| verda | 2026-11-02 | 2026-11-02 | https://gpujournal.ai/story/verda-eighth-rise-nov-2 | What changed, read on verda.com/pricing on Nov 2, 2026 (unrounded page figures in brackets): GB300 $13.05 → $13.18 [$13.18], B300 $11.35 → $11.46 [$11.46], B200 | False | 0.0 | False |
| verda | 2026-11-04 | 2026-11-04 | https://gpujournal.ai/story/verda-ninth-rise-nov-4 | Verda raises prices for the ninth time — all nine GPUs up about 1% again / GPUJournal. What changed, read on verda.com/pricing on Nov 4, 2026 (unrounded page fi | True | 0.0 | False |
