# ForecastBench: A Dynamic Benchmark of AI Forecasting Capabilities

Karger et al., 2024. arXiv 2409.19839. Read from local LaTeX (paper.tex abstract line; tables/combined_leaderboard.tex, human_combo_leaderboard_overall.tex).

- 1,000 auto-generated questions about unresolved future events; human and LLM forecasts on a 200-question subset. Abstract: expert forecasters outperform the best LLM (p < 0.001).
- Brier scores (lower is better), human combination-question leaderboard overall: superforecaster median 0.076, public median 0.096, best LLM row about 0.155 to 0.16, imputed forecaster 0.155. Combined leaderboard: superforecasters 0.091, public median 0.111, Always 0.5 baseline 0.163 / 0.150 on two question sets.
- A zero-information style baseline is strong: the best Claude-3.5-Sonnet row in the combined leaderboard that uses "freeze values" (carry forward the last value) with a scratchpad scores 0.111, close to the public median 0.111 on that table.
- LLMs given news did not clearly beat zero-shot with freeze values in the rows I looked at (Claude-3.5-Sonnet news with freeze values 0.116 versus freeze values 0.111); I did not verify across all models.

Relevance to us: a last-value baseline ("freeze values") is competitive; this supports using last value and drift as the bars.
