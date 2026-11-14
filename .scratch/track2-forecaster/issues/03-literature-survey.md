# Literature survey

Type: research
Status: resolved
Blocked by: 

## Question

What does prior work say about forecasting sticky, step-like posted prices with quantiles, and about error-controlled acceptance of hypotheses by an automated scientist?

## Answer

Survey in `literature/survey.md`. Acceptance gate: Popper-style e-values, e = 0.5 / sqrt(p) per look, accept when the product reaches 1/alpha, with a fixed budget of looks; Bonferroni as fallback. Short horizons are hard to beat in comparable price benchmarks. No published model for hurdle-type price-change forecasting was found.
