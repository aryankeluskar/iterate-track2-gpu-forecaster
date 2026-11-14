# Findings

## Current understanding

Nothing is established yet beyond the starter baselines. Drift (a random walk with empirical increments) is the bar: pooled skill about +0.18 at horizons 1, 3 and 7.

## Patterns and insights

None yet.

## Lessons and constraints

- Shortening the window used for drift's change quantiles (30 to 120 days) lowers skill. Do not retry without a new reason. (Exploratory, pre-protocol.)
- zsh does not word-split variables: call the interpreter directly, not through a `$PY` string.
- A formatter hook strips hard wraps from markdown. Write prose unwrapped.

## Open questions

- Which series does Sunday's scorer cover?
- Is the forecastable structure in the centre (smoothed level) or in the intervals (step hazard)?
