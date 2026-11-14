# A decoder-only foundation model for time-series forecasting (TimesFM)

Das et al., 2024 (first author Abhimanyu Das per the local LaTeX). arXiv 2310.10688. Read from local LaTeX (foundation_ts.tex).

- Decoder-only patched transformer; about 200M parameters, pretraining on O(100B) time points; scaling study with 17M, 70M and 200M models. Maximum context 512 (256 for weekly, 64 for monthly or coarser during training).
- Output patches are longer than input patches (example: input 32, output 128) to reduce autoregressive steps; a synthetic-data ablation shows the real data lacks coverage of patterns.
- The base model outputs point forecasts; the paper says probabilistic output is easy by adding quantile-loss heads, i.e. not the released default.
- Zero-shot accuracy approaches supervised SOTA on Monash, Darts and ETT-style benchmarks. No text found on flat or step-like series.

Relevance to us: 200M parameters is heavier than Chronos-Mini; point forecast only means q10/q90 would need conformal wrapping (CQR/ACI).
