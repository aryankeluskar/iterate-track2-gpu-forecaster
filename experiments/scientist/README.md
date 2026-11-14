# scientist: research iterations with no human choice between steps

Code: `src/gpuf/scientist.py` (grammar, evaluator, controller, walk-forward, memory comparison, report, replay) and
`src/gpuf/store.py` (member store with origin-time facts). Tests: `tests/test_scientist.py`. Protocol, fixed before any
result: `protocol.yaml`. Results: `results/replay.md` (plain-language report), `results/tables.md` and `results/summary.json`
(generated), `results/system_final.json` (the frozen system of the 13 October run), `results/systems/` (every frozen system).
Trace: `data_out/scientist_journal.jsonl` (one line per run start, iteration and run end). Model replies are cached in
`data_out/llm_cache/` (logged in `data_out/llm_journal.jsonl`), recall answers in `cache/recall/`, the ledger text given to
the `ledger` condition in `cache/ledger/`, Exa answers in `data_out/exa_cache/scientist_*`.

## Commands (from `track_2/`)

```bash
export OMP_NUM_THREADS=2 PYTHONPATH=src
# inputs (dev only): the member dump (about 90 s) and the origin-time facts (about 10 s)
.venv/bin/python experiments/maturity/dump.py
.venv/bin/python -m gpuf.store --rebuild

# one run: K iterations at one checkpoint (live model, live past.dev, live Exa under the 0.50 USD cap)
PAST_ALLOW_WRITES=1 .venv/bin/python -m gpuf.scientist run --checkpoint 2026-09-25 --iterations 8 --memory pastdev --rep r1

# the main result: checkpoints 2026-09-18, 09-25, 10-02 (6 iterations each, chained), then 2026-10-13 (8 iterations)
PAST_ALLOW_WRITES=1 .venv/bin/python -m gpuf.scientist walkforward
# the memory comparison: 2026-09-25, 8 iterations, none / ledger / pastdev x r1 r2 r3
PAST_ALLOW_WRITES=1 .venv/bin/python -m gpuf.scientist compare
# tables from the journal (later-origin scoring happens only here, never inside a run)
.venv/bin/python -m gpuf.scientist report

# offline replay from the caches (no network): any recorded run, compared row by row with its journal lines
.venv/bin/python -m gpuf.scientist replay --run c0918-pastdev-wf
GPUF_LLM_OFFLINE=1 PAST_OFFLINE=1 LOOP_OFFLINE=1 .venv/bin/python -m gpuf.scientist walkforward   # rewrites journal rows from the caches
.venv/bin/python -m pytest tests/test_scientist.py -q          # offline, a few seconds
.venv/bin/python -m gpuf.scientist validate SPEC.json          # strict check of one candidate spec
```

## What one iteration does (no human input)

1. observe: score the current system on the selection cells (dev origins o with o + 7 <= checkpoint) and build a failure
   report by slice (class, collector, horizon, the 37, panel or not, rows, recent changes, days since a change, outcome
   causes on the 37), with each member's skill if it alone replaced the system in the slice.
2. inspect: the model sees the report, the facts and the grammar, asks for up to three breakdowns (computed by the
   controller) and names a search query.
3. recall: `none` nothing; `ledger` the whole hypothesis ledger plus this run's verdicts; `pastdev` a past.dev recall as
   `proposer`, as of the checkpoint, for a query built from the report, plus this run's verdicts.
4. prior: one Exa search, end published date = checkpoint, undated and later results dropped, trackers excluded.
5. hypothesise: claim, mechanism, spec, falsification rule, prior ids used, expectation.
6. dedupe: a candidate equal to, or the same idea as (protocol.yaml), one tested in this run or carried in the memory
   block is refused without a test; the model gets one retry.
7. test: the fixed gate (both halves of the selection window, 200 cells in 5 series, the 37 not lower, 90% of week-block
   bootstrap resamples positive).
8. record: a journal row with prompts' cache keys, replies, breakdowns, spec, gate numbers, verdict, seconds and
   estimated tokens; one past.dev record `auto-<run>-i<k>` as `experimenter`, timed at the checkpoint.

## Grammar

`{"when": CONDITION, "do": ACTION}`. CONDITION: `{"fact", "op", "value"}`, `{"all": [...]}`, `{"any": [...]}`, `{"not": ...}`
over the 33 origin-time facts of `gpuf.store.FACTS` and the horizon (at most 6 comparisons, 3 levels). ACTION: `members_only`,
`drop_members`, `add_drift`, `last_zero`, `scale_width` (lo, hi in 0..3), `centre_last`, `cover_last`, `shrink_to_last`
(w in 0..1). Unknown facts, values, members, actions or parameters are errors. A system is the base blend plus an ordered
list of rules; the submitted `final` is the base blend of seven members plus rule 0, its 14-day gate on non-headline series.

## Testing `system_final.json` on the held-back weeks (orchestrator only)

The file is fully specified: base members plus ordered rules. To score it, build a member dump for the val origins
(the same columns as `runs/maturity/cells.parquet`), compute facts with `gpuf.store.build_facts(series_frame(), pairs,
allow_any=True)`, construct `gpuf.store.Store` (it refuses non-dev origins; this step needs a deliberate change by the
orchestrator), and call `gpuf.scientist.run_system(store, system)`. Nothing in this folder runs or reads a val origin.
