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
