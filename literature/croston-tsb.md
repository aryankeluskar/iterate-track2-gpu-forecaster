# Intermittent demand: Croston (1972) and TSB (Teunter, Syntetos, Babai 2011)

Teunter, Syntetos, Babai, "Intermittent demand: Linking forecasting to inventory obsolescence", European Journal of Operational Research 214(3): 606-615, 2011. Evidence from search-result snippets (EconPapers, Cardiff ORCA, a metricgate.com explainer, and a 2025 arXiv preprint listing); the paper text itself was not opened.

- Croston forecasts non-zero demand size and inter-demand interval separately and divides; it updates only in periods with demand, so it does not decay during long runs of zeros.
- TSB replaces the interval with a demand-occurrence probability p_t that is updated every period (toward 1 on demand, toward 0 otherwise); size is updated only when demand occurs; forecast f_t = p_t * y_t.
- Both Croston and TSB are point forecasts. Probabilistic counterparts exist (Hyndman et al. 2008; Snyder et al. 2012); common predictive distributions are negative binomial, empirical, or a hierarchical Bayesian Beta-Binomial occurrence with Log-Normal size (a preprint, unreviewed). No source found on hurdle or zero-inflated models for price changes specifically.

Relevance to us: the TSB decomposition (probability of a change, times a size) is the right template for step series: update P(change) every day, and draw the size from the empirical distribution of non-zero increments.
