# Round 9 shared brief: improvement phase (read fully before starting)

You are one of about five agents working in parallel in `/Users/aryank/Developer/iterate_hackathon/track_2` (its own git repo, branch as checked out). The orchestrator reads only your final report and the files you name in it. Hackathon deadline: Sunday 15 November 2026, 14:00 PT. Today is Saturday 14 November.

Read first, in this order: `description.md` (the organisers' brief), `AGENTS.md` (commands and rules), `research-state.yaml` (where the project stands), `experiments/advisor/advice.md` (an independent adviser's diagnosis; your task comes from it), `experiments/audit/results/audit.md` (what an adversarial audit found). `research-log.md` is the authoritative history. Older shared briefs (`experiments/AGENT_BRIEF.md`, `_R2`, `_R3`, `_R5`) describe the harness, the method interface, the offer panel and the shared memory; read the parts your task touches.

## Where the project stands

- Task: forecast q10/q50/q90 of posted GPU rental prices at 1, 3 and 7 days from origin 2026-11-06. The score is pinball loss, reported as skill against the last value (0 = no better than assuming the price stays put). The organisers' baseline is `drift`.
- Submitted forecaster `final`: equal-weight blend (mean of log quantiles) of seven members: mix, gbm, chronos (long context), analog, prov, fm2 (16-day context), fragility; a 14-day zero-width gate on non-headline series. `bash reproduce.sh final` rebuilds `submissions/forecast_final_*.csv` in about 25 s.
- Practice dates (split `dev`, origins 2026-08-18..2026-10-06, targets to 2026-10-13), 37 headline series: final 0.208, mix 0.169, drift 0.089. Held-back weeks (split `val`, 2026-10-13..2026-10-30): final 0.214 against drift 0.084 on the 37; 0.228 against 0.102 on the other posted rental series.
- The finding behind it: each published price is the median of a short list of provider offers (3 to 17), reproducible from the pack's offer rows. Simulating the provider offers behind the median (`prov`) is the strongest single idea. The Exa announcement calendar helps on two practice episodes only and is switched off in the submission.
- Ledger: 37 hypotheses (13 supported, 15 refuted, 7 not significant, 2 untestable): `PYTHONPATH=src .venv/bin/python -m gpuf.ledger`.

## What the audit and the adviser found (do not repeat these mistakes)

- The 37 series were chosen as of 6 November (hindsight). The held-back weeks have 3 calendar weeks: ranges there are rough, never "90% intervals". Only prov and fm2 clearly hold on the held-back weeks under a stricter test.
- The non-headline series were used on practice dates (member selection, the gate). Never write "never used for any choice"; write "first evaluation on these series in the held-back weeks".
- New diagnostic (dev only, `experiments/maturity/results/diag.txt`, `slice.txt`): on cells where the series already met the organisers' headline rule at the origin (60 rows or more), `final` beats drift by +0.017, against +0.119 on the fixed 37; on those cells mix alone (0.171) beats `final` (0.154). Most of those cells are four hyperscaler-spot series; the mature rate-card evidence is one week. All 37 series are mature at the scored origin. This is a risk to the Sunday result and is being followed up by the orchestrator.
- The research loop (`src/gpuf/loop.py`) has commands for autopsy, scout (Exa), prior, propose, gate and forecast, but `propose` invents nothing: every hypothesis so far was written by an agent under direction. Nothing measures what the shared memory adds.
- The adviser's ranked list is in `experiments/advisor/advice.md` section 3. Its acceptance tests are the standard your work is held to.

## Hard rules

1. Practice dates only. Never run, score or read forecasts for origins 2026-10-13..2026-10-30 (split `val`), and never tune anything on numbers already reported for those weeks. Only the orchestrator runs held-back checks.
2. A forecast or feature for an origin may use only rows dated on or before it. Anything new that reads a table directly needs a test that deletes and corrupts later rows and gets bit-identical output (see `tests/test_prov_leak.py`, `tests/test_analog_leak.py`).
3. Never fetch price data from the network. Exa searches set an end published date on or before the as-of date and never later than 2026-11-06; undated results are discarded; live price-tracker pages are never opened. Exa spend cap for your whole task: 1 USD unless your task says otherwise. API keys are in `../.env`; never print or commit them.
4. Machine: 24 GB laptop shared by all agents. `export OMP_NUM_THREADS=2`. Run one process at a time, each under 3 GB. Before any run longer than a minute check `uptime`; if the 1-minute load is above 8, wait. No model training, no torch, no new heavy dependencies. Shell is zsh: call `.venv/bin/python` directly with `PYTHONPATH=src`.
5. Git: do not commit, do not push, do not touch git config. The orchestrator commits. Write only inside the folders and files your task names. Other agents are editing other files at the same time: do not reformat, move or "clean up" anything outside your scope. Do not edit `src/gpuf/methods/final.py`, `reproduce.sh`, `submissions/`, `EVAL_PROTOCOL.md`, `research-log.md`, `research-state.yaml`, `data_out/ledger.jsonl` unless your task says so.
6. Protocol before results: write `experiments/<your-slug>/protocol.yaml` (question, what you will run, the acceptance test with its thresholds, what would make you drop the claim) before you compute any result, and do not change the thresholds afterwards. If you must deviate, say so in the report.
7. Honesty: report null and negative results as they are. Give sample sizes and say what is in-sample. Never present a number you did not compute; never round a failure into a success. If the acceptance test fails, say "failed" and stop tuning.
8. Shared memory (past.dev): follow `experiments/AGENT_BRIEF_R5.md` (brief before you start, one record when you finish; identity `researcher`). If a memory call fails, carry on and say so.

## Tools already in the repo

- `gpuf.llm` (`src/gpuf/llm.py`): `ask(prompt, tag)` and `ask_json(prompt, tag)` call GPT-6 Astra through the headless Devin CLI in an empty folder (about 3 s a call), refuse any reply that used a tool, cache every reply in `data_out/llm_cache/` and log to `data_out/llm_journal.jsonl`. `GPUF_LLM_OFFLINE=1` replays from the cache only. Use `salt` for independent draws of the same prompt. Use this for any model call your code makes; do not add another client.
- Member store for practice dates: `runs/maturity/cells.parquet` (built by `experiments/maturity/dump.py`, about 90 s, dev only): one row per (series, origin, horizon) for all 357 posted rental series with history, with the truth `y`, the last value, `baseline_loss`, each member's q10/q50/q90 (NaN where the member gave no forecast), drift's quantiles, and origin-time facts (`rows`, `span`, `tier`, `in37`, `gate14`, `chg14`, `chg30`, `cls`). `experiments/maturity/slice.py` shows how to blend and score from it.
- Offer panel: `gpuf.panel` (offers behind each median, truncated at the origin). Harness: `gpuf.harness`, `gpuf.scoring.score_fast`, `gpuf.compare.paired` (week-block bootstrap). Loop: `gpuf.loop`. Memory: `gpuf.memory`. Exa: `gpuf.scout.exa_call` through `gpuf.loop._exa` (cached in `data_out/exa_cache`).

## Your final report (the only thing the orchestrator reads)

Plain language, short sentences, no jargon that is not defined. In this order: what you built and where it is; the acceptance test and whether it passed, with the numbers and the file each comes from; what failed or stayed uncertain; what you typed in by hand rather than read from a file; every file you created or changed; the exact commands to reproduce. Keep a running `experiments/<your-slug>/STATUS.md` (three to ten lines, updated at each milestone) so progress is visible before you finish.
