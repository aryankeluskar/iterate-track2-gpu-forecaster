# Round 5 addendum: shared memory (read after the R2 and R3 briefs)

The project's agents share a long-term memory on past.dev. Use it at the start and at the end of your task. It costs a few seconds.

Set `PYTHONPATH=src PAST_ALLOW_WRITES=1` and call `.venv/bin/python -m gpuf.memory ...` from the project root. Identity for research agents: `researcher` (reads all three audiences, writes to `gpuf-experiments`).

1. Before you write your protocol, get a briefing on your topic and read it:
   `python -m gpuf.memory brief --as researcher "your failure mode or idea in a few words" --text`
   It returns refuted and supported hypotheses written by the experimenter, failure modes and dated failure cases written by the autopsy agent, and dated web evidence written by the scout. Say in your protocol.yaml which memory items changed your plan (give their ids), or that none did.
2. For a specific question: `python -m gpuf.memory recall --as researcher "question" --top 5`.
3. When you finish, write one record with your verdict so the next agent finds it (keep it factual and self-contained: claim, failure mode targeted, what you ran, numbers with intervals and sample sizes, verdict):
   `python -m gpuf.memory remember --as researcher --audience gpuf-experiments --id exp-<slug>-<short-topic> --timestamp <now, ISO UTC> --label "Experiment: <slug>" --text-file <file>`

Rules: never put an API key, personal data or anything dated after 2026-11-06 into the memory. A forecaster may only read the memory through `recall --as forecaster --as-of <origin date>`, which is bounded by date. If a memory call fails, carry on with your task and say so in your report.
