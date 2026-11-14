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
