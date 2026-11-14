# Approaching Human-Level Forecasting with Language Models

Halawi, Zhang, et al., 2024. arXiv 2402.18563. Read from local LaTeX (sec/abstract.tex, sec/evaluations.tex, tables/one_table_ablation.tex).

- Retrieval-augmented LM system with fine-tuned reasoning; evaluated on questions after the model knowledge cutoff. Full system Brier .179 versus crowd aggregate .146 (accuracy 71.5 versus 77.8 percent): it nears but does not beat the crowd on average.
- Retrieval ablation: base GPT-4 with retrieval .186, base GPT-4 without retrieval .206 (accuracy 66.6 percent); retrieval is worth about .02 Brier.
- Performance depends on how many relevant articles are retrieved: with at least 5 articles the system Brier is .175 (crowd .143); the system beats the crowd only when the crowd is uncertain, at earlier retrieval dates, and when many articles are retrieved. It hedges even as evidence becomes decisive.
- Averaging with the crowd improves on the crowd in some settings (aggregate rows in the ablation table).

Relevance to us: news retrieval buys modest gains and only when evidence is plentiful; our target (posted GPU prices) has sparse news. Expect LLM-driven hypotheses to add little without a leak-free numeric test, which is exactly what the gate is for.
