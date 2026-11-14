# exatrace status

- 13:40 PT: brief and context read; protocol.yaml frozen before any result.
- 13:45 PT: task 1 arms done (results/arms_summary.json). A1: the deferred arm is bit-identical to off. A2: all 101 changed cells are inside the 142 affected. A3: removing an event restores off on its own cells. A4: the no-price arm equals off. Lag 0: 0.216 -> 0.308 on 2,331 cells (two events, an in-sample mechanism demo).
- 13:48 PT: trace rows written (results/trace_series.csv, trace_sources.csv, trace_events.json).
- 13:52 PT: task 2 (scout evidence passes `assess`) and task 3 (prior --as-of) done in src/gpuf/loop.py.
- 13:55 PT: task 4 forward search done ($0.243). No announcement found effective 7-13 Nov; nothing flagged. Calendar file not appended.
- 14:00 PT: full suite: 89 passed. The one failure, test_memory live opt-in, came from my extra PAST_OFFLINE=1 and passes when rerun with the AGENTS.md command. tests/test_loop.py: 7 pass offline, including one test added after the full run. results/trace.md written; memory record exp-exatrace-causal-trace ingested. DONE.
