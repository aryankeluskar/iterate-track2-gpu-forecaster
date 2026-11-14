# Literature survey for Track 2 (GPU rental price forecasting, AI scientist loop)

Every claim below was read this session (local LaTeX, fetched PDF text, or a fetched web page); items resting only on search snippets are marked "(snippet)". Per-source notes are in this folder under the slug in brackets.

## Q1. Acceptance gate for "keep a change only if it survives held-out origins"

- Popper [popper]: per-look e-value e_i = kappa * p_i^(kappa-1), kappa in (0,1) (kappa = 0.5 is consistent with the paper's worked example, not stated); evidence E_i = product of e_s; accept when E_i >= 1/alpha; stop at a fixed budget (3 tests on DiscoveryBench, 5 on TargetVal), alpha = 0.1. Validity (P(accept | null) <= alpha even with optional stopping) needs: each look's p-value is valid given earlier looks, and the test is chosen before seeing that look's data.
- Reported error rates at alpha = 0.1: 0.103, 0.082, 0.085 across three benchmarks; power 0.638, 0.580, 0.591. Baselines without sequential control exceeded alpha (Fisher combined 0.311/0.264/0.173; CodeGen 0.145; no relevance check 0.134/0.340/0.300).
- Thresholdout [thresholdout]: answer queries with the training-split value unless |holdout - train| > T + noise, in which case return the noisy holdout value and spend one unit of budget B; stop at B = 0. Laplace scales 2 sigma (threshold), 4 sigma (comparison), sigma (answer). DP bound (2B/(sigma n), 0). Number of queries can be exponential in n if overfitting events are few.
- Alpha splitting (my own, not from a source): with K planned looks at level alpha, test each at alpha/K (Bonferroni); valid under any dependence between looks, no optional stopping needed. Lan-DeMets spending functions not verified.

## Q2. Sticky, step-like, intermittent series

- TSB [croston-tsb]: update an occurrence probability every period (so forecasts decay in long flat runs, unlike Croston), update size only on events; point forecast p_t * y_t. Probabilistic versions exist (NB, empirical, Beta-Binomial occurrence with Log-Normal size, the last a preprint). (snippet-level evidence).
- Nakamura and Steinsson 2008 [nakamura-steinsson]: monthly frequency of regular price change 9 to 12 percent (about 7.5 months duration); one third of changes are decreases; hazard slightly downward sloping in the first months then mostly flat (no upward slope), spike at 12 months for services and producer prices; increases covary with inflation, sizes do not.
- No source found on hurdle or zero-inflated models of price changes.

## Q3. Quantile calibration under shift

- ACI [aci]: alpha_{t+1} = alpha_t + gamma (alpha - err_t); for every T, |mean(err_t) - alpha| <= (max{alpha_1, 1 - alpha_1} + gamma) / (T gamma) with no distributional assumption. Controls average coverage over time only.
- CQR [cqr]: score E_i = max{q_lo(X_i) - Y_i, Y_i - q_hi(X_i)} on a calibration set; interval [q_lo - Q, q_hi + Q] with Q the (1-alpha)(1+1/n) quantile of scores; coverage >= 1 - alpha under exchangeability only (Theorem 1), so it can break under drift.

## Q4. Local refs

- [secondhand-electronics-benchmark]: at 1 to 7 days all 11 models sit near 0.72 percent MAPE and naive is competitive; N-BEATS wins beyond 30 days (8.51 vs 14.94 percent at 365 days); LSTM/TCN degrade past 90 days.
- [chronos] [timesfm]: Chronos-T5 Mini 20M, Small 46M, Base 200M, Large 710M; 4096-token vocabulary, context 512, mean scaling, sampled quantiles; Mini beats Moirai Large (311M) on their benchmark; stated limitation for strong trends. TimesFM about 200M, point output (quantile heads proposed). Neither paper discusses flat or step series in the text searched; CPU timings not reported for the small models.
- [halawi-forecasting] [forecastbench]: retrieval lowers Brier from .206 to .186 (base GPT-4); the full system is .179 vs crowd .146; ForecastBench best LLM rows about 0.155 to 0.16 vs superforecasters 0.076 to 0.091; a carry-forward ("freeze values") Claude 3.5 row reaches 0.111 on the combined table.
- [ai-scientist] [reflexion]: AI Scientist keeps an archive of ideas with review scores; reported failures include silently wrong implementations, a changed metric not accounted for when comparing, hallucinated ablation tables and hardware, positive spin on negative results, and overrated novelty. Reflexion keeps 1 to 3 verbal lessons per episode in an episodic buffer (no weight updates), 91 percent pass@1 HumanEval.

## Q5. Cloud spot and GPU pricing

- [agmon-spot]: EC2 spot prices were drawn from a narrow interval consistent with a hidden random reserve price, not supply and demand (2013; snippet-level); later mechanism undisclosed algorithm.
- [gpu-rental-prices]: Silicon Data H100 index 2.57 (May 4 2026), 2.79 (Jun 5 high), 2.59 (late Jun), 2.75 (Jul 27); H200 2.70 to 3.10; H200 premium 0.4 to 16.2 percent, H100 and H200 daily changes essentially uncorrelated. Epoch: FLOP/s per dollar doubles every 2.46 years (2.24 to 2.72), ML GPUs 2.07, top GPUs 2.95 (June 2022 data to 2021).

## Q6. Weight-space programming

- [weight-space-programming]: nothing found where an LLM edits weights of a forecasting, tabular or regression model; nothing found on iWSP, Mehta, Singh or Microsoft Research.

## What this changes for our experiments

1. Acceptance gate: use Popper-style e-values with a fixed budget of K = 3 looks, alpha = 0.1, kappa = 0.5, accept when the product of e_i = 0.5 * p_i^(-0.5) is at least 10 (for example two looks at p about 0.01 each give 5 x 5 = 25). Each look must use a fresh, disjoint block of held-out origins that the proposing agent never saw, and p_i must be a one-sided test that the candidate's mean pinball-loss difference against the incumbent is below zero (block bootstrap or Diebold-Mariano style on day-clustered differences). Source: Popper Eq. 1 and Theorem 1.
2. Fallback gate if per-look p-values are awkward: split alpha = 0.1 equally over the K = 3 looks (0.033 each). Thresholdout is the right choice only when the same holdout must be queried many times; set B to the number of times a candidate may disagree with its training-origin score by more than T.
3. Bars: keep last value and empirical-increment drift as the comparison on every look; evidence from the electronics benchmark and ForecastBench says carry-forward is hard to beat at 1 to 7 days.
4. Step-like series: build a TSB-style hurdle forecaster: P(change within h days) updated daily, times the empirical distribution of non-zero increments from that series (pooled across series if sparse), then read q10/q50/q90 from the mixture. When P(no change) > 0.5, q50 is the last value. This mixture construction is my inference from the sources, not a published method, and needs testing.
5. Calibration: apply CQR-style recalibration on the last K calibration origins and, for drift, ACI with gamma chosen on origins excluded from the gate. Update with the h-day delayed error.
6. Do not expect time-since-last-change to help beyond the first months (flat hazard, Nakamura and Steinsson); features for market-wide moves and calendar effects are the better hypothesis space. Transfer to GPU rate cards is untested.
7. Foundation-model arm: try Chronos-T5 Mini (20M) zero-shot with native sampled quantiles as a baseline; test it on flat series because mean scaling and a token range are failure risks. Skip TimesFM unless wrapped with CQR (point output).
8. Agent-loop hygiene: freeze the scoring script, log every look against the budget, store only 1 to 3 bounded lessons per hypothesis family (Reflexion), and recompute baselines whenever the metric changes (an AI Scientist failure mode).

## Not verified

- Popper's actual kappa and the relevance threshold (only inferred; not in the text read), and whether its Type-I result holds under dependent time-series p-values.
- Lan-DeMets alpha spending and Thresholdout default T = 4/sqrt(n), sigma = 1/sqrt(n) (the latter from a snippet).
- Croston/TSB equations and the Syntetos original (paper not opened); Hyndman et al. 2008 and Snyder et al. 2012 probabilistic versions.
- Hurdle/zero-inflated models of price changes; Klenow and Kryvtsov; hazard evidence for GPU rate cards.
- Agmon Ben-Yehuda full text; Silicon Data primary pages for Dec 2025 to Jan 2026 and Oct 2026 values (only snippets); SemiAnalysis and a16z index values (snippet); Epoch Feb 2026 figure of 2.2 years (snippet); Epoch 2.46-year data end in 2021.
- iWSP (Mehta, Singh; Microsoft Research): no result; any LLM-edits-weights work for forecasting: none found.
- Chronos and TimesFM CPU feasibility, behaviour on constant series; ForecastBench claims about news retrieval across all models; Reflexion limitations section (not fully read).
- MemGPT, DumpsterCluster, Kosmos: not read (not asked).
