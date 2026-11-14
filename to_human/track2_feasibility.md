# Track 2 feasibility, for the team's track decision

Written Saturday 14 November, about 13:00 PT. Every number is in `research-log.md`, `data_out/ledger.jsonl` or `data_out/val_gate.jsonl`.

## Verdict

Track 2 is feasible. A forecaster that beats the organisers' baseline on dates it was not built on exists, rebuilds from one command, and already has a valid submission file. What is left is packaging, not research.

## What is established

| Period | Our blend | Drift (the baseline to beat) | Gain, 90% interval |
|---|---|---|---|
| Unseen weeks (13 to 30 Oct), 37 headline series | 0.214 | 0.084 | +0.130 (+0.098 to +0.152) |
| Unseen weeks, all other posted rental series, never used for any choice | 0.228 | 0.102 | +0.126 (+0.115 to +0.134) |
| Development period, 37 headline series | 0.208 | 0.089 | +0.119 (+0.102 to +0.144) |

Scores are pooled skill against the last value, the organisers' headline metric. Interval coverage on the unseen weeks is 80% against a target of 80%.

- **The idea.** A posted price median is the middle of a small panel of provider offers. It moves when a provider near the middle reprices or an offer enters or leaves. The system found this by analysing its own forecast failures, then forecast the panel instead of the series.
- **The research record.** 36 hypotheses logged with verdicts: 13 supported, 14 refuted, 7 not significant, 2 untestable. Each validation query was written down and committed before it ran.
- **Reproducibility.** `bash reproduce.sh final` takes 25 seconds and gives byte-identical files across runs.
- **Sponsors.** Exa built a calendar of announced repricings (17 of 17 checked offers moved to the announced price). past.dev is live with three writer agents and date-bounded reads.
- **Economic insight and the 2 to 3 year view.** Both are written; neither has been reviewed line by line.

## What is not established

- **Sunday is one forecast date.** On the 50 development dates the blend beat drift on 46 and scored below the last value on 2. The dates overlap, so this is weaker than 46 independent wins. A bad week is possible.
- **Which series Pacific scores.** The scorer scores whatever is in the file unless they restrict it to the 37 headline series. We submit all 592, so either way is covered, but the answer changes which number matters.
- **Two of the four new members rest on thinner evidence.** An independent audit, still running, finds the significance test used on the 18 unseen dates is too generous. Under a stricter test the provider simulator and the short-context Chronos width hold (p about 0.005); the fragility tails are borderline (0.05 to 0.08) and the analogs are not significant alone (0.13 to 0.16).
- **One small leak, found by the audit.** In the analog member a series' later rows could change a scaling constant. Largest effect 0.00002 in log price; none at the scored date. A fix is ready and not yet applied.
- **Long-run section.** It gives ranges with stated scenario probabilities. No method beat "no change" at one to two years on any backtest, and it says so.
- **The brief says leaderboard position alone will not win.** The case rests on the method, the negative results and the insight, which a judge has to read.

## What is left to do for a Track 2 submission

- README and findings, including the audit's caveats.
- Demo page and pitch script (an agent is building them).
- The research loop as commands (an agent is building it); this is what the "autonomy" criterion looks at.
- Apply the analog fix, rerun the reproduce command, record the new file hashes.
- By the team: public repo and push, platform registration by Sunday 12:00, a 2-minute video.

## What this does not tell you

Nothing here compares Track 2 with Track 5. I have not seen the Track 5 prototype. An agent is reading the Track 5 text, the prizes by track and the finalist rule from the hackathon page.
