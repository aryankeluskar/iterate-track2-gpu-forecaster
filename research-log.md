# Research log

## 2026-11-14 10:35 PT: bootstrap

- Track chosen provisionally: Track 2 (Pacific). This log supports the go/no-go decision due about 15:00.
- Starter demo reproduced locally: drift pooled skill +0.200 frozen at 2026-10-24, +0.173 over 15 weekly origins (all four horizons), +0.183 on horizons 1, 3 and 7.
- Exploratory, before the protocol was locked: drift with lookback 30, 60 and 120 days scored 0.057, 0.073 and 0.095 on the same 15 origins. Shorter windows for the change distribution hurt.
- 80 of 97 headline series at the 2026-10-24 cutoff are AWS spot tick series, which the brief says are not scored on Sunday.
- Evaluation protocol locked in EVAL_PROTOCOL.md.

### Charting assumptions (made in place of a grilling session)

1. Sunday's scorer covers posted rental series from `daily_statistics` only. To confirm with Pacific.
2. The headline tier as of 2026-11-06 is the primary universe. To confirm with Pacific.
3. Direction A (self-improving forecasts) is the default; B and C stay open until the go decision.
4. Local commits only, no push, until the team creates the public repo.

## 2026-11-14 10:45 PT: data profile in, protocol amended

- The scored universe is 37 series, and 33 of them start in August or September. The original May to August dev split saw 4 of them. Amended the splits (EVAL_PROTOCOL.md, Amendment 1) and committed before any method was scored.
- Dropped the internal test set: the pack is too short. Sunday's organiser scoring is the test.
- H1 (smoothed level) refuted on afhubbard by the profile, still open for the two newer collectors. H5 untestable. H7 unlikely.
- Priority is now H2 (state-dependent chance of a change) and H3 (pooling across series).

## 2026-11-14 10:50 PT: swarm launched

- Dev-period check on the 37 scored series (exploratory, orchestrator): a smoothed centre loses to the last value almost everywhere (loss-weighted error ratio 1.6 at h=1, 1.2 at h=3, 1.1 at h=7). H1 is refuted on the scored universe apart from two fastgpu A100 rate cards. fastgpu shows partial reversion at h=3 and h=7, gpurentalprices momentum; small samples.
- The scored series change on about a third of days, so the "rare step" picture from older afhubbard data does not transfer.
- User asked for breadth and speed. Nine method agents launched in parallel, dev split only, shared brief in experiments/AGENT_BRIEF.md: hazard (state-dependent hurdle mixture), gbm (pooled LightGBM quantiles), calib (online interval recalibration), foundation (TimesFM, Chronos), decision (up/flat/down classifier plus weight-space programming feasibility), hedge (online expert aggregation), centre (momentum and reversion), panel (provider-level model under the median), cross (cross-collector coupling).
- Validation is run only by the orchestrator, once per nominated method, with the query count logged.

## 2026-11-14 11:20 PT: session resumed (Devin), splits fixed, dev round 1

- The Claude Code session hit its usage limit right after launching the nine method agents; none reported. Left on disk: working `calib`, `gbm`, a `centre` module that crashes on short histories, protocols for hazard and cross.
- `src/gpuf/splits.py` still held the pre-amendment dates. Fixed to Amendment 1 (dev 08-18..10-06, val 10-13..10-30, old dev kept as `dev_old`). The four gbm rows logged at 10:42 to 10:43 in trajectory.jsonl were scored on the old dev range (17 series) and are superseded. No validation or test origin had been queried (val_query_log was empty of method runs).
- Drift on corrected dev, 37 series: pooled skill +0.0886, coverage 0.63. It falls back to flat on 2,722 of 4,278 dev cells (42% of baseline loss) because fastgpu and gpurentalprices have under 20 samples early on. On the cells where drift is live its skill is +0.153. Sunday's origin has 60+ days for every series, so the live cells are the relevant regime.
- New method `mix` (src/gpuf/methods/mix.py, protocol in experiments/mix/): weighted empirical mixture of own and peer-group h-day log changes, optional state conditioning and recency weights. Dev results, difference against drift with 90% interval:
  - pooling only (cc, k=20): +0.045 [+0.036, +0.059] overall, but 0.150 against 0.153 on live cells. Pooling fixes the fallback, nothing more.
  - plus state (changed within 3 days): +0.072 [+0.054, +0.086]; live 0.177.
  - plus recency (half-life 30 days): +0.081 [+0.057, +0.093]; live 0.192.
  - state without pooling: +0.004, live 0.134 (worse than drift). The state split needs pooled samples.
  - signed state (direction of the last move): worse than unsigned. H_direction refuted on dev.
  - centre = last instead of median: slightly worse at h=7, same at h=1/3. Width scale 0.8 to 1.5: flat optimum near 1 to 1.2.
  - pooling across a whole collector with state: unstable (+0.003, interval -0.117 to +0.055). Classes must not be mixed.
- gbm (pooled LightGBM quantiles, written by the interrupted agent), corrected dev: +0.053 [+0.001, +0.075]; live 0.185.
- Chronos-Bolt zero-shot: raw quantiles -0.050 (small), -0.037 (base). Keeping the last value as centre and only the model's width: +0.055 [+0.018, +0.104]; live 0.160. The centre is where it loses. H6 holds for the centre, not for the width.
- Ensembles (log-quantile average): mix + gbm +0.089 (live 0.210); three mix variants +0.100 [+0.071, +0.124] (live 0.219).
- Nearly all gain is at h=7. h=1 and h=3 gains are under 0.015 for every method.

### Validation plan (written before any validation query)

Budget: 4 method queries on rental_headline, frozen params, in this order. Rule from the protocol: 90% week-bootstrap interval of the difference against drift above zero. With 4 looks the per-look level is not adjusted in the interval; the count is reported beside every result. A secondary rental_all query is run only for a method that passes.
1. mix {"pool":"cc","k":20,"state":"chgk","sk":3,"hl":30}
2. ens of mix (1), mix dirk sk=7 hl=30, mix pool=all chgk sk=3 hl=30
3. ens of mix (1) and gbm full/all
4. chronos-bolt-small, centre=last

## 2026-11-14 12:10 PT — validation round 1 results, and a fifth query declared before running

Validation (13–30 Oct, headline, 1,816 cells), each of the four planned queries run once:
| method | skill | vs drift | 90% CI | pass |
|---|---|---|---|---|
| drift | 0.0845 | | | |
| mix cc k20 chgk3 hl30 | 0.1121 | +0.0276 | [-0.0055,+0.0511] | no |
| ens of 3 mix | 0.1266 | +0.0421 | [+0.0233,+0.0554] | yes |
| ens mix+gbm | 0.1538 | +0.0693 | [+0.0507,+0.0825] | yes |
| chronos-bolt-small centre=last | 0.2058 | +0.1214 | [+0.0711,+0.1569] | yes |

Dev/val rank order flipped (dev: 3-mix > mix+gbm > mix > chronos_last; val: the reverse). Read: "beats drift" is supported; the ranking between methods is not.
Dev secondary universe (rental_all, 40,338 cells): mix +0.041 [+0.020,+0.063]; mix+gbm +0.043 [+0.024,+0.062]; chronos_last +0.012 [-0.023,+0.062] (loses on neocloud_rate_card and afhubbard). Chronos_last alone is not robust across universes.
TimesFM 2.5 dev headline: raw -0.055, centre=last +0.061. Same pattern as Chronos (H6 holds for both).
Dev blends (headline / rental_all): mix+chronos_last +0.088 / +0.042; mix+gbm+chronos_last +0.093 [+0.073,+0.108] / +0.044 [+0.024,+0.071]; adding timesfm_last +0.090 (no gain).
Width diagnostic (dev, drift-live cells): q50 loss is the same for every method (0.333 of baseline); all gain is in q10/q90. Upper tail is under-covered at h=7 by every method (27–33% of truths above q90).

Query 5 (declared now, before running): ens of mix + gbm + chronos_last, equal weights. Caveat recorded up front: this query was added after seeing queries 1–4, and its members are the ones that did well there, so its validation number is optimistic and is not a clean test. It is run to pick the submission candidate, not as evidence.

## 2026-11-14 11:40 PT: session resumed in T3 Code, turn to failure-driven research

- Correction: the previous entry's header says 12:10 PT. The validation queries it reports ran 10:57 to 11:17 PT (val_query_log.jsonl, UTC stamps).
- Recorded from the interrupted session (dev headline, base mix +0.0805 over drift): H7 collector-wide breadth as a width signal, H8 gpurentalprices leading fastgpu, H9 reversal after a >5% move: every variant at or below the base, all refuted (runs/failure/sig_round1.txt). H10 Exa dated-headline burst widening q90: +0.0096 skill against the base, 90% interval [-0.004, +0.015], gain from one episode (runs/failure/news_vs_base.txt). Not significant; not sent to validation.
- Failure decomposition (runs/failure/decomp.txt): 52% of dev cells have no change; moves above 5% are 9% of cells and 61% of last-value loss; 10 of 50 origin days carry 56%. Hindsight bounds for the blend (0.182): knowing whether the price moves 0.219, direction 0.226, both 0.262. What remains is jump size.
- Direction set by the team: study the failure modes and aim changes at them, not sweep for skill.
- Verified by the orchestrator: the scored daily median is reproduced exactly from rental_observations (fastgpu 2,770 of 2,770 series-days to 6 Oct; gpurentalprices 99.94% of 7,193, misses are .5 rounding). Each jump therefore has an observable cause in the offer panel (a repriced offer near the middle, or offers entering or leaving).
- Round 2 launched, five agents, brief in experiments/AGENT_BRIEF_R2.md, dev only: autopsy (cause of every median change; failure taxonomy), panel (structural forecaster that simulates the offer panel), exa_attrib (were the repricings behind the largest misses announced in public before they hit the data), memory (past.dev client and plan; no data sent until the owner approves), longrun (2 to 3 year rental and resale view).
- wayfinder skill is not installed for this harness; the map in .scratch/ is maintained by hand.

## 2026-11-14 11:50 PT: round 3 breadth swarm, scored-set finding, safety-net submission

- Goal from the team: prototype fast across many directions. Ten more agents launched (brief in experiments/AGENT_BRIEF_R3.md, dev only): tail (online asymmetric tail recalibration), stack (online expert aggregation and quantile stacking), hazard (hurdle: move probability times jump size), decision (Laya decision model as the move classifier, against logistic regression), fm2 (pretrained time-series models round 2: width only, Chronos-2 group context and covariates, quantile levels), ecm (cross-instrument level gaps and other instruments as signals), wsp (weight-space programming of a tiny net, writer GPT-6 Astra, against the same net trained by gradient descent), analog (nearest-neighbour analogs), tabpfn (in-context tabular model), allrental (router for every posted rental series).
- Scored-set finding (orchestrator, read from starter/scorer.py): the scorer's default scored set is the series in the forecast file; the headline restriction applies only with --tier headline. On dev, rental_all has 357 scored series and 40,338 cells; the 37 headline series carry 9.4% of its last-value loss. drift scores 0.096 on rental_all and mix 0.137; on the non-headline part drift 0.097 and mix 0.134, with mix below the last value on hyperscaler_list (-0.037) and worse than the last value on 112 of 320 series. Decision: submit forecasts for every posted rental series (rows outside a --tier headline scope are ignored by the scorer), with a guard that returns the last value at zero width where nothing better is supported. Question sent to the team for Pacific's office hours.
- Safety-net submission v1 written: submissions/forecast_v1_blend3.csv, origin 2026-11-06, 37 headline series, 111 rows, blend of mix + gbm + chronos_last (the blend of validation query 5). Passes the starter schema check and the scorer's frozen-cutoff mode (scored_no_cells, no refusals). LightGBM and torch cannot share a process on this machine (duplicate OpenMP runtime), so the Chronos member is produced in its own process and replayed.

## 2026-11-14 11:53 PT: interim autopsy read, provider finding, round 4 launched

- Autopsy interim (experiments/autopsy/results, agent's numbers, not yet re-verified): 653 median changes on 2,446 day pairs; 86% repricing, 10% composition, 4% mixed; composition carries 28% of summed absolute log change and 40% of last-value error at h=1. Of the blend's loss on dev, 77% sits in cells where the truth fell outside [q10, q90].
- Orchestrator exploration (runs/orch/prov.py, offer rows on or before 2026-10-13, 33 headline series with a loaded panel): repricing is concentrated in a few providers. verda: reprices on 59% of offer-days on fastgpu_daily and 32% on gpurentalprices, 97% of them increases, mean daily log change rising week by week from 0.08% to 0.93%. scaleway 67% of days, spheron 45%, sfcompute 89%; nebius, digitalocean, crusoe, lambdalabs, hyperstack, coreweave under 1%. Bucketing (series, day) by the trailing 14-day reprice rate of the provider at the middle of the panel: static (under 2%) moves on 6% of days with mean absolute change 0.2% (h=1) and 1.4% (h=7); dynamic (over 50%) moves on 76% of days with 2.1% and 8.3%. Rank correlation of the middle provider's trailing signed change with the median's next change: 0.31, 0.36, 0.29 at h=1, 3, 7 (n 1,373 to 1,570). A naive centre shift by drift times horizon does not lower absolute error (0.0309 against 0.0308 at h=7): the median is an order statistic and stops at its neighbour.
- Exa probe by the orchestrator (3 searches, end published date 2026-08-17, $0.021): the mechanism has a public source: PRWeb, 2 August 2024, "DataCrunch.io Introduces Dynamic Pricing to Democratize GPU Computing for AI" (DataCrunch is now Verda): "the dynamic market price changes daily based on demand". A Verda digest dated 5 December 2025 says dynamic pricing is being phased out, which the 2026 offer data does not show; to be checked by the policy agent.
- Leak hazard found and closed: Exa returned an undated price-tracker page whose text covers dates after the pack's cutoff. Only its title line was printed; no value was read or used. Rule from now on: results without a published date on or before the origin are discarded, and price-tracker pages are never opened.
- Round 4 launched: prov (provider-specific signed dynamics simulated under the median, H24), midstate (middle-provider repricing state as the forecast state, H25), policy (Exa lookup of each provider's pricing policy as a prior, labelled blind to the measured rates, H26).

## 2026-11-14 12:00 PT: first round 2 reports; owner says go ahead without approvals

- autopsy (final report): H11 supported, H4 refuted. Composition is 10% of one-day changes and 32% of the blend's dev loss, mixed days 22%, Verda's steady increases 17.5%. Composition jumps do not revert; their size equals the one-offer fragility of the panel; their timing clusters by provider (60 events on 19 dates). Cross-check: the panel agent's independent count on 33 series gives 84% repricing, 6% composition, 10% both.
- exa_attrib (final report): H13 refuted as a general claim (2 of 37 events announced ahead), with one useful exception: rate-card repricings that are announced carry an effective date and a price (Nebius, Jarvislabs). That is exactly the input a panel simulator can apply. Exa Snapshot is not available on our plan.
- memory (final report): client, tests, API notes and plan written; key accepted, 550,000 credits. The owner approved and said not to wait on approvals. Agent memory-live launched: setup, 12-record test, full import of ledger, failure modes and evidence, shell commands for agents (recall, remember, sync-ledger, brief).
- New: calendar (H27, Exa-built calendar of announced dated repricings, checked against the panel, plus the entries that fall in the Sunday window) and fragility (H28, tails placed on the one-offer-out medians).
- to_human/progress.html: dotted target lines (reference model, the two hindsight bounds) and dotted milestone lines per round.
- Machine load is 25 on 15 cores with 21 agents; no further CPU-heavy launches until some finish.

## 2026-11-14 12:00 PT: panel and longrun reports

- panel (final): H12 not significant. Simulator alone 0.170 (+0.001 against mix), blend with mix 0.180 (+0.011, CI -0.002 to +0.040), upper tail unchanged. The agent's reason: up-moves over 5% in which a brand-new offer entered are 115 cells and 31% of last-value loss on the panel series; entry cannot be simulated from the panel's own history. Not nominated for validation. Loader src/gpuf/panel.py and its leak test are kept: prov, midstate and fragility build on it.
- longrun (final): H29 refuted by its own backtest (no-change beats the decay model over one year on 117 weekly-median series and on AWS spot). The write-up is conditional: 2026 is a shortage regime in which every on-demand median rose 15-82% a year, against a multi-year AWS spot decline of 31%/yr (H100) and 9.5%/yr (A100). Older chips rent at a premium per unit of work over B200/B300 (A100 2.30x, H100 1.78x), shrinking. Report: experiments/longrun/results/longrun.md. Not yet reviewed line by line by the orchestrator.
- Machine: load 87, swap 11.1 of 12.3 GB used. No new launches until agents finish.

## 2026-11-14 12:08 PT: four round 3 reports; machine thrash fixed

- analog (H21 supported on dev, nominee pending the orchestrator's re-run), stack (H15 not significant: equal weights), ecm (H19 refuted), allrental (H23: routing over-fits, the activity gate carries over). Details in the ledger.
- Machine: load reached 130 with swap full. Cause: the Laya fine-tune process at 7.2 GB (over its limit) on a 24 GB machine with the browser holding several GB. Killed that process and told the decision agent to fine-tune only a head on cached embeddings under 3 GB or skip it. Cancelled the tabpfn agent (heaviest job, lowest expected gain; H22 marked untestable, not a result about the method). Load fell to about 50 within a minute.
- Orchestrator gate script added: experiments/halves.py (Amendment 2, rule 1: difference against mix overall and on both halves of dev).

## 2026-11-14 12:13 PT: analog passes the dev gate; validation query 6 declared before running

- Orchestrator re-run (experiments/halves.py): analog {pool all, k 600, drop n14 and sign} dev 0.1987, +0.0296 against mix [+0.009,+0.061], matching the agent. Blend of mix and analog: 0.1999, +0.0307 [+0.017,+0.053]; first half +0.034 [+0.005,+0.070], second half +0.030 [+0.015,+0.056]. Passes rule 1 of Amendment 2. Caveat: with all features the first half alone is -0.063 for analog by itself; the feature drop was chosen on dev, so the blend is the claim, not analog alone.
- Declared, query 6 on validation headline (first of the 8 in Amendment 2's budget): ens of mix (reference params) and analog {"pool":"all","k":600,"drop":["n14","sign"],"cap":"2026-11-06"}, against mix. The cap is moved from the dev cap only so the neighbour table can hold outcomes up to each validation origin; each origin still uses only situations whose outcome day is on or before it.
- Result, query 6: blend of mix and analog 0.1340 against mix 0.1121 on validation headline (1,816 cells): +0.0219, 90% CI [+0.0068,+0.0433], one-sided DM p=0.031. drift 0.0845. By horizon: h=1 -0.0001, h=3 +0.0070, h=7 +0.0150. By collector: fastgpu +0.0132, gpurentalprices +0.0106, afhubbard -0.0019. First direction of rounds 2 to 4 to hold on validation. Budget used: 1 of 8.

## 2026-11-14 12:18 PT: round 3 and 4 reports; prov and fm2 pass the dev gate; queries 7 and 8 declared

- Reports in: tail (H14: the upper-tail gap is one multi-week regime, 0.11 above q90 in the first half of dev and 0.33 in the second; conformal q90 correction +0.023 on mix but -0.006 in the first half; not nominated), decision (H17 refuted: Laya zero-shot is below the base rate even after temperature refit, log loss 1.105 against 0.760; logistic regression 0.562, LightGBM 0.491; fine-tune not completed), fm2 (H18), wsp (H20), prov (H24), policy (H26 refuted as a prior), calendar (H27 supported). Details in the ledger.
- Orchestrator re-run on dev headline (experiments/halves.py, against mix 0.1691):
  - prov {L 1, W 21, gate dyn}: 0.2083, +0.039 [+0.013,+0.087]; first half +0.009 [-0.007,+0.029], second +0.046 [+0.016,+0.116]. q50 loss 0.966 of mix's. With W 14 the first half is negative (-0.014), so the window choice matters and was made on dev.
  - blend mix + prov: 0.1973, +0.028 [+0.015,+0.053]; halves +0.008 [-0.002,+0.019] and +0.033 [+0.018,+0.070]. Positive in both halves; passes rule 1 on the point estimates, weakly in the first half.
  - fm2 (Chronos-Bolt-small, 16 days of context, lower level 0.15) alone: 0.1670, -0.002; blend mix + fm2: 0.1899, +0.021 [+0.010,+0.044]; halves +0.044 [+0.017,+0.074] and +0.016 [+0.004,+0.041]. Passes rule 1.
  - blend of mix + fm2 + analog + prov: 0.2131, +0.044 [+0.029,+0.076]; halves +0.049 and +0.043, both intervals above zero.
- Declared, query 7 on validation headline: ens of mix and prov {"L":1,"W":21,"gate":"dyn"}, against mix.
- Declared, query 8 on validation headline: ens of mix and fm2_live {"ctx_len":16,"lo":0.15} (the model run live on the validation origins; same forecasts as the cached-grid method on dev), against mix.
- Results (data_out/val_gate.jsonl), validation headline, 1,816 cells, mix 0.1121, drift 0.0845:
  - Query 7, mix + prov: 0.1845, +0.0724 [+0.0589,+0.0868], one-sided DM p<0.001. h=1 +0.005, h=3 +0.017, h=7 +0.051; fastgpu +0.047, gpurentalprices +0.026.
  - Query 8, mix + fm2: 0.1698, +0.0577 [+0.0391,+0.0795], p<0.001. h=1 -0.005, h=3 +0.011, h=7 +0.052; fastgpu +0.052, gpurentalprices +0.007.
  - With query 6 (p=0.031) all three pass Benjamini-Hochberg at 10%. Kept so far: analog, prov, fm2. Budget used: 3 of 8.

## 2026-11-14 12:22 PT: round 5 launched

- hazard (H16 refuted: whether a price moves is predictable, AUC 0.83; direction is not, AUC 0.54; the hurdle forecaster loses to mix) and midstate (H25 not significant: the middle-provider state as a lookup key ties mix; the same information simulated, as in prov, wins).
- Round 5, six agents at most at once after the thrashing incident: prov follow-up (Exa calendar inside the simulator, marketplace fixes, synthetic trend-reversal stress test); final (the rule-based blend for every posted rental series behind one command, leave-one-out on rental_all, gate decision); autopsy2 (iteration 2 failure analysis: loss by cause across drift, mix, the earlier blend and the current blend; H31); entry (H30); insight (economic section: index quality per series, robust statistics, announced changes). Still running from before: fragility, memory go-live.

## 2026-11-14 12:31 PT: fragility passes the dev gate; validation query 9 declared before running

- fragility (final report, H28): tails get mass at the origin-day panel's one-offer-out and one-offer-in medians, with the membership hazard raised 20 times for a provider that changed any of its other series in the last 3 days. The agent measured the clustering on dev: after a provider's entry or exit on one series, the chance of another on a different series of the same collector within a day is 0.102 (118 of 1,156) against a base of 0.0036 (90 of 25,006).
- Orchestrator re-run on dev headline: fragility {mode mix, boost 20, bkind any} over mix 0.1924, +0.0232 against mix [+0.011,+0.045]; first half +0.049 [+0.013,+0.094], second +0.018 [+0.001,+0.038]. Passes rule 1. Boost 10: +0.017, second half +0.010 [-0.004,+0.014]. The boost was chosen on dev.
- On top of the current blend it adds little on dev: mix + fm2 + analog + prov 0.2133; with fragility as a fifth member 0.2164; fragility wrapped around that blend 0.2134 (boost 20) and 0.2165 (boost 10). The causes overlap with what prov and analog already cover.
- Declared, query 9 on validation headline: fragility {"mode":"mix","boost":20,"bkind":"any"} with base mix (reference params), against mix. The wrapper is mix plus the direction, so it is tested as it stands, not blended again.
- Result, query 9: fragility over mix 0.2190 against mix 0.1121 on validation headline: +0.1070, 90% CI [+0.0523,+0.1522], one-sided DM p=0.008. h=1 +0.001, h=3 +0.023, h=7 +0.084; fastgpu +0.090, gpurentalprices +0.017. Upper-tail exceedance at h=7 0.14. The largest single gain on validation so far. All four queries of this round pass Benjamini-Hochberg at 10% (p = 0.031, <0.001, <0.001, 0.008). Kept: analog, prov, fm2, fragility. Budget used: 4 of 8.

## 2026-11-14 12:34 PT: prov follow-up; past.dev live

- past.dev (final report from the go-live agent): 3 audiences, 6 identities, 119 records at import, six test questions pass including the forecaster's access and date-bound checks; 347 credits used. The orchestrator then synced the ledger, wrote the 8 calendar entries as scout evidence dated by publication, and ran a live proposer briefing. experiments/AGENT_BRIEF_R5.md tells later agents to brief from memory before their protocol and to write their verdict back.
- prov follow-up (orchestrator re-run, dev headline, against prov 0.2089): calendar on 0.2827 (+0.074 [0.000,+0.100], first half exactly 0, second +0.089); no return of absent marketplace offers 0.2179 (+0.009 [0.000,+0.016]); both 0.2917. The gain from the calendar is two events and in-sample for the lag. Trend-reversal stress test: prov stays ahead of mix by +0.033 to +0.035 pooled under stop, reversal and mirrored paths.
- Decision: the validated prov configuration {L 1, W 21, gate dyn} is not changed. The calendar switch may be turned on in the submitted run only if the forecast for origin 2026-11-06 is identical with it on and off (no entry takes effect before the last target date); to be checked on the forecast file, where no truth is involved.

## 2026-11-14 12:36 PT: entry, autopsy2 and insight reports

- entry (H30 not significant): the footprint flags are real (17.5 times for a provider listing the same GPU on the other collector) but the base rate is so low that the forecaster built on them does not beat prov at the measured rates. Not nominated.
- autopsy2 (H31 supported): loss by cause across four systems is in experiments/autopsy2/results/loss_by_cause.csv with a figure. What remains in the current blend: offers entering 29%, dynamic repricing 16%, announced one-offs 14%, marketplace 11%, unannounced one-offs 10%, offers leaving 10%. Note for the blend rule: the six-member blend (with gbm and the long-context Chronos) is 0.2036 on dev against 0.2133 for mix + fm2 + analog + prov. The final agent's leave-one-out on both universes decides whether the rule's exception applies.
- insight (economic section, experiments/insight/results/insight.md; descriptive, uses panel facts up to 2026-11-06, no forecast accuracy after 13 Oct): 5 of 37 scored series pass every robustness test on 6 Nov; 25 move more than 5% if one offer or provider is removed; the two collectors' 7-day disagreement is 0.048 log on posted medians and 0.005 on the same static offers; about a third of static rate-card providers raised H100 and H200 prices and none cut.
- Correction to the calendar from the insight agent: Lambda's rates announced as effective 16 November are already in the gpurentalprices panel on 6 November, and on fastgpu Lambda does not hold a middle offer. So the entry's effective date is wrong for that collector and the announcement does not move the fastgpu medians. Consequence for the submitted run: none through the calendar switch (the price is already in the origin-day panel). It does support H33 (registered): offer-level changes reach gpurentalprices a day before fastgpu.

## 2026-11-14 12:38 PT: Amendment 3; H33 refuted by measurement; round 6

- EVAL_PROTOCOL.md Amendment 3 committed before any multi-member blend was scored on validation: membership of the submitted blend is decided on dev by leave-one-out on both universes; switches added after a member's validation stay off unless they leave the Sunday forecast unchanged.
- H33 (a static provider's change reaches gpurentalprices a day before fastgpu) measured by the orchestrator before building anything and refuted: same-sign move on fastgpu the next day in 33% of 24 cases; standing price gaps between collectors for the same provider do not close (neither side moves within 3 days in 80% of 470 cases).
- Round 6: hyper (provider simulator for the afhubbard hyperscaler panels, under a 3 GB limit; first agent briefed from the shared memory) and loop (one CLI per step of the research loop with Exa and past.dev in the path, plus one recorded iteration). Still running: final.

## 2026-11-14 12:41 PT: mapping the work to the four judging criteria

The team's instruction: make sure of a win in Track 2. The brief's criteria are rigour, useful economic insight, reproducibility and originality, and its headline question is the 2 to 3 year view. Three agents launched against the gaps:
- audit (rigour): an independent referee told to break the evaluation: bit-identical forecasts under deletion and corruption of all rows after the origin for every kept method, caches across origins, static catalog fields computed over the full history, the universe chosen as of 6 November, the fast scorer against the organisers' scorer, the week-block bootstrap with 8 and 3 weeks, the validation log against git commit times, and the ledger's ten main claims against their files. It may not run validation and may not change code.
- longrun version 2 (the headline question): panel-robust inputs, explicit scenarios with probabilities (shortage persists, eases to trend, successor glut), backtests of what can be backtested including year-end projections on the four-year AWS spot history, resale by income approach with a lender's loan-to-value view and a depreciation schedule.
- rules: the exact submission requirements, deadlines and artefacts for the hackathon, Track 2, Exa and past.dev, read from the hackathon page through the team's browser.
Running besides: final (reproducibility: one command, every posted rental series, membership by Amendment 3), hyper, loop (originality and the sponsors: the loop as commands with Exa and past.dev in the path).

## 2026-11-14 12:44 PT: submission requirements read

- experiments/submission/requirements.md (read from the hackathon page in the team's browser, new tab, nothing submitted). Hard deadline taken as Sunday 15 Nov 14:00 PT (the page also says 14:30). Required: public GitHub repo with no commits before the event (this repo's first commit is 14 Nov 10:31 PT), a 2-minute demo video, a short description, one track plus challenges; Track 2 adds the forecast CSV for origin 2026-11-06, one reproduce command and findings. Round 1 pitch 3 minutes plus 2 of questions at 14:45; finals 3 minutes with a live demo.
- Overall judging, five criteria at 20% each: research rigour; novelty; results (a measurable result against a baseline, a working live demo); autonomy and self-improvement (how much of the loop runs without a human; extra credit if it improves from its own results); interpretability and reproducibility (logs, traces, sources; failures reported honestly). Track 2 adds useful economic insight.
- Secret scan by the orchestrator: neither API key value appears in any tracked file or in git history. Tracked content is 41 MB in 1,733 files.
- Not done and needs the team: creating the public repository and pushing (nothing has been pushed), joining the platform by Sunday 12:00, recording the video.

## 2026-11-14 12:46 PT: final blend built; its two validation looks declared before running

- final (agent report, checked by the orchestrator): `bash reproduce.sh final` runs in 25 s here and gives the same SHA-256 as the agent's two runs (all series d144025579fa..., headline 874522fc0c17...); 1,776 rows for 592 series, 249 with zero width (235 by the gate), headline file 111 rows; both pass the starter schema check and the frozen-cutoff scorer with no refusals. Dev: headline 0.208 against mix 0.169 (+0.039 [+0.025,+0.068]; halves +0.052 and +0.036); rental_all with the non-headline gate 0.164 against mix 0.137 (+0.027 [+0.007,+0.057]; halves +0.056 and +0.015). Leave-one-out under Amendment 3 drops no member (gbm misses by -0.0005 on one of four cells). Gate [14, 1] on non-headline series only. hyperscaler_list stays below the last value (-0.034).
- The seven-member blend is below the four-member blend without gbm and the long-context Chronos on dev headline (0.208 against 0.213 to 0.216). The rule keeps them; that is the price of not choosing members on the number we want to report.
- Orchestrator built the pretrained members' files for the 18 validation origins (runs/final/*_val_rental_all.parquet; forecasts only, nothing scored). src/gpuf/final_build.py refuses validation origins unless GPUF_ORCHESTRATOR=1.
- Declared, Amendment 3 rule 4, each run once: (a) query 10, `final` {"gate":[14,1],"gate_scope":"nonhead","cap":"2026-11-06","tag":"val","universe":"rental_all"} with all seven members on validation headline against mix; labelled optimistic because four members were kept on this period. (b) the same forecaster on the non-headline posted rental series on validation against mix: the first evaluation of any kind on those cells.
- Results (data_out/val_gate.jsonl), each run once:
  - Query 10, final blend on validation headline (1,816 cells): 0.2141 against mix 0.1121 and drift 0.0845. +0.1021 over mix [+0.0914,+0.1139]; +0.1297 over drift [+0.098,+0.152]. Coverage of [q10,q90] 0.80; 11% above q90 at h=7. h=1 0.000, h=3 +0.024, h=7 +0.078 against mix. Optimistic by construction, and slightly below fragility alone (0.2190), which is reported and changes nothing.
  - Query 11, the same forecaster on the non-headline posted rental series (22,390 cells; first evaluation of any kind on these cells): 0.2276 against mix 0.1777 and drift 0.1021. +0.0499 over mix [+0.0411,+0.0569]; +0.1255 over drift [+0.115,+0.134]. Coverage 0.85. Gains on afhubbard +0.010, fastgpu +0.017, gpurentalprices +0.025; cheapest -0.001.
  - Validation budget of Amendment 2: 4 direction queries used of 8, plus these two looks under Amendment 3. No further validation runs are planned for the submitted forecaster.

## 2026-11-14 12:51 PT: hyper report

- hyper (H35 refuted for spot, zero width confirmed for list): the provider simulator does not transfer to the hyperscaler panels; independent offer moves cancel across 450 offers. Hyperscaler list prices never reprice; their median moves only when an offer enters or leaves (14 of 1,152 series-days), so any interval width is paid for on the other 99% of cells. The submitted blend's gate already gives those series zero width. Submitted forecaster unchanged.
