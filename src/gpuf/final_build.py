"""Produce the pretrained members of the `final` blend, each in its own process, for `final` to read back.

LightGBM and torch abort when they share a process on this machine (two OpenMP runtimes), so the torch members
are run here in child processes and written to runs/final/; `final` (which runs gbm in-process) only reads files.

  python -m gpuf.final_build --split dev --universe rental_all
  python -m gpuf.final_build --origin 2026-11-06 --universe rental_all [--force]

Members (file runs/final/<member>_<tag>_<universe>.parquet, tag = "dev" or the origin's ISO date)
  chronos  method `chronos` {"centre": "last"} (Chronos-Bolt-small, default context): the harness forecast
           frame (series_id, origin_day, horizon_days, q10, q50, q90), every series with history, every origin.
  fm2      method `fm2_live` {"ctx_len": 16} (Chronos-Bolt-small, 16 days): the full quantile grid
           (h = 1..7) of every series with >= 8 positive rows, read back with `fm2` {"grids": [...], "lo": 0.15}.

Nothing is scored. Existing files are kept (resumable) unless --force. Weights come from the local
Hugging Face cache (HF_HUB_OFFLINE=1 is set for the children); no data is fetched.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from . import data

OUT = data.ROOT / "runs/final"
MEMBERS = ("chronos", "fm2")
HORIZONS = (1, 3, 7)
MODEL = "amazon/chronos-bolt-small"
ENV = {"OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "PYTHONHASHSEED": "0", "HF_HUB_OFFLINE": "1",
       "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}


def tag_of(split: str | None = None, origin: str | None = None) -> str:
    return split if split else str(origin)


def path(member: str, tag: str, universe: str) -> Path:
    return OUT / f"{member}_{tag}_{universe}.parquet"


def _setup(split, origin):
    """(origin days, store, meta). The Sunday origin reads the history truncated at the cutoff, as gpuf.submit does."""
    from . import harness, splits
    from .data import starter_common
    if split:
        if split != "dev":
            raise ValueError("final_build runs the dev split or a single origin only")
        origins = splits.origins("dev")
        store, cat = data.load_store(data.series_path()), data.load_catalog()
    else:
        o = starter_common.day_of(starter_common.parse_date(origin))
        if splits.touches([o], splits.VAL) and os.environ.get("GPUF_ORCHESTRATOR") != "1":
            raise ValueError("validation origins are run by the orchestrator only (set GPUF_ORCHESTRATOR=1)")
        origins = [o]
        if origin == data.AS_OF:  # exactly the inputs gpuf.submit uses (it checks no row is after the cutoff)
            from .submit import history
            _, hist_cat, store = history()
            cat = data.load_catalog(str(hist_cat))
        else:
            store, cat = data.load_store(data.series_path()), data.load_catalog()
    return origins, store, harness.static_meta(cat)


def worker(member: str, split, origin, universe: str, out: Path) -> None:
    import pandas as pd
    import torch
    torch.set_num_threads(2)
    from . import harness, methods
    origins, store, meta = _setup(split, origin)
    sids = data.universe(universe)
    tmp = out.with_suffix(".tmp.parquet")
    if member == "chronos":
        f = methods.get("chronos", model=MODEL, centre="last")
        fc, _ = harness.forecast(f, origins, sids, HORIZONS, store, meta)
        fc[["series_id", "origin_day", "horizon_days", "q10", "q50", "q90"]].to_parquet(tmp, index=False)
    elif member == "fm2":
        f = methods.get("fm2_live", model=MODEL, ctx_len=16, universe=universe, dump=str(tmp),
                        n_origins=len(origins))
        harness.forecast(f, origins, sids, HORIZONS, store, meta)
        if not tmp.exists():
            raise RuntimeError("fm2_live wrote no grid")
        g = pd.read_parquet(tmp)
        if set(g["origin_day"]) != set(origins):
            raise RuntimeError("fm2 grid lacks origins")
    else:
        raise ValueError(member)
    os.replace(tmp, out)


def build(split=None, origin=None, universe="rental_all", members=MEMBERS, force=False) -> dict:
    if bool(split) == bool(origin):
        raise ValueError("give exactly one of split, origin")
    OUT.mkdir(parents=True, exist_ok=True)
    tag = tag_of(split, origin)
    times = {}
    for m in members:
        p = path(m, tag, universe)
        if p.exists() and not force:
            print(f"[final_build] {m:<8} {p.relative_to(data.ROOT)} exists, skipped", flush=True)
            times[m] = 0.0
            continue
        t0 = time.time()
        cmd = [sys.executable, "-B", "-m", "gpuf.final_build", "--worker", m, "--universe", universe]
        cmd += ["--split", split] if split else ["--origin", origin]
        env = {**os.environ, **ENV, "PYTHONPATH": str(data.ROOT / "src")}
        r = subprocess.run(cmd, env=env, cwd=data.ROOT)
        if r.returncode:
            raise RuntimeError(f"final_build worker {m} failed ({r.returncode})")
        times[m] = round(time.time() - t0, 1)
        print(f"[final_build] {m:<8} {p.relative_to(data.ROOT)} written in {times[m]:.1f}s", flush=True)
    return times


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--split", choices=["dev"])
    g.add_argument("--origin", help="ISO date of a single origin, e.g. 2026-11-06")
    ap.add_argument("--universe", default="rental_all", choices=list(data.UNIVERSES))
    ap.add_argument("--members", default=",".join(MEMBERS))
    ap.add_argument("--force", action="store_true", help="rebuild files that exist")
    ap.add_argument("--worker", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.worker:
        worker(a.worker, a.split, a.origin, a.universe, path(a.worker, tag_of(a.split, a.origin), a.universe))
        return 0
    t0 = time.time()
    build(a.split, a.origin, a.universe, tuple(a.members.split(",")), a.force)
    print(f"[final_build] done in {time.time() - t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
