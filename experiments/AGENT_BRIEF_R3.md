# Round 3 addendum: breadth swarm (read after AGENT_BRIEF.md and AGENT_BRIEF_R2.md)

Read `experiments/AGENT_BRIEF.md` (task, harness, method interface) and `experiments/AGENT_BRIEF_R2.md` (where the project stands, the failure picture, hard rules). Everything there applies. This file adds what is new for round 3.

## Goal of this round

Speed and breadth. About fourteen agents run at once, each on one direction. Find out fast whether your direction adds skill on dev beyond what we have, and why. Report a clean number either way. Time budget 30 minutes unless your task says otherwise: simplest version first, score it, then at most two refinements.

## Dev leaderboard (rental_headline, 4,278 cells, pooled skill against last value)

| method | skill | coverage |
|---|---|---|
| ens of three `mix` variants | 0.188 | 0.75 |
| ens of mix + gbm + chronos_last | 0.182 | |
| `mix` {"pool":"cc","k":20,"state":"chgk","sk":3,"hl":30} | 0.169 | 0.73 |
| `timesfm` {"centre":"last"} | 0.149 | 0.69 |
| `chronos` {"centre":"last"} | 0.144 | 0.75 |
| `gbm` {"mode":"full","train":"all"} | 0.142 | 0.74 |
| `calib` {"pool":true} | 0.123 | 0.66 |
| `drift` | 0.089 | 0.63 |

Two bars for every report: the paired difference against `drift`, and against `mix` with the params above (the reference single model). A direction matters if it beats `mix`, or if blending it with `mix` through `ens` beats `mix` (it adds something `mix` does not have). Always report the blend.

Validation history, for context only (you never touch validation): on 13 to 30 October the rank order flipped against dev; chronos_last scored 0.206, mix + gbm 0.154, three mix 0.127, drift 0.084. So width taken from a pretrained model generalised better than our fitted widths. Robustness across periods counts for more than a small dev gain.

## Useful tools already on disk

- `experiments/dump.py OUT.parquet METHOD 'PARAMS_JSON' [--universe rental_headline|rental_all] [--split dev]` saves a method's dev forecasts; the `replay` method reads them back ({"path": ...}); `ens` blends members by averaging log quantiles ({"members": [[name, params], ...]}).
- Cached dev forecasts: `runs/cache/chronos_last_rental_headline.parquet`, `runs/cache/timesfm_last_rental_headline.parquet`, and the `_rental_all` versions. Never read `runs/cache/*val*`.
- `runs/failure/blend_dev_cells.parquet`: the blend's dev cells with truth and loss. `experiments/failure/decomp.py` shows how the outcome buckets are computed.
- `gpuf.compare` gives the paired difference with a 90% week-block bootstrap interval. `experiments/sweep.py` shows a compact way to score many variants in one process.
- A dev run of a light method takes about 2 seconds.

## Shared machine rules

- 15 cores and 24 GB of RAM are shared by all agents. Set `OMP_NUM_THREADS=2` (and `MKL_NUM_THREADS=2`, `torch.set_num_threads(2)`) in everything you run. Keep each process under 3 GB unless your task is a pretrained model. Do not load pretrained models unless your task says so.
- Every module in `src/gpuf/methods/` is imported by every agent's runs. A module that fails to import breaks everyone. Keep heavy imports (torch, lightgbm, tabpfn, transformers) inside `make()`, and run `PYTHONPATH=src .venv/bin/python -c "import gpuf.methods as m; print(m.names())"` after every save of a methods file. A method name may be registered once: use your slug.
- Your files only: `src/gpuf/methods/<slug>*.py`, `experiments/<slug>/` (protocol.yaml, code, `results/` for small files worth keeping), `runs/<slug>/` (git-ignored scratch), `tests/test_<slug>*.py`.
- Use `--no-log` while debugging so `data_out/trajectory.jsonl` holds only runs you would report.

## Final report (under 350 words)

Verdict in one line (beats mix / adds in a blend / ties / loses). Best configuration with exact params. Dev pooled skill, difference against drift and against mix with 90% intervals, coverage. The blend with mix. Breakdown of the gain by collector, horizon and outcome bucket (no change, under 1%, 1 to 5%, up over 5%, down over 5%). Mechanism in two or three sentences. Variants tried, one line each. Whether you nominate it for a validation query and with which frozen params. What you ran versus what you assume.
