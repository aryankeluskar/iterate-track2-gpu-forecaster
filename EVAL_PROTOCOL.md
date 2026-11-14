# Evaluation protocol (locked before any hypothesis is run)

Locked Saturday 14 November 2026, about 10:35 PT, before any forecasting method other than the starter baselines was scored.

## Metric

Pinball loss at quantiles 0.1, 0.5 and 0.9, averaged over each (series, origin, horizon) cell, for horizons 1, 3 and 7 days. Skill is 1 minus loss over last-value loss. The headline number is pooled skill, exactly as `starter/scorer.py` computes it. Mean, median and geometric-mean skill across series and interval coverage (target 0.8) are reported beside it. Horizon 30 is ignored: it is not scored on Sunday.

## Baseline to beat

`drift` from `starter/baselines.py`, default settings. A method counts as an improvement only relative to drift, not to last value.

## Universe

Series in the starter catalog built as of 2026-11-06 whose table is `daily_statistics` (posted rental series; AWS spot tick series are excluded because the brief says they are not scored on Sunday). The primary universe is the headline tier of that set. The secondary universe is every tier of that set. Choosing the universe as of 6 November for earlier origins is a mild look-ahead in which series are scored, never in what a forecast sees. Ticket "Scoreable universe and loss profile" quantifies it.

## Origins

- Dev: every day from 2026-05-01 to 2026-08-31. Free to look at.
- Validation: every day from 2026-09-08 to 2026-10-04. A method change is accepted only if it beats the current best on validation. Every validation query is counted and logged.
- Test: every day from 2026-10-12 to 2026-10-30. Locked. Scored once, at the end, for the method that will be submitted and for drift.

Seven-day gaps separate the sets so that no target date is shared between them.

## Leakage rule

A forecast for origin d may read only rows dated on or before d, for its own series and for any other series. The harness enforces this by handing forecasters truncated arrays. No data dated after 2026-11-06 is ever fetched.

## Uncertainty

Differences against drift are reported with a 90% interval from a block bootstrap over origin weeks, paired by cell. A validation win needs the interval's lower end above zero.

## Reference check

The harness must reproduce the starter's drift result exactly before anything else is trusted: pooled skill 0.183267 on 15 weekly origins from 2026-07-15 to 2026-10-24, headline tier of the catalog as of 2026-10-24, horizons 1, 3 and 7 (4,209 cells scored).

## Amendment 1 (14 November 2026, about 10:45 PT)

Made before any forecasting method was scored on validation or test, and before any method other than the starter baselines was scored anywhere. Reason: the data profile showed the original splits cannot see the series Sunday scores. The headline rental universe as of 2026-11-06 has 37 series. Twenty come from the fastgpu collector, which starts on 2026-09-08. Thirteen come from gpurentalprices, which starts on 2026-08-04. Only four (afhubbard spot) exist before August. The original dev period (May to August) held zero cells for 20 of the 37 series, and the original test period left too little room.

The Universe, Metric, Baseline, Leakage and Reference sections stand. The Origins section is replaced by:

- Dev: every day from 2026-08-18 to 2026-10-06 (targets up to 2026-10-13). Free to look at.
- Validation: every day from 2026-10-13 to 2026-10-30 (18 origins, targets up to 2026-11-06). The gate for accepting a method change. Every query is counted and logged, and the acceptance rule spends a fixed error budget across queries.
- Test: the organisers' Sunday scoring (origin 2026-11-06, targets 7, 9 and 13 November). The pack is too short to hold out a third period, so no internal test set exists. This is stated in the findings.

Secondary check for any accepted change: it must not lower pooled skill on the all-tier rental universe on validation, and its result on the four long-history afhubbard series over the old dev period (May to August) is reported as a robustness check.
