# Maturity review

**My recommendation is to keep the submission unchanged, correct the diagnostic's errors and claims, and finish the autonomous-cycle demonstration without promising to deploy its winner.** The practice result really is concentrated in young histories. It does not establish that history length causes the mature-series weakness, or that removing pretrained members would improve Sunday.

This is an advisory review. I inspected local source and saved reports, and computed only from the practice rows of [runs/maturity/cells.parquet][cells]. I did not open held-back forecast files, run held-back scoring, generate forecasts, use the network, change project code, or commit. My only files are this report and [check_maturity.py][check].

All tables labelled **Computed** below come from that store through that script. The exact command, from `/Users/aryank/Developer/iterate_hackathon/track_2`, is:

```bash
OMP_NUM_THREADS=2 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python experiments/advisor/check_maturity.py
```

The script prints its results and writes nothing. It filters to the practice origins before computing, checks unique cell keys and finite available quantiles, and imports no project forecaster. Its declaration and the disclosed follow-up are preserved at the end.

**1. Is the diagnostic sound? Verdict: the main headline comparison is sound; several supporting labels and the slice implementation are wrong. “Most gain comes from young histories” is supported. “Maturity makes the blend fail” is not.**

The full tier implementation in [diag.py][diag-code], [dump.py][dump-code] and [audit/universe.py][universe] matches the daily-statistics branch of the starter's [build_series.py][starter-tier]: at least **60 history rows**, last observation at most **3 days** old, at least **5 distinct prices rounded to 6 decimals** in the trailing **90 days**, and median historical provider count at least **3**. Those are the starter's thresholds, not thresholds I fitted. Rows are not necessarily consecutive calendar days. “Has enough rows” and “meets the headline rule” must remain separate.

The main diagnostic reuses `final.blend`, applies `harness._clean`, scores against exact target dates and asserts equality with its recorded harness run. Its headline result is reproduced by my independent reconstruction from the store:

| Computed sample | Cells | Drift skill | Mix skill | Blend skill |
|---|---:|---:|---:|---:|
| Fixed headline universe | 4,278 | 0.088649 | 0.169109 | 0.207944 |
| Meets full tier rule at origin | 745 | 0.137527 | 0.170820 | 0.154204 |

Source for every entry: **Computed**, [cells.parquet][cells], [check_maturity.py][check]; agrees with [diag.txt][diag]. Thus the main difference survives correcting the slice code.

The specific defects matter:

- **The log's tier decomposition is arithmetically and conceptually wrong.** The [13:36 log entry][log] describes **745** tier cells using **588 + 195** cells. Those latter counts describe the row-count threshold, which gives **783** cells. The full-rule sample is actually **580 afhubbard cells across 4 series**, plus **165 gpurentalprices cells across 11 series**. The row-count sample is **588 across 4**, plus **195 across 13**, respectively. **Computed:** [cells.parquet][cells], [check_maturity.py][check]. The store lacks the underlying provider-count and distinct-price histories, so I cannot attribute each excluded cell to an individual failed criterion from this store alone.
- **`slice.py` omits the harness's quantile cleanup.** Its reported maximum discrepancy, **0.003146669559961533**, is not explained by absent GBM horizons: those are already represented as missing member outputs and excluded from the mean. The final blended quantiles must also be made monotone and nonpositive values floored, exactly as [harness.py][harness] does. Reproducing that and the single-member special case gives **zero maximum loss discrepancy** with the stored harness losses. The uncleaned calculation differs on **798 cells**, including **27 headline cells**. For the older gpurentalprices headline slice, standalone fragility skill changes from **0.052401** to **0.061880**, explaining the disagreement between the two saved reports. **Computed:** [cells.parquet][cells], [check_maturity.py][check]; original discrepancy in [slice.txt][slice].
- **The fastgpu week tables are empty because the collector comparison is wrong.** [slice.py][slice-code] extracts the first identifier component and compares it with `fastgpu`; the store contains `fastgpu_daily`. [diag.py][diag-code] uses a prefix check and does include it. The existing collector result is not missing, but the proposed same-calendar comparison in the slice report was never produced.
- **“Active” does not always mean “moved recently.”** [slice.py][slice-code] uses `~gate14`. In [allrental.py][gate], insufficient history also prevents gating. There are **4,513** ungated cells with `chg14 == 0` in this store (**Computed**, [check_maturity.py][check]). I used `chg14 > 0` in the added analysis. The distinction mainly changes the young comparison.
- **The all-rental diagnostic is the ungated blend.** Both diagnostic builders call `final(record=True)` without the submitted non-headline gate. The headline results are unaffected; active mature slices are also unaffected by that gate. The overall/non-headline tables must not be labelled as the complete submitted system. Applying the declared gate to the saved losses gives all-rental skill **0.164097**, versus **0.155725** ungated (**Computed**, [cells.parquet][cells], [check_maturity.py][check]). The older [final/results/dev.txt][dev] reports **0.1639** for its gated run; I have not traced that small cross-run difference and would not silently substitute one run's total for the other's.
- **Unavailable standalone members become last value.** That is consistent with the harness, but an apparent zero skill for prov on a collector with no supported offer panel is not evidence about an active provider model. Member availability also changes the effective blend by cell. See [final.py][final-code] and [diag.py][diag-code].

The margin decomposition is stronger evidence than comparing two conditional skill scores. Skill differences must be weighted by each slice's last-value loss, not by its cell count.

| Computed partition of the fixed headline universe | Share of baseline loss | Contribution to overall blend-minus-drift skill | Share of total gain |
|---|---:|---:|---:|
| Meets full tier rule | 13.18% | +0.002197 | 1.84% |
| Does not meet full tier rule | 86.82% | +0.117097 | 98.16% |
| Fewer than 60 rows | 85.95% | +0.115803 | 97.07% |
| At least 60 rows | 14.05% | +0.003492 | 2.93% |

Source: **Computed**, [cells.parquet][cells], [check_maturity.py][check]. The first pair and second pair are alternative partitions; do not add all rows together.

“Too young for drift to work” needs tightening. The starter requires **20 usable historical horizon-length changes**, not the headline history threshold ([baselines.py][starter-drift]). Cells where drift exactly equals last value account for **59.13%** of the total gain; cells certainly short of enough pairs, using `rows - horizon < 20`, account for **52.01%** (**Computed**, [check_maturity.py][check]). A flat empirical forecast can also arise with adequate history, so flatness alone does not prove a fallback. The remaining gain includes cases where drift is already operating. Say **“the gain is concentrated in short histories, including a substantial contribution from drift's insufficient-history fallback.”**

Alternative readings consistent with the tables are a cold-start advantage from pooling, a collector/panel-specific advantage, a change in event type or direction around October, and different loss weights across samples. The full tier rule also selects historically variable and sufficiently populated panels; it is not an intervention on age. The same collector ages with the calendar, and the fixed universe was selected using the later catalog. These explanations are not separated by the original age buckets.

The best further cheap analysis is a **within-collector/calendar comparison with an explicit overlap check**, together with removing October *targets*, not merely October origins. I ran it. The activity restriction uses only origin-time information.

| Computed active mature rate-card cohort | Cells | Drift | Mix | Blend | Chronos | fm2 |
|---|---:|---:|---:|---:|---:|---:|
| afhubbard, targets before October | 297 | 0.024458 | 0.430454 | 0.415129 | 0.305358 | 0.369003 |
| Same series, targets in October | 174 | 0.205727 | 0.379473 | 0.309319 | 0.179065 | 0.282683 |
| All active mature afhubbard cells | 531 | 0.132530 | 0.381274 | 0.211215 | −0.107760 | −0.039906 |
| All active mature gpurentalprices cells | 267 | 0.231237 | 0.248486 | 0.029471 | −0.881382 | −0.428074 |

Source: **Computed**, [cells.parquet][cells], [check_maturity.py][check]. The first two rows hold the same **6 series** fixed. They are descriptive, not matched independent events; origin sets overlap because horizons differ.

This changes the interpretation materially. The pretrained members are positive on the same older series both before and during October. The full afhubbard aggregate turns negative after adding **3 other active series / 60 cells** present only in the October-target part of this analysis. Their future last-value loss is **zero**, while their summed losses are **0.361571 for mix, 2.710683 for the blend, 6.502352 for Chronos and 6.880046 for fm2**. **Computed:** [cells.parquet][cells], [check_maturity.py][check]. These are absolute summed losses, not skill scores; skill is undefined when baseline loss is zero. An interval that stays wide after an earlier move can lose heavily on a subsequent flat stretch. This is a concrete event/cohort explanation, not evidence of a universal age failure.

Also, the **798 active mature rate-card cells** in [slice.txt][slice] are not all “other January collectors”: the calculation above decomposes them into the afhubbard and gpurentalprices rows. The slice code includes headline as well as non-headline cells. There are no mature gpurentalprices cells with pre-October targets in this practice store (**Computed**, [check_maturity.py][check]).

Exact matching on collector, origin, horizon and recent-change category finds **30 strata / 183 cells**, but only **2 strata** have positive baseline loss on both age sides. Matched afhubbard cells have zero baseline loss on both sides; the gpurentalprices young and mature matched groups have baseline-loss sums **8.022500** and **0.050750**, respectively. **Computed:** [check_maturity.py][check]. That is poor support for an age contrast, not a credible causal estimate. I would not headline the script's normalized contrast.

**Conclusion from the added analysis:** a simple “long history poisons pretrained widths” explanation fails. Calendar and which series just became active are important competing explanations. A clean maturity effect is still unidentified. A fixed-history-length intervention on the same series and dates would identify the model-input effect more directly, but it would require new forecasts and cannot be done from this store; I did not run it.

**2. Sunday and the headline claim. Verdict: lower the claim, not the submitted forecast, on this evidence.**

For the headline part of Sunday's task, the full-rule universe is the relevant universe: [audit.md, item 2][audit] reports that applying the rule at the cutoff reproduces the catalog. Its historical advantage over drift is partly a cold-start result that cannot simply be transported to that origin. The mature practice evidence contains a different mix of panels and events. It does not support a probability of winning Sunday, a particular expected margin, or a universal instruction to prefer mix.

The already reported held-back aggregate argues against claiming that the blend has plainly collapsed. But its members were selected using those weeks, it pools mature and younger histories, and the audit rejects the printed confidence interpretation. I checked those statements in [EVAL_PROTOCOL.md, Amendments 2–3][protocol], [audit.md][audit] and [research-log.md][log]. I did not re-score or decompose that aggregate.

**Exact sentence for the findings:**

> The blend's reported held-back skill of 0.214 versus drift's 0.084 is an optimistic result on the 37 series selected using the 6 November catalog, because those weeks helped select its members; on practice cells already meeting the organisers' headline rule at the origin it scored 0.154 versus 0.138 for drift and 0.171 for mix, so we have not established a comparable advantage for Sunday's fully eligible headline universe.

Numerical sources: the held-back numbers and catalog scope are reported in [research-state.yaml][state] and [research-log.md][log]; the practice numbers are [diag.txt][diag], independently reproduced above. “Fully eligible” is preferable to treating history length as the entire tier rule. Keep the disclosed optimistic result visible; do not replace it with a flattering subset.

**3. Proposal A. Verdict: legitimate reporting, but it is another look at the held-back outcomes. I would do it once, after the submission decision is frozen.**

Reusing saved forecasts avoids changing predictions; it does not avoid learning from outcomes. The existing final queries did not predeclare this slice. [EVAL_PROTOCOL.md][protocol] permits the original final reports, and [research-state.yaml][state] says no further validation runs are planned. This requires an explicit reporting amendment, not the claim that cached predictions make the analysis free.

I would conservatively charge it **one of the four nominal remaining checks** identified in [research-state.yaml][state], labelled “additional reporting diagnostic, no model selection.” That is my proposed accounting rule, not an existing protocol provision. The scientific fact is the extra information exposure, whatever the ledger calls it.

If B remains possible, freeze and finish its decision before releasing A. Otherwise A can change which candidate the team builds, what gate it writes, or whether it tries B at all, despite a promise not to alter the current weights directly. With my preferred unchanged submission, declare the freeze and do A promptly. Only the orchestrator executes it.

Suggested declaration:

> We are adding a reporting-only maturity diagnostic to the already completed q10/q11 record. The attached manifest fixes the saved submitted-blend, mix and drift forecast files, their hashes, the universe lists, scorer version and analysis code before execution. The submission/model-selection decision is already frozen. We will report both original universes, each partitioned by the starter's complete headline rule evaluated using only history available at each origin. We will report every partition, including empty or zero-baseline-loss partitions, with cell/series/origin counts, summed pinball loss, summed last-value loss and pooled skill on common keys. Missing saved forecasts will be disclosed; we will not regenerate them to complete this diagnostic. We will publish the entire output whatever it shows. This diagnostic is an additional held-back look, not independent confirmation. It will not change the submitted forecasts, members, weights, gates, proposal grammar, candidate choice, acceptance thresholds, or the decision to run another selection check before Sunday. Its only permitted consequence is correcting the interpretation and wording of the existing result.

The actual file paths/hashes must accompany the declaration and be committed by the orchestrator before looking. I have not opened those artifacts and cannot supply or verify their manifest here. Do not add best-collector, best-horizon or alternative maturity-cutoff searches after seeing the table. No bootstrap confidence claim is needed for this descriptive report.

**4. Proposal B. Verdict: “the unattended cycle found it and it won the aggregate” is not enough. A tightly bounded operational decision is possible, but I would default to no submission change.**

The audit found only **3 held-back week clusters** and badly calibrated small-sample tests; it also documented selection on those same weeks ([audit.md, items 4–5][audit]). Automation does not restore independence. A cycle can optimize a fixed grammar just as aggressively as a person can optimize weights.

Nor is its purported blindness established. The current [round-9 log entry][log] explicitly describes observing failures on mature practice data, and the grammar offers history length. That is legitimate research direction, but it is not evidence of an unprompted discovery. Inspect and retain the actual proposal prompts and full rejected-candidate trace before making that autonomy claim.

The gates below are **my proposed decision rules**, written here before any new held-back breakdown; they are not fitted results or a claim of controlled statistical error. They deliberately make preservation of the current submission the default.

For practice:

1. Freeze the complete controller, grammar, candidate budget, feature definitions, member versions and keep/reject rule. Evaluate the whole adaptive procedure walk-forward. At each checkpoint, proposal and selection outcomes must have target dates on or before the checkpoint; later cells score a frozen decision. Do not call a full-dev autopsy “historical replay.” The final frozen candidate must also pass the ordinary comparison against the submitted blend; a changing sequence of past winners alone does not validate the final state.
2. Preserve the existing positive-gain requirement in both practice halves, with the split specified in [EVAL_PROTOCOL.md][protocol] and [halves.py][halves]. Compare against the **complete submitted blend**, not merely mix, and keep mix and drift visible. My proposed minimum pooled improvement over the submitted blend is **+0.010 absolute skill**, with the existing practice week-bootstrap lower bound above zero as a screening rule. Because development has already been searched, do not label that interval confirmatory.
3. Require the affected mature regime to improve in at least **two distinct target-week blocks**, including evidence before the October event window, and require a consistent mechanism/result in at least **two collectors**, including a target rental collector. These are proposed minimum replication requirements, not inferred effective sample sizes. Report full-rule maturity and row-count maturity separately. A gain confined to the October transition, a single collector, or young cells fails the claimed mature-series repair. Lack of comparable cells is insufficient evidence, not a pass.
4. Require no pooled all-rental regression in either practice half, no regression when October targets are removed, and the required deletion/corruption leakage tests. Verify the saved-store scorer matches deployment cleanup and the actual gate. Record all attempted rules, not only the selected one.

A maturity-only rule that changes nothing in the first practice half cannot satisfy the existing positive-both-halves rule. Do not quietly replace “positive” with “unchanged is good enough” to rescue it. The sparse mature target-collector history is a real obstacle; the current record does not earn relaxing this gate.

If, despite that, a candidate clears practice, freeze its final code, params, artifacts and this decision rule before the held-back run. Under a prospective amendment, I would permit **one frozen challenger**, require **at least +0.010 pooled skill over the current blend**, require positive gain in **each of the three calendar-week blocks**, positive gain on both the origin-eligible cells and the affected mature rate-card cells, and no loss increase at any scored horizon. Empty affected samples fail the evidence requirement. These are conservative operational guardrails, not a significance test. Report the week table and rough ranges; do not use a nominal small-sample p-value to override a failed guardrail.

There is a scope problem with B as phrased. A comparison on the fixed headline universe alone cannot approve a rule that also changes other submitted rental series. The protocol requires an all-tier non-regression check. Either freeze a rule whose forecasts outside the headline universe are provably identical, in which case lower summed headline loss also lowers summed all-rental loss, or prospectively budget the additional all-series evaluation. Do not hide an extra final look inside a direction-check label. This must be settled before any held-back execution.

Any failed gate, unsupported affected regime, leakage/scorer mismatch, missing frozen manifest, or result-dependent adjustment means **retain the existing submission and stop**. No second threshold, alternate subset, new blend weight or exception after inspecting the held-back comparison. If the main justification becomes “we have unused checks,” refuse the change.

B would expressly replace the original rule that submission membership is fixed without choosing the final validation winner ([EVAL_PROTOCOL.md, Amendment 3][protocol]). Even a carefully declared amendment cannot make the resulting score an independent estimate. Given the current evidence and deadline, the unchanged blend plus the maturity limitation is the stronger research decision. The cycle can still succeed as an autonomy demonstration by rejecting its proposed change.

**5. Is there a cheaper or safer forecast move? Verdict: no evidence-backed free repair is hiding here. Mechanistic diagnosis is useful; a new rule or hedge is still a model change.**

The two pretrained members are not independent model families. [final_build.py][build] uses the same Chronos-Bolt-small checkpoint: the long-context path uses the default **512-day cap** in [foundation.py][foundation], and fm2 uses **16 days** and the lower-quantile setting **0.15** from [final.py][final-code]. Both submitted variants recenter their forecasts at the last price. These are chiefly choices of interval shape/width, not two independent predictions of the next price trend.

- **Long-context Chronos:** prior steps could help estimate recurring uncertainty, but old regimes or a recent isolated jump could leave inappropriate width around a now-static last price. That is a plausible mechanism, not an identified cause. The fixed-cohort check shows it can work on long rate-card histories.
- **Short-context fm2:** it avoids most distant history. Once the recent window is populated, adding older observations cannot directly change its numerical context. A loss gradient with total row count therefore is not evidence that its input got too long. It can still assign costly width after a recent move; the computed flat-future cohort is concrete evidence of that failure mode.

Consequently, “drop pretrained members when history reaches the headline minimum” is a slice-based rule dressed up as a mechanism. “Trust only recently active series” also misses the observed problem: the bad cohort already had prior activity. A provider/panel-based test for whether a jump is finished versus continuing is a more plausible mechanism, but it must distinguish those states using origin-time facts and pass the same practice gates. It is not a cheap exemption from evaluation, and parts of that reasoning are already in prov.

An arithmetic quantile hedge between two valid systems has a limited mathematical safeguard: pinball loss is convex in each forecast, so the hedge's loss cannot exceed the same weighted average of the two systems' losses. It can still be worse than the current blend. The project's geometric quantile averaging is a different operation and does not inherit that particular argument directly. This is an algebraic property, not an empirical gain claimed from the store.

If hedging is explored, fix the weight using practice rules before any held-back look and treat the hedge itself as the sole challenger. Do not test two systems and then choose an attractive mixture from their held-back performance. For this deadline I recommend neither a new hedge nor a maturity switch. The cheaper useful move is to fix the analysis and show the event/cohort limitation while preserving the forecast artifact.

**6. Next three hours. Verdict: integrate the maturity correction into the judging package immediately; do not let it become another model-search campaign.**

The ranking below updates [advice.md, items 1–6][advice] against the work listed as launched in [research-log.md][log]. Time caps are my planning recommendations for the requested window, not measured runtimes.

| Rank | Work | What I would insist on / cut |
|---|---|---|
| First | Prior item 1: coherent, reproducible package, including this maturity result | Spend the first **30 minutes** checking this report and correcting the tier counts, activity label, cleanup explanation, ungated label and Sunday claim. Freeze the submission decision. Declare A only under that freeze. Reserve the final **30 minutes** for artifact checks and the demonstration. |
| Second | Prior item 2: bounded unattended research cycle | Finish one trace with a frozen grammar, mature outcomes, a new proposed rule or principled duplicate rejection, and an automatic verdict. Cap remaining work at **60 minutes** before reducing scope. Cut deployment pressure, general code synthesis and additional rule families. |
| Third | Prior item 3: memory versus local-ledger baseline | Use the already bounded benchmark or the cycle trace; retain the local-ledger comparator and negative results. Cap marginal work at **30 minutes**. Cut claims about live speed/cost that a replay cannot support. |
| Fourth | Prior item 4: provider-balanced index | Finish the existing acceptance test if close. A negative result with a concentration/coverage warning is useful. Cut further index variants and any attempt to sell reduced movement as accuracy. |
| Fifth | Prior item 5: Exa causal trace | Finish cached-source controls and the source-eligibility fixes. Cut further search intended to find a reason to alter Sunday's forecast. A clear source-to-decision trace is enough. |
| Sixth | Prior item 6: long-run decision table | Pull necessary wording/weighting corrections into the first priority. Cut new scenarios and expanded long-run forecasting; retain an honestly labelled sensitivity table. |
| Last / cut | B and extra forecast hedges | Do not allocate a new search lane. Only reconsider a submission change if the already running cycle independently clears the stricter gates above before the artifact freeze. |

These are priorities for concurrent work already launched, not an instruction to serially squeeze every task into the window. If work slips, preserve packaging and the bounded cycle, then cut optional expansions from the bottom. The diagnostic/reporting correction is mandatory; a new submitted model is not.

**Scope and limitations of this review**

I read the requested brief, earlier advice, protocol amendments, audit/universe code, maturity builders and reports, the specified log entry, and the relevant starter/scorer/member/gate implementations. I did not regenerate pretrained grids, verify cached forecasts against a live model, recompute the original tier metadata from raw histories, inspect post-cutoff truth, inspect held-back per-cell forecasts, or evaluate the unfinished autonomous controller. Exact reproduction of the store's blend losses verifies its reconstruction, not every upstream forecast's provenance. The existing audit supplies the broader leakage evidence; its limitations remain.

I hand-wrote the review, the check script, the proposed declaration and decision thresholds. No model, cutoff or weight was selected by my computations. Every empirical number above is either attributed to a named existing report or marked Computed from the saved practice store. The helper's output is reproduced by the command at the top; no separate result file was created.

**Preserved pre-analysis declaration**

Before the first run I wrote here: reconstruct the existing forecasts, including harness cleanup, and check cell counts, losses, collector labels and gain contributions. This is verification, not candidate selection. The single added analysis is a collector/calendar comparison on neocloud rate-card cells with an actual prior change, split at the existing starter history threshold. Check common support at identical collector, origin, horizon and recent-change category. Report empty comparisons. Show each collector before October, excluding targets that reach October. No threshold sweep, significance claim, model nomination or new forecasts. Without within-collector/calendar support, the maturity effect is unidentified; persistence before October would reject an October-only explanation for that cohort, not establish an age effect.

After the first output, I declared a verification follow-up here before rerunning: the pre-October and complete mature cohorts contained different series, so hold the series cohort fixed across the October boundary and expose whether matched strata have positive baseline loss on both sides. Also show raw versus cleaned standalone fragility. The fixed-cohort/excluded-cohort detail was prompted by the first output and was not initially prespecified. The analysis selected no model and changed no acceptance rule.

[cells]: /Users/aryank/Developer/iterate_hackathon/track_2/runs/maturity/cells.parquet
[check]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/advisor/check_maturity.py
[diag]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/maturity/results/diag.txt
[slice]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/maturity/results/slice.txt
[diag-code]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/maturity/diag.py
[dump-code]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/maturity/dump.py
[slice-code]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/maturity/slice.py
[universe]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/audit/universe.py
[audit]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/audit/results/audit.md
[log]: /Users/aryank/Developer/iterate_hackathon/track_2/research-log.md
[state]: /Users/aryank/Developer/iterate_hackathon/track_2/research-state.yaml
[protocol]: /Users/aryank/Developer/iterate_hackathon/track_2/EVAL_PROTOCOL.md
[advice]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/advisor/advice.md
[dev]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/final/results/dev.txt
[starter-tier]: /Users/aryank/Developer/iterate_hackathon/track_2/data/pack/gpu-price-pack-v0.1.1-handover/starter/build_series.py
[starter-drift]: /Users/aryank/Developer/iterate_hackathon/track_2/data/pack/gpu-price-pack-v0.1.1-handover/starter/baselines.py
[harness]: /Users/aryank/Developer/iterate_hackathon/track_2/src/gpuf/harness.py
[final-code]: /Users/aryank/Developer/iterate_hackathon/track_2/src/gpuf/methods/final.py
[gate]: /Users/aryank/Developer/iterate_hackathon/track_2/src/gpuf/methods/allrental.py
[foundation]: /Users/aryank/Developer/iterate_hackathon/track_2/src/gpuf/methods/foundation.py
[build]: /Users/aryank/Developer/iterate_hackathon/track_2/src/gpuf/final_build.py
[halves]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/halves.py
