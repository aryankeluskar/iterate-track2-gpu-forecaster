# Findings: forecasting posted GPU rental prices by modelling the offers under the median

Iterate AI Research Hackathon, Track 2 (Pacific Machines), Direction A, with the Exa and past.dev challenges. This file supersedes the early working note `findings.md`. Every number below is copied from a file in the repository; the list with sources is `experiments/writeup/numbers.md`.

## 1. The question and the answer in five lines

The question has two parts. First, can a loop that tests hypotheses against its own forecast failures beat the starter `drift` baseline, with calibrated intervals, on posted GPU rental prices 1, 3 and 7 days ahead, on dates it had not used? Second, what will H100 and A100 rentals and resale be worth in 2 to 3 years?

1. A posted rental median is the middle of a small panel of 3 to 17 provider offers. It moves only when an offer near the middle is repriced or an offer enters or leaves. Forecasting that panel, rather than the series, produced the gains.
2. On the 18 validation origins the submitted blend scored 0.2141 pooled skill against 0.0845 for drift on the 37 scored series, and 0.2275 against 0.1021 on 22,390 cells of the other posted rental series.
3. Those numbers are optimistic. Part of the blend's membership was chosen on the validation period, the 37-series universe was chosen with hindsight, and an independent audit found that only two of the four directions added after the first round survive a correctly sized test.
4. Rents in 2 to 3 years: the H100 static rate-card median is 3.49 USD per GPU-hour today and 2.31 (1.21 to 4.17) at +24 months; the A100 is 2.35 today and 1.81 (1.01 to 3.05). No method beat "no change" in any long-horizon backtest, so these are ranges with stated assumptions, not forecasts with demonstrated skill.
5. The most usable economic finding: 32 of the 37 scored medians fail at least one index-quality test, and 25 of them move more than 5% if one offer or one provider is removed.

## 2. Method

**Terms.** An *offer panel* is the set of posted offers (provider, region, SKU, GPU count) behind one series on one day; the scored daily median is reproduced from it, within half a cent, on 100% of 2,483 series-days checked. *Pinball loss* is the quantile loss at 0.1, 0.5 and 0.9, averaged over each (series, origin, horizon) cell. *Pooled skill* is 1 minus total loss over total last-value loss across all cells, the organisers' headline. *Drift* is the starter baseline: the last value scaled by the 0.1, 0.5 and 0.9 quantiles of the series' own historical h-day log changes. The *development period* (dev) is the 50 origin days from 18 August to 6 October 2026, free to inspect; the *validation period* is the 18 origin days from 13 to 30 October, in 3 ISO weeks, where every query is declared, counted and logged. *mix*, the reference model from iteration 1, is a pooled, state-conditioned empirical mixture of h-day log changes.

**Declared targets.** Instrument class: posted rental prices from `daily_statistics` (neocloud rate cards, neocloud spot, marketplace asks, hyperscaler spot and list prices), never spliced across classes. A series is the daily median, in USD per GPU-hour, of the offers posted by one collector for one GPU model, pricing tier and instrument class. Origin 2026-11-06; horizons 1, 3 and 7 days. The primary universe is the 37 headline-tier series as of 6 November (20 fastgpu, 13 gpurentalprices, 4 afhubbard); the submission file covers all 592 posted rental series. AWS spot tick series and horizon 30 are excluded because they are not scored on Sunday.

**Protocol.** `EVAL_PROTOCOL.md` was locked before any method was scored and amended three times, each time before the affected data was queried. Forecasters receive histories truncated at the origin. A direction is nominated for validation only if, on dev, its blend with mix beats mix with the 90% week-bootstrap interval above zero and gains in both halves of dev (Amendment 2). At most 8 validation queries, one per direction, with frozen parameters; false discovery rate 10% by Benjamini-Hochberg on one-sided Diebold-Mariano p-values. The submitted forecaster is fixed by rule: the equal-weight mean of log quantiles of every validated member, with membership decided by leave-one-out on dev (Amendment 3). The pack is too short for an internal test set; Sunday's scoring is the test.

**The loop.** Forecast, attribute the loss to physical causes, hypothesise, test on dev dates, gate on validation dates, record in `data_out/ledger.jsonl` and `research-log.md`. The ledger holds 37 hypotheses: 13 supported, 15 refuted, 7 not significant, 2 untestable. Hypotheses and forecasters were written by LLM research agents, launched in six rounds by an orchestrator agent that was directed by a human. Since round 6 the steps `autopsy`, `scout`, `prior`, `propose`, `gate`, `forecast` and `status` exist as commands (`python -m gpuf.loop`); one iteration was recorded with them (`experiments/loop/iteration3.md`). Still done by hand by agents or the human: writing a hypothesis or forecaster, choosing what to gate, declaring and running validation queries, checking calendar lines the scout adds, and writing the log. In its recorded run the loop pointed at the largest residual cause and did not write a hypothesis.

## 3. What the system learned, iteration by iteration

**Iteration 1: a reference model and the first failure analysis.** A smoothed level loses to the last value (H1 refuted). Pooling change distributions across series (H3) and conditioning them on whether the series changed recently (H2) gave mix, +0.0805 over drift on dev. Pretrained time-series models lose with their own quantiles (Chronos-Bolt -0.050, TimesFM -0.055 against drift) but help when the last value is kept as the centre and only their width is used (H6). On validation, mix alone did not pass against drift (+0.0276, week-bootstrap range -0.0055 to +0.0511). The first failure analysis found that 52% of dev cells have no change, moves above 5% are 9% of cells but 61% of last-value loss, and, on cells where drift is live, the median (q50) loss was the same for every method: all gain came from the tails. Hindsight bounds put knowing whether the price moves at 0.219 and knowing its direction at 0.226, against 0.182 for the blend then.

**Iteration 2: the offer panel under the median.** Because the median is reproducible from offers, every jump has an observable cause. Of 579 one-day median changes, 86% were repricing, 10% composition (offers entering or leaving) and 4% mixed. Composition changes were 10% of changes but 32% of the blend's dev loss, rarely reverted (5.6% of 162 fastgpu exits returned within 7 days), and had the size of the panel's one-offer fragility (correlation 0.88, n=60). Repricing is concentrated in a few providers: Verda repriced on 59% of its fastgpu offer-days, 97% of them increases, while Nebius, Lambda, CoreWeave and others repriced on under 1%. Four directions followed. A *provider simulator* (prov, H24) moves each offer by its own provider's recent signed changes and lets the order statistics cap the median; it was the first method with median loss below the last value (0.95 of it). *Fragility tails* (H28) put tail mass on the one-offer-out and one-offer-in medians. *Analogs* (H21) use nearest-neighbour situations from the whole pack. *Pretrained widths* (fm2, H18) use Chronos-Bolt-small on 16 days of context; its width tracks recent volatility (elasticity 1.02 to 14-day volatility). A first panel simulator with pooled symmetric reprices was not significant (H12), because brand-new entrants cannot be simulated from a panel's own history.

**Iteration 3: residual loss by cause.** The second failure analysis attributed dev loss to causes for four systems ([figure](experiments/autopsy2/results/loss_by_cause.png)):

| cause | cells | share of last-value loss | drift | mix | mix+gbm+Chronos | six-member blend |
|---|---|---|---|---|---|---|
| dynamic repricing | 1027 | 0.2047 | 0.8087 | 0.6283 | 0.6719 | 0.6122 |
| announced one-off | 52 | 0.1269 | 0.9517 | 0.8541 | 0.8681 | 0.8541 |
| unannounced one-off | 195 | 0.0983 | 0.9729 | 0.8563 | 0.8396 | 0.8257 |
| offer enters | 236 | 0.2785 | 0.9563 | 0.9070 | 0.8537 | 0.8409 |
| offer leaves | 125 | 0.0875 | 0.9728 | 0.9650 | 0.9382 | 0.9427 |
| marketplace ask | 124 | 0.1359 | 0.8129 | 0.7135 | 0.6243 | 0.6209 |
| hyperscaler spot | 308 | 0.0683 | 0.7517 | 0.6984 | 0.6823 | 0.6954 |
| total (4,278 cells) | 4278 | 1.0 | 0.9114 | 0.8309 | 0.8182 | 0.7964 |

Entries are loss as a fraction of last-value loss on dev headline; lower is better. The six-member blend is mix, gbm, Chronos width, fm2, analog and prov; the submission adds fragility. The kept changes cut loss mainly where they were aimed (dynamic repricing, marketplace asks). Offers leaving are handled worst. Of the remaining loss, offers entering are 29% and dynamic repricing 16%. Then tried and not kept: an entry model (H30), a hyperscaler-panel simulator (H35), a cross-collector lead (H33), and an Exa repricing calendar inside prov, which is in-sample and off in the submission (section 6). The rule-fixed seven-member blend scores 0.2079 on dev, below the four-member blend of mix, fm2, analog and prov (0.2131); the rule kept every member, which is the cost of not choosing members on the reported number.

## 4. Results with uncertainty

**Development period, 37 headline series, 4,278 cells.** Intervals are 90% week-bootstrap intervals over 8 ISO weeks. They are in-sample for each direction's parameters, which were chosen on dev.

| system | dev skill | difference against mix | first half / second half |
|---|---|---|---|
| drift | 0.0886 | -0.0805 [-0.093, -0.057] | |
| mix (reference) | 0.1691 | | |
| mix + analog | 0.1999 | +0.0307 [+0.017, +0.053] | +0.034 / +0.030 |
| mix + prov | 0.1973 | +0.028 [+0.015, +0.053] | +0.008 / +0.033 |
| mix + fm2 | 0.1899 | +0.021 [+0.010, +0.044] | +0.044 / +0.016 |
| fragility over mix | 0.1924 | +0.0232 [+0.011, +0.045] | +0.049 / +0.018 |
| submitted blend (7 members) | 0.2079 | +0.0388 [+0.025, +0.068] | +0.0516 / +0.0361 |

**Validation period, 37 headline series, 1,816 cells; mix 0.1121, drift 0.0845.** Validation has 3 ISO weeks, so the week bootstrap has 10 distinct resamples: its ranges are the spread of the worst and best week, not 90% intervals. The logged one-sided Diebold-Mariano p-values are anti-conservative on 18 days (true size 10 to 18% at a nominal 5%); the audit's simulated p-values (Gaussian / block bootstrap) are beside them.

| query | system | skill | difference against mix | week-bootstrap range | logged p | simulated p | coverage |
|---|---|---|---|---|---|---|---|
| 6 | mix + analog | 0.1339 | +0.0218 | +0.0067 to +0.0433 | 0.0314 | 0.135 / 0.158 | 0.75 |
| 7 | mix + prov | 0.1845 | +0.0724 | +0.0588 to +0.0868 | below 1e-9 | 0.005 / 0.006 | 0.758 |
| 8 | mix + fm2 | 0.1698 | +0.0577 | +0.0390 to +0.0796 | below 1e-5 | 0.004 / 0.006 | 0.783 |
| 9 | fragility over mix | 0.2190 | +0.1069 | +0.0523 to +0.1522 | 0.0085 | 0.051 / 0.077 | 0.810 |
| 10 | submitted blend | 0.2141 | +0.1020 | +0.0913 to +0.1139 | not simulated | | 0.797 |
| 11 | submitted blend, non-headline (22,390 cells; mix 0.1777, drift 0.1021) | 0.2275 | +0.0499 | +0.0411 to +0.0569 | not simulated | | 0.845 |

Against drift the submitted blend gains +0.1296 on headline (range +0.0979 to +0.1521) and +0.1255 on the non-headline series (+0.1145 to +0.1341). Query 11 is the least contaminated number we have: those cells were never evaluated before.

**The audit's corrected reading.** With the simulated p-values, Benjamini-Hochberg at 10% keeps prov and fm2; fragility is borderline and analog is not significant on validation alone. Read strictly, Amendment 2 would not have kept analog and fragility; they remain in the blend because the dev leave-one-out kept them, a deviation that rests on dev evidence. The headline numbers are optimistic for three further reasons: gbm and Chronos width entered the blend through Amendment 2, written after they won validation round 1; under the organisers' tier rule applied at each origin, dev holds 4 to 15 headline series, and mix's margin over drift falls from +0.080 on the fixed 37 to +0.033; and later rounds were designed after seeing round 1's validation results. Query 5's declaration was committed 32 seconds after its result was logged, and its result (0.1967) was missing from the log until the audit.

**Calibration.** Coverage of [q10, q90] is 0.797 on validation headline and 0.845 on the non-headline series (target 0.8), but the misses are one-sided: 11% of truths fall above q90 at h=7 on validation headline. On dev the six-member blend has 22.5% of truths above q90 at h=7, and 56.8% of its loss comes from truths above q90.

**One origin.** Over the 50 dev origins taken singly, the blend's pooled skill has median 0.215 (10th percentile 0.114, minimum -0.231); it beats drift on 46 and falls below the last value on 2 (drift does on 7). Neighbouring origins overlap, so these are not 50 independent trials.

**What Sunday's score can and cannot show.** It is one origin and one week of targets. It can show whether the blend beats drift on a week no one has seen; on dev it failed to on 4 of 50 single origins. It cannot rank the members, cannot test the long-run view, and depends on whether Pacific scores all 592 series or only the 37 headline series (both are covered in the file).

## 5. Negative results

| id | hypothesis | result |
|---|---|---|
| H1 | a smoothed level beats the last value as centre | refuted: error ratio 1.6 (h=1) to 1.1 (h=7) |
| H4 | composition jumps revert | refuted: 5.6% of fastgpu exits return within 7 days |
| H7, H7b | other collectors lead; collector-wide breadth sets the width | refuted: every variant at or below the base |
| H9 | moves above 5% partly reverse within 7 days | refuted: -0.001 and -0.003 |
| H10 | a burst of dated price-rise headlines (Exa) precedes up-jumps | not significant: +0.0096 [-0.004, +0.015], gain from one episode |
| H12 | panel simulator with pooled symmetric reprices | not significant: blend +0.011 [-0.002, +0.040] |
| H13 | large repricings are announced before they hit the data | refuted: 2 of 37 events |
| H14 | the h=7 upper-tail gap is stable and recalibration fixes it | refuted: above-q90 rate 0.110 then 0.330 within dev |
| H15 | stacking with learned weights beats equal weights | not significant: +0.0037 [-0.002, +0.007] |
| H16 | hurdle model (move probability times jump size) | refuted: 0.108 against mix 0.169; direction AUC 0.54 |
| H17 | the Laya text decision model classifies up/flat/down | refuted: log loss 1.105 against 0.562 for logistic regression |
| H19 | cross-instrument level gaps close; indices as signals | refuted: slope +0.005 per unit z |
| H20 | weight-space programming of a tiny net by a frontier model | not significant: blend 0.172 against mix 0.169 |
| H22 | in-context tabular model | untestable: stopped for machine load |
| H25 | the middle provider's state as a lookup key | not significant: 0.167 against 0.169 |
| H26 | Exa pricing-policy labels as a prior on reprice rates | refuted: a constant zero beats the label |
| H29 | age-decay projection of rents | refuted: no-change error 0.42 against 0.66 |
| H30 | entries predictable from a provider's footprint elsewhere | not significant: -0.011 against prov at measured rates |
| H33 | gpurentalprices leads fastgpu by a day | refuted: same-sign next-day move in 33% of 24 cases |
| H35 | the provider simulator transfers to hyperscaler panels | refuted: loses to mix, -0.039 |
| H36 | the scenario mixture gives skilful 1 to 2 year ranges | not significant: no centre beat no-change |
| H37 | the evaluation is leak-free and correctly sized | refuted by the audit (section 9) |
| H5 | trailing days are revised upstream | untestable: one data vintage |

Also refuted on dev without a ledger number: signed state (direction of the last move), pooling across a whole collector, and routing methods by instrument class (over-fits; H23 kept only its activity gate).

## 6. What search contributed (Exa) and what it did not

Exa supplied the dated public record that the price data lacks. Its main product is a calendar of announced repricings with effective dates (9 entries; `data_out/repricing_calendar.jsonl`), built from 463 searches with end published dates on or before 6 November; price-tracker pages were discarded unopened, and a forecaster may use an entry only from its publication date. On dev, 17 of 17 checkable offers moved to the announced price. Inside prov the calendar raises dev skill from 0.2089 to 0.2827, but all of it comes from two events (Nebius, Jarvislabs) and the collector lag was read off the same events, so it is an in-sample upper bound; it cannot be checked on validation, where no announced change takes effect. The switch is off in the submission; the only entry inside the Sunday window (Lambda, effective 16 November) takes effect after the last target and is already in the 6 November gpurentalprices panel. The submitted forecast therefore does not depend on Exa output. Exa also refuted three ideas (H10, H13, H26), supplied the dated news behind the long-run scenarios, and in the loop's prior-work step found nothing close to the fragility claim. Exa's published date does not prove a page's text is unchanged (Snapshot is not on our plan). Total Exa spend: $7.62.

| date | title | link |
|---|---|---|
| 2024-08-02 | DataCrunch.io Introduces Dynamic Pricing to Democratize GPU Computing for AI (DataCrunch is now Verda, the main daily repricer) | https://www.prweb.com/releases/datacrunchio-introduces-dynamic-pricing-to-democratize-gpu-computing-for-ai-302212007.html |
| 2026-09-16 | Nebius raises GPU prices 20% as supply tightens | https://www.thefivenines.com/data-ai/nebius-raises-gpu-prices-20-as-supply-tightens |
| 2026-09-24 | New GPU rates from October 5, 2026, Jarvislabs Updates | https://jarvislabs.ai/updates/gpu-pricing-october-2026 |
| 2026-09-01 | Upcoming SaladCloud Price Changes: September 12, 2026 | https://blog.salad.com/saladcloud-price-changes-september-2026/ |
| 2026-11-06 | Lambda announces GPU price rises of about 15%, B200, H100 and A100 80GB, from Nov 16 (GPUJournal) | https://gpujournal.ai/story/lambda-announced-rises-nov-16 |
| 2026-08-22 | Nvidia Warns Hyperscalers Its AI Server Prices Are Jumping More Than 15% (Startup Fortune; found by the loop's scout, confidence C, used by nothing) | https://startupfortune.com/nvidia-warns-hyperscalers-its-ai-server-prices-are-jumping-more-than-15/ |

## 7. Economic insight

**A posted median is an index of a few providers, not of a market.** Only 5 of the 37 scored series pass every robustness test on 6 November; no H100 or A100 on-demand series does. The median worst one-offer removal moves a series 7.2%. The two collectors' 7-day disagreement is 0.048 log on posted medians and 0.005 on the same static offers. About a third of static H100 and H200 rate-card providers raised prices from August to early November and none cut; the static mean rose about 5 to 10% while posted medians report 15 to 21% ([figure](experiments/insight/results/fig1_index_quality.png); `experiments/insight/results/insight.md`).

- **Lessor.** Do not index a lease to any of the 32 failing series; use the equal-weight change of a fixed set of static rate cards, which disagrees across collectors by 0.005 log per week against 0.048.
- **Lender.** Mark collateral on a basket and haircut by at least the worst removal (7.2% at the median series, 58% on afhubbard A100 SXM spot). In the long-run model the 10th-percentile path supports about 65% loan-to-value on a 20k USD used H100.
- **Reserved-capacity buyer.** Per unit of inference work an A100 costs about 2.3 times a B200 and an H100 about 1.5 times, and fewer than 6% of A100-against-B200 provider pairs reverse that. Expect discrete steps: 2 of 9 recent large static steps came with 10 to 15 days' notice.

## 8. The 2 to 3 year view

**Ranges, not forecasts.** Starting from the median of static neocloud rate cards on 6 November, a three-scenario mixture gives ([figure](experiments/longrun/results/v2_fig3_scenarios.png)):

| USD per GPU-hour, q50 (q10 to q90) | now | +12 months | +24 months | +36 months |
|---|---|---|---|---|
| H100 | 3.49 | 3.11 (2.11 to 4.69) | 2.31 (1.21 to 4.17) | 1.79 (0.76 to 3.76) |
| A100 | 2.35 | 2.20 (1.55 to 3.09) | 1.81 (1.01 to 3.05) | 1.57 (0.73 to 3.04) |
| resale by income approach, USD per GPU | now | | +24 months | +36 months |
| H100 | 26.1k (12.1k to 54.2k) | | 10.0k | 5.3k |
| A100 | 9.1k (4.0k to 18.7k) | | 2.3k | 0.1k |

The scenario probabilities are judgement, frozen before computing: shortage persists through 2027, 0.35; eases to the multi-year trend, 0.40; successor glut from 2028, 0.25. Published used-GPU figures (mostly asking prices) fall inside the resale ranges.

**Backtests that failed.** An age-decay model lost to no-change on 117 weekly-median series (log error 0.66 against 0.42). On AWS spot from year-ends 2023 to 2025 the mixture's centre never beat no-change (0.60 to 0.88 against 0.54), and its intervals covered only with noise widened to 0.6 log per root-year; the projections use 0.25, so spot users should widen them. The one-year mixture covered 11 of 16 series, but its probabilities were set knowing 2026. Nothing beyond 24 months can be backtested.

**Assumptions.** Utilisation (50 to 85%) dominates resale value; remaining life (H100 4 to 7 years, A100 2 to 5) and the discount rate matter less. Capability units come from MLPerf inference medians. Most of the 2026 rise in aggregator medians is panel effect, so earlier 12-month trends are upper bounds.

## 9. Limitations and threats to validity, in order of importance

1. **Only prov and fm2 survive a correctly sized validation test.** Analog's p of 0.0314 is about 0.14 to 0.16 once autocorrelation over 18 days is simulated; fragility's is 0.05 to 0.08.
2. **Validation ranges rest on 3 week clusters** (10 distinct resamples) and are not 90% intervals.
3. **The universe is chosen with hindsight.** Applied date by date, the organisers' rule admits 4 to 15 series on dev, and mix's margin over drift falls from +0.080 to +0.033. Most of the dev "beats drift" size is a young-series effect.
4. **Blend membership is partly selected on validation** (gbm and Chronos width), and validation guided which directions were explored; the count of 11 queries understates the reuse.
5. **Parameters were chosen on dev** (prov's 21-day window, analog's feature drop, fragility's boost, fm2's context and lower level), so dev intervals are in-sample for them.
6. **One forecast origin on Sunday**, with one-sided upper-tail misses at h=7.
7. **Data vintage.** The pack holds revised values; real-time last values may have differed, and nothing here bounds that.
8. **A leak found and fixed.** Analog's table membership depended on rows after the origin; the effect on forecasts used was at most 2.1e-5 in log and none at the scored origin.
9. **No skill at long horizons**, and no transaction-level resale data exists.

## 10. Reproduce, and where the evidence lives

`bash reproduce.sh final` rebuilds the submission from the pack (README.md has hashes and requirements).

| claim | evidence |
|---|---|
| validation results | `data_out/val_gate.jsonl`, `data_out/val_query_log.jsonl` |
| dev results, leave-one-out | `experiments/final/results/dev.txt`, `experiments/halves.py` |
| audit | `experiments/audit/results/audit.md` |
| hypotheses | `data_out/ledger.jsonl` (`python -m gpuf.ledger`) |
| decisions and corrections | `research-log.md`, `EVAL_PROTOCOL.md` |
| loss by cause | `experiments/autopsy/results/failure_modes.json`, `experiments/autopsy2/results/loss_by_cause.csv` |
| calendar and attribution | `data_out/repricing_calendar.jsonl`, `experiments/exa_attrib/results/attribution.md`, `experiments/prov/results/cal_summary.json` |
| economic insight | `experiments/insight/results/insight.md` |
| long-run view | `experiments/longrun/results/longrun.md` |
| the loop | `experiments/loop/iteration3.md`, `src/gpuf/loop.py` |
