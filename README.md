# GPU rental price forecaster: a research loop that forecasts the offer panel under each posted median

This repository is a Track 2 entry (Pacific Machines) at the Iterate AI Research Hackathon, with the Exa and past.dev challenges. It forecasts posted GPU rental prices 1, 3 and 7 days after 6 November 2026, with q10, q50 and q90 quantiles, for every posted rental series in Pacific's data pack, and argues a 2 to 3 year view of H100 and A100 rents and resale. The forecaster came out of a loop that attributes its own forecast loss to causes in the offer panel, tests hypotheses on development dates and gates them on unseen dates; every hypothesis, refuted or not, is in `data_out/ledger.jsonl`.

**Read [FINDINGS.md](FINDINGS.md) first.** It supersedes the early working note, kept only as a record at `experiments/writeup/findings_early.md` (it was `findings.md`; on a case-insensitive disk the two names cannot coexist). `research-log.md` is the authoritative day log, corrections included.

## Quickstart

Environment: Python 3.12. `pyproject.toml` pins the eight packages the submitted forecaster needs (numpy, pandas, duckdb, pyarrow, lightgbm, chronos-forecasting, torch, transformers) at the versions used here; tests, figures and side experiments need the optional group `research`. Put the unchanged pack at `data/pack/gpu-price-pack-v0.1.1-handover/` (git-ignored). Then:

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r pyproject.toml    # add `--extra research` for the tests
bash reproduce.sh final
```

Checked on 14 November: a fresh clone with a fresh environment built from `pyproject.toml` alone reproduces both hashes below (`research-log.md`, clean-environment rebuild entry).

It checks the pack against `MANIFEST.sha256`, rebuilds the series and catalog as of 2026-11-06 with the starter's `build_series.py`, builds the two pretrained members in their own processes (LightGBM and torch cannot share one process on this machine), blends the seven members and validates both files with the starter scorer in frozen-cutoff mode. It takes about 25 s here. Expected:

- `submissions/forecast_final_all.csv`: 1,776 rows, 592 series, 249 of them at zero width, 0 schema problems, scorer status `scored_no_cells` (no truth exists after the cutoff), 0 refusals. SHA-256 `7b49870ea47622fc9cb1375bdf8a43c047d5254a6a6dc944c8d06bc2f1e93809`.
- `submissions/forecast_final_headline.csv`: 111 rows, the 37 headline series. SHA-256 `90330d1ea2a90a957e41839ca91d3c0b67234277a7b042f6b967a82a18247123`.

These match the hashes in `research-log.md` after the audit's analog fix (13:03 entry) and the rerun after the calendar's ninth entry (13:07 entry); runs are byte-identical.

Live demo, no install: https://aryankeluskar.github.io/iterate-track2-gpu-forecaster/demo/

Two-minute walkthrough of that page: https://github.com/aryankeluskar/iterate-track2-gpu-forecaster/releases/download/demo-2026-11-14/demo-2min-720.mp4

Model weights: the `final` run needs the Chronos-Bolt-small weights (`amazon/chronos-bolt-small`) in the local Hugging Face cache. The script sets `HF_HUB_OFFLINE=1`, so it fails rather than downloads. Fetch them once, with network, by running the one-liner printed in the header of `reproduce.sh`. No data is fetched from the network.

## Repository map

| path | what it holds |
|---|---|
| `FINDINGS.md` | the findings: question, method, evaluation, results, iterations, negative results, economic insight, long-run view |
| `reproduce.sh` | the one command |
| `EVAL_PROTOCOL.md` | the evaluation protocol and its four amendments (the fourth: the late-window check, `experiments/late/`) |
| `research-log.md` | decisions, validation declarations and corrections, timestamped |
| `src/gpuf/` | harness (`harness.py`, `splits.py`, `scoring.py`), offer panel (`panel.py`), submission (`submit.py`, `final_build.py`), loop CLI (`loop.py`), Exa client (`scout.py`), past.dev client (`memory.py`), ledger (`ledger.py`) |
| `src/gpuf/methods/` | every forecaster tried; the submitted blend is `final.py` over `mix`, `gbm`, `foundation` (Chronos width), `analog`, `prov`, `fm2`, `fragility` |
| `experiments/<name>/` | one folder per direction: protocol, code, results |
| `experiments/audit/` | the independent audit of the evaluation |
| `data_out/` | ledger, validation log and results (`val_query_log.jsonl`, `val_gate.jsonl`), repricing calendar, Exa cache, memory and loop journals |
| `submissions/` | the forecast files |
| `tests/` | leak tests for every method that reads a table directly, scorer, loop and memory tests |
| `to_human/` | plain-language notes for the team |
| `ATTRIBUTION.md` | data, model and library credits |

## Where Exa is called

- `src/gpuf/scout.py`, `exa_call()`: the single cached client for Exa `search` and `contents` (cache in `data_out/exa_cache/`, so reruns are free and offline). `search_day()` in the same file served the news-burst signal (H10, not significant).
- `src/gpuf/loop.py`, `_exa()`: the loop's only route to Exa, through `scout.exa_call`. It is used by `step_scout()` and `step_prior()`.
- `experiments/calendar/` (`search.py`, `build_calendar.py`): the agent-run searches that built the repricing calendar, `data_out/repricing_calendar.jsonl`.
- `experiments/exatrace/forward.py`: the search for announcements due in the scored week, through the same cached client.

What the main loop does with the results. `step_scout` recalls dated failure cases written to past.dev by the autopsy step, searches Exa for announcements by the providers involved, with every search's end published date bounded by `--as-of`, extracts dated price changes with the calendar's rules and appends them to the calendar, and writes the sources to past.dev. `step_prior` searches Exa for prior work on a claim before compute is spent on it. The calendar feeds the provider simulator's optional switch (`cal` in `src/gpuf/methods/prov.py`), which applies announced repricings from their publication date. **That switch is off in the submitted forecast.** Its dev gain rests on two events and is in-sample, it could not be checked on validation, and EVAL_PROTOCOL.md Amendment 3 allows it on only if it leaves the 6 November forecast unchanged; the only entry in the Sunday window (Lambda, effective 16 November) falls after the last target. So the submitted numbers do not depend on Exa. What Exa found and how it was used, with sources, is in FINDINGS.md section 6.

**What breaks if Exa is removed.** The submitted forecast does not: `bash reproduce.sh final` reads no Exa output. What breaks is the research loop's evidence path: `python -m gpuf.loop scout` can no longer find dated price announcements, so no calendar lines and no evidence records are made, and `prior` can no longer check a claim against dated outside sources. Recorded traces stay checkable because every response is cached in `data_out/exa_cache` and replays with `LOOP_OFFLINE=1`. With the calendar switch on, on the two practice episodes that had dated announcements, deleting the sources changes the forecasts: skill on the 142 cells between announcement and effect falls from 0.4756 to 0.1539, and moving the same sources to after the target date gives forecasts bit-identical to no calendar (`experiments/exatrace/results/trace.md`). That is a demonstration of the mechanism on two events, not a validated gain, which is why the switch stays off. A forward search found no dated announcement of a change taking effect in the scored week by any provider at or next to the middle of a scored list. Exa spend: $7.62 before this round, plus $0.24 for the forward search.

## Shared memory (past.dev)

Which memory holds what:

| store | holds |
|---|---|
| past.dev, audience `gpuf-failures` | failure modes and dated failure cases of the median forecast, written by `autopsy` |
| past.dev, audience `gpuf-evidence` | dated web evidence (URL, published date, quoted sentence), written by `scout` |
| past.dev, audience `gpuf-experiments` | the hypothesis ledger, one record per hypothesis, written by `experimenter` (`sync-ledger`) and `researcher` (method agents) |
| `data_out/ledger.jsonl` | source of truth for hypotheses; past.dev holds a searchable copy |
| `data_out/memory_journal.jsonl` | every live write and recall, for offline replay (`PAST_OFFLINE=1`) |
| markdown (`research-log.md`, `FINDINGS.md`, `experiments/*/`) | the record for humans; not in past.dev |

Writers: `autopsy`, `scout`, `experimenter`, `researcher`. Readers: those four plus `proposer` and `forecaster`. Cross-agent reads: `scout` reads the failure cases `autopsy` wrote and searches for the providers they name (`experiments/memory/results/cross_agent_demo.md`, section a, and `step_scout`); `proposer` briefs itself from all three audiences before a hypothesis is written (section b, `step_prior`, `step_propose`). The `forecaster` identity reads only failures and evidence, never experiments, and always with `--as-of` set to the forecast origin; in every live check nothing dated after the origin came back (`experiments/memory/results/test_report.md`). The `status` command counts 165 data points (77 failures, 48 evidence, 40 experiments).

Did the memory improve results? We did not measure an effect on forecast accuracy, and no number in FINDINGS.md depends on it. What it did: it let a scout read another agent's failure cases and turn them into a list of providers and dates to search, it gave later agents a briefing of refuted hypotheses before they started (`experiments/AGENT_BRIEF_R5.md`), and it gave the forecaster a date-bounded read of evidence. Measuring an effect would need runs of the same agents with and without the memory on the same tasks, scored on how many already-refuted ideas they re-test and on the dev gain of what they propose.

## Tests

```bash
OMP_NUM_THREADS=2 PYTHONPATH=src .venv/bin/python -m pytest tests -q
```

The loop and memory tests run offline. A quick subset: `tests/test_loop.py tests/test_analog_leak.py tests/test_prov_leak.py`.

## Data licence and attribution

The pack is Pacific Machines' gpu-price-pack v0.1.1-handover, CC BY 4.0 on the compilation; each upstream source keeps its own licence. Credits, with the wording the pack requires, are in [ATTRIBUTION.md](ATTRIBUTION.md). Web sources found through Exa are cited by date, title and link in FINDINGS.md.

## Team and tools

Built during the hackathon (first commit 14 November 2026, 10:31 PT) by a human working with LLM coding agents: an orchestrator agent directed by the human launched research agents in rounds, and those agents wrote the hypotheses, forecasters and reports; an independent agent audited the evaluation. Pretrained model in the submission: Chronos-Bolt-small (`amazon/chronos-bolt-small`). Other pretrained models tried and not submitted: Chronos-Bolt-base, Chronos-2, TimesFM 2.5, Laya. Main libraries: numpy, pandas, duckdb, pyarrow, LightGBM, PyTorch, chronos-forecasting, scikit-learn, matplotlib, pytest. APIs: Exa (search), past.dev (memory).
