# Round 2 shared brief: failure-driven research (read fully before starting)

You are one of several agents working in parallel in `/Users/aryank/Developer/iterate_hackathon/track_2` (its own git repo). The orchestrator reads only your final report. Read `experiments/AGENT_BRIEF.md` first for the task, the harness and the method interface; this file updates it. `description.md` is the organisers' brief.

## Where the project stands (Saturday 14 Nov 2026, midday)

Hackathon: Iterate SF, Track 2 (Pacific). Forecast q10/q50/q90 of posted GPU rental prices at 1, 3 and 7 days for origin 2026-11-06. Scored set: 37 headline rental series (20 `fastgpu_daily`, 13 `gpurentalprices`, 4 `afhubbard`). Judged on rigour, economic insight, reproducibility and originality, not on leaderboard position alone. Sponsor prizes we also target: Exa (search must be central to the main loop, sources shown) and past.dev (several agents write to and read from a shared memory).

Splits (EVAL_PROTOCOL.md, Amendment 1): dev = daily origins 2026-08-18..2026-10-06 (targets up to 2026-10-13); validation = 2026-10-13..2026-10-30, run by the orchestrator only.

Scores so far, pooled skill against last value on dev headline (4,278 cells), difference against drift with 90% week-bootstrap interval:
- drift +0.0886 (coverage 0.63). On cells where drift has 20+ samples: +0.153.
- `mix` {"pool":"cc","k":20,"state":"chgk","sk":3,"hl":30} (pooled empirical h-day changes by collector and class, conditioned on "changed in the last 3 days", recency-weighted): +0.081 over drift.
- `gbm` (pooled LightGBM quantiles): +0.053 over drift. Chronos-Bolt and TimesFM zero-shot: raw quantiles lose (-0.05); keeping the last value as centre and only the model's width gives +0.055 to +0.061.
- Blend mix + gbm + chronos_last: dev skill 0.182. Validation: 0.197 against drift 0.084.
- Every method has the same q50 loss as the last value. All gain so far is interval width, nearly all at h=7.

## The failure picture (dev, `runs/failure/decomp.txt`, `runs/failure/events.txt`)

- 52% of cells have no change and carry 0% of last-value loss. Moves above 5% are 9% of cells and carry 61% of the loss (up-moves 46%, down-moves 15%). 10 of 50 origin days carry 56% of the loss.
- Hindsight bounds for the blend (0.182): knowing whether the price moves 0.219; knowing direction 0.226; both 0.262. The remaining loss is the size of jumps.
- The upper tail is under-covered at h=7 by every method (27 to 33% of truths above q90).
- Refuted on dev (do not retry without a new reason): smoothed centre; signed momentum state; collector-wide breadth of changes as a width signal (H7); gpurentalprices leading fastgpu by a day as a centre shift (H8); reversal after a >5% one-day move as a centre shift (H9); shorter drift windows.
- Exa news burst (H10): 7-day count of dated "price increase" headlines, used to widen q90: +0.0096 skill on dev, interval [-0.004, +0.015], gain comes from one episode (mid-September to early October, the Nebius repricing). Not significant.

## The new lever (verified by the orchestrator)

The scored value is a median over a small panel of posted offers, and the panel is in the pack. `daily_statistics.median_usd_per_gpu_hour` is reproduced exactly (fastgpu 100% of 2,770 series-days, gpurentalprices 99.94% of 7,193; the misses are .5 rounding) by:

```sql
select dt, gpu_model, pricing_tier, instrument_class, median(usd_per_gpu_hour), count(*) n_obs, count(distinct provider) n_providers
from read_parquet('data/pack/gpu-price-pack-v0.1.1-handover/rental_observations/source_id=<src>/*/*.parquet')
group by all
```

Columns include `provider`, `region_raw`, `sku_raw`, `gpu_count`, `available`, `quality_flag`. Series id format: `<source_id>.<instrument_class>.<gpu_model with spaces as underscores>.<pricing_tier>.median` (check `src/gpuf/data.py`). A median over n offers can only move when an offer near the middle is repriced or when offers enter or leave the panel. So every jump has an observable cause, and the set of values the median can jump to is largely known in advance (the neighbouring order statistics).

## Research stance for this round

Do not sweep for skill. Start from a failure mode, measure how much loss it carries, explain its cause, then test one change aimed at it. State what you ran versus what you infer. A clean negative result is a deliverable.

## Hard rules

1. Dev only. Never run `--split val`. For analysis outside the harness, never read rows dated after 2026-10-13. Never fetch price data from the network. Any web search must set an end published date on or before 2026-11-06.
2. A forecast for origin d may use only rows dated on or before d. If you read pack tables directly inside a forecaster, filter by date there and add a test that perturbing rows after the origin leaves the forecast unchanged.
3. Read-only: `data/pack/`, `src/gpuf/harness.py`, `scoring.py`, `splits.py`, `data.py`, `EVAL_PROTOCOL.md`, `research-state.yaml`, `findings.md`, `research-log.md`, `.scratch/`, and other agents' files. Write only to the paths your task names.
4. Before your first scored run, save `experiments/<slug>/protocol.yaml`: failure mode targeted, its measured loss share, mechanism, prediction (direction, rough size, where) and what would refute it.
5. Do not git commit. Install packages only with `uv pip install --python .venv/bin/python <pkg>`. Shell is zsh: call `.venv/bin/python` directly with `PYTHONPATH=src`.
6. Never print, log or copy an API key. Keys are read from the environment or `../.env` by code.
7. Do not start subagents. Do the work yourself.

## Final report (under 400 words, plain prose and short lists)

Verdict in one line. The numbers that support it, each with its sample size and interval where one applies. The mechanism in two or three sentences. Files you wrote. What you ran versus what you assume, and anything that failed. The single next step you would take.
