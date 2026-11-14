# Numbers used in FINDINGS.md and README.md, with sources

Section references (§) are to FINDINGS.md unless marked README. "log L" is research-log.md line L; "ledger Hn" is the `result` field of that id in data_out/ledger.jsonl; "val_gate qN.key" is that key of the line named qN in data_out/val_gate.jsonl; "dev.txt L" is experiments/final/results/dev.txt line L; "csv" is experiments/autopsy2/results/loss_by_cause.csv; "audit L" is experiments/audit/results/audit.md line L; "insight L" is experiments/insight/results/insight.md line L; "longrun L" is experiments/longrun/results/longrun.md line L.

Rounding policy for validation numbers taken from val_gate.jsonl (raw values have 16 digits): skills and differences of our systems are truncated to 4 decimals, never rounded up; lower ends of ranges are floored and upper ends ceiled (the range is widened, not narrowed); p-values are ceiled; reference skills (mix, drift) are rounded to nearest as in research-log.md, which can only make our margins look smaller. Coverage is given to 3 decimals so that 0.797 is not shown as 0.80.

## Decimal numbers (machine-checked by check_numbers.py)

| number | where | source |
|---|---|---|
| 0.001 | §5 H9 | ledger H9 ("rev 0.15: -0.001") |
| 0.002 | §5 H12, H15 | ledger H12 ("[-0.002,+0.040]"), ledger H15 ("[-0.002,+0.007]") |
| 0.003 | §5 H9 | ledger H9 ("rev 0.3: -0.003") |
| 0.0037 | §5 H15 | ledger H15 |
| 0.004 | §4 validation table q8 simulated p; §5 H10 | audit 98 (0.004 / 0.006); ledger H10 ("[-0.004,+0.015]") |
| 0.005 | §4 q7 simulated p; §5 H19; §7 | audit 97; ledger H19 ("+0.005 per unit z"); insight 88 (static median 0.005) |
| 0.006 | §4 q7, q8 simulated p | audit 97, 98 |
| 0.0067 | §4 q6 range low | val_gate q6.ci90[0] = 0.0067868 (floored) |
| 0.007 | §5 H15 | ledger H15 ("+0.007]") |
| 0.008 | §4 dev table mix+prov first half | log 133 ("halves +0.008 [-0.002,+0.019]") |
| 0.0085 | §4 q9 logged p | val_gate q9.p_one_sided = 0.0084477 (ceiled; log 154 prints 0.008) |
| 0.0096 | §5 H10 | ledger H10 |
| 0.010 | §4 dev mix+fm2 interval | log 134 ("[+0.010,+0.044]") |
| 0.011 | §4 dev fragility interval; §5 H12, H30 | log 151 ("[+0.011,+0.045]"); ledger H12 ("+0.011"); ledger H30 ("-0.011 against prov") |
| 0.015 | §4 dev mix+prov interval; §5 H10 | log 133 ("[+0.015,+0.053]"); ledger H10 ("+0.015]") |
| 0.016 | §4 dev mix+fm2 second half | log 134 |
| 0.017 | §4 dev mix+analog interval | log 124 ("[+0.017,+0.053]") |
| 0.018 | §4 dev fragility second half | log 151 |
| 0.021 | §4 dev mix+fm2 | log 134 ("+0.021 [+0.010,+0.044]") |
| 0.0218 | §4 q6 difference | val_gate q6.d_vs_ref = 0.0218956 (truncated; log 126 prints +0.0219) |
| 0.0232 | §4 dev fragility | log 151 |
| 0.025 | §4 dev submitted blend interval | dev.txt 8 ("[+0.025,+0.068]") |
| 0.028 | §4 dev mix+prov | log 133 ("+0.028 [+0.015,+0.053]") |
| 0.030 | §4 dev mix+analog second half | log 124 |
| 0.0307 | §4 dev mix+analog | log 124 |
| 0.0314 | §4 q6 logged p; §9 item 1 | val_gate q6.p_one_sided = 0.0313805 (ceiled; log 126 prints 0.031) |
| 0.1542 | §9 item 3 | experiments/maturity/results/diag.txt, table 'universe', row 'tier at origin', column final (truncated) |
| 0.1375 | §9 item 3 | same row, column drift |
| 0.1708 | §9 item 3 | same row, column mix |
| 0.0167 | §9 item 3 | same row, column final-drift |
| 0.1193 | §9 item 3 | experiments/maturity/results/diag.txt, row 'fixed 37', column final-drift; also dev.txt 'final against drift' |
| 0.033 | §4 dev mix+prov second half; §9 item 3 | log 133 ("+0.033"); audit 51 and log 226 (point-in-time universe, mix minus drift) |
| 0.034 | §4 dev mix+analog first half | log 124 |
| 0.0361 | §4 dev submitted blend second half | dev.txt 8 |
| 0.0388 | §4 dev submitted blend | dev.txt 8 |
| 0.039 | §5 H35 | ledger H35 ("-0.039 [-0.069,-0.003]") |
| 0.0390 | §4 q8 range low | val_gate q8.ci90[0] = 0.0390789 (floored) |
| 0.040 | §5 H12 | ledger H12 ("+0.040]") |
| 0.0411 | §4 q11 range low | val_gate q11.ci90[0] = 0.0411011 (floored) |
| 0.0433 | §4 q6 range high | val_gate q6.ci90[1] = 0.0432698 (ceiled) |
| 0.044 | §4 dev mix+fm2 interval and first half | log 134 ("[+0.010,+0.044]", "halves +0.044") |
| 0.045 | §4 dev fragility interval | log 151 |
| 0.048 | §7 | insight 86 (posted median, mean abs. 7-day disagreement 0.048) |
| 0.049 | §4 dev fragility first half | log 151 ("+0.049") |
| 0.0499 | §4 q11 difference | val_gate q11.d_vs_ref = 0.0499095 |
| 0.050 | §3 iteration 1 | ledger H6 ("Chronos-Bolt -0.050"); log 46 |
| 0.051 | §4 q9 simulated p; §9 item 1 | audit 99 (0.051 / 0.077) |
| 0.0516 | §4 dev submitted blend first half | dev.txt 8 |
| 0.0523 | §4 q9 range low | val_gate q9.ci90[0] = 0.0523334 (floored) |
| 0.053 | §4 dev mix+analog and mix+prov intervals | log 124, log 133 |
| 0.055 | §3 iteration 1 | ledger H6 ("TimesFM -0.055"); log 71 |
| 0.0569 | §4 q11 range high | val_gate q11.ci90[1] = 0.0568736 (ceiled) |
| 0.057 | §4 dev drift row | dev.txt 7 ("[-0.093,-0.057]") |
| 0.0577 | §4 q8 difference | val_gate q8.d_vs_ref = 0.0577433 |
| 0.0588 | §4 q7 range low | val_gate q7.ci90[0] = 0.0588571 (floored) |
| 0.068 | §4 dev submitted blend interval | dev.txt 8 |
| 0.0683 | §3 table | csv row hyperscaler_spot, share_lv_loss |
| 0.0724 | §4 q7 difference | val_gate q7.d_vs_ref = 0.0724358 |
| 0.077 | §4 q9 simulated p; §9 item 1 | audit 99 |
| 0.0796 | §4 q8 range high | val_gate q8.ci90[1] = 0.0795432 (ceiled) |
| 0.080 | §9 item 3 | audit 51 (mix − drift on fixed 37, +0.080); log 226 |
| 0.0805 | §3 iteration 1; §4 dev drift row | dev.txt 7 ("d=-0.0805"); experiments/fm2/results/summary.txt line 5 ("+0.0805"). Ledger H2 prints +0.081 (rounded) |
| 0.0845 | §1 line 2; §4 validation heading | val_gate q10.drift_skill = 0.0844537; log 63 |
| 0.0868 | §4 q7 range high | val_gate q7.ci90[1] = 0.0867998 (ceiled) |
| 0.0875 | §3 table | csv row exit, share_lv_loss |
| 0.0886 | §4 dev drift | dev.txt 7; audit 65 (0.088649) |
| 0.0913 | §4 q10 range low | val_gate q10.ci90[0] = 0.0913552 (floored) |
| 0.093 | §4 dev drift row | dev.txt 7 |
| 0.0979 | §4 q10 range against drift, low | val_gate q10.ci90_vs_drift[0] = 0.0979871 (floored) |
| 0.0983 | §3 table | csv row unannounced_oneoff, share_lv_loss |
| 0.1 | §2 terms (quantile level) | EVAL_PROTOCOL.md line 7 |
| 0.1020 | §4 q10 difference | val_gate q10.d_vs_ref = 0.1020520 (truncated; log 197 prints +0.1021) |
| 0.1021 | §1 line 2; §4 q11 drift | val_gate q11.drift_skill = 0.1020502 (reference, rounded as in log 198) |
| 0.1069 | §4 q9 difference | val_gate q9.d_vs_ref = 0.1069718 (truncated; log 154 prints +0.1070) |
| 0.108 | §5 H16 | ledger H16 |
| 0.110 | §5 H14 | ledger H14 |
| 0.1121 | §4 validation heading (mix) | val_gate q10.ref_skill = 0.1120701; log 64 |
| 0.1139 | §4 q10 range high | val_gate q10.ci90[1] = 0.1138762 (ceiled) |
| 0.114 | §4 one origin | log 217 ("10th percentile 0.114") |
| 0.1145 | §4 q11 range against drift, low | val_gate q11.ci90_vs_drift[0] = 0.1145065 (floored) |
| 0.1255 | §4 q11 against drift | val_gate q11.d_vs_drift = 0.1255279 |
| 0.1269 | §3 table | csv row announced_oneoff, share_lv_loss |
| 0.1296 | §4 q10 against drift | val_gate q10.d_vs_drift = 0.1296684 (truncated; log 197 prints +0.1297) |
| 0.1339 | §4 q6 skill | val_gate q6.skill = 0.1339657 (truncated; log 126 prints 0.1340) |
| 0.1341 | §4 q11 range against drift, high | val_gate q11.ci90_vs_drift[1] = 0.1340993 (ceiled) |
| 0.135 | §4 q6 simulated p; §9 item 1 | audit 96 (0.135 / 0.158) |
| 0.1359 | §3 table | csv row marketplace_ask, share_lv_loss |
| 0.1521 | §4 q10 range against drift, high | val_gate q10.ci90_vs_drift[1] = 0.1520630 (ceiled) |
| 0.1522 | §4 q9 range high | val_gate q9.ci90[1] = 0.1521979 (ceiled) |
| 0.158 | §4 q6 simulated p; §9 item 1 | audit 96 |
| 0.167 | §5 H25 | ledger H25 |
| 0.169 | §5 H16, H20, H25 | ledger H16, H20, H25 (mix on dev) |
| 0.1691 | §4 dev mix | dev.txt 6; audit 66 (0.169109) |
| 0.1698 | §4 q8 skill | val_gate q8.skill = 0.1698134 |
| 0.172 | §5 H20 | ledger H20 |
| 0.1777 | §4 q11 mix | val_gate q11.ref_skill = 0.1776686 (reference, rounded as in log 198) |
| 0.182 | §3 iteration 1 | log 81 ("Hindsight bounds for the blend (0.182)") |
| 0.1845 | §4 q7 skill | val_gate q7.skill = 0.1845059 |
| 0.1899 | §4 dev mix+fm2 | log 134 |
| 0.1924 | §4 dev fragility | log 151 |
| 0.1967 | §4 query 5 | log 228; audit 124 |
| 0.1973 | §4 dev mix+prov | log 133 |
| 0.1999 | §4 dev mix+analog | log 124; audit 67 (0.199857) |
| 0.1k | §8 resale table | longrun 101 (A100 Nov 2029 0.1k) |
| 0.2047 | §3 table | csv row dynamic_reprice, share_lv_loss |
| 0.2079 | §3; §4 dev submitted blend | dev.txt 8 |
| 0.2089 | §6 | log 159 ("against prov 0.2089"); ledger H32; audit 144. See disagreement 1 |
| 0.2131 | §3 | log 135; dev.txt line "orch4_mix_fm2_analog_prov skill +0.2131" |
| 0.2141 | §1 line 2; §4 q10 | val_gate q10.skill = 0.2141221; log 197 |
| 0.215 | §4 one origin | log 217 |
| 0.219 | §3 iteration 1 | log 81 |
| 0.2190 | §4 q9 skill | val_gate q9.skill = 0.2190419; log 154 |
| 0.226 | §3 iteration 1 | log 81 |
| 0.2275 | §1 line 2; §4 q11 | val_gate q11.skill = 0.2275781 (truncated; log 198 prints 0.2276) |
| 0.231 | §4 one origin | log 217 ("minimum -0.231") |
| 0.25 | §8 (glut probability; noise used in projections) | longrun 13 (0.25); longrun 43 and 159 (0.25 log per root-year) |
| 0.2785 | §3 table | csv row entry, share_lv_loss |
| 0.2827 | §6 | log 159; experiments/prov/results/cal_summary.json cal.skill |
| 0.330 | §5 H14 | ledger H14 |
| 0.35 | §8 | longrun 13 |
| 0.40 | §8 | longrun 13 |
| 0.42 | §5 H29; §8 | ledger H29 ("log error 0.42 against 0.66") |
| 0.5 | §2 terms (quantile level) | EVAL_PROTOCOL.md line 7 |
| 0.54 | §5 H16; §8 | ledger H16 (direction AUC 0.54); ledger H36 and longrun 77 (no-change error 0.54) |
| 0.562 | §5 H17 | ledger H17 |
| 0.6 | §8 | ledger H36 ("noise widened to 0.6"); longrun 77 and 159 |
| 0.60 | §8 | ledger H36 ("log error 0.60-0.88") |
| 0.6122 | §3 table | csv dynamic_reprice S3_loss_over_lv |
| 0.6209 | §3 table | csv marketplace_ask S3_loss_over_lv |
| 0.6243 | §3 table | csv marketplace_ask S2_loss_over_lv |
| 0.6283 | §3 table | csv dynamic_reprice S1_loss_over_lv |
| 0.66 | §5 H29; §8 | ledger H29 |
| 0.6719 | §3 table | csv dynamic_reprice S2_loss_over_lv |
| 0.6823 | §3 table | csv hyperscaler_spot S2_loss_over_lv |
| 0.6954 | §3 table | csv hyperscaler_spot S3_loss_over_lv |
| 0.6984 | §3 table | csv hyperscaler_spot S1_loss_over_lv |
| 0.7135 | §3 table | csv marketplace_ask S1_loss_over_lv |
| 0.73 | §8 table | longrun 65 |
| 0.75 | §4 q6 coverage | val_gate q6.coverage = 0.75 |
| 0.7517 | §3 table | csv hyperscaler_spot S0_loss_over_lv |
| 0.758 | §4 q7 coverage | val_gate q7.coverage = 0.7588106 (truncated) |
| 0.76 | §8 table | longrun 61 |
| 0.783 | §4 q8 coverage | val_gate q8.coverage = 0.7830396 |
| 0.7964 | §3 table | csv total S3_loss_over_lv; ledger H31 (.796) |
| 0.797 | §4 q10 coverage; calibration | val_gate q10.coverage = 0.7973568 (log 197 prints 0.80) |
| 0.8 | §4 calibration (target) | description.md line 92; EVAL_PROTOCOL.md line 7 |
| 0.8087 | §3 table | csv dynamic_reprice S0_loss_over_lv |
| 0.810 | §4 q9 coverage | val_gate q9.coverage = 0.8100220 |
| 0.8129 | §3 table | csv marketplace_ask S0_loss_over_lv |
| 0.8182 | §3 table | csv total S2_loss_over_lv |
| 0.8257 | §3 table | csv unannounced_oneoff S3_loss_over_lv |
| 0.8309 | §3 table | csv total S1_loss_over_lv |
| 0.8396 | §3 table | csv unannounced_oneoff S2_loss_over_lv |
| 0.8409 | §3 table | csv entry S3_loss_over_lv |
| 0.845 | §4 q11 coverage; calibration | val_gate q11.coverage = 0.8452434 (log 198 prints 0.85) |
| 0.8537 | §3 table | csv entry S2_loss_over_lv |
| 0.8541 | §3 table | csv announced_oneoff S1 and S3_loss_over_lv |
| 0.8563 | §3 table | csv unannounced_oneoff S1_loss_over_lv |
| 0.8681 | §3 table | csv announced_oneoff S2_loss_over_lv |
| 0.88 | §3 iteration 2; §8 | ledger H11 (correlation 0.88, n=60); ledger H36 ("0.60-0.88") |
| 0.9 | §2 terms (quantile level) | EVAL_PROTOCOL.md line 7 |
| 0.9070 | §3 table | csv entry S1_loss_over_lv (0.907) |
| 0.9114 | §3 table | csv total S0_loss_over_lv |
| 0.9382 | §3 table | csv exit S2_loss_over_lv |
| 0.9427 | §3 table | csv exit S3_loss_over_lv |
| 0.95 | §3 iteration 2 | ledger H24 ("q50 loss 0.95 of the last value's"); audit 144 (0.949) |
| 0.9517 | §3 table | csv announced_oneoff S0_loss_over_lv |
| 0.9563 | §3 table | csv entry S0_loss_over_lv |
| 0.9650 | §3 table | csv exit S1_loss_over_lv (0.965) |
| 0.9728 | §3 table | csv exit S0_loss_over_lv |
| 0.9729 | §3 table | csv unannounced_oneoff S0_loss_over_lv |
| 1.0 | §3 table | csv total share_lv_loss |
| 1.01 | §1 line 4; §8 | longrun 65; ledger H36 |
| 1.02 | §3 iteration 2 | ledger H18 (elasticity 1.02) |
| 1.1 | §5 H1 | ledger H1 |
| 1.105 | §5 H17 | ledger H17 |
| 1.21 | §1 line 4; §8 | longrun 61; ledger H36 |
| 1.5 | §7 buyer | insight 180 ("H100 1.5 times") |
| 1.55 | §8 | longrun 65 |
| 1.57 | §8 | longrun 65 |
| 1.6 | §5 H1 | ledger H1 |
| 1.79 | §8 | longrun 61 |
| 1.81 | §1 line 4; §8 | longrun 65 |
| 10.0k | §8 | longrun 100 |
| 12.1k | §8 | longrun 100 |
| 18.7k | §8 | longrun 101 |
| 1e-5 | §4 q8 logged p ("below 1e-5") | val_gate q8.p_one_sided = 4.94e-6; audit 98 prints 5e-6 |
| 1e-9 | §4 q7 logged p ("below 1e-9") | val_gate q7.p_one_sided = 3.89e-10; audit 97 prints 4e-10 |
| 2.11 | §8 | longrun 61 |
| 2.1e-5 | §9 item 7 | log 224-225; audit 8 |
| 2.20 | §8 | longrun 65 |
| 2.3 | §7 buyer | insight 180 ("A100 costs 2.3 times B200"). See disagreement 9 |
| 2.31 | §1 line 4; §8 | longrun 61 |
| 2.35 | §1 line 4; §8 | longrun 10; ledger H36 |
| 2.3k | §8 | longrun 101 |
| 2.5 | README team and tools (TimesFM 2.5) | log 71 |
| 22.5 | §4 calibration | experiments/autopsy2/results/summary.json calib_by_h["7"].above_q90 = 0.225 |
| 26.1k | §8 | longrun 100 |
| 3.04 | §8 | longrun 65 |
| 3.05 | §1 line 4; §8 | longrun 65 |
| 3.09 | §8 | longrun 65 |
| 3.11 | §8 | longrun 61 |
| 3.12 | README quickstart (Python 3.12) | pyproject.toml requires-python ">=3.12"; `.venv/bin/python --version` prints 3.12.12 |
| 3.49 | §1 line 4; §8 | longrun 9; ledger H36 |
| 3.76 | §8 | longrun 61 |
| 4.0 | README data licence (CC BY 4.0) | description.md line 19; pack ATTRIBUTION.md |
| 4.0k | §8 | longrun 101 |
| 4.17 | §1 line 4; §8 | longrun 61 |
| 4.69 | §8 | longrun 61 |
| 5.3k | §8 | longrun 100 |
| 5.6 | §3 iteration 2; §5 H4 | ledger H4 ("5.6% of 162 fastgpu exits"); failure_modes.json composition_entry_exit.reverts |
| 54.2k | §8 | longrun 100 |
| 56.8 | §4 calibration | experiments/autopsy2/results/summary.json S3_loss_side.above_q90_share = 0.568 |
| 7.2 | §7 lender | insight 64 ("The median worst removal is 7.2%"); insight 173 rounds it to 7% |
| 7.62 | §6; README Exa | log 236 ("Exa spend for the whole project $7.62"); `gpuf.loop status` exa_spend_usd.total = 7.621 |
| 9.1k | §8 | longrun 101 |

## Integers and percentages (listed for completeness, not machine-checked)

| number | where | source |
|---|---|---|
| 3 to 17 offers | §1 | experiments/autopsy/results/failure_modes.json ("3-17 offer panel"); insight 12 |
| 18 validation origins, 1,816 cells | §1, §4 | EVAL_PROTOCOL.md line 44; val_gate n_cells |
| 37 series (20 / 13 / 4) | §1, §2 | EVAL_PROTOCOL.md line 39; experiments/writeup/findings_early.md line 5 |
| 592 series, 1,776 rows, 249 zero width, 111 headline rows | §2, §4, README | log 192; runs/submission/final_validation.json |
| 22,390 cells | §4 | val_gate q11.n_cells; log 198 |
| 32 of 37 fail, 5 pass, 25 move >5% | §1, §7 | insight 62, 64, 168 |
| 2,483 series-days, 100%, within half a cent | §2 | ledger H11; audit 139 |
| 50 dev origins, 8 ISO weeks; 3 validation weeks, 10 resamples | §2, §4, §9 | audit 79; EVAL_PROTOCOL.md line 43 |
| 4,278 dev cells | §3, §4 | dev.txt 6 |
| 8 queries, 10% FDR | §2 | EVAL_PROTOCOL.md lines 56-57 |
| 37 hypotheses: 13 / 15 / 7 / 2 | §2 | data_out/ledger.jsonl, 38 rows minus L3-frag-b20 (log 238). See disagreement 3 |
| six rounds | §2 | research-log.md entries for rounds 1 to 6 (lines 29, 84, 89, 99, 146, 173) |
| 52%, 9%, 61% | §3 | log 81 |
| 579; 86% / 10% / 4%; 32%; 162; 0.88, n=60 | §3 | ledger H11, H4 |
| Verda 59%, 97%; under 1% | §3 | log 96 |
| 16 days of context | §3 | ledger H18 |
| 29% of residual (entry) | §3 | ledger H31; log 165 |
| cell counts 1027, 52, 195, 236, 125, 124, 308, 4278 | §3 table | csv column cells |
| 46 of 50; 2; 7 | §4 | log 217 |
| 11% above q90 at h=7 | §4 | val_gate q10.h7_above_q90 = 0.1075 (log 197: 11%) |
| 32 seconds | §4 | audit 118, 124; log 228 |
| 4 to 15 series | §4, §9 | audit 9, 45 |
| 2 of 37 events | §5 H13 | ledger H13 |
| 33% of 24 cases | §5 H33 | ledger H33 |
| 9 calendar entries; 463 searches; 17 of 17 | §6 | `gpuf.loop status` calendar.entries; ledger H27 |
| a third, none cut; 5 to 10%; 15 to 21% | §7 | insight 135, 175 |
| 58% | §7 | insight 173 |
| 65% loan-to-value, 20k | §7 | longrun 12, 126 |
| fewer than 6%; 2 of 9; 10 to 15 days | §7 | insight 179, 180 |
| 117 series; 11 of 16; year-ends 2023 to 2025; 24 months | §8 | ledger H29, H36; longrun 75-77 |
| 50 to 85%; 4 to 7 years; 2 to 5 years | §8 | longrun 93, 96 |
| 165 data points (77 / 48 / 40) | README | `LOOP_OFFLINE=1 PAST_OFFLINE=1 python -m gpuf.loop status`, memory.by_audience |
| 25 s | README | log 192 |
| first commit 14 November 2026, 10:31 PT | README | `git log --reverse` (de9fefa 2026-11-14 10:31:19 -0800) |
| SHA-256 7b49870e..., 90330d1e... | README | log 225 (prefixes); `shasum -a 256 submissions/forecast_final_*.csv` (full) |
| library versions | README, ATTRIBUTION.md | `.venv` package metadata (importlib.metadata) |

## Disagreements between sources and how they were resolved

1. **prov on dev.** Log 132 (12:18) gives 0.2083; log 159 (12:34), ledger H32 (after the hash-seed fix made the simulation deterministic) and audit 144 give 0.2089. Used 0.2089. FINDINGS shows the gated object (mix + prov) from log 133 instead of prov alone.
2. **mix + prov dev interval.** Log 133: +0.028 [+0.015, +0.053]. Audit 86: +0.029 [+0.015, +0.054]. Used the log.
3. **Hypothesis count.** `to_human/track2_feasibility.md`: 36 (13 supported, 14 refuted, 7 not significant, 2 untestable), written before the audit's H37. `experiments/loop/iteration3.md` status: 37 with 14 supported and 14 refuted (counts the L3-frag-b20 re-run, before H37). `gpuf.loop status` now: 38 rows. Log 238 says to quote 37, excluding the re-run. Used 37 = 13 / 15 / 7 / 2 from the ledger minus L3-frag-b20.
4. **Number of median changes.** Log 95 (interim autopsy): 653 changes on 2,446 day pairs, 86 / 10 / 4%. Ledger H11 and audit 138 (verified): 579 changes. Used 579.
5. **Analog's simulated p.** Audit caveat (line 153) says "about 0.14 to 0.16"; log 218 says 0.13 to 0.16; audit table line 96 gives 0.135 / 0.158. Used the table.
6. **Fragility's simulated p.** Log 218: 0.05 to 0.08; audit 99: 0.051 / 0.077. Used the table.
7. **Validation "90% CI".** `to_human/track2_feasibility.md` and log 197-198 label the validation ranges "90% interval" / "90% CI". Audit item 4 shows they rest on 3 week clusters. FINDINGS calls them week-bootstrap ranges.
8. **Median reproduction.** Log 83 says "reproduced exactly"; audit 139 says within half a cent ("not exact"). Used the audit's wording.
9. **Per-unit premium of A100 over B200.** Insight 180: 2.3 times (median over provider pairs, on-demand rate cards and list prices, 12 Oct to 6 Nov). Longrun 35: 2.95 times (static providers, 6 Nov). Ledger H29 (version 1): 2.30 times on GetDeploying medians. Used the insight figure in the buyer recommendation, which is where insight.md makes it; the long-run figure is not quoted.
10. **Mix over drift on dev.** Ledger H2: +0.081; dev.txt 7 and fm2 summary: 0.0805. Used 0.0805.
11. **Shared-memory size.** Log 158: 119 records at import; iteration3.md: 164; `gpuf.loop status` at writing: 165. Used 165.
12. **prov median-quantile loss.** Ledger H24: 0.95 of the last value's; log 132: 0.966 of mix's (different denominator); audit 144: 0.949. Used 0.95 against the last value.
13. **Worst-removal haircut.** Insight 64: 7.2%; insight 173 (recommendation): 7%. Used 7.2%.
14. **Exa spend.** Log 236 and `gpuf.loop status`: total $7.621 over attribution, calendar, day scout and loop. Ledger H26 ($1.05 for policy) and log 208 ($0.16 for longrun v2) are not separately listed in that total; only the total is quoted.
