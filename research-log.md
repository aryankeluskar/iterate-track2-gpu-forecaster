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
