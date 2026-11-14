# Chronos: Learning the Language of Time Series

Ansari et al., 2024. arXiv 2403.07815. Read from local LaTeX (sections/*.tex).

- Method: scale the series by mean absolute value, quantize into a vocabulary of 4096 tokens (incl. PAD, EOS), train T5 encoder-decoder with cross entropy; probabilistic forecasts by sampling. Context length 512, prediction length 64.
- Sizes: T5 Mini 20M, Small 46M, Base 200M, Large 710M (plus GPT-2 90M). The smallest model (Mini, 20M) outperforms Moirai-1.0-R Large (311M) on the reported benchmark.
- The authors state a limitation: the range of the quantized vocabulary [c_1, c_B] makes strongly trending series theoretically infeasible. They note larger models are slower than task-specific deep models but comparable to some statistical local models; inference timings were on GPU instances (p3.2xlarge V100 for the compared pretrained baselines). CPU feasibility of the 20M model is not reported in the text I read; at 20M parameters it is plausible but unverified.
- I found no explicit discussion of flat, step-like, or very short series in the sections searched (grep for constant, flat, short, intermittent).

Relevance to us: Chronos-Mini is the plausible zero-shot benchmark arm. Mean scaling with a flat series (mean abs value fine, but zero-variance context) is a failure risk worth a direct test. Sampling gives quantiles natively.
