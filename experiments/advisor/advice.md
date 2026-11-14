# Advisor review: what would improve the chance of winning

Written 14 November 2026. This is advice, not an implementation or a new model selection. I read the requested record in order, including the complete research log and amendments, and formed the diagnosis below from that record. I cannot erase having seen the task's proposed weaknesses; I did not use them as the outline.

**My diagnosis: the entry has a strong research finding, a credible short-horizon result with substantial qualifications, and a useful economic question. Its weakest link is the demonstration that the scientist itself closes the research loop.** The best next investment is observable decision-making and trustworthy evidence, rather than a larger ensemble. The brief explicitly says leaderboard position alone will not win, and autonomy carries the same overall weight as results. [Brief §5][brief] [Overall rubric][requirements] [Current loop][loop]

## 1. Independent diagnosis, criterion by criterion

“Strong” and “weak” below are my judgments of the cited evidence, not predicted judge scores. Each row gives three of each. The five overall criteria each carry 20%; Pacific additionally asks for useful economic insight. The sponsor rubrics are separate. [Requirements][requirements]

| Criterion | Three strongest things | Three weakest things |
|---|---|---|
| **Research rigour** | **1.** The scorer cross-check reproduces 0.088649, 0.169109 and 0.199857 exactly. **2.** Deletion tests, corruption tests and planted cheating controls make the leak audit unusually substantive. **3.** The log records failed ideas and corrects its own statistical and chronology mistakes. [Audit][audit] [Log, 13:03][log] | **1.** Model membership and research direction adapted to validation; “held back” does not mean untouched. **2.** Three week clusters cannot support the printed confidence interpretation, and the corrected tests robustly retain only prov and fm2. **3.** The fixed future-qualified universe and revised data vintage limit historical realism. These are distinct weaknesses; a small analog leak fix does not cure them. [Audit §§1–5][audit] |
| **Novelty** | **1.** Connecting failures to the offers beneath an order statistic gives an intelligible mechanism. **2.** Signed provider motion capped by neighboring offers is more interesting than generic trend fitting. **3.** Provider concentration and index fragility connect forecasting to an actual financing problem. [Ledger H11/H24/H28][ledger] [Insight §§1–3][insight] | **1.** “Medians depend on membership” is already a warning in the organiser brief; discovery of that fact alone is not the novelty. **2.** The prior search returned mechanism-design papers with best overlap 0.03, which establishes neither novelty nor absence of prior art. **3.** Much of the submitted system is familiar pooling, boosting, analogs and pretrained widths; the story needs to isolate the new mechanism rather than credit the whole score to panel simulation. [Brief §5][brief] [Iteration §3][iteration] [Final implementation][finalcode] |
| **Results and working live demo** | **1.** Saved results show headline skill 0.2141221415746758 and non-headline 0.22757811604091316; these are meaningful results to explain, not dismiss. **2.** Development gains persist across the two halves for the submitted blend. **3.** The local HTML offer explorer can make a median's movement understandable immediately. [Saved-result check][checks] [Dev table][dev] [Demo source][demo] | **1.** Sunday is one origin, and overlapping development origins do not give an independent success probability. **2.** Better overall coverage conceals horizon/cause differences; dev coverage of the final headline model is 0.75. **3.** The page is an interactive explanation of saved outputs, not yet proof of an autonomous new research cycle; I did not browser-test it. [Log, 12:58][log] [Dev table][dev] [Loop/iteration][iteration] |
| **Autonomy and self-improvement** | **1.** Loss analysis genuinely changed research direction. **2.** Commands now cover autopsy, search, prior check, proposal ranking, development gating and forecasting. **3.** Cross-agent memory and a persisted ledger provide the infrastructure for avoiding repeated failures. [Log, 11:40 onward][log] [Loop][loop] [Memory][memory] | **1.** `propose` explicitly invents nothing; humans or directed coding agents still write the hypothesis and choose the test. **2.** The recorded gate repeats H28 rather than demonstrating a newly chosen experiment. **3.** There is no measured comparison of the complete research process with and without its memory/search, or proof it improves under a fixed research budget. [Loop `step_propose`][loop] [Iteration §§5,7][iteration] [README memory disclosure][readme] |
| **Interpretability and reproducibility** | **1.** The offer explorer, cause decomposition and negative-result ledger make decisions inspectable. **2.** The forecast files have recorded hashes, matching the current files in my check. **3.** Journals, cached sources and shipped cause labels are actually tracked, despite the general ignore rule. [Demo][demo] [Check output][checks] | **1.** `pyproject.toml` declares only duckdb, pandas, numpy and pyarrow, while the final build needs other packages and cached model weights; this is not a clean-environment installation recipe. **2.** Narrative drift across pitch, findings, ledger and historical reports creates contradictory claims. **3.** The long-run “one price per provider” aggregation actually groups by collector and provider, obscuring weighting. [Build][reproduce] [Dependencies][dependencies] [Checks][checks] [Long-run source][panelv2] |
| **Pacific: useful economic insight** | **1.** Lambda's 5 of 7 offers and the 36% provider-removal effect make concentration tangible. **2.** Posted-median disagreement 0.048 versus balanced-median 0.019 shows that measuring the market is itself a problem. **3.** Utilisation sensitivity and the failure of long-run no-change challengers identify what a lender should ask before trusting a price path. [Insight §§1–2][insight] [Long-run §§3–4][longrun] | **1.** Static-provider classification uses the whole sample, so the proposed index has not been demonstrated as an implementable historical rule. **2.** Lower disagreement can mean both indices barely move; six of eleven static pairs never moved. **3.** A removal stress is not a calibrated collateral haircut, posted asks are not realised revenue, and scenario q10 is not a measured default probability. [Insight §§2,6,assumptions][insight] [Long-run §§3–6][longrun] |
| **Exa prize** | **1.** Search is in the actual scout and prior commands. **2.** Dated announcements yield exact provider/price/effective-date objects; 17 of 17 checkable offer changes matched. **3.** Refuting the general announcement hypothesis—2 of 37 events announced ahead—is an honest research result. [Loop][loop] [Ledger H13/H27][ledger] | **1.** Exa centrality is worth 30%, yet the submitted forecasts do not depend on its outputs. **2.** The calendar gain is fitted to two episodes, including collector lag. **3.** Published dates are not historical snapshots; furthermore the scout's memory-write path does not apply the calendar's full rejection/date logic. This is a source-inspection concern, not a demonstrated leak into the final forecasts. [Exa rubric][exa] [Log, 12:34][log] [Loop `step_scout`][loop] |
| **past.dev prize** | **1.** Multiple writers/readers and cross-author use are documented. **2.** The forecaster has a dated evidence view distinct from experiment memory. **3.** A durable journal makes individual reads and writes inspectable. [Memory][memory] [Iteration][iteration] | **1.** Accuracy, latency and cost gains remain unmeasured, despite the stricter submission-form wording. **2.** A strong baseline already exists: the local ledger; `step_prior` consults it even if memory retrieval is absent. **3.** “Forecast reads memory” does not mean memory changes its numerical prediction: `step_forecast` compares calendar inventories, then forecasts through the method's existing inputs. [Track-choice §6][choice] [Loop `step_prior`, `step_forecast`][loop] |

**Underclaimed:** the failed first panel simulator followed by the successful signed-provider version is a better scientific narrative than “we tried many models.” It distinguishes an incorrect mechanism from a more useful one. The audit is also evidence that the team can revise a claim after a hostile check. [Ledger H12/H24/H37][ledger]

**Overclaimed:** “the system forecasts the list” describes important members, not all seven; “13 worked” compresses mixed claims such as H6, whose claim was supported for centres and refuted for widths; and “clean number on untouched series” confuses unscored period-cells with a universe used in development. [Final code][finalcode] [Ledger H6][ledger] [Dev all-series tables][dev] [Pitch][pitch]

## 2. What I checked, and what I did not

I inspected the files above, ran the read-only ledger command, and wrote a small standard-library artifact check. **I ran no new forecast scoring, no validation code, no network calls and no child agents.** All my writes are in this folder. I did not rerun the existing audits, build, browser demo, model training or long-run backtests. Their results below are attributed to their saved reports.

Reproduce my check from the repository root:

```bash
OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python experiments/advisor/check_record.py
```

The saved [output][checks] includes:

```text
hypotheses 37 {'refuted': 15, 'supported': 13, 'untestable': 2, 'not_significant': 7}
other_ledger_rows ['L3-frag-b20']
declared_dependencies ['duckdb', 'pandas', 'numpy', 'pyarrow']
source experiments/longrun/code/panel_v2.py:61: pp = last.groupby(["src", "provider"]).price.median()
```

It also confirms both submission hashes against the README and records the exact saved q10/q11 results. This is an artifact consistency check, not independent replication of forecast accuracy. [Check script][checkscript] [Check output][checks] [README][readme]

The demo and writeup agents changed files during this review. Several initially false pitch statements—untuned headline dates, all four directions validated, 38 hypotheses—were removed while I worked. The current check therefore distinguishes repaired wording from the remaining “555 series never used for any choice” claim. [Check output][checks] [Pitch][pitch] [Demo][demo]

## 3. Ranked next work

These are ranked by my expected judging value per agent-hour before **Sunday 15 November, 14:00 PT**, not by estimated leaderboard points. Effort and acceptance thresholds below are **planning estimates and proposed tests**, not observed gains. I cannot honestly predict a numeric improvement in judges' scores. The first five recommendations deliberately consume **zero held-back checks**. [Deadline][requirements]

### 1. Finish one consistent, reproducible judging package

**Build/change:** make the pitch, page, findings and installation instructions tell the same qualified story, then rehearse an actual local rebuild and two-minute demonstration.

**Why noticed / expected gain:** high, reliable benefit to rigour, results and reproducibility; no forecast improvement claimed. A judge should be able to follow one mechanism and reproduce the artifact without discovering an inconsistent headline.

**Evidence:** the revised page still says “555 price series we never used for any choice,” while all-series development results and leave-one-out selection are in `dev.txt`. The final headline dev score is 0.2079; the gated all-series score is 0.1639. The build is documented as about 25 s, but only four dependencies are declared. [Demo][demo] [Dev][dev] [README][readme] [Checks][checks]

**Exact acceptance test:** at origin **2026-11-06**, with no subsequent truth loaded, rebuild from the unchanged pack and pre-provisioned model weights in an isolated clean environment, with the network disabled. Match both recorded hashes or explain a deterministic/version difference before changing the expected hashes. Run the existing schema/refusal checks. Rehearse the two-minute video: offer movement → failure → hypothesis → result → limitation → artifact. Replace the headline with “first evaluation on these non-headline cells in 13–30 October”; mention the same universe was used on dev. Keep coverage beside its universe. Mark demonstrations of saved traces as replay. Reject a “one-command reproducible” claim until installation prerequisites are complete.

**Effort:** 1–2 agent-hours, plus a human recording. **Risk:** low; avoid rebuilding figures from different model versions accidentally. **Dependencies:** coordinate with the active demo/writeup agents; use one source for displayed values. Include the required screenshot, video, team registration and final submission checklist already identified in the requirements. [Requirements][requirements] [Choice §4][choice]

### 2. Close one bounded research iteration without manual candidate selection

**Build/change:** add a controller that turns a mature failure report into a new structured hypothesis and executable candidate specification, checks prior work/memory, runs a bounded development test, records the verdict, and either keeps or rejects the candidate without a human choosing it.

**Why noticed / expected gain:** the largest substantive opportunity on the 20% autonomy criterion, with additional novelty and interpretability value. A successful rejection counts: the target is demonstrated autonomous research discipline, not a guaranteed score increase.

**Evidence:** every execution primitive already exists, but `step_propose` states “it does not invent hypotheses”; the recorded gate reruns H28. H30's failed entry wrapper is a useful negative memory that a genuine controller must not blindly rediscover. [Loop][loop] [Iteration][iteration] [Ledger H30][ledger]

**Exact acceptance test:** use a historical replay checkpoint of **2026-09-25**. Supply only prices and evidence available by then; proposal/gate data may include development origins through **2026-09-18**, so every 7-day outcome is mature. Have the existing coding-agent interface produce an allowlisted candidate spec with a claimed mechanism, falsification rule, resource cap and prior-experiment references. Do not give it the final selected candidate or a whitelist containing only the desired winner. Compare with the existing manual `ens4`/`mix` workflow under the same experiment-count budget. Freeze the candidate before evaluating dev origins **2026-09-26 through 2026-10-06**, targets through **2026-10-13**; call this a retrospective development replay, not a fresh generalisation test. The program must distinguish selection data from later evaluation truth.

Acceptance: one complete cycle, no intermediate human choice, a traceable new specification or principled duplicate rejection, unchanged evaluator/split files, and a second run that does not waste a test on the same rejected idea. Drop the “autonomous new research” claim if the run merely selects H28 again or requires a human to supply its next experiment. Forecast gain may be zero.

**Effort:** 3 agent-hours for the minimum bounded version; more for arbitrary code synthesis. **Risk:** high if scope expands. Current `autopsy` consumes the full dev set, `prior` hardcodes a November search cutoff, and proposal ranking reads the latest ledger; these must be bounded or explicitly presented as current-day research rather than historical replay. Separate research execution time from market information time. **Dependencies:** frozen artifact snapshots, a working existing agent interface, and mutation/deletion checks that future rows cannot affect any forecast. Do not automate access to `val`. [Loop][loop]

### 3. Measure shared memory against the baseline that could replace it

**Build/change:** create a blinded, fixed-budget task benchmark comparing no shared memory, local ledger/Markdown retrieval, and past.dev retrieval, with correct decisions, tokens, elapsed time and actual cost reported separately.

**Why noticed / expected gain:** high sponsor value because it directly addresses the stricter form's accuracy/latency/cost question; useful autonomy evidence even if past.dev does not win. **Expected accuracy or speed gain is unknown**, and a null result is preferable to an invented attribution.

**Evidence:** the existing memory demo demonstrates cross-author reads, but not improvement; the README admits this. `step_prior` has a local-ledger fallback, so removing past.dev alone may change nothing. Recall can return about 8,000 tokens, while recorded recalls take about 1 s; more memory may increase context cost. [README][readme] [Memory caveats][memory] [Loop `step_prior`][loop]

**Exact acceptance test:** freeze the **14 November research-state snapshot** and prepare **12 paraphrased tasks** before retrieval: eight asking about previously tested mechanisms, four genuinely unresolved/control tasks. Include direction versus occurrence, a known failed entry model, and contradictory evidence. Have answer keys cite the contemporaneous ledger/source records; assess correct verdict, supporting record and useful next action, not string overlap. Use identical prompts and budgets across all three conditions. Score cross-author evidence use and duplicate experiments avoided. Date-sensitive forecasting tasks additionally use cutoffs **2026-09-25** and **2026-10-06**, and must exclude every later fact. Research-memory tasks may use November experiment verdicts only when not represented as knowledge available at a September forecast.

For this offline project phase, use recorded past.dev responses for matching requests, and label them replay. **Do not present local replay latency or lexical fallback as live past.dev performance.** Compute live cost/latency only where existing journal records actually support it; otherwise report “not measured.” A local ledger is the critical comparator. If past.dev does not improve correct decisions or save duplicate work over that comparator, drop superiority claims and retain only the demonstrated coordination claim.

**Effort:** 2–3 agent-hours. **Risk:** answer leakage from copied ledger language; vendor-specific benefit confounded with extra information; tiny task set. **Dependencies:** frozen tasks and retrieval corpus, token/cost instrumentation, correction of evidence timestamps described below. Zero scoring queries needed.

### 4. Turn the index finding into a causal, provider-balanced monitoring instrument

**Build/change:** implement one simple matched-offer change index with equal provider weights, an explicit missing-offer policy, and a displayed concentration/coverage warning, then test whether it reduces collector disagreement without suppressing real repricings.

**Why noticed / expected gain:** strongest economic product opportunity for Pacific; adds novelty and interpretability. It could turn “the median is fragile” into “here is a better way to monitor a lease benchmark.” No claim of calibrated collateral value or forecast-score gain.

**Evidence:** seven-day collector disagreement is **0.048** for posted medians, **0.019** for balanced medians, and **0.005** for static same-offer measures. But six of eleven static pairs never move, and whole-sample static classification is retrospective. Long-run levels use collector/provider pairs, not unique providers. [Insight §§2,assumptions][insight] [Panel code][panelv2]

**Exact acceptance test:** practice dates **2026-09-08 through 2026-10-06** only. For each daily change, use offers present at both endpoints, one change per provider, and equal provider weights; do not choose a cohort by survival to the end of the test. Avoid static/dynamic exclusions in the first version. Freeze any minimum-overlap and missing-provider rules before computation; report days where no valid index can be formed. Anchor each collector's level once at the start; compare subsequent changes, not incompatible price levels.

Compare against posted median, balanced median and a deliberately constant index. Require at least **20% lower mean absolute seven-day collector disagreement** than posted medians and a lower change under one-provider deletion, with matched coverage disclosed. Also require positive response to the Nebius/Jarvislabs common-offer repricings visible within these dates and report the fraction of their provider-level move retained. A constant index must fail that responsiveness test. Publish paired differences by chip and week, including inactive pairs separately. Drop the product claim if agreement comes only from inactivity, provider duplication, discarded hard days or future-selected membership.

**Effort:** 3 agent-hours using the existing panel loader. **Risk:** collector agreement is consistency, not ground truth; no capacity weights or transaction prices exist in the cited analysis. **Dependencies:** contract/SKU matching, unique provider identity and the day-local overlap rule. Keep it separate from the scored target and do not tune it on the existing October validation results.

### 5. Make Exa's contribution causally checkable on the cached development episodes

**Build/change:** show a source-to-announcement-to-offer-to-forecast trace with a fixed calendar-off control, a date/price perturbation control and an explicit “too late / wrong contract / already reflected” outcome.

**Why noticed / expected gain:** addresses Exa centrality and checkable-output criteria much better than a list of API calls. Expected gain is demonstrable research value on the known episodes; **no proven Sunday gain**.

**Evidence:** calendar-on prov scores **0.2827 versus 0.2089** on dev, entirely from two episodes; corrected counts are **142 eligible cells**, **100 changed forecasts** and **4,178 bit-identical forecasts**. Lambda's quoted November effective date was already reflected in one collector and has zero median impact in the five fastgpu panels tested. [Log, 12:34/12:54][log] [Insight §4][insight]

**Exact acceptance test:** use cached sources available by each dev origin **2026-09-16 through 2026-10-06**, with the existing provider simulator. Freeze zero collector lag as the first transparent control, rather than learning a lag from both episodes; report the prior fitted-lag result separately. Compare no calendar, valid extracted calendar, and controls that remove the price pair or defer availability until after the target. Score only dev origins, with `--split dev --no-log`, showing the affected subset and all cells, plus one-event-removed sensitivity. Use outcomes only for scoring; an event may change a forecast only if its source was known by that origin. Later publication must produce no effect. Add a source rejection fixture with an early publication date and later-dated content.

Drop any causal-search claim if deleting the source does not change the decision, the effect survives a future-availability control, or the source cannot justify the price/contract mapping. This is a retrospective mechanism demonstration, not a new independent validation of H27. Do not enable the calendar in the final submission merely to satisfy a sponsor.

**Effort:** 2 agent-hours. **Risk:** two events cannot establish generality; web-page versions remain uncertain even when cached now. **Dependencies:** fix the common eligibility contract for calendar and memory; display publication, evidence-availability, effective and first-observed dates separately. No new search or price fetch is needed.

### 6. Replace long-run point recommendations with an assumption-sensitive decision table

**Build/change:** correct provider weighting and unsupported decomposition claims, then show rent/value sensitivity to utilisation, realised rates and scenario weights, with no-change and failed backtests alongside.

**Why noticed / expected gain:** modest implementation effort protects Pacific credibility; no accuracy gain claimed. The output becomes an explicit stress exercise rather than a seemingly calibrated lending rule.

**Evidence:** H100 value is **18.8k versus 34.3k** across utilisation quintiles, whereas the discount-rate comparison is **27.5k versus 24.9k**. AWS backtest error is **0.60–0.88 versus 0.54** for no-change. Static rate-card uncertainty at noise **0.25** has not been validated on a long history. [Long-run §§3–6][longrun]

**Exact acceptance test:** keep the origin at **2026-11-06** and make no new historical selection. Recompute the displayed base from unique providers with a documented collector reconciliation rule, or relabel it accurately as collector/provider weighting. Verify that lower utilisation/rent cannot raise value and higher costs cannot raise value. Present the already reported year-end **2023, 2024, 2025** failures without tuning probabilities/noise to improve them. Label 65% LTV as a conditional model output, not an empirically safe advance rate. Drop an economic recommendation if its direction changes across plausible displayed assumptions.

**Effort:** 1–2 agent-hours. **Risk:** deduplication changes levels and every downstream display; avoid multiplying new scenarios. **Dependencies:** one consistent definition of provider/contract and source-availability caveats.

### 7. Only after the above, test one narrow forecasting repair: list-price membership waves

**Build/change:** investigate a causal zero-width rule for hyperscaler list prices after composition changes, rather than starting another broad model family.

**Why noticed / expected gain:** potentially removes a small, explainable failure; limited value if Sunday scores only headline series. Replacing the class forecast with no change would move its reported dev skill from **−0.034 to zero**, by definition; that is a class result, not an overall gain. The overall gain is uncomputed.

**Evidence:** the submitted gated class score is **−0.034**, but its first-half class score is **+0.019** and second-half **−0.052**. Thus a blanket no-change replacement would fail the current both-halves rule; it is not a free improvement. H35 reports **14 of 1,152 series-days** of median movement from entry/exit, and the panel simulator did not transfer. [Dev class/half tables][dev] [Ledger H35][ledger]

**Exact acceptance test:** one predeclared mechanism—distinguish an isolated completed membership change from a still-active provider-wide membership wave using only prior/current offers. Compare against the frozen final and no-change on **2026-08-18–2026-09-11** and **2026-09-12–2026-10-06**, horizons 1/3/7. Count quantile loss on unchanged cells as well as missed subsequent jumps. Require positive class loss reduction in both halves and no all-series regression in either; reject immediately otherwise. No threshold sweep. No change is selected using the October results already reported.

**Effort:** 1–2 agent-hours, capped. **Risk:** rare events; class routing has already overfit. **Dependencies:** a new mechanistic signal beyond the existing 14-day gate. This class is outside the headline set, so the current headline nomination rule cannot approve the change. If it passes development, the orchestrator—not this advisor—would need an explicit prospective amendment: at most one new check of the frozen candidate versus frozen final and no-change on hyperscaler-list cells at **2026-10-13 through 2026-10-30**, then one check of the resulting all-series aggregate on those origins, with no subsequent adjustments. That spends at most two of the four remaining checks and creates no new independent test set. Do not reuse q10/q11 as confirmation. If that amendment cannot be justified, retain the current forecast and report the negative result.

### Budget and stopping rule

Recommendations 1–6 need no new held-back forecast evaluation. Recommendation 7 is optional and must first clear its development test. Four nominal queries remaining is a ceiling, not four fresh independent datasets; all reuse the same short period. The current protocol also says no more final looks are planned. A changed final requires an explicit prospective amendment and cannot keep advertising the original non-headline result as a clean score of the changed system. The existing 13–30 October numbers must not select a candidate, a threshold, a weight or an exception. [Protocol, Amendments 2–3][protocol] [State][state]

I would not spend time trying to force the four-member blend through a rewritten acceptance rule. Its **0.2131** dev headline score and the five-member **0.2161** are tempting against **0.2079**, but its all-series score **0.1642** is almost the already gated final's **0.1639**, with unequal gate treatments. These are not evidence of a large safe gain. Amendment 3 was specifically written after seeing dilution; changing it again to get the desired winner would weaken the story. [Dev][dev] [Protocol][protocol]

## 4. Stop doing or cut from the story

1. **Stop model-family breadth and high-memory training.** The ledger already contains failed direction classifiers, stacking, cross-collector signals and an uncompleted heavy model run. Additional breadth is unlikely to repair the missing autonomy demonstration before the deadline. This is a time-allocation inference, not a theorem that those methods cannot work. [Ledger H15/H17/H19/H22][ledger] [Log, 12:08][log]
2. **Stop treating residual loss share as recoverable gain.** Entry's **0.294** share belongs to the six-member S3 system, whereas **0.298** belongs to ens4 in the loop; neither is the final seven-member residual. Exit remains **0.9427** of last-value loss in S3. Recompute on final if using these as a current model diagnosis, and preserve the system label. [Cause CSV][causes] [Iteration §1][iteration]
3. **Cut “never tuned on these series,” “four independent successes,” and “every query preregistered.”** The new page fixes some of the old language but still overstates the non-headline claim; q5's declaration was committed after its result. Use exact period/cell qualifiers. [Demo][demo] [Audit §5][audit] [Log, 13:03][log]
4. **Cut “Exa is necessary for this submitted forecast.”** It currently is not. Explain the calendar experiment and search's role in learning which claims fail. Do not turn on a redundant or unvalidated feature solely for prize eligibility. [Final code][finalcode] [Log, 12:34][log] [Exa rubric][exa]
5. **Cut unmeasured memory accuracy/speed/cost claims.** Multiple identities and an ingestion matrix prove interaction, not superiority over Markdown. [Memory][memory] [Track-choice §6][choice]
6. **Cut definitive lending, accounting and purchasing prescriptions from unvalidated ranges.** “65% is safe,” a mechanical haircut equal to removal sensitivity, and an impairment conclusion exceed what the scenario model tests. Present conditional decisions and uncertainty instead. [Insight recommendations][insight] [Long-run §§4–7][longrun]
7. **Cut “two thirds of GetDeploying's rise is panel effect” and “prior rises are upper bounds.”** There are no GetDeploying offer rows in this decomposition, and the same report shows the panel effect can run the opposite way. A comparison with another collector does not identify that decomposition or a bound. [Long-run §1][longrun]
8. **Keep long-run work out of the main score narrative.** Give it one honest stress-table view, not a second supposed forecasting success. Likewise, keep fine-tuning/weight-writing anecdotes in the appendix unless asked. [Long-run §3][longrun] [Ledger H17/H20][ledger]

## 5. The hard two-minute questions

These are rehearsal questions, not claims that judges will use this wording. Answers describe the evidence today; the last column identifies an achievable strengthening.

### Pacific judge

| Question | Honest answer today | Stronger by Sunday |
|---|---|---|
| **1. Did you actually beat drift without selecting on the test?** | We beat it on the reported cells, but headline membership was partly selected on those weeks. The first evaluation on non-headline validation cells is the least contaminated result; the same universe was used on development. Only Sunday is the external test. [Audit][audit] [Dev][dev] [Protocol][protocol] | Consistent claim language, source-linked raw results, and a frozen submission. Do not manufacture a cleaner history with another October run. |
| **2. What can a lessor use that your competitor's forecasting dashboard cannot show?** | Which provider controls a mark, how much removal moves it, and whether its trend agrees across collectors. Lambda's 5 of 7 A100 offers and 36% removal sensitivity show why a median can be a poor standalone benchmark. We have not validated a haircut rule. [Insight §1][insight] | The causal provider-balanced index and responsiveness test in recommendation 4. |
| **3. Where is the self-improving scientist rather than people running models?** | Agents wrote and tested hypotheses under human/orchestrator direction. The CLI ranks failures and gates a supplied candidate; its recorded iteration did not invent a new hypothesis. [Loop][loop] [Iteration][iteration] | One bounded unattended cycle, including a rejection and remembered reason, with intervention count shown. |
| **4. Why seven members if four do better, and why keep methods your audit rejected?** | The selection rule retained all members on dev; analog and fragility remain on development evidence despite weaker corrected validation support, explicitly deviating from the original gate. We did not replace the blend with the best validation number. [Dev][dev] [Log, 13:03][log] | Show the actual leave-one-out table and explain the fixed rule. A last-minute winner swap would weaken this answer. |
| **5. Would you lend 65% against an H100 using this forecast?** | That number is a conditional income-model output with assumed utilisation, realised rent and scenario weights. We have no transaction-level resale test, and no long-horizon centre beat no-change. It is a stress-analysis starting point, not a demonstrated safe advance rate. [Long-run §§3–6][longrun] | Correct provider weighting; show sensitivity, loan amortisation assumptions and no-change beside the scenarios. |

### Exa judge

| Question | Honest answer today | Stronger by Sunday |
|---|---|---|
| **1. What breaks if I delete Exa?** | Main-loop search and new evidence gathering stop, but the frozen numerical submission still runs because its calendar switch is off. We have a research-process contribution, not demonstrated dependence of Sunday's predictions. [Loop][loop] [README][readme] | A cached controlled trace where removing the source prevents a justified action and changes an episode forecast. |
| **2. Is the impressive calendar gain just two hand-picked events?** | Yes, it rests on two development episodes and the collector lag was read off them. The saved result is 0.2827 versus 0.2089, an in-sample mechanism demonstration rather than general forecasting evidence. [Log, 12:34/12:54][log] | Fixed-lag and one-event-removed controls; report every unaffected and harmed cell, without calling it fresh validation. |
| **3. How do you know an old publication date did not expose future text?** | We filter dates and avoid trackers, but Snapshot is unavailable, so publication date cannot prove historical text. Source inspection also found that memory writes need the same eligibility checks as calendar acceptance. [Ledger H13][ledger] [Loop `step_scout`][loop] | A shared availability-date contract, a later-content rejection fixture, cached passage hashes and explicit remaining version uncertainty. |
| **4. Did search discover prior work or just give irrelevant links?** | The demonstrated prior search did not find close prior work: best overlap 0.03, mostly mechanism design. It is not a novelty certificate. The stronger result is extracting and checking dated provider announcements. [Iteration §3][iteration] | Show source-to-action attribution and the honest “no relevant source found” state; avoid spending the deadline on a literature-search count. |
| **5. Does a real announcement necessarily move your target?** | No. It must match a contract, arrive before the forecast, and affect the middle of the panel. Lambda's rates were already reflected in gpurentalprices, and applying them changed none of five fastgpu medians. [Insight §4][insight] | Demonstrate those rejection/pass-through cases beside a successful Nebius/Jarvislabs case. |

### past.dev judge

| Question | Honest answer today | Stronger by Sunday |
|---|---|---|
| **1. Prove one agent used another agent's work.** | The scout recalled autopsy-authored failure cases and used their providers/dates to build searches; experimenter verdicts are available to later proposers. The journal and iteration trace show the interaction. [Memory][memory] [Iteration §§1–4][iteration] | One displayed chain: writer record ID → reader result → changed search/test decision → outcome. |
| **2. Why is this better than a shared Markdown file?** | We have not measured that. The local ledger remains authoritative, and the prior checker already uses a lexical fallback. [README][readme] [Loop `step_prior`][loop] | The equal-budget three-condition benchmark, including the strong local baseline. |
| **3. Show better accuracy, latency and cost.** | We cannot claim those gains today. Recorded ingestion and recall times describe operations, not improvement over alternatives; repeated Exa searches becoming free is an Exa-cache effect, not evidence for memory. [Memory][memory] [Iteration §2][iteration] | Correct-task rate and duplicate work avoided, with actual measured per-condition cost/time and unsupported metrics marked unavailable. |
| **4. Can memory leak future market events or future research conclusions?** | The forecaster audience is date-bounded and excludes experiments. That does not make the entire research loop historically causal: `prior` has a fixed November cutoff and `propose` reads the latest ledger/journal. Those are current-day research tools unless explicitly bounded. [Memory][memory] [Loop][loop] | Separate event availability, observation time and research execution time; deletion tests on later evidence and outcome rows. |
| **5. Is the forecast actually using the recalled memory?** | Its current forecast step cross-checks recalled calendar entries against a local calendar, then calls the forecaster. Numerical forecasts are not derived from arbitrary recalled text, and calendar use is off in the final blend. [Loop `step_forecast`][loop] [Final code][finalcode] | Demonstrate memory changing a research decision and avoiding a redundant experiment; do not invent a numerical dependency to make a demo look integrated. |

## 6. If I had only the next three hours

I would spend them closing **one bounded autonomous development iteration**, with a short claim-correction pass as its prerequisite: choose a failure from mature data, retrieve a previous negative result, produce a new executable hypothesis or reject a duplicate, run the predeclared development comparison, and persist an honest verdict with no human choice between steps. The primitives already exist, but this is exactly the behavior the recorded iteration lacks. It would make the autonomy criterion visible, give past.dev a decision to explain, and let Exa's evidence have a traceable place in the research process. I would preserve the submitted forecasts during that work, use no October validation checks, and count an autonomous rejection as success rather than demand a lucky score improvement. [Brief §5][brief] [Overall rubric][requirements] [Iteration][iteration] [Loop][loop]

## 7. Specific corrections and limitations to hand back

- **Wrong as written:** the current page/pitch says the non-headline series were never used for any choice. The all-series development and leave-one-out tables contradict that. Say “first evaluation on these period-cells.” [Demo][demo] [Pitch][pitch] [Dev][dev]
- **Wrong as written:** the long-run level reports “one price per static provider” and provider counts, while the code groups by `["src", "provider"]`. Providers observed in both collectors receive multiple entries; the reported counts are collector/provider units. This establishes a definition/weighting error, not its numerical impact, which I did not recompute. [Panel source, lines 59–66][panelv2] [Long-run §1][longrun] [Checks][checks]
- **Unsupported inference:** GetDeploying's precise panel-effect share and the “upper bounds” on pre-August changes do not follow from other collectors' panels. The report itself says GetDeploying cannot be decomposed and shows bias in both directions. [Long-run §1][longrun]
- **Unsafe future integration path, not a proven final-forecast leak:** calendar candidates are filtered using a later-content `known` date; the separate memory loop iterates over `kept` search hits and stamps the original publication date without propagating those rejections. Fix that before giving memory-derived evidence predictive authority. [Loop, lines 568–612][loop]
- **Historical replay limitation:** `prior` uses **2026-11-06** regardless of an earlier replay checkpoint, and `propose` uses the latest ledger and journal. Do not describe the full recorded October iteration as an as-of-October autonomous experiment. Its final forecast can still be causally constructed from its own bounded inputs. [Loop, lines 657, 703–749, 808–853][loop] [Iteration][iteration]
- **Version-label issue:** the residual-cause figures supplied in the task refer to ens4/S3, not an autopsy of the final seven-member blend. Keep that distinction on the demo. [Cause CSV][causes] [Iteration §1][iteration] [Dev][dev]
- **Packaging detail:** on this Mac, `FINDINGS.md` and `findings.md` resolved to the same inode when checked, and git listed the lowercase path. The README's claim that one supersedes a separately retained other file is therefore not true of this checkout; choose one canonical filename before publishing on a case-sensitive host. [Checks][checks] [README][readme]
- **Do not overcorrect:** the audit found meaningful problems, but the saved result and the demonstrated provider mechanism remain useful evidence. Neither the audit nor this review establishes a clean, independent confidence interval for Sunday's performance. [Audit][audit] [Saved-result check][checks]

[brief]: /Users/aryank/Developer/iterate_hackathon/track_2/description.md
[requirements]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/submission/requirements.md
[choice]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/submission/track_choice.md
[exa]: /Users/aryank/Developer/iterate_hackathon/exa.md
[state]: /Users/aryank/Developer/iterate_hackathon/track_2/research-state.yaml
[log]: /Users/aryank/Developer/iterate_hackathon/track_2/research-log.md
[protocol]: /Users/aryank/Developer/iterate_hackathon/track_2/EVAL_PROTOCOL.md
[ledger]: /Users/aryank/Developer/iterate_hackathon/track_2/data_out/ledger.jsonl
[audit]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/audit/results/audit.md
[causes]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/autopsy2/results/loss_by_cause.csv
[iteration]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/loop/iteration3.md
[dev]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/final/results/dev.txt
[insight]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/insight/results/insight.md
[longrun]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/longrun/results/longrun.md
[panelv2]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/longrun/code/panel_v2.py
[memory]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/memory/README_memory.md
[loop]: /Users/aryank/Developer/iterate_hackathon/track_2/src/gpuf/loop.py
[finalcode]: /Users/aryank/Developer/iterate_hackathon/track_2/src/gpuf/methods/final.py
[demo]: /Users/aryank/Developer/iterate_hackathon/track_2/demo/index.html
[pitch]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/demo/pitch.md
[readme]: /Users/aryank/Developer/iterate_hackathon/track_2/README.md
[reproduce]: /Users/aryank/Developer/iterate_hackathon/track_2/reproduce.sh
[dependencies]: /Users/aryank/Developer/iterate_hackathon/track_2/pyproject.toml
[checkscript]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/advisor/check_record.py
[checks]: /Users/aryank/Developer/iterate_hackathon/track_2/experiments/advisor/check_record.txt
