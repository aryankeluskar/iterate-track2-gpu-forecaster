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
