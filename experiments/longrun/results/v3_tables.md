## Table A. Posted rent, static rate-card median, unique providers (USD/GPU-h)

| chip, horizon | no change | frozen 0.35/0.40/0.25: q50 (q10-q90) | toward shortage 0.50/0.25/0.25 | toward glut 0.35/0.25/0.40 | frozen, spot-level noise 0.60: q10-q90 | frozen, v2 collector-provider base: q50 (q10-q90) |
|---|---|---|---|---|---|---|
| H100, +12 months | 3.44 | 3.05 (2.08-4.64) | 3.22 (2.16-4.89) | 3.05 (2.08-4.64) | 1.36-6.88 | 3.10 (2.11-4.71) |
| H100, +24 months | 3.44 | 2.28 (1.20-4.12) | 2.41 (1.23-4.36) | 2.14 (1.09-4.03) | 0.69-7.15 | 2.31 (1.21-4.18) |
| H100, +36 months | 3.44 | 1.76 (0.76-3.69) | 1.86 (0.78-3.89) | 1.62 (0.66-3.58) | 0.39-7.19 | 1.79 (0.77-3.75) |
| A100, +12 months | 2.03 | 1.89 (1.35-2.66) | 1.92 (1.37-2.72) | 1.89 (1.36-2.66) | 0.87-4.14 | 2.19 (1.57-3.08) |
| A100, +24 months | 2.03 | 1.57 (0.88-2.65) | 1.60 (0.89-2.71) | 1.48 (0.80-2.57) | 0.50-4.82 | 1.82 (1.02-3.07) |
| A100, +36 months | 2.03 | 1.37 (0.63-2.63) | 1.39 (0.64-2.68) | 1.25 (0.55-2.52) | 0.32-5.36 | 1.58 (0.73-3.04) |

## Table B (H100). Income-approach value per GPU (USD): q50 (q10-q90) under frozen weights; q50 under the two alternative weights; q50 with no change in rent

| utilisation | realised / posted | Nov 2026 frozen | +24 m frozen | +24 m shortage / glut | +24 m no change | +36 m frozen | +36 m shortage / glut | +36 m no change |
|---|---|---|---|---|---|---|---|---|
| 0.5 | 0.70 | 10.0k (4.2k-23.9k) | 2.6k (0.0k-14.8k) | 3.2k / 1.9k | 15.1k | 0.9k (0.0k-10.0k) | 1.1k / 0.5k | 11.5k |
| 0.5 | 0.85 | 14.5k (6.6k-31.8k) | 4.7k (0.0k-20.0k) | 5.4k / 3.8k | 20.5k | 2.0k (0.0k-13.7k) | 2.4k / 1.5k | 15.6k |
| 0.5 | 1.00 | 19.1k (9.1k-39.7k) | 6.9k (0.3k-25.2k) | 7.8k / 5.8k | 25.8k | 3.4k (0.0k-17.4k) | 3.9k / 2.6k | 19.6k |
| 0.675 | 0.70 | 16.9k (7.9k-36.2k) | 5.8k (0.1k-22.9k) | 6.6k / 4.7k | 23.5k | 2.6k (0.0k-15.8k) | 3.1k / 2.0k | 17.8k |
| 0.675 | 0.85 | 23.2k (11.4k-46.9k) | 8.8k (0.6k-30.0k) | 9.9k / 7.5k | 30.7k | 4.5k (0.0k-20.8k) | 5.1k / 3.6k | 23.3k |
| 0.675 | 1.00 | 29.6k (15.1k-57.6k) | 12.0k (1.3k-37.0k) | 13.2k / 10.4k | 37.8k | 6.5k (0.1k-25.9k) | 7.2k / 5.4k | 28.7k |
| 0.85 | 0.70 | 24.1k (11.8k-48.7k) | 9.1k (0.6k-31.1k) | 10.2k / 7.7k | 31.8k | 4.7k (0.0k-21.5k) | 5.3k / 3.7k | 24.1k |
| 0.85 | 0.85 | 32.1k (16.5k-62.1k) | 13.1k (1.5k-39.9k) | 14.4k / 11.4k | 40.8k | 7.1k (0.1k-27.9k) | 7.9k / 5.9k | 31.0k |
| 0.85 | 1.00 | 40.1k (21.3k-75.7k) | 17.1k (2.8k-48.9k) | 18.7k / 15.0k | 49.8k | 9.6k (0.5k-34.3k) | 10.5k / 8.2k | 37.8k |

## Table B (A100). Income-approach value per GPU (USD): q50 (q10-q90) under frozen weights; q50 under the two alternative weights; q50 with no change in rent

| utilisation | realised / posted | Nov 2026 frozen | +24 m frozen | +24 m shortage / glut | +24 m no change | +36 m frozen | +36 m shortage / glut | +36 m no change |
|---|---|---|---|---|---|---|---|---|
| 0.5 | 0.70 | 2.5k (0.7k-6.8k) | 0.3k (0.0k-3.6k) | 0.3k / 0.2k | 1.9k | 0.0k (0.0k-1.7k) | 0.0k / 0.0k | 0.6k |
| 0.5 | 0.85 | 4.4k (1.6k-9.8k) | 0.8k (0.0k-5.3k) | 0.8k / 0.5k | 3.1k | 0.0k (0.0k-2.7k) | 0.0k / 0.0k | 1.1k |
| 0.5 | 1.00 | 6.3k (2.8k-12.9k) | 1.4k (0.0k-7.1k) | 1.5k / 1.0k | 4.3k | 0.0k (0.0k-3.6k) | 0.0k / 0.0k | 1.5k |
| 0.675 | 0.70 | 5.4k (2.2k-11.5k) | 1.1k (0.0k-6.3k) | 1.2k / 0.8k | 3.8k | 0.0k (0.0k-3.2k) | 0.0k / 0.0k | 1.3k |
| 0.675 | 0.85 | 8.0k (3.8k-15.6k) | 1.9k (0.0k-8.6k) | 2.0k / 1.5k | 5.4k | 0.1k (0.0k-4.5k) | 0.1k / 0.0k | 1.8k |
| 0.675 | 1.00 | 10.6k (5.6k-19.8k) | 2.8k (0.1k-11.0k) | 2.9k / 2.3k | 7.0k | 0.3k (0.0k-5.8k) | 0.3k / 0.1k | 2.4k |
| 0.85 | 0.70 | 8.3k (4.0k-16.3k) | 2.0k (0.0k-9.0k) | 2.1k / 1.6k | 5.6k | 0.1k (0.0k-4.7k) | 0.1k / 0.0k | 1.9k |
| 0.85 | 0.85 | 11.6k (6.2k-21.5k) | 3.2k (0.1k-11.9k) | 3.3k / 2.6k | 7.6k | 0.3k (0.0k-6.4k) | 0.4k / 0.2k | 2.6k |
| 0.85 | 1.00 | 15.0k (8.5k-26.7k) | 4.4k (0.3k-14.9k) | 4.5k / 3.6k | 9.6k | 0.6k (0.0k-8.1k) | 0.7k / 0.4k | 3.3k |

## Table C. Loan cover at q10 as a share of the used-market price (H100 20k, A100 7k); conditional model output, not an advance rate

| chip, loan | utilisation | realised / posted | frozen | toward shortage | toward glut | no change in rent |
|---|---|---|---|---|---|---|
| H100, 24 m | 0.5 | 0.70 | 0.22 | 0.23 | 0.21 | 0.93 |
| H100, 24 m | 0.5 | 0.85 | 0.34 | 0.36 | 0.33 | 1.27 |
| H100, 24 m | 0.5 | 1.00 | 0.47 | 0.50 | 0.45 | 1.61 |
| H100, 24 m | 0.675 | 0.70 | 0.41 | 0.43 | 0.39 | 1.47 |
| H100, 24 m | 0.675 | 0.85 | 0.59 | 0.62 | 0.56 | 1.92 |
| H100, 24 m | 0.675 | 1.00 | 0.79 | 0.82 | 0.74 | 2.38 |
| H100, 24 m | 0.85 | 0.70 | 0.61 | 0.64 | 0.58 | 1.99 |
| H100, 24 m | 0.85 | 0.85 | 0.86 | 0.89 | 0.81 | 2.56 |
| H100, 24 m | 0.85 | 1.00 | 1.11 | 1.15 | 1.05 | 3.13 |
| H100, 36 m | 0.5 | 0.70 | 0.22 | 0.23 | 0.21 | 0.95 |
| H100, 36 m | 0.5 | 0.85 | 0.34 | 0.36 | 0.33 | 1.30 |
| H100, 36 m | 0.5 | 1.00 | 0.47 | 0.50 | 0.45 | 1.64 |
| H100, 36 m | 0.675 | 0.70 | 0.41 | 0.43 | 0.39 | 1.49 |
| H100, 36 m | 0.675 | 0.85 | 0.59 | 0.62 | 0.56 | 1.96 |
| H100, 36 m | 0.675 | 1.00 | 0.79 | 0.82 | 0.74 | 2.42 |
| H100, 36 m | 0.85 | 0.70 | 0.62 | 0.64 | 0.58 | 2.03 |
| H100, 36 m | 0.85 | 0.85 | 0.86 | 0.89 | 0.81 | 2.61 |
| H100, 36 m | 0.85 | 1.00 | 1.11 | 1.16 | 1.05 | 3.18 |
| A100, 24 m | 0.5 | 0.70 | 0.10 | 0.10 | 0.10 | 0.38 |
| A100, 24 m | 0.5 | 0.85 | 0.24 | 0.25 | 0.23 | 0.67 |
| A100, 24 m | 0.5 | 1.00 | 0.41 | 0.42 | 0.39 | 0.95 |
| A100, 24 m | 0.675 | 0.70 | 0.33 | 0.34 | 0.31 | 0.82 |
| A100, 24 m | 0.675 | 0.85 | 0.57 | 0.58 | 0.54 | 1.19 |
| A100, 24 m | 0.675 | 1.00 | 0.82 | 0.84 | 0.78 | 1.54 |
| A100, 24 m | 0.85 | 0.70 | 0.60 | 0.61 | 0.57 | 1.24 |
| A100, 24 m | 0.85 | 0.85 | 0.92 | 0.94 | 0.87 | 1.69 |
| A100, 24 m | 0.85 | 1.00 | 1.26 | 1.28 | 1.19 | 2.13 |
| A100, 36 m | 0.5 | 0.70 | 0.10 | 0.11 | 0.10 | 0.43 |
| A100, 36 m | 0.5 | 0.85 | 0.25 | 0.25 | 0.23 | 0.78 |
| A100, 36 m | 0.5 | 1.00 | 0.42 | 0.43 | 0.39 | 1.11 |
| A100, 36 m | 0.675 | 0.70 | 0.33 | 0.34 | 0.31 | 0.96 |
| A100, 36 m | 0.675 | 0.85 | 0.58 | 0.59 | 0.54 | 1.42 |
| A100, 36 m | 0.675 | 1.00 | 0.84 | 0.86 | 0.79 | 1.87 |
| A100, 36 m | 0.85 | 0.70 | 0.61 | 0.62 | 0.57 | 1.48 |
| A100, 36 m | 0.85 | 0.85 | 0.95 | 0.96 | 0.88 | 2.05 |
| A100, 36 m | 0.85 | 1.00 | 1.30 | 1.32 | 1.22 | 2.62 |

## Table D. Backtests already reported in v2 (v2_t3c, AWS spot), by origin; not re-run

| variant | origin | n | 80% coverage, method / no change | mean abs log error, method / no change | method better on error? |
|---|---|---|---|---|---|
| as_run_then_noise0.25 | 2023-12 | 6 | 0.00 / 0.33 | 1.20 / 0.73 | no |
| as_run_then_noise0.25 | 2024-12 | 5 | 0.40 / 0.60 | 0.71 / 0.33 | no |
| as_run_then_noise0.25 | 2025-12 | 3 | 0.00 / 0.00 | 0.53 / 0.52 | no |
| as_run_then_noise0.60 | 2023-12 | 6 | 0.33 / 0.50 | 1.20 / 0.73 | no |
| as_run_then_noise0.60 | 2024-12 | 5 | 0.80 / 1.00 | 0.69 / 0.33 | no |
| as_run_then_noise0.60 | 2025-12 | 3 | 1.00 / 1.00 | 0.52 / 0.52 | no |
| frozen_v2_rates_noise0.60 | 2023-12 | 6 | 0.67 / 0.50 | 0.75 / 0.73 | no |
| frozen_v2_rates_noise0.60 | 2024-12 | 5 | 1.00 / 1.00 | 0.44 / 0.33 | no |
| frozen_v2_rates_noise0.60 | 2025-12 | 3 | 0.67 / 1.00 | 0.60 / 0.52 | no |

## Table E. Recommendation direction tests (protocol_v3 task4)

| id | test | cells holding | statistic range | verdict | no change agrees? |
|---|---|---|---|---|---|
| R1 | H100 q50 posted rent at +24m / 6 Nov level < 1 | 3 of 3 | 0.623 to 0.701 | keep (conditional) | no |
| R2 | A100 q50 posted rent at +24m / 6 Nov level < 1 | 3 of 3 | 0.728 to 0.787 | keep (conditional) | no |
| R3 | A100 q50 value +36m / q50 value Nov 2026 < 0.10 | 27 of 27 | 0 to 0.0436 | keep (conditional) |  |
| R4_24m | H100 24-month loan: q10 cover / 20k >= 0.60 | 12 of 27 | 0.209 to 1.15 | DROP |  |
| R4_36m | H100 36-month loan: q10 cover / 20k >= 0.60 | 12 of 27 | 0.209 to 1.16 | DROP |  |
| R5 | H100 q50 value at +36m < 10.5k (35% of 30k) | 27 of 27 | 506 to 1.05e+04 | keep (conditional) |  |
| R6 | H100 q90 posted rent at +12m / 6 Nov level > 1 | 3 of 3 | 1.35 to 1.42 | keep (conditional) | yes |
| R7 | per-unit ratio vs frontier > 1 (H100, A100; v2 units and v3 unique) | 4 of 4 | 1.77 to 2.95 | keep (conditional) | yes |
| R8 | H100 q50 value Nov 2026 - Nov 2028 > 10k (2 years of 6-year straight line) | 22 of 27 | 7.33e+03 to 2.4e+04 | DROP |  |
| R9 | H100 q50 value Nov 2026 > 15k (6-year straight-line book at age 3) | 22 of 27 | 9.29e+03 to 4.27e+04 | DROP |  |

## Table F. Sanity properties

| property | chip | from month | worst per-draw violation (USD; <= 0 means it holds) | holds |
|---|---|---|---|---|
| P1 lower utilisation never raises value | H100 | 0 | -880.45 | True |
| P1 lower realised rent never raises value | H100 | 0 | -586.07 | True |
| P2 higher cost never raises value: fixed opex +0.10 USD/GPU-h | H100 | 0 | -615.57 | True |
| P2 higher cost never raises value: power price x1.5 | H100 | 0 | -153.40 | True |
| P2 higher cost never raises value: discount rate +5 points | H100 | 0 | -29.29 | True |
| P1 on displayed q50 (both directions, every weight set) | H100 | 0 |  | True |
| P1 lower utilisation never raises value | H100 | 24 | 0.00 | True |
| P1 lower realised rent never raises value | H100 | 24 | 0.00 | True |
| P2 higher cost never raises value: fixed opex +0.10 USD/GPU-h | H100 | 24 | 0.00 | True |
| P2 higher cost never raises value: power price x1.5 | H100 | 24 | 0.00 | True |
| P2 higher cost never raises value: discount rate +5 points | H100 | 24 | 0.00 | True |
| P1 on displayed q50 (both directions, every weight set) | H100 | 24 |  | True |
| P1 lower utilisation never raises value | H100 | 36 | 0.00 | True |
| P1 lower realised rent never raises value | H100 | 36 | 0.00 | True |
| P2 higher cost never raises value: fixed opex +0.10 USD/GPU-h | H100 | 36 | 0.00 | True |
| P2 higher cost never raises value: power price x1.5 | H100 | 36 | 0.00 | True |
| P2 higher cost never raises value: discount rate +5 points | H100 | 36 | 0.00 | True |
| P1 on displayed q50 (both directions, every weight set) | H100 | 36 |  | True |
| P1 lower utilisation never raises value | A100 | 0 | -171.74 | True |
| P1 lower realised rent never raises value | A100 | 0 | -83.53 | True |
| P2 higher cost never raises value: fixed opex +0.10 USD/GPU-h | A100 | 0 | -296.95 | True |
| P2 higher cost never raises value: power price x1.5 | A100 | 0 | -51.16 | True |
| P2 higher cost never raises value: discount rate +5 points | A100 | 0 | -4.63 | True |
| P1 on displayed q50 (both directions, every weight set) | A100 | 0 |  | True |
| P1 lower utilisation never raises value | A100 | 24 | 0.00 | True |
| P1 lower realised rent never raises value | A100 | 24 | 0.00 | True |
| P2 higher cost never raises value: fixed opex +0.10 USD/GPU-h | A100 | 24 | 0.00 | True |
| P2 higher cost never raises value: power price x1.5 | A100 | 24 | 0.00 | True |
| P2 higher cost never raises value: discount rate +5 points | A100 | 24 | 0.00 | True |
| P1 on displayed q50 (both directions, every weight set) | A100 | 24 |  | True |
| P1 lower utilisation never raises value | A100 | 36 | 0.00 | True |
| P1 lower realised rent never raises value | A100 | 36 | 0.00 | True |
| P2 higher cost never raises value: fixed opex +0.10 USD/GPU-h | A100 | 36 | 0.00 | True |
| P2 higher cost never raises value: power price x1.5 | A100 | 36 | 0.00 | True |
| P2 higher cost never raises value: discount rate +5 points | A100 | 36 | 0.00 | True |
| P1 on displayed q50 (both directions, every weight set) | A100 | 36 |  | True |
