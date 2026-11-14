# Attribution

## Data pack

Pacific Machines (2026). gpu-price-pack v0.1.1-handover (data cutoff 2026-11-06 23:59:59 UTC; frozen 2026-11-09; cut from the internal freeze v0.1.1 of 2026-11-08): posted rental offers, AWS spot change events, index prints, hardware fundamentals and an MLPerf capability layer, compiled from open sources for the Iterate AI Research Hack, San Francisco, 14 to 15 November 2026. CC BY 4.0 on the compilation.

(Wording from the pack's `DATA.md`, section 10.) The pack is used unchanged and is not redistributed in this repository (`data/` is git-ignored). The pack asks that each upstream be cited with the publisher's wording in its `ATTRIBUTION.md` and the pinned version (DOI, commit sha or file sha256) in `sources_register.csv`, column `pinned_version`.

Changes made by this project: none to the pack. Derived files (series built by the starter's `build_series.py`, offer panels, forecasts, statistics) are computed from it and written outside it.

## Upstream sources used, with the wording required by the pack's ATTRIBUTION.md

Posted rental offers and daily statistics (the forecast targets):

- "Hubbard, A. (2026). GPU Price Tracker dataset. https://github.com/alex-hubbard/gpu_price_tracker (CC BY 4.0)." (pack item 2; source_id afhubbard)
- "GPU rental price data by gpurentalprices.com (https://gpurentalprices.com), licensed under CC BY 4.0." (pack item 3; DOI 10.5281/zenodo.21435394 for the frozen July 2026 copy)
- "Data: FastGPU GPU cloud pricing dataset (https://fastgpu.co/dataset), CC BY 4.0." (pack item 4; archived versions https://doi.org/10.5281/zenodo.22842387)
- Tanod, "Cloud GPU prices and Akash marketplace bids", https://huggingface.co/datasets/tanod/cloud-gpu-list-prices, snapshot as pinned in the pack's `sources_register.csv`. CC BY 4.0 on the compilation. (pack item 5)

Long-run section, analog features and cross-instrument tests:

- "AWS Spot Price History", Eric Pauley (University of Wisconsin-Madison), Zenodo, https://doi.org/10.5281/zenodo.14198917 (version 2026-10: https://doi.org/10.5281/zenodo.23853281), CC BY 4.0. (pack item 1)
- "GetDeploying, GPU rental price history, https://getdeploying.com/gpus, CC BY 4.0". No endorsement implied. (pack item 10)
- "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/): credit Compute Screener (computescreener.com)". (pack item 7)
- GPU Economy, "Cloud GPU Price Index", snapshot as pinned in the register. https://gpueconomy.com/price-index. Concept DOI https://doi.org/10.5281/zenodo.22706541. CC BY 4.0. (pack item 8)
- "henryzhangpku/gpu-price-index (GIX), Copyright (c) 2026 Henry Zhang, MIT License, https://github.com/henryzhangpku/gpu-price-index." With the author's line: "It is a demonstration. Do not settle anything against these values." (pack item 9)
- Epoch AI, 'Data on machine learning hardware'. Published online at epoch.ai. Retrieved from 'https://epoch.ai/data/machine-learning-hardware' [online resource]. CC BY 4.0. (pack items 11 and 16)
- MLCommons Association, MLPerf® Inference v3.0, v3.1, v4.0, v4.1, v5.1, v6.0 and v6.1 results and MLPerf® Training v2.0 to v4.0 results, github.com/mlcommons/inference_results_v<round> and github.com/mlcommons/training_results_v<round> (Apache License 2.0); Result verified by MLCommons Association. The capability units and ladder ratios used here are composites: "Result not verified by MLCommons Association"; they are not official MLPerf® scores. The MLPerf name and logo are registered and unregistered trademarks of MLCommons Association in the United States and other countries. (pack items 15 and 17)

Not used: Epoch AI GPU clusters (pack item 12) and the pack's optional items 13 and 14.

## Sources outside the pack

- US Bureau of Labor Statistics. PPI, electric power distribution, PCU221122221122. data.bls.gov/timeseries/PCU221122221122. Used in the long-run section through September 2026 (the October print was published after the cutoff). Licence: not recorded in this repository.
- Pointer-only publishers quoted in the long-run section follow the pack's rules for them: CCIR is cited as "CCIR (ccir.io)" with the publication date, by quotation only; Silicon Data is cited by headline through a dated news report, with no values stored or recomputed.
- Web pages found through Exa are cited by date, title and link in `FINDINGS.md` (section 6) and `experiments/longrun/results/longrun.md`, and stored in `data_out/repricing_calendar.jsonl` and `data_out/exa_cache/` as short quotes with their URLs. Search used the Exa API (docs.exa.ai) under its terms; price-tracker pages were never opened.

## Pretrained models

| model | used for | licence |
|---|---|---|
| Chronos-Bolt-small, `amazon/chronos-bolt-small` (Ansari et al., Chronos: Learning the Language of Time Series, arXiv:2403.07815) | two members of the submitted blend (Chronos width, fm2) | unknown: the local Hugging Face cache holds only `config.json` and the weights, no model card |
| Chronos-Bolt-base, `amazon/chronos-bolt-base` | experiments only | unknown: no model card in the local cache |
| Chronos-2, `amazon/chronos-2` | experiments only | apache-2.0 (model card in the local cache) |
| TimesFM 2.5, `google/timesfm-2.5-200m-pytorch` (Das et al., arXiv:2310.10688) | experiments only | unknown: no model card in the local cache |
| Laya 0.4.32 (421M parameters, weights loaded by the `laya` package) | experiment H17 only | weights: unknown; Python package `laya`: Apache-2.0 (installed metadata) |

## Libraries

Licences as stated in the installed package metadata in `.venv` (`License-Expression` or `License` field, otherwise the trove classifier).

| package | version | licence (metadata) | role |
|---|---|---|---|
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | submission |
| pandas | 3.1.1 | BSD-3-Clause | submission |
| duckdb | 2.0.0 | MIT License (classifier) | submission |
| pyarrow | 26.0.1 | Apache-2.0 | submission |
| lightgbm | 4.7.0 | MIT | submission (gbm member) |
| torch | 2.15.0 | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause (and further terms in the field) | submission (Chronos members) |
| chronos-forecasting | 2.3.2 | Apache License | submission |
| transformers | 5.23.0 | Apache 2.0 License | dependency of chronos-forecasting |
| huggingface_hub | 2.4.0 | Apache-2.0 | model loading |
| accelerate | 1.15.0 | Apache | dependency |
| safetensors | 0.8.0 | Apache Software License (classifier) | dependency |
| scikit-learn | 1.9.1 | BSD-3-Clause | experiments |
| scipy | 1.18.1 | BSD License (classifier) | experiments |
| matplotlib | 3.11.2 | Python Software Foundation License (classifier); field reads "License agreement for matplotlib versions 1.3.0 and later" | figures |
| timesfm | 3.0.2 | Apache-2.0 | experiments |
| tabpfn | 10.0.0 | Apache-2.0 | experiment H22 (stopped) |
| requests | 2.34.2 | Apache-2.0 | experiments |
| pyyaml | 6.0.3 | MIT | protocols |
| pytest | 9.2.0 | MIT | tests |

The starter kit (`starter/` inside the pack: `build_series.py`, `baselines.py`, `scorer.py`) is Pacific's; the harness imports and calls it from the pack (`src/gpuf/data.py`, `src/gpuf/scoring.py`).

## APIs

- Exa (search and contents), docs.exa.ai, called through `src/gpuf/scout.py`.
- past.dev memory API, https://past.dev/docs/memory-api/overview, called through `src/gpuf/memory.py`.
