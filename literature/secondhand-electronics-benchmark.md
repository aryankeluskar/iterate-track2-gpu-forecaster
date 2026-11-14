# Deep Learning vs. Statistical Models for Multi-Horizon Price Forecasting of Second-Hand Electronics

Buczynski, Wozniak, Kaczynski, Wroblewska, Kuk (local LaTeX). arXiv 2610.10727. Read from local LaTeX (abstract, results around lines 865-1175).

- Setup: daily listings from Polish marketplaces, Jan 2022 to Mar 2025, 100+ smartphone and laptop models; 11 models (ARIMA, ETS, Theta, LSTM, TCN, N-BEATS, N-HiTS, TFT, PatchTST, Informer, plus a naive baseline); horizons 1 to 365 days; MAPE primary.
- Short horizons (1 to 7 days): all models converge near 0.72 percent MAPE (naive h=1 MAPE 0.0072) and the naive baseline remains competitive; differences are marginal.
- Long horizons: N-BEATS wins beyond 30 days, 8.51 percent MAPE at 365 days versus 14.94 percent for the best statistical baseline (43 percent reduction). LSTM and TCN degrade sharply beyond 90 days; PatchTST MAPE grows from 0.0556 at h=30 to 0.3023 at h=365; naive is comparable to most ML models at 365 days.
- N-BEATS and N-HiTS show the best hyperparameter stability; a single N-BEATS model trained for 365 days generalizes to shorter horizons.
- Point forecasts and MAPE; no pinball/quantile scoring of intervals in what I read (distributional scores appear in tables but I did not verify which).

Relevance to us: deep models did not beat naive at 1 to 7 days, which is our horizon range. Expect the last-value or drift baseline to be very hard to beat on short-horizon daily medians.
