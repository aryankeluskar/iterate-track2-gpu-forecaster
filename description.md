Recursive Self-Improvement by Pacific: An AI Scientist for GPU Value 

1 The challenge 

What will H100 and A100 GPUs resell for, and what will cloud rentals cost, in 2–3 years? 

Build an AI scientist that works on this question the way a researcher would: it forms hypotheses about what drives GPU prices, tests them on real data, and improves its own forecasts with each iteration. Pacific provides a data pack of GPU rental prices, spot prices, price indices and hardware data from public, openly licensed sources, and a starter kit that builds price series, runs baselines and scores forecasts. 

2 Context 

GPUs are leased, financed and depreciated like long-lived capital equipment. A lessor pricing a multi-year H100 lease, a lender advancing money against GPUs held as collateral, a buyer committing to reserved capacity and an operator setting a depreciation schedule all need the same number: what a given chip will earn, and what it will be worth, over the next few years. 

That number is hard to observe. Posted rental prices are public. Transacted prices are mostly private, and no public transaction-level resale dataset for datacenter GPUs exists. The public instruments also disagree. In one open panel, AWS, GCP and OCI changed their H100 on-demand prices 0 times across 436 snapshots, while AWS spot prices changed in 56 percent of observations \[3\]. Pooled medians shift with the mix of providers sampled, and one commercial index added marketplace prices in June 2024 and neocloud prices in July 2024 \[19\]. 

Value also depends on capability. Each new generation (H200, B200, B300) changes what an older chip earns per hour of useful work. In the MLPerf results in the data pack, an H100 delivers 2.46 times the per-accelerator inference throughput of an A100 (cross-benchmark median of Inference v3.0 and v3.1 results, SXM 80GB parts) \[13\]. A system that forecasts these prices with honest uncertainty, and learns from its own errors, is directly useful to anyone who prices GPU leases, lends against GPUs or buys reserved capacity. 

3 Data 

Pacific compiled the data pack, gpu-price-pack v0.1.1-handover, for this event from public sources whose licences allow redistribution with attribution. Its data cutoff is 6 November 2026, 23:59:59 UTC: no row is dated later. Pacific and the organisers distribute it as one zip (about 300 MB, 673 files) with a SHA-256 manifest, MANIFEST.sha256, that lists every file. Pass the pack on unchanged so anyone can verify it. The compilation is licensed CC BY 4.0; every row carries its  source\_id, source\_url and licence\_id, and DATA.md, ATTRIBUTION.md and sources\_register.csv give full provenance. 

Component What it holds Coverage Source, licence 

Posted rental offers rental\_observations/ 

Daily statistics   
daily\_statistics.csv 

GetDeploying weekly medians   
aggregator\_medians.csv   
3,778,472 posted offers from five open collectors: hyperscaler list and spot prices, neocloud rate cards and marketplace asks, with provider, GPU model, region, pricing tier and USD per GPU-hour 

39,203 rows: daily median, p25, p75 and minimum USD per GPU-hour per collector, GPU model, pricing tier and instrument class 

Prediction target for Sunday’s scoring 

16,711 rows: weekly median USD per GPU-hour for 103 GPU models by pricing mode (on-demand, spot, reserved terms)   
12 Jan to 6 Nov 2026 

12 Jan to 6 Nov 2026 

Weeks of 5 May 2025 to 2 Nov 2026 (last week provisional)   
GPU Price Tracker,  

gpurentalprices.com, FastGPU,  Tanod; CC BY 4.0 

Computed by Pacific from the offers above 

GetDeploying; CC BY 4.0  
Component What it holds Coverage Source, licence 

Cloud spot prices aws\_spot\_ticks/ 

Price indices   
index\_prints.csv 

Hardware specs   
hardware\_fundamentals/ 

Capability benchmarks capability/   
31,045,164 AWS EC2 spot price change events for GPU and accelerator instances in all regions, including A100 (p4d, p4de), H100 (p5), H200 (p5e, p5en), B200 and B300 (p6) 

Target for development backtests 

309 prints of standardized USD-per-GPU-hour indices for A100, H100, H200, B200 and other chips, with each index’s contract and day basis 

183 accelerators (release date, FP16 and FP8 TFLOPS, memory, bandwidth, TDP; release price for 60\) and 482 GPU clusters with hardware cost estimates 

3,256 MLPerf closed-division results on A100, H100 and later NVIDIA systems, a generation ladder (574 rows) and chained capability units (70 rows) for comparing chips per hour of work   
31 May 2022 to 31 Oct 2026; 1 Mar to 30 Jun 2026 

absent from the archive 

7 Sep to 6 Nov 2026 

Chips released 2008 to 2026; clusters 2010 to 2025 

Inference v3.0 to v6.1, Training v2.0 to v4.0   
AWS Spot Price History, 

E. Pauley, Zenodo; CC BY 4.0 

Compute Screener (CC BY 4.0),  GIX (MIT), GPU Economy (CC BY 4.0) 

Epoch AI hardware, Epoch AI clusters; CC BY 4.0 

MLCommons results 

repositories; Apache-2.0 

Resale and market pointers resale\_pointers.csv   
pointer\_sources.csv   
market\_implied\_baselines.csv External public signals   
URLs, coverage and reuse terms for resale indices, appraisals, used-GPU price ranges, commercial indices and prediction markets, with no values. No open resale dataset exists; these list where resale prices are published.   
As published American Compute, CCIR,  Compute Exchange, Silicon Data 

and others; each publisher’s 

terms; cite with attribution 

NVIDIA Newsroom announcements, live Epoch AI hardware data and the BLS electricity distribution index (Producer Price Index, series PCU221122221122). Cite news by date, title and link, and follow each site’s terms on automated access. External data must be public, free to every team and dated before each forecast origin. The pack leaves out sources whose terms bar compiling their data; do not add them back (DATA.md, section 9). 

4 Starter kit 

starter/ inside the pack is a Python kit that reads only the pack, needs no network and writes outside it. 

•    
build\_series.py builds daily target series and their catalog from daily\_statistics.csv and aws\_spot\_ticks/;  \--cutoff writes a history truncated at a date. 

•    
baselines.py writes four quantile baselines: last\_value, last\_value\_empirical, drift and seasonal\_naive. •    
scorer.py scores forecasts with pinball loss and skill against the last-value baseline, with a frozen-cutoff mode. •    
make\_sample\_submission.py writes a valid sample forecast file. 

Quickstart 

Python 3.10 or later (use a venv if pip refuses). In the folder holding gpu-price-pack-v0.1.1-handover: 

python3 \-m pip install \-r gpu-price-pack-v0.1.1-handover/starter/requirements.txt 

bash gpu-price-pack-v0.1.1-handover/starter/run\_demo.sh gpu-price-pack-v0.1.1-handover demo\_out 2026-10-24

Expect six numbered steps in under a minute: series, baselines, a sample submission, frozen scoring, a refusal check and a rolling-origin backtest. Step 5 prints REFUSED, which is the leakage check working. To check the pack is intact, run sha256sum \-c MANIFEST.sha256 \| grep \-v ': OK\$' inside it (on a Mac, shasum \-a 256 \-c); no output means every file matches. 

Series ids are opaque strings listed in series\_catalog.csv with their key columns, coverage, tier and benchmark contract, for example gpurentalprices.neocloud\_rate\_card.H100\_SXM\_80GB.on\_demand.median. At the demo cutoff the catalog holds 728 series, 97 of them in the headline tier.   
Forecast file 

One CSV, one row per (series\_id, origin\_date, horizon\_days). 

Column Rule 

series\_id an id from series\_catalog.csv 

origin\_date the last day whose data the forecast may use (YYYY-MM-DD) 

horizon\_days 1, 3, 7 or 30; the target date is origin\_date \+ horizon\_days 

q10, q50, q90 the 0.1, 0.5 and 0.9 quantiles in USD per GPU-hour; q10 \> 0 and q10 ≤ q50 ≤ q90 optional target\_date (must equal origin \+ horizon), team\_id, method\_note 

series\_id,origin\_date,horizon\_days,q10,q50,q90,target\_date 

gpurentalprices.neocloud\_rate\_card.H100\_SXM\_80GB.on\_demand.median,2026-10-24,7,3.40,3.79,4.10,2026-10-31 

5 Notes on the challenge 

What we are looking for 

A system that does research: it proposes a hypothesis about what moves GPU prices, designs a test, runs it, keeps what survives, records what it learned and repeats. We care how its forecasts improve across iterations and why. Leaderboard position alone will not win. Well-supported negative results count as much as positive ones: if nothing beats a random walk at one week, show that convincingly. 

Baselines to beat 

All baselines use only data on or before the origin. last\_value is the flat last observation and the denominator of every skill score. drift scales the last value by the empirical 0.1, 0.5 and 0.9 quantiles of the series’ historical h-day log changes, a random walk with empirical increments. The starter kit reports drift at pooled skill \+0.20 over the 97 headline series at the demo cutoff of 24 October 2026, and \+0.17 pooled over 15 weekly backtest origins from 15 July to 24 October. last\_value\_empirical is within 0.01 of drift; seasonal\_naive loses to the last value at 1 and 3 days because posted prices have no weekly cycle. Beat drift with calibrated intervals. 

Evaluation setup: a backtest 

Judges cannot wait 2–3 years, so the scored part is a short-horizon backtest with a hard cutoff. 

•    
Origin and horizons. Forecasts start from 6 November 2026, where the data pack stops, at horizons of 1, 3 and 7 days (targets 7, 9 and 13 November). 

•    
Truth. Posted rental prices collected daily from the same sources after the cutoff, frozen at the end of Friday 13 November (UTC) with its SHA-256 hash published. 

•    
Scoring on Sunday 15 November. scorer.py scores forecasts of posted rental prices against that truth in frozen cutoff mode. The metric is pinball loss at quantiles 0.1, 0.5 and 0.9, averaged over each (series, origin, horizon) cell; skill is 1 − loss / last-value loss. The report gives pooled skill (the scorer’s default headline), mean, median and geometric-mean skill across series, and interval coverage (target 0.8 inside \[q10, q90\]). Cells you leave out are filled with the last-value baseline, which scores zero skill. 

•    
Honesty checks. Frozen mode refuses, with REFUSED and exit code 2, any forecast whose origin is not the cutoff and any history file holding a row dated after it. Invalid rows (non-positive or crossed quantiles, bad horizons, duplicates) are dropped and listed in the report. 

•    
Not scored on Sunday. AWS spot series have no November data until the archive’s next monthly file (due 1 December), and horizon 30 lands on 6 December. 

•   
Your own backtests. Run the scorer in backtest mode on earlier cutoffs: the demo uses 24 October 2026, and  baselines.py can write forecasts for weekly origins. Every historical truth is inside the pack, so fix your origins before you look and treat these runs as development feedback. A self-improving system should show its gains on origins it had not seen when it changed itself.   
•    
Resale and the 2–3 year view. These cannot be scored by Sunday. Argue them from public evidence (the resale pointers, the capability ladder, launch prices, the four-year spot history) and the judges assess the argument. State your assumptions and give ranges. 

Pitfalls documented in the data pack 

•    
List prices, rate cards, marketplace asks, indices, medians, resale prints and launch prices are different instruments. Never chain them into one curve, and declare the instrument class and benchmark contract (SKU, GPU count, region, tier, term) of every target. 

•    
Define targets per source and series: pooled medians move with the mix of providers. 

•    
Rate-card medians move in steps: one H100 SXM 80GB neocloud median took six distinct values in 235 days. •    
AWS spot is an administered price. Its archive hole (1 March to 30 June 2026\) splits every series into two segments; never interpolate across it. 

•    
Index prints use different day bases (US Central day, a fixing published about 14:10 UTC, ISO week); never align them by naive date. 

6 Directions 

Choose one direction. Each states a question; the method is yours. 

Direction A: Self-improving GPU price forecasts 

Forecast GPU prices with a system that learns from previous predictions and new evidence. Possible inputs include daily posted rental prices and GetDeploying advertised rental price history, both in the data pack. Explore how its forecasts could improve over time. 

Direction B: Forecasting GPU prices from market signals 

Forecast GPU prices using market news, infrastructure developments and historical pricing. Possible signals include NVIDIA Newsroom announcements, Epoch AI hardware data and the BLS electricity distribution index. Explore how memory could help make sense of evolving evidence and inform predictions. Cite news by date, title and link, and follow each site’s terms on automated access. 

Direction C: Your own approach to GPU price forecasting 

Bring your own research question or approach to forecasting GPU prices. Explore the signals, methods or market dynamics you find most promising. 

7 Submission 

Submit code and a demo, plus concise findings. 

•    
Forecasts in the starter kit’s format with origin\_date 2026-11-06 and horizons 1, 3 and 7, for the posted rental series you choose. 

•    
One command that reproduces them from the pack and any cited public data dated on or before 6 November. •   
Findings: the question, method, evaluation, results with uncertainty, what your system learned across iterations and, if you address it, your argued view on resale and rentals in 2–3 years.   
8 Evaluation criteria 

•    
Rigour: a leak-free evaluation with declared targets, honest uncertainty and conclusions the evidence supports. •    
Useful economic insight: findings that someone pricing a GPU lease, lending against GPUs or buying reserved capacity could act on. 

•    
Reproducibility: one command rebuilds your forecasts and results from the pack and cited public data. •   
Originality: a question, signal or method that teaches us something new about GPU value. \$5,000 worth of Pacific compute hours: first \$3,000, second \$1,500, third \$500. 

9 References 

Data sources (cite with the wording in ATTRIBUTION.md) 

1\. Pacific Machines (2026). gpu-price-pack v0.1.1-handover, data cutoff 6 November 2026\. CC BY 4.0 on the compilation. 2\. Pauley E. AWS Spot Price History. Zenodo. doi.org/10.5281/zenodo.14198917 

3\. Hubbard A (2026). GPU Price Tracker dataset and methodology. github.com/alex-hubbard/gpu\_price\_tracker/blob/main/methodology.md 4\. gpurentalprices.com. GPU rental price data. gpurentalprices.com 

5\. FastGPU. GPU cloud pricing dataset. fastgpu.co/dataset 

6\. Tanod. Cloud GPU prices and Akash marketplace bids. huggingface.co/datasets/tanod/cloud-gpu-list-prices 7\. GetDeploying. GPU rental price history. getdeploying.com/gpus 

8\. Compute Screener. Index methodology. computescreener.com/methodology 

9\. Zhang H. GIX, gpu-price-index. github.com/henryzhangpku/gpu-price-index 

10\. GPU Economy. Cloud GPU Price Index. gpueconomy.com/price-index 

11\. Epoch AI. Data on machine learning hardware. epoch.ai/data/machine-learning-hardware 

12\. Epoch AI. Data on GPU clusters. epoch.ai/data/gpu-clusters 

13\. MLCommons Association. MLPerf Inference and Training results repositories. github.com/mlcommons 

14\. US Bureau of Labor Statistics. PPI, electric power distribution, PCU221122221122. data.bls.gov/timeseries/PCU221122221122 15\. NVIDIA Newsroom. nvidianews.nvidia.com/ 

Resale, spot markets and hardware economics 

16\. American Compute. GPU Resale Index and residual-value bands. www\.amcompute.com/gpu-resale-index 17\. CCIR. Used datacenter GPU hardware record. ccir.io/hardware 

18\. Silicon Data. H100 GPU market value trends. www\.silicondata.com/use-cases/h100-gpu-market-value-trends 19\. Silicon Data. H100 rental price over time. www\.silicondata.com/blog/h100-rental-price-over-time 

20\. Cao Z, Guo X, Zhang C, et al. DumpsterCluster: From Dumpster Diving to Serving LLaMA-70B on \$60 GPUs. arXiv:2608.14614, 2026\. 21\. Buczyński M, Woźniak M, Kaczyński K, et al. Deep Learning vs. Statistical Models for Multi-Horizon Price Forecasting of Second-Hand Electronics: A Systematic Benchmark. arXiv:2610.10727, 2026\. 

22\. Agmon Ben-Yehuda O, Ben-Yehuda M, Schuster A, Tsafrir D. Deconstructing Amazon EC2 Spot Instance Pricing. ACM Transactions on Economics and Computation, 2013\. ladypine.org/spotprice-acmsmall.pdf 

23\. Baughman M, Haas C, Wolski R, Foster I, Chard K. Predicting Amazon Spot Prices with LSTM Networks. ScienceCloud 2018\. labs.globus.org/ pubs/Baughman\_ScienceCloud\_2018.pdf 

24\. Hobbhahn M, Besiroglu T. Trends in GPU price-performance. Epoch AI, 2022\. epoch.ai/blog/trends-in-gpu-price-performance 25\. Hobbhahn M, Heim L, et al. Trends in machine learning hardware. Epoch AI, 2023\. epoch.ai/blog/trends-in-machine-learning-hardware 

Forecasting and evaluation 

26\. Koenker R, Bassett G. Regression Quantiles. Econometrica 46(1):33–50, 1978\. doi.org/10.2307/1913643 

27\. Gneiting T, Raftery AE. Strictly Proper Scoring Rules, Prediction, and Estimation. JASA 102(477):359–378, 2007\. doi.org/10.1198/ 016214506000001437 

28\. Diebold FX, Mariano RS. Comparing Predictive Accuracy. JBES 13(3):253–263, 1995\. doi.org/10.1080/07350015.1995.10524599 29\. Tashman LJ. Out-of-sample tests of forecasting accuracy: an analysis and review. IJF 16(4):437–450, 2000\. doi.org/10.1016/ S0169-2070(00)00065-0 

30\. Makridakis S, Spiliotis E, Assimakopoulos V. The M4 Competition: 100,000 time series and 61 forecasting methods. IJF 36(1):54–74, 2020\.  doi.org/10.1016/j.ijforecast.2019.04.014 

31\. Hyndman RJ, Athanasopoulos G. Forecasting: Principles and Practice, 3rd ed. OTexts, 2021\. otexts.com/fpp3/ 32\. Ansari AF, Stella L, Turkmen C, et al. Chronos: Learning the Language of Time Series. arXiv:2403.07815, 2024\. 33\. Das A, Kong W, Sen R, Zhou Y. A decoder-only foundation model for time-series forecasting. arXiv:2310.10688, 2023\. 

AI scientists, memory and LLM forecasting 

34\. Lu C, Lu C, Lange RT, et al. The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery. arXiv:2408.06292, 2024\. 35\. Shinn N, Cassano F, Berman E, et al. Reflexion: Language Agents with Verbal Reinforcement Learning. arXiv:2303.11366, 2023\. 36\. Packer C, Wooders S, Lin K, et al. MemGPT: Towards LLMs as Operating Systems. arXiv:2310.08560, 2023\. 37\. Halawi D, Zhang F, Yueh-Han C, Steinhardt J. Approaching Human-Level Forecasting with Language Models. arXiv:2402.18563, 2024\. 38\. Karger E, Bastani H, Yueh-Han C, et al. ForecastBench: A Dynamic Benchmark of AI Forecasting Capabilities. arXiv:2409.19839, 2024\. 