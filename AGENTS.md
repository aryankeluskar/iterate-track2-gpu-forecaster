# Track 2: GPU price forecaster (Iterate hackathon, Pacific)

Resume from `research-state.yaml`, then `research-log.md` (authoritative, includes corrections) and `EVAL_PROTOCOL.md`.

## Commands (run from this folder)
- Rebuild the submission: `bash reproduce.sh final` (about 25 s; writes `submissions/forecast_final_*.csv`)
- Score a method on the practice dates: `PYTHONPATH=src .venv/bin/python -m gpuf.run --method NAME --split dev --universe rental_headline --params '{...}' [--no-log]`
- Practice-date gate against the reference model: `PYTHONPATH=src .venv/bin/python experiments/halves.py SPEC.json`
- Ideas tried, with verdicts: `PYTHONPATH=src .venv/bin/python -m gpuf.ledger`
- Research loop steps: `PYTHONPATH=src .venv/bin/python -m gpuf.loop status` (set `LOOP_OFFLINE=1 PAST_OFFLINE=1` to stay off the network)
- Progress page: `PYTHONPATH=src .venv/bin/python experiments/report.py`; demo page: `PYTHONPATH=src .venv/bin/python -m gpuf.demo`
- Tests: `OMP_NUM_THREADS=2 PYTHONPATH=src .venv/bin/python -m pytest tests -q`
- Packages: `uv pip install --python .venv/bin/python <pkg>`. Shell is zsh: call `.venv/bin/python` directly.

## Rules
- A forecast for a date may use only rows dated on or before it. Any method that reads a table directly needs a test that deletes and corrupts later rows.
- The held-back weeks (13 to 30 October, split `val`) are run by the orchestrator only, one declared query at a time, committed before running. Never tune on them.
- Never fetch price data from the network. Web searches set an end published date on or before 2026-11-06; undated results are discarded; live price-tracker pages are never opened.
- Never print or commit API keys (they are in `../.env`). `data/`, `runs/`, `.venv/` are git-ignored.
- LightGBM and torch cannot share a process here: pretrained members are built separately (`python -m gpuf.final_build`).
- Keep `OMP_NUM_THREADS=2` and each process under 3 GB; the machine has 24 GB.
- Documents in `to_human/` are written in plain language for the team.
