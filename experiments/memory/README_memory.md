# Shared agent memory (past.dev): what is where, who writes, who reads

## Which memory holds what

| store | holds | role |
|---|---|---|
| past.dev, audience `gpuf-failures` | 7 failure modes and 60 dated top events (autopsy), plus 3 test cases | recall for failure cases |
| past.dev, audience `gpuf-evidence` | dated web evidence with URL, published date and the quoted sentence (scout), 10 items | recall for evidence |
| past.dev, audience `gpuf-experiments` | every hypothesis of the ledger (`exp-<H id>`), kept in step by `sync-ledger` | recall for tested hypotheses |
| `data_out/memory_journal.jsonl` | every live write and recall (request, response, time, agent) | offline replay; `PAST_OFFLINE=1` needs no network |
| `data_out/ledger.jsonl` | the hypothesis ledger | source of truth for hypotheses; past.dev is a searchable copy |
| `data_out/memory_ledger_state.json` | hash of each ledger entry last synced | lets `sync-ledger` send only new or changed entries |
| markdown (`findings.md`, `research-log.md`, `experiments/*/`) | findings for humans | not in past.dev |

Project: existing `default-project`. Ids are stable (`exp-H7b`, `autopsy-<series>-<date>`, `autopsy-mode-<id>`, `scout-<sha8 of url>`): sending the same id again replaces the data point when anything changed, and is free and a no-op when nothing did. Timestamps are when the information became known (end of day UTC for date-only sources; the later of Exa's published date and any date in the page text; failure modes are timed 2026-10-13, the end of the dev events they summarise). Experiments are timed at their `updated_utc`.

## Who writes, who reads

| identity | writes (author) | reads |
|---|---|---|
| `autopsy` | gpuf-failures | failures, evidence, experiments |
| `scout` | gpuf-evidence | failures, evidence |
| `experimenter` | gpuf-experiments (via `sync-ledger`) | failures, evidence, experiments |
| `researcher` | gpuf-experiments (method agents) | failures, evidence, experiments |
| `proposer` | nothing | failures, evidence, experiments |
| `forecaster` | nothing | failures, evidence (never experiments), always with `--as-of` the forecast origin |

Audience decides who can read; `--as` on a recall is the reader; the author is stored in `identity` and `metadata.agent`.

## Commands

Run from `track_2/`, with `PYTHONPATH=src` (or the project's venv setup). Live calls need `PAST_ALLOW_WRITES=1`; `PAST_OFFLINE=1` replays from the journal (a question never asked before is answered from the journalled writes by word overlap, a crude fallback). Output is JSON on stdout; failure exits 1 with the error on stderr (the API key is scrubbed everywhere). `python -m gpuf.memory --help` and `<command> --help` show examples.

```bash
export PYTHONPATH=src PAST_ALLOW_WRITES=1
# read: one row per source data point, with author, date, excerpt
python -m gpuf.memory recall --as proposer "upper tail under-covered at 7 days" --top 5
python -m gpuf.memory recall --as forecaster --as-of 2026-10-06 "announced price increases effective soon"
# write one data point and wait for completion
python -m gpuf.memory remember --as researcher --audience gpuf-experiments --id exp-H40 \
  --timestamp 2026-11-14T21:00:00Z --label "Experiment: H40" --text-file notes.txt
# send ledger entries that are new or changed since the last sync (--dry lists them)
python -m gpuf.memory sync-ledger
# briefing before starting work: refuted hypotheses, failure modes, evidence (only what the identity may read)
python -m gpuf.memory brief --as proposer "upper tail under-covered at 7 days" --text
python -m gpuf.memory usage          # credits left
PAST_OFFLINE=1 python -m gpuf.memory brief --as proposer "upper tail under-covered at 7 days"   # no network
```

Every recall costs 1 credit, every 350 bytes sent cost 1 credit (rounded up per data point); polls and unchanged re-sends are free. A brief is up to 3 recalls. Ingestion takes about 6 to 8 s per record and a batch can queue behind other sends (a 29-record batch took 2 to 6 minutes); recalls take about 1 s.

Method agents: run `brief --as researcher "<your topic>"` before starting; after a test, update the ledger (`gpuf.ledger.put`) and run `sync-ledger`. Write only to `gpuf-experiments` as `researcher`; do not write other audiences.

## Caveats from the live runs

- Recall returns about 8,000 tokens of ranked memories across all audiences the identity can read; a topic phrased like an experiment can return mostly failure cases. `brief` words each section's query like its records and filters by `metadata.kind`.
- Derived memories (claim, observation) sometimes come back instead of the source text; the briefing then shows the derived sentence.
- The forecaster's date bound held in every live check (raw API response, not only our filter); see `results/test_report.md`.
- Offline `sync-ledger` keeps its own state file (`memory_ledger_state_offline.json`) and writes the journal only.

Reproduce the live runs: `build_records.py` (records from files), `run_test_send.py`, `run_test_recall.py`, `write_test_report.py`, `run_import.py`, `run_demo.py` (all in this folder; live ones need `PAST_ALLOW_WRITES=1`).
