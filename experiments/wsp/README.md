# Reproduce WSP forecasts

Run from `/Users/aryank/Developer/iterate_hackathon/track_2`. Forecasting needs only the existing NumPy/pandas/DuckDB environment, the read-only data pack, the registered method, and the committed NPZ. It makes no model or network calls.

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=src .venv/bin/python -m gpuf.run \
  --method wsp --split dev --universe rental_headline --no-log \
  --params '{"base":{"pool":"cc","k":20,"state":"chgk","sk":3,"hl":30},"weights":"experiments/wsp/weights/hand.npz"}'
```

This reproduces full-dev skill 0.174315. Do not treat a repeat as another independent experiment. Official validation remains reserved for the orchestrator.

Frozen alternatives use the identical method and base parameters, replacing only the weight path:

- `weights/zero.npz`: exact reference mix, full-dev skill 0.169109.
- `weights/adam_zero.npz`: literal all-zero Adam; early stopping selected epoch 0.
- `weights/adam_function_zero.npz`: trainable gradient control with zero initial residual function.
- `weights/random40.npz`: search winner under the 40-call ceiling.
- `weights/random50.npz`: 50-call sensitivity, identical selected arrays to random40.

The equal blend is registered `ens` with:

```json
{"members":[["mix",{"pool":"cc","k":20,"state":"chgk","sk":3,"hl":30}],["wsp",{"base":{"pool":"cc","k":20,"state":"chgk","sk":3,"hl":30},"weights":"experiments/wsp/weights/hand.npz"}]]}
```

The original experiment sequence was:

```sh
# Each command was run with OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=src.
.venv/bin/python experiments/wsp/run.py prepare
.venv/bin/python experiments/wsp/run.py score experiments/wsp/weights/zero.npz
# Invoke "patch" once for each numbered JSON in patches/, in numeric order.
.venv/bin/python experiments/wsp/run.py freeze
.venv/bin/python experiments/wsp/run.py train
.venv/bin/python experiments/wsp/run.py random
.venv/bin/python experiments/wsp/run.py final
```

`score WEIGHTS --label NAME` is the forward-pass tool. It returns pooled skill, horizon/outcome/collector splits, joint outcome-horizon splits, and per-tail coverage. Its lock and append-only ledger enforce the 40-call ceiling. It refuses further hand calls once `results/freeze.json` exists. The checked-in experiment is already frozen; do not erase its logs to rerun selection.

`final` creates an exclusive held-out guard and saves forecasts for every model before aggregation. It refuses to run a second time. `finish` is reporting-only recovery from the existing `runs/wsp/final_*.parquet` files; it makes no predictions. Those parquet caches are git-ignored. The numerical results, pass ledgers, training traces, patches, and every candidate/control weight file are committed.

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=src .venv/bin/python -m pytest tests/test_wsp.py -q
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=src .venv/bin/python experiments/wsp/audit.py
shasum -a 256 -c experiments/wsp/results/hashes.txt
```

The audit's cache-parity and tolerance-coverage checks require the original git-ignored `runs/wsp` caches. The hash check and focused tests do not. `results/hashes.txt` covers all NPZ files, every patch, code, protocol, and numerical result files; paths are relative to `track_2`.

Feature order and fixed scaling are explicit in `src/gpuf/methods/wsp.py`. For base log quantiles `(l10,l50,l90)` and network outputs `(s10,s90,c)`:

```text
new_centre = l50 + c * (l90-l10)
new_q10 = exp(new_centre + exp(s10) * (l10-l50))
new_q50 = exp(new_centre)
new_q90 = exp(new_centre + exp(s90) * (l90-l50))
```

Outputs are clipped to `s10,s90 ∈ [-2,2]`, `c ∈ [-0.5,0.5]`. The hand model has `c=0`; it changes interval shape only. All-zero output returns the base quantiles directly for exact identity. Features use only histories supplied by the origin-truncated context and auxiliary rows filtered at the origin inside the forecaster.

See `REPORT.md` for the result, limitations, initialization correction, budget discrepancy, coverage precision diagnostic, and all hypotheses.
