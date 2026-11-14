# Adaptive Conformal Inference Under Distribution Shift

Gibbs and Candes, 2021. arXiv 2106.00170. Read from fetched PDF text.

- Update rule (Eq. 2): alpha_{t+1} = alpha_t + gamma * (alpha - err_t), where err_t = 1 if y_t is outside the set built with quantile level 1 - alpha_t, else 0, and gamma > 0 is a step size. alpha_1 = alpha in their experiments. Eq. 3 is a smoothed variant with weights w_s on past errors; they find (2) and (3) give almost identical results with (3) smoother.
- Proposition 4.1 (no distributional assumptions): for all T, |(1/T) sum_{t<=T} err_t - alpha| <= (max{alpha_1, 1 - alpha_1} + gamma) / (T * gamma). So long-run miscoverage converges to alpha for any data stream, at rate O(1/(T gamma)).
- It wraps any black-box quantile or point forecaster; it controls average (marginal over time) coverage, not conditional coverage, and a larger gamma adapts faster but makes the interval level jumpier.

Relevance to us: wrap q10/q90 (or the pair of quantile levels) with a per-series, per-horizon alpha_t. For horizon h, err_t is only observable after h days, so update with the delayed outcome. Trade-off: gamma is a tuning parameter that must itself be chosen on origins that are not reused for acceptance.
