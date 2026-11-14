# Independent audit of the track_2 evaluation

Referee run, 14 Nov 2026, about 12:42 to 13:05 PT. No validation scoring path was run: forecasts at validation origins were made with `harness.forecast` only, which does not score them and does not write to the validation log. All code is in `experiments/audit/`, all outputs in `experiments/audit/results/`, scratch files in `runs/audit/`. No project file was changed.

| # | Item | Verdict | One-line evidence |
|---|---|---|---|
| 1a | Future-data leaks: mix, prov (with and without cal), fragility, gbm, fm2_live, chronos, drift | PASS | 0 of 3,690 forecast rows differ, bit for bit, under deletion and under wild values (18 tests each); forward and reverse order identical |
| 1b | Future-data leak: analog | **FAIL** (strict), negligible in size | deletion after the origin changes 86, 100 and 163 cells at 13, 21 and 30 Oct (max 0.054 in log); cause at `src/gpuf/methods/analog.py:124-125`; leak-free analog differs from the shipped one by ≤2.1e-5 in log at every validation origin |
| 2 | Selection: universe chosen as of 6 Nov | **FAIL** (material, disclosed but never measured) | point-in-time headline tier holds 4 series until 3 Oct and 15 on 6 Oct; dev mix minus drift is +0.033 on it against +0.080 on the fixed 37 |
| 2b | Static catalog fields | PASS (one small exception) | only static fields are read; `final.py:154` uses the 6 Nov headline membership as a switch |
| 3 | Scoring | PASS | starter `scorer.py` gives drift 0.088649, mix 0.169109, mix+analog 0.199857; fast and official scorer agree in every cell (max difference 0.0); zero-width rows are scored |
| 4 | Statistics | **FAIL** for the validation p-values and intervals; PASS for the dev conclusions | 3 validation weeks give 10 distinct resamples; DM with 18 days has true size 9.5 to 18% at nominal 5%; analog's p=0.031 becomes 0.13 to 0.16 |
| 5 | Validation log | **FAIL** on two counts, otherwise consistent | query 5 committed 32 s after its result and its result is not in research-log.md; gbm and Chronos joined the submitted blend through Amendment 2, written after they won validation round 1 |
| 6 | Ledger claims | PASS on 9 of 10; 1 mismatch | H28 quotes the cluster ratio of the composition flag (28x) for a configuration that uses the "any" flag (21x) |

## 1. Future-data leaks

**Test** (`experiments/audit/leak.py`). Origins: 20 Aug, 31 Aug, 10 Sep, 21 Sep, 30 Sep and 6 Oct (dev), plus 13 Oct, 21 Oct and 30 Oct (validation, forecast only). Series: the 37 headline series plus 60 random `rental_all` series (seed 2026), 97 in total. For every origin O there were three runs, each with a fresh forecaster and every module cache cleared (`analog._TABLES`, `fragility._C`, `gbm._CODES`, `panel.load`/`_index`, `data.load_store`):
- base: the real tables;
- del: every row dated after O deleted;
- wild: every row after O replaced. Series values were multiplied by exp(U(−3, 3)), and `n_providers` and `n_obs` were randomised. Panel prices were multiplied the same way, 20% of providers were relabelled, and 20% extra fake entrant offers were added.

Two tables were perturbed: `runs/series/series_daily.csv`, which feeds the harness store and analog's direct read, and the raw `rental_observations` rows, which were perturbed before `panel.load`'s key construction was re-applied. Two positive controls show the test can fail. `cheat` reads the series CSV from disk and fails 18 of 18 tests. `cheat_panel` reads `panel._index()` unfiltered and fails 18 of 18.

| method (validated params) | tests | rows differing | forward/reverse order | how rows after O are excluded |
|---|---|---|---|---|
| drift, mix | 18 | 0 | identical | only harness-truncated arrays and ctx; mix's donor cache is keyed by (group, origin, h) |
| analog `{all, 600, drop n14 sign, cap 11-06}` | 18 | **349 (del only, val origins)** | identical | situations with t+h ≤ O (`analog.py:209`), sd over t ≤ O−h (`:212`), causal features. But series membership is decided on the full table (below) |
| prov `{L1, W21, dyn}` and with `cal, ret_mkt=False` | 18 + 18 | 0 | identical | `panel.offers` ≤ O; provider-day stats and composition events filtered `d <= o` at query time (`prov.py:114, 122-126`); calendar entries published ≤ O (tested in tests/test_prov_leak.py with a positive control) |
| fragility `{mix, 20, any}` | 18 | 0 | identical | event tables built on all dates, filtered `day <= origin` (`fragility.py:84, 88, 111`); rate cache keyed by origin |
| gbm `{full, all}` | 18 | 0 | forward: 204 differ (expected: the 30 Sep model is reused at 6 Oct, an earlier model); reverse: `AssertionError` at `gbm.py:138` | training targets `t+h ≤ n−1` of the history truncated at O (`gbm.py:94-95`), so no training row has a target after O; the assertion blocks a later model at an earlier origin |
| fm2_live `{ctx 16, lo .15}` | 18 | 0 | identical | `ctx.history` only; the batch set is the 6 Nov headline list (selection only) |
| chronos `{centre last}` | 18 | 0 | identical | own truncated series only |

Results are in `leak_<method>.json`. A sanity check confirmed that the methods were active: at 21 Oct, analog, prov and fragility differ from mix on 101, 70 and 93 of the 111 headline rows.

**The analog leak.** `AnalogTable.__init__` (`analog.py:124-125`) drops a whole series if it has fewer than 2 rows, or any non-positive value, over the full table up to `cap`. At validation origins the cap is 6 Nov. A series with exactly one row on or before O therefore enters the standardisation sums (`AnalogTable.sd`, through `cs`/`cs2`) only if it has more rows after O. The candidate sets are identical. The standard deviations differ, by up to 0.0023 at h=1 on 21 Oct, and between 4 and 33 series are affected at each validation origin (`analog_fix.json`). The forecast therefore depends on the existence of post-origin rows, not on their values, which is why the wild test passes. tests/test_analog_leak.py misses it because it perturbs values only and uses the dev cap.

Patch: `analog_membership.patch`. With it applied by monkeypatch, all deletion and wild tests are bit-identical. The leak is tiny: the shipped and patched analog differ by at most 2.1e-5 in log, mean 3.8e-8, on all 18 validation origins, and the mix+analog blend by half of that. Query 6's number stands, the dev origins tested are unaffected, and the Sunday origin cannot be affected because no row exists after 6 Nov.

**Not tested.** The saved Chronos and fm2 grid files were not re-derived; they are produced by the tested live methods through `harness.forecast`. Data vintage is also outside the test. The pack holds the latest revision of every row ("the trailing day of tanod and gpurentalprices can be revised upstream", catalog `truth_availability`), so a forecast at O sees a last value that may differ from what was published on O. No perturbation can test this from the pack.

## 2. Selection leaks

**Universe** (`universe.py`, `universe.json`). The starter's rule reproduces the 37-series catalog exactly at 6 Nov. Applied at each dev origin, the rule admits only the 4 afhubbard series until 3 Oct and 15 series on 6 Oct. fastgpu starts on 8 Sep and cannot reach 60 days before 6 Nov. Over 745 point-in-time cells, against 4,278 on the fixed universe:

| | fixed 37 (protocol) | point-in-time headline |
|---|---|---|
| drift | 0.0886 | 0.1375 |
| mix | 0.1691 | 0.1708 |
| mix − drift | +0.080 | +0.033 |

No series ever leaves the tier (`pit_not_37` = 0), so this is not survivorship. The effect is the inclusion of young series, where drift falls back to flat: 2,722 of the 4,278 dev cells, carrying 42% of the baseline loss. More than half of the headline "beats drift" margin on dev comes from cells that the organisers' own rule would not have scored at the time. For Sunday the fixed 37 is the right set, because all of them have more than 60 days.

**Static fields.** Methods read `source_id`, `instrument_class`, `gpu_model`, `pricing_tier` and `table` (ctx.meta, analog's catalog read, gbm) and parse the series id. None reads `median_n_providers`, `n_distinct_values_90d`, `last_value_to_as_of` or any other as-of field, and ctx.meta withholds them. analog takes `n_providers` per row from the series file, which is causal. Exceptions:
- `final.py:154` decides which series get the activity gate from the 6 Nov headline list, a look-ahead switch on dev (small).
- `fm2_live` and `tabpfn`/`tail` use the 6 Nov list as a batch or scope.

## 3. Scoring (`score_check.py`, `score_check.json`)

The dev headline forecasts, 4,278 cells, were scored by `starter/scorer.py` in a subprocess. The pooled skill was also recomputed by hand from the scorer's per-cell truths and quantiles.

| | logged | fast | official | hand | max cell difference |
|---|---|---|---|---|---|
| drift | 0.0886 | 0.088649 | 0.088649 | 0.088649 | 0.0 |
| mix | 0.1691 | 0.169109 | 0.169109 | 0.169109 | 0.0 |
| mix+analog (dev cap) | 0.1999 | 0.199857 | 0.199857 | 0.199857 | 0.0 |
| last value (q10=q50=q90) | 0 | 0.0 | 0.0 | 0.0 | 0.0 |

- Status was "scored" in every case, with no refusals.
- Zero-width rows were scored as valid: 2,722 of drift's rows and all 4,278 of last value's.
- Missing truth days are dropped, not filled, as in scorer.py: 1,052 cells.
- The pinball loss averages the three τ, and pooled skill = 1 − mean loss / mean baseline loss.

The scorer is the organisers'; the forecasts are the project's.

## 4. Statistics (`stats.py`, `stats.json`)

**Resample counts.** Dev has 8 ISO weeks, giving C(15,8) = 6,435 distinct resamples. Validation has 3 weeks (6, 7 and 5 origins), giving C(5,3) = 10. Each one-week-repeated resample carries probability 1/27 = 3.7%, so the validation "90% interval" is close to the range spanned by the worst and best week. With 3 clusters it is not a 90% interval, and its "lower end above zero" says little.

**Dev differences against mix** (50 origin days):

| direction | d | week bootstrap | day-block bootstrap (L=7) | DM NW6 p₁ | HLN-t p₁ | NW14 p₁ |
|---|---|---|---|---|---|---|
| mix+analog | +0.031 | [+0.017, +0.053] | [+0.019, +0.051] | 3e-6 | 1e-4 | 2e-5 |
| mix+prov | +0.029 | [+0.015, +0.054] | [+0.012, +0.052] | 0.005 | 0.015 | 0.005 |
| mix+fm2 | +0.021 | [+0.010, +0.044] | [+0.009, +0.044] | 2e-4 | 0.002 | 2e-5 |
| fragility | +0.023 | [+0.011, +0.045] | [+0.012, +0.044] | 3e-4 | 0.002 | 3e-4 |

The dev conclusions survive every method. These intervals are still in-sample for each direction's own parameter choices: W=21, the feature drop, boost 20 and lo=0.15 were all picked on dev.

**Validation p-values.** I simulated the one-sided DM statistic (NW lag 6, normal reference) on 18-day null series, using (a) a Gaussian process with each direction's dev autocorrelation and (b) a circular 7-day block bootstrap of the centred dev differences, 20,000 replications each.

| query | logged p₁ | simulated p₁ (Gaussian / bootstrap) | true size at nominal 5% |
|---|---|---|---|
| q6 mix+analog | 0.031 | **0.135 / 0.158** | 16% / 18% |
| q7 mix+prov | 4e-10 | 0.005 / 0.006 | 15% / 10% |
| q8 mix+fm2 | 5e-6 | 0.004 / 0.006 | 10% / 8% |
| q9 fragility | 0.008 | **0.051 / 0.077** | 12% / 15% |

The test is anti-conservative by a factor of 2 to 3.5 at the 5% level. Benjamini-Hochberg at 10% keeps all four directions with the logged p-values, three with the Gaussian simulation (analog drops out), and two with the bootstrap (analog and fragility drop out). Only prov and fm2 are robust validation findings.

## 5. Validation log (`data_out/val_query_log.jsonl`, 42 lines at 12:48 PT)

**What the 42 lines are.**
- 10 lines on starter15 (drift and odd, the reference check at 10:38 to 10:48 and 11:17). They touch validation origins 14 and 21 Oct. These are baselines only and are not mentioned as validation touches anywhere.
- 32 lines on the val split:
  - 11 candidate queries (q1 to q11);
  - 2 repeats with the same forecasts (the Chronos cache, line 18; the q5 breakdown, line 21);
  - 19 mix and drift reference evaluations.
- Everything was run by user aryank, and every candidate matches a logged entry.

**Declaration against commit time.** Results are logged when a run ends, so a commit a few seconds earlier shows the text predates the result, not the launch.

| queries | declaring commit | first result | gap |
|---|---|---|---|
| q1–q4 | 63677c2, 10:57:47 | 10:57:49 | 2 s |
| **q5** | ea2849f, **11:17:38** | **11:17:06** | **commit after the result** |
| q6 | a3e9851, 12:14:20 | 12:14:32 | 12 s |
| q7, q8 | 8a74ca1, 12:18:21 | 12:18:37 | 16 s |
| q9 | 23eecc2, 12:24:24 | 12:24:33 | 9 s |
| q10, q11 | b5d2809, 12:47:02 | 12:47:33 | 31 s |

**FAIL.** q5's "declared now, before running" has no git support. Its result (0.1967) also appears nowhere in research-log.md or findings, although it chose the v1 safety-net submission.

**Amendments.**
- Amendment 1 (10:38) precedes every method run.
- Amendment 2 (11:49:59) was committed after validation round 1. Its rule 4 makes "mix, gbm, Chronos width" fixed members of the submitted blend. gbm and Chronos are there because they won q3 and q4, so the blend's membership was partly selected on validation. The log labels the final validation number "optimistic", but does not name this cause.
- Amendment 3 (12:37:25) precedes q10 and q11 and decides on dev.
- q9 tested a wrapper, not the "blend with mix" that rule 2 requires (disclosed).

**Parameters after validation.** No kept direction's parameters were changed after its query; they are frozen in val_gate.jsonl and identical in final.py. The direction choice was adaptive, though. Rounds 2 to 5 were designed after round 1's validation results were seen, for example fm2 ("Chronos width, round 2") after Chronos width won q4. Agents also read panel rows from the validation period: `experiments/insight/analysis.py` reads 15 Oct to 6 Nov, the calendar searches run to 6 Nov, and EDA q6 looks at revisions. None of this scored forecasts. "One query per direction" therefore understates how much validation informed the work.

## 6. Ledger claims

| # | claim | file | verdict |
|---|---|---|---|
| 1 | H11: 579 changes, 86/10/4% | autopsy/results/step3_summary.json: 496/60/23 | ✓ |
| 2 | H11: median reproduced on 100% of 2,483 series-days | step12_summary.json (840+720+923, within half a cent, max diff 1e-4) | ✓ (not "exact") |
| 3 | H11: loss shares 32 / 22 / 17.5 / 8.9 / 6.8% | failure_modes.json | ✓ |
| 4 | H11: jump vs fragility corr 0.88, n=60 | probe_summary.json (not the cited file) | ✓; the 79%/54% and "19 dates" figures were not located |
| 5 | H21: dev +0.030 [+0.009, +0.061]; blend +0.031 [+0.017, +0.053] | rerun: blend +0.0307 [+0.017, +0.053] | ✓ |
| 6 | H21/H24: validation +0.022 p=0.031; +0.072 p<0.001 | val_gate.jsonl | ✓ as logged; p anti-conservative (item 4) |
| 7 | H24: prov dev 0.208, +0.039 [+0.013, +0.087], q50 0.95 | rerun 0.2089, +0.0398 [+0.014, +0.088], 0.949 | ✓ (research-log line 132 says 0.2083, 0.0006 off) |
| 8 | H27: cal 0.283, +0.074 [0.000, +0.100], 100 cells, 0.154→0.489 | cal_summary.json; rerun 0.2827 | ✓; "4,136 other cells bit-identical" means the cells outside the 142 affected; 42 affected cells are unchanged |
| 9 | H28: dev 0.192, +0.023 [+0.011, +0.045]; "0.102 vs 0.0036, 28 times" | rerun +0.0232; fragility/results/cluster_test.json | **mismatch**: 0.102/0.0036 is `comp_win1`; the kept `bkind any` corresponds to `any_win1`, 0.431 vs 0.020 (21x) |
| 10 | H31: loss/last-value table, totals .911/.831/.818/.796, residual shares, 55% | autopsy2/results/loss_by_cause.csv | ✓ (55% computes to 56%) |

Also, `experiments/final/results/dev.txt` labels rows `only_prov` (0.1952) and `only_fragility` (0.1787). These are final.py's member read-backs, not the validated methods (0.2089 and 0.1924), and should not be quoted as the methods' scores.

## Caveats the findings must state, in order of importance

1. Only two kept directions, prov and fm2, survive a correctly sized validation test. Analog's p = 0.031 is about 0.14 to 0.16 once the 18-day autocorrelation is simulated. Fragility's 0.008 is 0.05 to 0.08. The validation DM test rejects 10 to 18% of the time at nominal 5%.
2. The validation "90% intervals" come from 3 week clusters (10 distinct resamples) and are not 90% intervals. Report them as week ranges, or drop them.
3. The universe is chosen with hindsight. Under the organisers' tier rule applied at each origin, dev holds 4 to 15 series, and mix's margin over drift falls from +0.080 to +0.033. The dev "beats drift" size is largely a young-series effect.
4. The submitted blend's membership is partly selected on validation: gbm and Chronos entered through Amendment 2, written after they won round 1. So the final validation numbers, 0.214 headline and 0.228 non-headline, are optimistic for that reason, not only because the kept directions were chosen there.
5. Validation guided which directions were explored (rounds 2 to 5 followed round 1's results), and agents read panel rows from the validation period. The count of 11 queries understates the reuse.
6. Query 5 was declared in a commit made after it ran, and its result is unreported.
7. analog's table membership looks ahead (fix in `analog_membership.patch`). The effect on reported numbers is below 1e-4, and Sunday is unaffected.
8. The data is the pack's revised vintage. Real-time last values for gpurentalprices and tanod may have differed, and no test here can bound that.
9. All parameter choices of the kept directions (W=21, the feature drop, boost 20, lo=0.15) were made on dev, so dev intervals are in-sample for them. H28's cited cluster ratio belongs to a different flag than the kept one.
