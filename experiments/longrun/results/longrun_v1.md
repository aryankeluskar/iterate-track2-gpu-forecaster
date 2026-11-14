# What will H100 and A100 rent and resell for in 2 to 3 years? (slug `longrun`)

Data: gpu-price-pack v0.1.1-handover, rows to 2026-11-06 (AWS spot archive ends 2026-10-31). Not a scored forecaster. Nothing here feeds the 1 to 7 day methods.
Reproduce: `.venv/bin/python experiments/longrun/code/aws.py && .venv/bin/python experiments/longrun/code/analysis.py && .venv/bin/python experiments/longrun/code/figures.py` (seeded; Exa calls are cached in `runs/longrun/exa_cache`, `code/exa_resale.py`).
Predictions were written down before fitting: `experiments/longrun/protocol.yaml`. The verdict on each is at the end.

## Bottom line

- **Rent, H100, aggregator on-demand median (GetDeploying, all priced listings, SXM and PCIe pooled by the publisher):** 3.83 USD/GPU-h in Nov 2026. Projection: **1.7 at +24 months (q10 0.8, q90 3.8)** and **1.1 to 1.4 at +36 months (q10 0.4 to 0.5, q90 3.0 to 3.7)**. The decay model and the per-unit-parity model agree for H100.
- **Rent, A100, same instrument:** 1.80 today. The two models disagree. Decay gives **1.5 at +24 months (0.7 to 3.2)**. Per-unit parity gives **0.45 (0.17 to 1.15)**. A100 today rents at about 2x the frontier's price per unit of work. The answer depends on whether that premium survives.
- **Resale, income approach, Nov 2026:** H100 **16k USD per GPU (q10 10k, q90 25k)** on a 3-year-reserved rent basis, or 24k on an on-demand basis. A100 **8.8k (5k to 14k)**. Published used prices (Exa, below) fall inside these ranges: H100 SXM 18k to 22k, A100 80GB 5k to 9.5k.
- **The long-run method failed its backtest.** A log-linear decay fitted before the 2026 shortage lost to no-change on both instruments. All the projections above are therefore conditional on 2026 being a regime and not a new trend. The q90 values are set so they roughly hold today's price.

## 1. Price per unit of work (`t1_*.csv`, fig1)

Capability units come from `capability_units.csv`, central set `ship_only_inf_cross_benchmark_median_a100ref_sxm80`: A100 1, H100 2.46, H200 2.72, B200 7.91, B300 8.77. The range uses the LLM offline and server chains and the FP16 datasheet. Each price is the median over the last 4 final weeks (aggregator) or over 2026-10-07 to 2026-11-06 (daily_statistics, per source × class × tier). There are 26 instruments, each kept separate.

| instrument (Nov 2026) | A100 | H100 | H200 | B200 | B300 | A100 / frontier | H100 / frontier |
|---|---|---|---|---|---|---|---|
| aggregator_median on_demand, USD per unit-h | 1.80 | 1.55 | 1.82 | 0.97 | 1.04 | 1.86 (1.69 to 3.66) | 1.60 (1.13 to 1.62) |
| aggregator_median spot | 1.20 | 0.97 | 1.23 | 0.60 | 0.60 | 2.00 | 1.61 |
| aggregator_median reserved_36m | 1.36 | 1.21 | 1.09 | 0.79 | 0.57 | 2.39 | 2.11 |
| neocloud_rate_card gpurentalprices on_demand | 2.02 | 1.54 | 1.68 | 0.87 | 1.11 | 2.32 | 1.76 |
| marketplace_ask fastgpu on_demand | 1.49 | 0.83 | 1.34 | 0.70 | 0.91 | 2.15 | 1.19 |
| **median over 26 instruments** | | | | | | **2.30** | **1.78** |

"Frontier" means the cheaper of B200 and B300 per unit on the same instrument. The range in brackets is the spread across unit sets.

- **Older chips rent at a premium per unit of work, not a discount.** For A100 the ratio is above 1 on all 23 instruments that price it, under every unit set. For H100 it is above 1 on all 26 at the central units. Under the most generous unit set its lower bound drops below 1 on 4 marketplace instruments. The power cost does not explain the premium. At 0.05 to 0.12 USD/kWh and PUE 1.2 to 1.5, an H100's extra energy per unit of work relative to B300 costs **0.038 USD/GPU-h** (A100: 0.033). That is about 1% of its price.
- **The premium is shrinking.** The weekly on-demand ratio against B200 went from 2.26 to 1.85 for A100, a trend of **−21%/yr (90% CI −35 to −3)**. For H100 it went from 1.78 to 1.59, **−13%/yr (−25 to +6)**. H200 moved −6%/yr (−16 to +0.5). The window is 52 weeks, with an 8-week moving-block bootstrap.
- The weekly medians for these five chips start on 2025-11-03. The "18 months" in the task is really **12 months** for these chips, because the earlier weeks cover only 4 to 9 legacy models.

## 2. Decay with age (`t2_decay_rates.csv`, `t2b`, `t2c`, fig2)

Within-chip log price is regressed on time. For AWS the regression has AZ fixed effects on weekly per-AZ prices, and segments A (to 2026-02) and B (from 2026-07) are fitted separately. Intervals come from a moving-block pairs bootstrap.

| instrument | chip | window | annual change (90% CI) |
|---|---|---|---|
| aggregator_median on_demand | A100 | 2025-11 to 2026-10 | **+15%** (+5, +23) |
| aggregator_median on_demand | H100 | same | **+26%** (−6, +68) |
| aggregator_median on_demand | H200 / B200 / B300 | same | +37% / +45% / +82% |
| aggregator_median spot | A100 / H100 | same | −38% (−69, −14) / −12% (−58, +65) |
| aggregator_median reserved_36m | A100 / H100 | same | −11% (−16, 0) / +12% (−17, +121) |
| hyperscaler_spot AWS segA | A100 40GB p4d | 2022-05 to 2026-02 | **−9.5%** (−13.7, −2.2) |
| hyperscaler_spot AWS segA | H100 p5 | 2023-07 to 2026-02 | **−31%** (−46, −20) |
| hyperscaler_spot AWS segB (4 months only) | p4d / p5 | 2026-07 to 2026-10 | −11% (−48, +27) / +72% (−18, +118) |

- Over multiple years, H100 on AWS spot fell about 31%/yr and A100 about 10%/yr. Over the last 12 months, every on-demand and rate-card median **rose**, and newer chips rose faster. Rolling 12-month AWS windows change sign: p5 −66%/yr from Dec 2023, +49% from Jun 2025; p4d +209% from Dec 2023 (`t2b`). Decay is not a stable property of a chip. It is the combination of an age trend and market-wide regimes.
- **Successor event study:** I compared the 26-week slope before and after six dates (Epoch releases of H200/B200 and B300; first AWS ticks of p5en, p5e, p6-b200 and p6-b300) on p4d and p5, giving 12 pairs. Only **5 of 12** pairs were steeper after the event. The mean change was **+0.48 log/yr** (later prices fell less). Individual pairs swing by ±2 log/yr, with tight but contradictory intervals. **No evidence that a successor's arrival speeds up the decay of AWS spot prices.** AWS spot is an administered price. It also moved with AWS's on-demand cut of June 2025: AWS announced "up to 45 percent price reduction for ... P4 (P4d and P4de) and P5 (P5 and P5en) instance types" (2025-06-05, *Announcing up to 45% price reduction for Amazon EC2 NVIDIA GPU-accelerated instances*, https://aws.amazon.com/blogs/aws/announcing-up-to-45-price-reduction-for-amazon-ec2-nvidia-gpu-accelerated-instances/). The H200 and B200 Epoch dates fall three days apart, so those two cannot be separated.

## 3. Backtest of the long-run method (`t3a`, `t3b`)

Both the decay model and no-change use the same random-walk width, so the test isolates the centre.

| test | n | MAE log: decay | MAE log: no-change | difference, 90% CI | coverage 80%: decay / no-change | pinball skill vs no-change |
|---|---|---|---|---|---|---|
| aggregator, fit 2025-11-03 to 2026-04-27, target week 2026-10-26 (26 weeks), all models × 4 modes | 117 | 0.66 | 0.42 | +0.18 to +0.30 | 0.68 / 0.78 | −0.85 |
| same, the five chips | 16 | 0.44 | 0.33 | +0.02 to +0.22 | 0.69 / 0.69 | −0.02 |
| AWS spot, fit 24 months to 2025-10-31 (segA), target monthly medians Jul to Oct 2026 (9 to 12 months), 5 instance types | 20 | 0.67 | 0.30 | +0.12 to +0.65 | 0.80 / 0.85 | −4.7 |

The decay centre **failed**: no-change wins on both instruments. Even no-change was biased low, with the truth 0.29 log above it on the five chips. The cause was the 2026 tightening, which the press reported as it happened. SemiAnalysis's H100 1-year index "surged almost 40% to $2.35/hour/GPU in March from a low of $1.70/hour/GPU in October 2025" (2026-04-02, Seeking Alpha, *Nvidia's H100 GPU rental prices surge nearly 40% in 6 months*, https://seekingalpha.com/news/4572260-nvidias-h100-gpu-rental-prices-surge-nearly-40-in-6-months-semianalysis). Another report: "Unlike the past, when rental rates for older products fell as new ones arrived, prices for previous-generation GPUs are rising as well" (2026-09-22, Seoul Economic Daily, *H100 Rental Prices Jump 22% in a Month...*, https://en.sedaily.com/economy/2026/09/22/h100-rental-prices-jump-22-percent-in-a-month-as-gpu). Short-window trend extrapolation is harmful at 6 to 12 months. I keep the decay model only with (a) the multi-year AWS segment-A rate and not a recent slope, and (b) a level noise of **0.41 log per √year**, calibrated on this backtest's no-change errors.

## 4. Projections at +24 and +36 months (`t4_projections.csv`, fig3)

- **Decay model:** start from today's level on each aggregator instrument. Apply the multi-year AWS segA within-chip rate (H100 −34%/yr, q10 −43, q90 −23; A100 −9%/yr, −13 to −4). Only the rate is borrowed from AWS, never the AWS level. Add level noise of 0.41·√T.
- **Parity model:** old-chip price = units × frontier price per unit − power handicap. The frontier per-unit price falls at the hardware price-performance rate. Half the draws use the pack's Epoch-catalogue fit, which gives FLOP/s per release-USD **+16%/yr (+2 to +27, n = 15 NVIDIA parts)**. The other half use 25 to 35% around Epoch's published figure: "hardware at any given precision and fixed performance level becomes 30% cheaper each year" (2024-10-23, Epoch AI, *Performance per dollar improves around 30% each year*, https://epoch.ai/data-insights/price-performance-hardware). Electricity is 0.05 to 0.12 USD/kWh, PUE 1.2 to 1.5, TDP from hardware_fundamentals (A100 400 W, H100 700 W, B300 1100 W). The "premium persists" variant keeps today's per-unit premium, decaying at its observed rate with a floor at 1.

| USD/GPU-h, q50 (q10 to q90) | H100 +24 m | H100 +36 m | A100 +24 m | A100 +36 m |
|---|---|---|---|---|
| on_demand: decay | 1.67 (0.76 to 3.78) | 1.11 (0.41 to 3.04) | 1.51 (0.72 to 3.17) | 1.38 (0.55 to 3.45) |
| on_demand: strict parity | 1.67 (0.74 to 3.80) | 1.36 (0.50 to 3.67) | 0.45 (0.17 to 1.15) | 0.37 (0.10 to 1.12) |
| on_demand: premium persists | 2.03 (0.90 to 4.61) | 1.44 (0.53 to 3.87) | 0.53 (0.20 to 1.34) | 0.37 (0.10 to 1.12) |
| reserved_36m: decay | 1.30 (0.59 to 2.90) | 0.87 (0.31 to 2.39) | 1.14 (0.54 to 2.37) | 1.04 (0.42 to 2.59) |
| spot: decay | 1.05 (0.47 to 2.36) | 0.70 (0.25 to 1.94) | 1.01 (0.48 to 2.11) | 0.91 (0.36 to 2.26) |

**Where and why the models disagree.** For H100 they agree. Today's parity value (2.39) is already 40% below the market price (3.83), and the steep H100 age decay closes most of that gap within two years. For A100 they disagree by about 3x. Parity says A100 should already rent at 0.97, not 1.80. The decay model says A100's price has eroded only about 10%/yr since 2022, so the premium is persistent.

The data contain both forces. The premium is real: it is about 2x and appears on all 26 instruments. It is also shrinking, at about 21%/yr. A shrinking premium sits closer to "decay" for 2 to 3 years and closer to "parity" for 5 years or more. My central A100 path is between the two, about 1.0 at +24 months. Power explains about 1% of the premium. The rest is more likely job granularity (many jobs do not need a B300 node), 80 GB memory being enough for small-model inference, owners with sunk cost who still price above marginal cost, and the frictions of moving software and contracts. This is an inference, not a test.

## 5. Resale by income approach (`t5_income_sensitivity.csv`)

Value per GPU = present value of monthly (rent × utilisation − fixed opex − power × utilisation) × 730 h over the remaining life. Rent is the aggregator median and decays at the long-run rate. A GPU is idled in any month where its net income is negative.

Ranges: utilisation 50 to 85%; discount rate 10 to 20%; remaining life H100 2 to 5 years, A100 1 to 4 years; fixed opex (colocation, network, maintenance) H100 0.25 to 0.45 USD/GPU-h, A100 0.20 to 0.35; power as in §4.

| USD per GPU | Nov 2026, reserved_36m rent | Nov 2026, on-demand rent | Nov 2028, reserved_36m rent |
|---|---|---|---|
| H100 | **16.4k** (10.4k to 24.7k) | 23.7k (15.6k to 34.8k) | 2.1k (0.3k to 7.0k) |
| A100 | **8.8k** (5.1k to 14.0k) | 13.3k (7.8k to 20.6k) | 1.5k (0 to 5.5k) |

Sensitivity is the q50 value with each input in its bottom versus top quintile.
- H100: utilisation 11.4k vs 21.4k; age-decay rate 12.2k vs 22.6k; fixed opex 18.2k vs 14.8k; discount rate 17.0k vs 15.7k; life 15.3k vs 16.9k.
- A100: life 5.6k vs 12.0k; utilisation 6.1k vs 12.3k.

Utilisation and the decay rate drive H100 value. Remaining life drives A100 value. The Nov 2028 figure depends mainly on how much life is left by then and should be read as a floor scenario.

**Published figures (Exa, end published date ≤ 2026-11-06, 12 searches, 0.08 USD):**

| date | title | link | quoted sentence |
|---|---|---|---|
| 2026-09-24 | The GPU Depreciation Schedule You're Using Wrong (GPUaaS.com) | https://gpuaas.com/blog/gpu-depreciation-resale-value-2026 | "Used H100s trade at $18,000 to $22,000 against $25,000 to $35,000 new." / "Rental rates fell 75-80% from the 2023 peak while resale held near half of list." |
| 2026-06-23 | NVIDIA H100 Resale Value 2026: Used Sells at $22K–$25K (Mercatus) | https://www.mercatus-ai.com/blog/h100-resale-value | Table row: "36 months \| 40 to 75% \| $12,000 to $22,500 \| Wide range, Blackwell-ramp dependent" |
| 2026-05-22 (page states data of 2026-09-09; evergreen page) | Used NVIDIA H100 & A100 Buying Guide 2026 (Caladan) | https://caladansemi.com/blog/used-nvidia-h100-a100-gpu-buying-guide-2026 | "H100 80GB SXM5 \| $14,000 to $22,550 · median $19,550 · 3 US listings ... asking prices, not sold" |
| 2026-11-05 | Used AI GPU Prices and Useful Life: A100 to H100 (Luminix, secondary compilation) | https://www.useluminix.com/reports/industry-analysis/gpu-depreciation-debate/source/3 | A100 "80GB variants trade at $5,000–$9,500 (some listings up to ~$13,000)"; H100 "SXM 80GB used ~$14,250–$27,000 (Q2 2026 data showed $15k–$19k realized ...)" |
| 2026-10-21 | Silicon Data CEO says older AI chips are still in high demand (Crypto Briefing) | https://cryptobriefing.com/silicon-data-ceo-older-ai-chip-demand/ | "Silicon Data's figures put H100 residual values at approximately 61% of their purchase price as of mid-October 2026" / A100: "After six years, it still holds about 22.5% of its original value." |
| 2026-01-30 | The Illusion of Stability: Unpacking H100 GPU Market Value Trends (Silicon Data) | https://www.silicondata.com/use-cases/h100-gpu-market-value-trends | "USED and REFURBISHED H100s trading as high as $50,000 in mid-2024, only to plunge sharply as supply increased and buyer power returned." |
| 2026-11-03 | What is a used GPU worth? (Foundation) | https://fdncompute.com/articles/gpu-residual-value-secondary-market | "GPU-backed lenders typically advance 60–70% of value" / "a $11.7M, 36-month Data Sales server lease to Corvex, disclosed in an SEC filing, assumed 35%." |

Cross-check results:
- H100: the income value of 16k (reserved basis) to 24k (on-demand basis) brackets the published 18k to 22k used-trade range and the 19.6k eBay ask median.
- A100 80GB: the income value of 8.8k (5k to 14k) matches the published 5k to 9.5k.
- Silicon Data's 22.5% A100 residual on a 15k release price (Epoch, A100 40 GB) comes to about 3.4k. That is below my q10, which fits the 40 GB part being worth less.
- A 35% lessor residual at 36 months on 25k to 35k new comes to 9k to 12k for H100 in 2029. My +24 month (Nov 2028) income value is 2k to 7k, and the resale market prices H100 above its income value. The market may be paying for scarcity optionality, or my decay rate may be too steep. Because of the backtest failure, I cannot rule out the second.

## Assumptions

- Instruments are never chained. Only rates are borrowed across instruments (AWS segA rate → aggregator level).
- MLPerf inference units measure work. For training, A100→H100 is 2.95 rather than 2.46, which would make H100's per-unit premium smaller.
- The GetDeploying medians pool SXM and PCIe and include RunPod upstream.
- Electricity 0.05 to 0.12 USD/kWh; PUE 1.2 to 1.5; no carbon price.
- Rent is a posted median. A lessor's realised rate is lower, which is why the reserved_36m rent basis is the central case.
- The AWS hole is not interpolated. Segment B (4 months) is too short for a reliable slope.

## What would change the answer

- **The 2026 shortage persisting.** All prices have risen about 15 to 80%/yr since Nov 2025. If that continues, the q90 values are the right planning numbers, not the q50.
- **The B300/Rubin ramp.** Frontier per-unit price falling faster than 30%/yr pushes A100 toward the parity path.
- **Evidence on why the premium exists.** If it is job granularity or memory, it lasts. If it is search frictions, it erodes.
- **A transaction-level resale series.** None exists in the pack. The published figures are mostly asks and broker ranges.

## For decision makers

**Lessor.** Price a new 36-month H100 lease to recover cost at an H100 rent of about 1.3 USD/GPU-h (reserved basis) in late 2028. Treat today's 3 to 3.8 as a peak, because the multi-year AWS rate is −31%/yr and the 2026 rise did not show up in any earlier window. For A100 the downside is the parity path (0.3 to 0.5 by 2028), not a slow drift. Keep A100 terms short or price them with a step-down. Charge for the per-unit premium while it lasts: it is about 2x for A100 and shrinks about 20%/yr.

**Lender.** On an income basis, H100 collateral is worth about 16k per GPU today (10k to 25k) and 2k to 7k in late 2028. The market's 18k to 22k used price is above income value, so an advance of 60 to 70% of market value is close to 100% of the income-based central value. Size H100 advances off the income value, and make the amortisation fall within the contract term. The A100 income value of 5k to 14k depends mainly on remaining life, so value it by maturity and not by chip.

**Reserved-capacity buyer.** Per unit of work, B200 and B300 are about half the price of H100 and a third of A100 on every instrument. Buy older chips only for jobs that cannot use a large node. My backtest showed that "prices only fall" was wrong over Nov 2025 to Oct 2026. Do not leave capacity unreserved on the assumption that prices will drop. Prefer 12 to 24-month terms on H100 at or below today's reserved median of about 3 USD, with options to switch to B-class chips.

## Predictions versus outcome (protocol.yaml)

- **P1 (older chips at a per-unit premium that is shrinking):** held. A100 2.30x and H100 1.78x the frontier, median of 26 instruments. Trend −21%/yr and −13%/yr. The H100 interval includes 0.
- **P2 (decay):** partly failed. Multi-year AWS decay held for H100 (−31%) and was smaller than predicted for A100 (−9.5%). The 12-month aggregator rates are positive. The successor-acceleration hypothesis is refuted (5 of 12).
- **P3 (decay beats no-change):** failed on both instruments.
- **P4 (H100 1.3 to 1.9 at +24 months):** consistent (1.67). The A100 forecast of 0.7 to 1.1 sits between the decay result (1.5) and the parity result (0.45). Parity came out lower than decay for A100 only, not for H100.
- **P5 (H100 8k to 18k, A100 3k to 8k):** H100 central 16k, inside the range. A100 at 8.8k is slightly above. Published figures sit inside or above the income range, as predicted.

Figures: `fig1_per_unit_ratio.png`, `fig2_aws_spot.png`, `fig3_projections.png`.
