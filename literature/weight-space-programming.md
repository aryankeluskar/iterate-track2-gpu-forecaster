# Weight-space programming for regression or forecasting models

Searches (WebSearch, standard) found: the MIT CSAIL post "Sparks of Weight-Space Programming" (Takehi, Teoh, Zhang, Khattab, Nov 2 2026) and arXiv 2611.09382 (Hu et al., Nov 6 2026; 16 editing trajectories across seven benchmarks, Qwen3.5-0.8B and 9B; localized edits help, cross-task generalization uneven). Both are about LLM weights, already summarized by the team.

- No work found in which an LLM writes or edits the weights of a regression, tabular, or time-series forecasting model.
- Nothing found on "interpretable weight-space programming (iWSP)", Yash Mehta, Chandan Singh, or a Microsoft Research paper by that name (search returned no matching result). Status: not verified, may be too new to be indexed.
- Reviewers note WSP falls short when the problem is not a localized fault in the weights.

Relevance to us: a forecasting arm built on this would be novel; treat as unvalidated, and keep every edit behind the same held-out gate.
