# The scientist, replayed on the practice dates

Plain-language report. Every number here is in `results/tables.md` or `results/summary.json` (both written by
`python -m gpuf.scientist report` from `data_out/scientist_journal.jsonl`) unless the line says where else it comes from.
Protocol, fixed before any run: `experiments/scientist/protocol.yaml`.

## What was built

One command runs research iterations with no human choice between steps:
`python -m gpuf.scientist run --checkpoint C --iterations K --memory none|ledger|pastdev --rep r1`.
In each iteration the program scores the current forecaster on the cells whose outcomes were known by the checkpoint,
writes a failure report, asks the model (GPT-6 Astra through `gpuf.llm`) which further breakdowns it wants, reads
memory, runs one Exa search for prior work dated on or before the checkpoint, asks the model for one hypothesis written
as a rule in a small grammar, refuses the rule without testing it if it is the same idea as one already tested, tests it
with a fixed gate, keeps or rejects it, and writes the full trace and one memory record.

A rule says "in cells where these origin-time facts hold, change the forecast this way" (use only some members, drop
members, add drift, last value with zero width, widen or narrow the tails, move the centre to the last value, cover
the last value, shrink toward the last value). The forecaster at the start is the submitted `final`: its seven-member
blend plus its 14-day gate, written as rule 0. The program reproduces the harness's `final` cell losses exactly
(maximum absolute difference 0.0 over 40,338 dev cells).

Selection and evaluation are separated by time. At checkpoint C the program only sees dev origins at least 7 days
before C, as a separate data store built before anything else runs. Later origins are scored only by `report`,
after a run has frozen its system.

## The walk-forward (main result): FAILED to improve on later origins

Checkpoints 18 September, 25 September and 2 October, 6 iterations each, each starting from the system frozen at the
previous one, memory `pastdev` bounded at the checkpoint. 18 iterations, 18 tests, 4 rules kept, 14 rejected, 0 human
interventions, 36 model calls.

| checkpoint | later origins | origins | cells all / 37 | rules kept so far | d all [90% week-block range] | d 37 |
|---|---|---|---|---|---|---|
| 2026-09-18 | 19 to 24 Sep | 6 | 5,671 / 666 | 3 | -0.0385 [-0.045, -0.021] | 0.0000 |
| 2026-09-25 | 26 Sep to 1 Oct | 6 | 5,803 / 666 | 4 | -0.0296 [-0.040, -0.026] | 0.0000 |
| 2026-10-02 | 3 to 6 Oct | 4 | 4,187 / 444 | 4 | -0.0271 [-0.027, -0.027] | 0.0000 |
| pooled | 19 Sep to 6 Oct | 16 | 15,661 / 1,776 | - | -0.0310 [-0.039, -0.025] | 0.0000 |

"d all" is the self-modified system's pooled skill minus the frozen submitted system's, on all posted rental series,
on origins it had not seen. Negative means worse. Pooled skill on those origins: 0.1109 against 0.1419. The protocol's
claim "the system improved on later origins" needed pooled d all above zero: it is -0.031, so the claim fails. The
range is a block bootstrap over ISO weeks, and each block spans only 2 weeks (4 pooled), so the ranges are rough; with
16 origins this is a small test. On the 37 headline series nothing changed: every kept rule excludes them (see below).

Every kept rule, its gain when it was kept and its own marginal gain on later dev origins:

| rule | kept at | what it does | gain on selection data | gain on later origins (origins) |
|---|---|---|---|---|
| c0918 i1 | 18 Sep | analog alone on non-headline marketplace asks that changed in the last 6 days | +0.0271 | -0.0016 [-0.008, +0.009] (18) |
| c0918 i2 | 18 Sep | last value, zero width, on non-headline neocloud rate-card and spot series outside the 14-day gate | +0.0078 | -0.0335 [-0.048, -0.024] (18) |
| c0918 i4 | 18 Sep | tails 25% wider on non-headline marketplace asks that changed in the last 6 days | +0.0194 | +0.0035 [+0.002, +0.009] (18) |
| c0925 i2 | 25 Sep | last value, zero width, on non-headline hyperscaler list series outside the gate, horizons 1 and 3 | +0.0042 | +0.0038 [+0.002, +0.005] (11) |

Two of four kept rules helped later, one was neutral, and one did most of the damage. Why the zero-width neocloud
rule failed (computed for this report with the store; the command is in the README section "diagnostic"): when it was
kept, its condition covered 846 selection cells in 60 series and the price moved in 5.1% of them (0.4% of the
window's last-value loss). On the later origins the same condition covered 2,477 cells in 99 series and the price
moved in 51.9% of them (12.6% of the window's last-value loss); in the afhubbard neocloud series it went from 0% to
73%. Late September brought repricing waves to series that had been quiet, and new series entered the condition. The
gate looked only at a quiet past, and "both halves positive" does not protect against a change of regime.

The 13 October run (all dev outcomes known, 8 iterations, starting from the 2 October system) kept 2 more rules
(prov alone on recently changed non-headline fastgpu series; tails 25% wider on non-headline hyperscaler spot series
with 8 or more changes in 14 days). Its frozen system is `results/system_final.json` (7 rules including rule 0). It
was not evaluated on any origin after 6 October here. It still carries the harmful neocloud rule: rules are only ever
added, and nothing in the loop removes a rule that later fails. On the 37 headline series it forecasts exactly what
the submitted `final` forecasts, because every rule excludes them.

## Memory comparison: interim, 5 of 9 runs

Checkpoint 25 September, 8 iterations, start = the submitted system, later origins 26 September to 6 October (11 origins).
Full table, definitions and the resume commands: `results/memory_comparison.md`. Five runs are complete (none r1 r2, ledger r1 r2,
pastdev r1). `pastdev r2` died after 6 of 8 iterations and was discarded, not spliced; `none r3`, `ledger r3` and `pastdev r3`
were not run because every call to the pre-registered model now returns "weekly usage quota exhausted" (I did not swap models).

| memory | rep | proposed | dup avoided | wasted tests | kept | later d all [range] |
|---|---|---|---|---|---|---|
| none | r1 | 10 | 2 | 1 | 4 | +0.0045 [+0.003, +0.009] |
| none | r2 | 10 | 2 | 1 | 4 | -0.0082 [-0.011, +0.002] |
| ledger | r1 | 8 | 0 | 0 | 3 | -0.0003 [-0.003, +0.000] |
| ledger | r2 | 8 | 0 | 0 | 3 | +0.0018 [-0.004, +0.003] |
| pastdev | r1 | 8 | 0 | 0 | 6 | +0.0201 [+0.005, +0.025] |

`claim_pastdev_better`: **no advantage shown**. The claim needs pastdev's wasted tests below ledger's in 2 of 3 pairs, and ledger
wasted 0 in r1 and r2, so it can hold in at most 1 pair whatever the missing runs do. Memory of any kind did avoid repeats (0
wasted tests in all three memory runs against 1 in each no-memory run), but the whole ledger did it as well as past.dev recall,
at about 50% more prompt tokens. Later-origin gains differ by less than the spread between the two `none` replicates, except `pastdev r1`
(+0.0201, one run, 1 rule of 6 gives +0.0143 of it). Known confound: past.dev recall can return records of earlier runs.

## What the loop did and did not do by itself

- No human supplied a hypothesis, picked a candidate or chose a test in any reported run (human interventions 0 in every
  journal row). Every hypothesis, mechanism, spec and falsification rule came from the model; every keep/reject came
  from the fixed gate. I wrote the grammar, the facts, the report layout, the prompts and the gate, before any run.
- Every rule the model proposed in every run excluded the 37 headline series (`in37 == false`): the gate forbids lowering
  their skill, and the model learned to avoid them. So the loop cannot change the Sunday forecast of the 37.
- Duplicate handling: in the walk-forward the controller refused no candidate as a duplicate (0 avoided), but 2 tests at
  2 October re-tested ideas rejected at 25 September (`c1002 i1` = `c0925 i1`, `c1002 i6` = `c0925 i5`). The past.dev
  recall for that iteration returned 40 results and the rejected `c0925 i1` record was not among them (checked in the
  cached recall answer), so the controller could not know. The 25 September run wasted no test on an idea rejected at 18
  September, which meets the adviser's "second run that does not spend a test on an already rejected idea" only in that
  pair.
- Prior-work search returned dated sources (forecast combination, regime-switching prices, analog forecasting) but the
  model listed them as used in few hypotheses and none changed a gate result. It is a research-process step, not a
  demonstrated source of forecast gain.

## Caveats you must keep

- Retrospective: the seven members' settings were chosen by earlier work on all practice dates, so even the start
  system was tuned with knowledge of the later origins. This is a replay, not a clean historical test.
- The 37 headline series are a hindsight universe (chosen as of 6 November).
- Later-origin windows are short: 6, 6 and 4 origins (1,776 cells on the 37, 15,661 on all series).
- past.dev records from the autopsy and scout agents dated on or before a checkpoint were legitimately available to the
  recall, but they were written in November by research that had seen all dev dates.
- In the walk-forward the inspect step's reply was reused from the cache when the system and report were unchanged
  (16 of 26 inspect calls; every hypothesis call was a fresh draw). The memory comparison uses a fresh draw for every call.

## Reproduce

See `experiments/scientist/README.md`. Offline replay of a recorded run:
`PYTHONPATH=src .venv/bin/python -m gpuf.scientist replay --run c0918-pastdev-wf` (identical rows, same final system).
