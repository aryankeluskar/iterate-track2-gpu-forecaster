# Findings: forecasting posted GPU rental prices by modelling the offers under the median

Iterate AI Research Hackathon, Track 2 (Pacific Machines), Direction A, with the Exa and past.dev challenges. This file supersedes the early working note, now at `experiments/writeup/findings_early.md`. Every number is copied from a file in the repository; `experiments/writeup/numbers.md` gives the source of each.

## 1. The question and the answer in five lines

Can a loop that tests hypotheses against its own forecast failures beat the starter `drift` baseline, with calibrated intervals, on posted GPU rental prices 1, 3 and 7 days ahead, on dates it had not used? And what will H100 and A100 rentals and resale be worth in 2 to 3 years?

1. A posted rental median is the middle of a panel of 3 to 17 provider offers; it moves only when an offer near the middle is repriced or an offer enters or leaves. Forecasting that panel, not the series, produced the gains.
2. On the 18 validation origins the submitted blend scored 0.2141 pooled skill against 0.0845 for drift on the 37 scored series, and 0.2275 against 0.1021 on the other posted rental series.
3. These numbers are optimistic: part of the blend was chosen on the validation period, the 37 series were chosen with hindsight, and an independent audit found that only two of the four later directions survive a correctly sized test.
4. Rents in 2 to 3 years: the H100 static rate-card median goes from 3.49 USD per GPU-hour to 2.31 (1.21 to 4.17) at +24 months; the A100 from 2.35 to 1.81 (1.01 to 3.05). No method beat "no change" in any long-horizon backtest: these are ranges with stated assumptions, not forecasts with skill.
5. The most usable economic finding: 32 of the 37 scored medians fail an index-quality test, and 25 move more than 5% if one offer or provider is removed.

## 2. Method

**Terms.** An *offer panel* is the set of posted offers (provider, region, SKU, GPU count) behind one series on one day; the scored median is reproduced from it, within half a cent, on 100% of 2,483 series-days checked. *Pinball loss* is the quantile loss at 0.1, 0.5 and 0.9, averaged over each (series, origin, horizon) cell. *Pooled skill* is 1 minus total loss over total last-value loss. *Drift* scales the last value by the 0.1, 0.5 and 0.9 quantiles of the series' own past h-day log changes. The *development period* (dev) is the 50 origin days from 18 August to 6 October 2026, free to inspect. The *validation period* is the 18 origin days from 13 to 30 October (3 ISO weeks); each query on it is declared, committed and logged. *mix*, the reference model, is a pooled, state-conditioned empirical mixture of h-day log changes.

**Declared targets.** Instrument class: posted rental prices in `daily_statistics` (neocloud rate cards, neocloud spot, marketplace asks, hyperscaler spot and list), never spliced across classes. A series is the daily median, in USD per GPU-hour, of the offers one collector posts for one GPU model, pricing tier and instrument class. Origin 2026-11-06; horizons 1, 3 and 7 days. Primary universe: the 37 headline-tier series as of 6 November (20 fastgpu, 13 gpurentalprices, 4 afhubbard). The submission covers all 592 posted rental series. AWS spot ticks and horizon 30 are excluded: not scored on Sunday.

**Protocol.** `EVAL_PROTOCOL.md` was locked before any method was scored and amended three times, each before the directions it governs were queried; Amendment 2 came after validation round 1 and made two of its winners blend members (section 9). Forecasters receive histories truncated at the origin. A direction goes to validation only if its blend with mix beats mix on dev with the 90% week-bootstrap interval above zero and gains in both halves of dev. At most 8 validation queries, frozen parameters, false discovery rate 10% (Benjamini-Hochberg on one-sided Diebold-Mariano p-values). The submission is fixed by rule: the equal-weight mean of log quantiles of the validated members, membership decided by leave-one-out on dev. There is no internal test set; Sunday is the test.

**The loop and who ran it.** Forecast, attribute loss to causes in the panel, hypothesise, test on dev, gate on validation, record in `data_out/ledger.jsonl` (37 hypotheses: 13 supported, 15 refuted, 7 not significant, 2 untestable). LLM research agents wrote the hypotheses and forecasters, launched in six rounds by an orchestrator agent directed by a human. Since round 6 the steps `autopsy`, `scout`, `prior`, `propose`, `gate`, `forecast` and `status` are commands (`python -m gpuf.loop`), run for one recorded iteration (`experiments/loop/iteration3.md`) in which the loop pointed at the largest residual cause and wrote no hypothesis. Still done by hand: writing a hypothesis or forecaster, choosing what to gate, declaring and running validation queries, checking calendar lines, writing the log.

## 3. What the system learned, iteration by iteration

**Iteration 1: reference model, first failure analysis.** A smoothed level loses to the last value (H1). Pooling change distributions across series (H3) and conditioning on recent change (H2) gave mix, +0.0805 over drift on dev. Pretrained models lose with their own quantiles (Chronos-Bolt -0.050, TimesFM -0.055 against drift) but help as widths around the last value (H6). The failure analysis: 52% of dev cells do not change; moves above 5% are 9% of cells and 61% of last-value loss; median-quantile loss was equal across methods, so all gain was in the tails. Knowing whether the price moves would give 0.219, knowing its direction 0.226, against 0.182 for the blend then.

**Iteration 2: the offer panel.** Of 579 one-day changes, 86% were repricing, 10% composition (offers entering or leaving) and 4% mixed. Composition carried 32% of the blend's dev loss, rarely reverted (5.6% of 162 fastgpu exits returned within 7 days) and matched the panel's one-offer fragility (correlation 0.88, n=60). Repricing is concentrated: Verda repriced on 59% of its fastgpu offer-days, 97% upward; Nebius, Lambda, CoreWeave and others on under 1%. Four directions followed: a *provider simulator* (prov, H24) that moves each offer by its provider's recent signed changes, the first method with median loss below the last value (0.95 of it); *fragility tails* (H28) on the one-offer-out and one-offer-in medians; nearest-neighbour *analogs* (H21); *pretrained widths* (fm2, H18), Chronos-Bolt-small on 16 days of context, whose width tracks recent volatility (elasticity 1.02). A panel simulator with pooled symmetric reprices failed (H12): new entrants cannot be simulated from a panel's own history.

**Iteration 3: residual loss by cause** ([figure](experiments/autopsy2/results/loss_by_cause.png)). Loss as a fraction of last-value loss, dev headline:

| cause | cells | share of last-value loss | drift | mix | mix+gbm+Chronos | six-member blend |
|---|---|---|---|---|---|---|
| dynamic repricing | 1027 | 0.2047 | 0.8087 | 0.6283 | 0.6719 | 0.6122 |
| announced one-off | 52 | 0.1269 | 0.9517 | 0.8541 | 0.8681 | 0.8541 |
| unannounced one-off | 195 | 0.0983 | 0.9729 | 0.8563 | 0.8396 | 0.8257 |
| offer enters | 236 | 0.2785 | 0.9563 | 0.9070 | 0.8537 | 0.8409 |
| offer leaves | 125 | 0.0875 | 0.9728 | 0.9650 | 0.9382 | 0.9427 |
| marketplace ask | 124 | 0.1359 | 0.8129 | 0.7135 | 0.6243 | 0.6209 |
| hyperscaler spot | 308 | 0.0683 | 0.7517 | 0.6984 | 0.6823 | 0.6954 |
| total | 4278 | 1.0 | 0.9114 | 0.8309 | 0.8182 | 0.7964 |

The six-member blend is mix, gbm, Chronos width, fm2, analog and prov; the submission adds fragility. Gains landed where aimed (dynamic repricing, marketplace asks); offers leaving are handled worst, and offers entering are 29% of what remains. Then tried and not kept: an entry model (H30), a hyperscaler simulator (H35), a cross-collector lead (H33) and an Exa calendar inside prov (section 6). The rule-fixed seven-member blend scores 0.2079 on dev, below the four-member blend of mix, fm2, analog and prov (0.2131): the cost of not picking members on the reported number.

## 4. Results with uncertainty

**Development period, 37 series, 4,278 cells.** 90% week-bootstrap intervals over 8 ISO weeks, in-sample for parameters chosen on dev.

| system | dev skill | difference against mix | first half / second half |
|---|---|---|---|
| drift | 0.0886 | -0.0805 [-0.093, -0.057] | |
| mix (reference) | 0.1691 | | |
| mix + analog | 0.1999 | +0.0307 [+0.017, +0.053] | +0.034 / +0.030 |
| mix + prov | 0.1973 | +0.028 [+0.015, +0.053] | +0.008 / +0.033 |
| mix + fm2 | 0.1899 | +0.021 [+0.010, +0.044] | +0.044 / +0.016 |
| fragility over mix | 0.1924 | +0.0232 [+0.011, +0.045] | +0.049 / +0.018 |
| submitted blend | 0.2079 | +0.0388 [+0.025, +0.068] | +0.0516 / +0.0361 |

**Validation period, 37 series, 1,816 cells; mix 0.1121, drift 0.0845.** With 3 weeks the bootstrap has 10 distinct resamples, so the ranges below span roughly the worst and best week; they are not 90% intervals. The logged Diebold-Mariano p-values are anti-conservative on 18 days; the audit's simulated p-values (Gaussian / block bootstrap) are beside them.

| query | system | skill | difference against mix | week-bootstrap range | logged p | simulated p | coverage |
|---|---|---|---|---|---|---|---|
| 6 | mix + analog | 0.1339 | +0.0218 | +0.0067 to +0.0433 | 0.0314 | 0.135 / 0.158 | 0.75 |
| 7 | mix + prov | 0.1845 | +0.0724 | +0.0588 to +0.0868 | below 1e-9 | 0.005 / 0.006 | 0.758 |
| 8 | mix + fm2 | 0.1698 | +0.0577 | +0.0390 to +0.0796 | below 1e-5 | 0.004 / 0.006 | 0.783 |
| 9 | fragility over mix | 0.2190 | +0.1069 | +0.0523 to +0.1522 | 0.0085 | 0.051 / 0.077 | 0.810 |
| 10 | submitted blend | 0.2141 | +0.1020 | +0.0913 to +0.1139 | not simulated | | 0.797 |
| 11 | submitted blend, other series (22,390 cells; mix 0.1777, drift 0.1021) | 0.2275 | +0.0499 | +0.0411 to +0.0569 | not simulated | | 0.845 |

Against drift the blend gains +0.1296 on headline (range +0.0979 to +0.1521) and +0.1255 on the other series (+0.1145 to +0.1341). Query 11 is the least contaminated number: those cells were never evaluated before, though the same series were used on development dates (member selection and the activity gate).

**The audit's corrected reading.** With simulated p-values, Benjamini-Hochberg at 10% keeps only prov and fm2; analog and fragility stay in the blend on dev leave-one-out evidence, a stated deviation from Amendment 2. Section 9 lists why the headline numbers are optimistic. Query 5's declaration was committed 32 seconds after its result, which (0.1967) was missing from the log until the audit.

**Calibration.** Coverage of [q10, q90] is 0.797 on validation headline and 0.845 on the other series (target 0.8), but misses are one-sided: 11% of truths land above q90 at h=7. On dev the six-member blend has 22.5% above q90 at h=7, and 56.8% of its loss comes from truths above q90.

**One origin.** Over the 50 dev origins taken singly, the blend's pooled skill has median 0.215 (10th percentile 0.114, minimum -0.231); it beats drift on 46 and is below the last value on 2 (drift on 7). Neighbouring origins overlap, so these are not independent trials.

**What Sunday can and cannot show.** One origin, one week of targets: whether the blend beats drift on an unseen week, nothing about member rankings or the long run. The file covers both the 592 series and the 37.

## 5. Negative results

| id | hypothesis | result |
|---|---|---|
| H1 | a smoothed level beats the last value as centre | refuted: error ratio 1.6 (h=1) to 1.1 (h=7) |
| H4 | composition jumps revert | refuted: 5.6% of fastgpu exits return within 7 days |
| H7, H7b | other collectors lead; collector-wide breadth sets width | refuted: every variant at or below the base |
| H9 | moves above 5% partly reverse | refuted: -0.001 and -0.003 |
| H10 | a burst of dated price-rise headlines (Exa) precedes up-jumps | not significant: +0.0096 [-0.004, +0.015], from one episode |
| H12 | panel simulator with pooled symmetric reprices | not significant: blend +0.011 [-0.002, +0.040] |
| H13 | large repricings are announced before they hit the data | refuted: 2 of 37 events |
| H14 | the h=7 upper-tail gap is stable; recalibration fixes it | refuted: above-q90 rate 0.110, then 0.330 |
| H15 | stacking with learned weights beats equal weights | not significant: +0.0037 [-0.002, +0.007] |
| H16 | hurdle model: move probability times jump size | refuted: 0.108 against mix 0.169; direction AUC 0.54 |
| H17 | the Laya text decision model classifies up/flat/down | refuted: log loss 1.105 against 0.562 for logistic regression |
| H19 | cross-instrument level gaps close; indices as signals | refuted: slope +0.005 per unit z |
| H20 | weight-space programming of a tiny net by a frontier model | not significant: blend 0.172 against mix 0.169 |
| H22 | in-context tabular model | untestable: stopped for machine load |
| H25 | the middle provider's state as a lookup key | not significant: 0.167 against 0.169 |
| H26 | Exa pricing-policy labels as a prior on reprice rates | refuted: a constant zero beats the label |
| H29 | age-decay projection of rents | refuted: no-change error 0.42 against 0.66 |
| H30 | entries predictable from a provider's footprint elsewhere | not significant: -0.011 against prov at measured rates |
| H33 | gpurentalprices leads fastgpu by a day | refuted: same-sign next-day move in 33% of 24 cases |
| H35 | the provider simulator transfers to hyperscaler panels | refuted: -0.039 against mix |
| H36 | a scenario mixture gives skilful 1 to 2 year ranges | not significant: no centre beat no-change |
| H37 | the evaluation is leak-free and correctly sized | refuted by the audit (section 9) |
| H5 | trailing days are revised upstream | untestable: one data vintage |

Also refuted on dev without a ledger entry: signed state, pooling a whole collector, and routing methods by class (H23 kept only its activity gate).

## 6. What search contributed (Exa) and what it did not

Exa supplied the dated public record the price data lacks: a calendar of announced repricings with effective dates (9 entries, `data_out/repricing_calendar.jsonl`) from 463 searches with end published dates on or before 6 November, price trackers discarded unopened. On dev, all 17 checkable offers moved to the announced price. Inside prov the calendar lifts dev skill from 0.2089 to 0.2827, all from two events (Nebius, Jarvislabs) whose collector lag was fitted on the same events: an in-sample upper bound that validation cannot check. The switch is off in the submission (the one entry in the Sunday window, Lambda, takes effect after the last target), so the submitted forecast does not depend on Exa. Exa also refuted three ideas (H10, H13, H26) and supplied the dated news for the long-run scenarios. A published date does not prove a page is unedited. Spend: $7.62.

| date | title | link |
|---|---|---|
| 2024-08-02 | DataCrunch.io Introduces Dynamic Pricing to Democratize GPU Computing for AI (DataCrunch is now Verda) | https://www.prweb.com/releases/datacrunchio-introduces-dynamic-pricing-to-democratize-gpu-computing-for-ai-302212007.html |
| 2026-09-16 | Nebius raises GPU prices 20% as supply tightens | https://www.thefivenines.com/data-ai/nebius-raises-gpu-prices-20-as-supply-tightens |
| 2026-09-24 | New GPU rates from October 5, 2026, Jarvislabs Updates | https://jarvislabs.ai/updates/gpu-pricing-october-2026 |
| 2026-09-01 | Upcoming SaladCloud Price Changes: September 12, 2026 | https://blog.salad.com/saladcloud-price-changes-september-2026/ |
| 2026-11-06 | Lambda announces GPU price rises of about 15%, B200, H100 and A100 80GB, from Nov 16 (GPUJournal) | https://gpujournal.ai/story/lambda-announced-rises-nov-16 |
| 2026-08-22 | Nvidia Warns Hyperscalers Its AI Server Prices Are Jumping More Than 15% (Startup Fortune; added by the loop's scout, confidence C, used by nothing) | https://startupfortune.com/nvidia-warns-hyperscalers-its-ai-server-prices-are-jumping-more-than-15/ |

## 7. Economic insight

**A posted median indexes a few providers, not a market.** Only 5 of the 37 scored series pass every robustness test on 6 November; no H100 or A100 on-demand series does. The two collectors disagree by 0.048 log over 7 days on posted medians and by 0.005 on the same static offers. A third of static H100 and H200 rate-card providers raised prices from August to early November and none cut; their mean rose about 5 to 10% while posted medians report 15 to 21% ([figure](experiments/insight/results/fig1_index_quality.png), `experiments/insight/results/insight.md`).

- **Lessor.** Do not index a lease to the 32 failing series; use the equal-weight change of a fixed set of static rate cards (0.005 log of cross-collector disagreement per week against 0.048).
- **Lender.** Mark collateral on a basket, haircut by at least the worst removal (7.2% at the median series, 58% on afhubbard A100 SXM spot). The long-run model's 10th-percentile path supports about 65% loan-to-value on a 20k USD used H100.
- **Reserved-capacity buyer.** Per unit of inference work an A100 costs about 2.3 times a B200 and an H100 about 1.5 times; fewer than 6% of A100-against-B200 provider pairs reverse that. 2 of 9 recent large static steps came with 10 to 15 days' notice: lock terms when one appears.

## 8. The 2 to 3 year view

**Ranges from a three-scenario mixture**, starting from the static neocloud rate-card median on 6 November ([figure](experiments/longrun/results/v2_fig3_scenarios.png)):

| USD per GPU-hour, q50 (q10 to q90) | now | +12 months | +24 months | +36 months |
|---|---|---|---|---|
| H100 | 3.49 | 3.11 (2.11 to 4.69) | 2.31 (1.21 to 4.17) | 1.79 (0.76 to 3.76) |
| A100 | 2.35 | 2.20 (1.55 to 3.09) | 1.81 (1.01 to 3.05) | 1.57 (0.73 to 3.04) |
| resale by income approach, USD per GPU | now | | +24 months | +36 months |
| H100 | 26.1k (12.1k to 54.2k) | | 10.0k | 5.3k |
| A100 | 9.1k (4.0k to 18.7k) | | 2.3k | 0.1k |

Scenario probabilities are judgement, frozen before computing: shortage persists through 2027, 0.35; eases to the multi-year trend, 0.40; successor glut from 2028, 0.25. Published used-GPU figures, mostly asking prices, fall inside the resale ranges.

**Backtests that failed.** Age decay lost to no-change on 117 weekly-median series (log error 0.66 against 0.42). On AWS spot from year-ends 2023 to 2025 the mixture's centre never beat no-change (0.60 to 0.88 against 0.54), and its intervals covered only with noise of 0.6 log per root-year; the projections use 0.25, so widen them for spot. The one-year mixture covered 11 of 16 series, but its probabilities were set knowing 2026. Nothing beyond 24 months can be backtested.

**Assumptions.** Utilisation (50 to 85%) dominates resale value; remaining life (H100 4 to 7 years, A100 2 to 5) and the discount rate matter less. Most of the 2026 rise in aggregator medians is panel effect, so earlier trends are upper bounds.

## 9. Limitations, in order of importance

1. **Only prov and fm2 survive a correctly sized validation test.** Analog's p of 0.0314 becomes 0.135 to 0.158 when 18-day autocorrelation is simulated; fragility's becomes 0.051 to 0.077.
2. **Validation ranges rest on 3 week clusters** (10 distinct resamples); they are not 90% intervals.
3. **The universe is chosen with hindsight.** Applied date by date, the organisers' rule admits 4 to 15 series on dev, and mix's margin over drift falls from +0.080 to +0.033: most of the dev "beats drift" size is a young-series effect. For the submitted blend the effect is larger: on dev cells whose series already met the rule at the origin (745 cells) it scores 0.1542 against drift 0.1375 and mix 0.1708, a margin over drift of +0.0167 against +0.1193 on the fixed 37. Most of those cells are four hyperscaler-spot series, and the mature rate-card cells are one collector in one week, so this is thin evidence either way; but all 37 series are mature at the scored origin (`experiments/maturity/results/diag.txt`).
4. **Membership partly selected on validation**: gbm and Chronos width joined by a rule written after they won round 1, and later rounds were designed after seeing it; 11 queries understate the reuse.
5. **Parameters chosen on dev** (prov's window, analog's feature drop, fragility's boost, fm2's context), so dev intervals are in-sample for them.
6. **One scored origin**, with one-sided upper-tail misses at h=7.
7. **Data vintage**: the pack holds revised values. **A leak, fixed**: analog's table membership depended on later rows, by at most 2.1e-5 in log on forecasts used and not at all at the scored origin.
8. **No skill at long horizons**, and no transaction-level resale data exists.

## 10. Reproduce, and where the evidence lives

`bash reproduce.sh final` rebuilds the submission from the pack; README.md gives requirements and file hashes.

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
