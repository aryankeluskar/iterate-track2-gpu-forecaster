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
