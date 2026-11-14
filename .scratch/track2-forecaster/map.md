# Map: Track 2 self-improving GPU price forecaster

Label: wayfinder:map

## Destination

A go/no-go decision on Track 2, backed by a working prototype: a leak-free evaluation harness plus a hypothesis-testing loop whose forecasts either beat the drift baseline on origins the loop never saw, or show convincingly that nothing does. Decision due about 15:00 PT Saturday 14 Nov 2026.

## Notes

- Domain: quantile forecasting (q10/q50/q90) of posted GPU rental prices, pinball loss, skill versus last value. Brief: `description.md`. Data pack: `data/pack/gpu-price-pack-v0.1.1-handover/` (read-only, never modify).
- **Execution is carried in this map** (overrides wayfinder's plan-only default): the user asked to prototype and hill-climb, then decide.
- Runs under `0-autoresearch-skill`: state in `research-state.yaml`, `research-log.md`, `findings.md`. Protocol commits precede result commits.
- Charted without a grilling session because the user asked for autonomous progress. Assumptions made in place of grilling are listed in `research-log.md` under "Charting assumptions".
- Heavy work goes to sonnet/opus subagents; the main session orchestrates.
- Never use data dated after an origin. Never fetch post-6-Nov prices.
- Skills to consult: `brainstorming-research-ideas`,
  `creative-thinking-for-research`, `academic-plotting`, `dataviz`.

## Decisions so far

<!-- one line per resolved ticket -->

- [Scoreable universe and loss profile](issues/02-scoreable-universe-and-loss-profile.md): Sunday scores 37 series, most with under 90 days of history; they move on a third of days.
- [Literature survey](issues/03-literature-survey.md): gate method changes with e-values under a fixed look budget; short horizons are hard to beat.

## Not yet specified

- Weight-space programming arm: an LLM-written tiny quantile net. Waits on knowing which features carry signal and which writer model is available.
- The 2 to 3 year resale and rental view (capability ladder, spot history).
  Not scoreable; waits on the go decision.
- Sponsor challenge integration (Exa news signals, past.dev shared memory, Modal parallel runs). Waits on the go decision.
- The autonomous loop itself (proposer, experimenter, critic roles and the acceptance gate with error control). Waits on the first hand-run hypotheses showing what an accepted edit looks like.

## Out of scope

- Tracks 1, 3 and 4 prototypes.
- AWS spot series as Sunday targets: the brief says they are not scored.
