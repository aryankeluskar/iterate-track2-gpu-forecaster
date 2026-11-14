# Findings

## Current understanding

Sunday scores 37 series, not 97. They are the headline tier of the posted rental series as of 2026-11-06: 20 from fastgpu (history starts 2026-09-08, 60 days), 13 from gpurentalprices (starts 2026-08-04, 89 days) and 4 afhubbard spot series (from January). By class: 23 neocloud rate cards, 7 neocloud spot, 6 hyperscaler spot, 1 marketplace ask. The headline rule (at least 60 days of history, a value within 3 days, at least 5 distinct values in 90 days, median of at least 3 providers) selects series that move: these medians took 5 to 57 distinct values in 90 days. The brief's +0.18 for drift was measured on a universe that was 80 of 97 AWS spot series and says little about the scored set.

From the data profile on May to August data (mostly afhubbard, since the other collectors barely exist then): drift's pooled skill on the headline series is +0.09, almost all at horizon 7 (h1 -0.001, h3 +0.003, h7 +0.155). On all rental series drift is worse than last value (-0.029), because its intervals come from rare large jumps. Loss is concentrated: on headline dev, 2 of 17 series carry half the baseline loss.

## Patterns and insights

- Changes cluster in time (afhubbard, May to August): the chance of a change is 0.63 the day after a change, 0.155 on average and 0.03 after two idle weeks. Drift ignores this. A forecaster that widens after a change and collapses to the last value when idle should gain.
- No day-of-week or month-start effect, and no asymmetry between cuts and rises.
- Rate-card levels rose about 4% a month for H100 and A100 over January to August.
- A change in provider count marks a step the same day (0.42 for rate cards against about 0.01 otherwise) and those steps do not clearly revert.
- No lead-lag between series was detectable (strongest pair 0.23 against a shuffled-date null of 0.37 to 0.58), on 19 series only.
- With 60 to 89 days of history for 33 of 37 scored series, per-series change quantiles rest on few samples. Pooling across series is the obvious lever.

## Lessons and constraints

- Shortening the window used for drift's change quantiles (30 to 120 days) lowers skill. Do not retry without a new reason. (Exploratory, pre-protocol.)
- On afhubbard in May to August there is no mean reversion (lag-1 autocorrelation about 0) and a median of the last k days is worse than the last value by 14% (k=3) to 90% (k=14). This was not measured on fastgpu or gpurentalprices, where medians over as few as 3 providers could behave differently. H1 is refuted for afhubbard and open for the other two collectors.
- The pack holds one data vintage, so trailing-day revisions cannot be measured. H5 is untestable.
- The data profiler could not write `experiments/00-eda/analysis.md` (its report-file write was blocked). Its scripts and result CSVs are in `experiments/00-eda/`; the findings live here.
- zsh does not word-split variables: call the interpreter directly, not through a `$PY` string.
- A formatter hook strips hard wraps from markdown. Write prose unwrapped.

## Open questions

- Does Pacific's Sunday scorer use the headline tier as of 2026-11-06 (37 series)? Measured from the starter's rule, not confirmed by Pacific.
- gpurentalprices has 6 missing days in its last 96. Cells with no truth on the target date are not scored.
- Is the forecastable structure in the centre (smoothed level) or in the intervals (step hazard)?
