# The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery

Lu, Lu, Lange, et al., 2024 (corresponding authors per the local LaTeX). arXiv 2408.06292. Read from local LaTeX (main.tex, limitations section around line 868).

- Loop: idea generation conditioned on an archive of previous ideas with numerical review scores; novelty filter via Semantic Scholar and web search; code via Aider with up to four fix attempts on errors; paper write-up; an LLM reviewer (65 percent vs 66 percent balanced accuracy against humans on ICLR 2022 data); results added to the archive. Cost under 15 USD per paper.
- Memory between iterations: the archive of ideas and their review scores, plus stored copies of all executed experiment files for reproducibility.
- Failure modes reported: ideas very similar across runs and models; Aider fails to implement a significant fraction of ideas; ideas may be implemented incorrectly and the error is hard to catch; limited experiments per idea so conclusions can be deceptive (no control for parameters, FLOPs); mistakes in comparing numbers and failure to account for a changed metric when comparing to baseline; rare hallucination of entire results (an ablation table) and frequent hallucination of unstated facts such as hardware (claimed V100 when H100 used); positive spin on negative results; the LLM judge overestimates novelty, interestingness and feasibility.
- The automated novelty check is self-assessed by each model.

Relevance to us: the observed failures (changed metric not accounted for, wrong implementation, positive spin on losses) are exactly what a fixed protocol with a frozen scoring script and a held-out gate should remove.
