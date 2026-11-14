# Conformalized Quantile Regression

Romano, Patterson, Candes, 2019. arXiv 1905.03222. Abstract read from arXiv; formulas read from fetched PDF text (Eq. 9, Theorem 1).

- Fit lower and upper conditional quantile estimators q_lo, q_hi on a proper training split; on a held-out calibration set compute the score E_i = max{ q_lo(X_i) - Y_i, Y_i - q_hi(X_i) } (Eq. 9).
- Let Q be the (1 - alpha)(1 + 1/n_cal) empirical quantile of the scores; the interval is [q_lo(x) - Q, q_hi(x) + Q].
- Theorem 1: if the calibration and test points are exchangeable, P(Y in C(X)) >= 1 - alpha in finite samples, with no distributional assumption. Intervals adapt in width to heteroscedasticity because the base learner is a quantile regressor.
- Guarantee is marginal and needs exchangeability, which fails for time series under drift; that is the gap ACI addresses.

Relevance to us: a one-line recalibration of the q10/q90 pair using the last K calibrated origins (pinball scoring still evaluates q50 separately). For step-like series the score distribution has a point mass at zero, so ties matter (Theorem 1 upper bound needs no ties).
