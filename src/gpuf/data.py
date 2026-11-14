"""Series and catalog as of 2026-11-06, built once with the starter's build_series.py.

History semantics (gaps, AWS carry-forward days, staleness) come from the starter's own
SeriesStore, so they are identical to the official baselines and scorer.
"""
from __future__ import annotations

import functools
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # importing the starter must never write __pycache__ into the hash-verified pack

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "data/pack/gpu-price-pack-v0.1.1-handover"
STARTER = PACK / "starter"
AS_OF = "2026-11-06"
SERIES_DIR = ROOT / "runs/series"
DATA_OUT = ROOT / "data_out"

if str(STARTER) not in sys.path:
    sys.path.insert(0, str(STARTER))
import _common as starter_common  # noqa: E402
import baselines as starter_baselines  # noqa: E402
import scorer as starter_scorer  # noqa: E402

import pandas as pd  # noqa: E402

SeriesStore = starter_common.SeriesStore
UNIVERSES = ("rental_headline", "rental_all")


def run_starter(script: str, *args) -> subprocess.CompletedProcess:
    """Run a starter script the way run_demo.sh does (python -I -B)."""
    cmd = [sys.executable, "-I", "-B", str(STARTER / script), *map(str, args)]
    return subprocess.run(cmd, capture_output=True, text=True)


def build_series(cutoff: str = AS_OF, out_dir: Path = SERIES_DIR, members_from: Path | None = None,
                 force: bool = False) -> tuple[Path, Path]:
    """series_daily.csv + series_catalog.csv truncated at `cutoff` (catalog as_of = cutoff). Cached."""
    out_dir = Path(out_dir)
    series, catalog = out_dir / "series_daily.csv", out_dir / "series_catalog.csv"
    cached = series.exists() and catalog.exists() and \
        pd.read_csv(catalog, dtype=str, nrows=1)["as_of"].iloc[0] == cutoff
    if force or not cached:
        out_dir.mkdir(parents=True, exist_ok=True)
        args = ["--pack", PACK, "--cutoff", cutoff, "--out", series, "--catalog", catalog,
                "--report", out_dir / "build_series_report.json", "--tmp-dir", out_dir / "_duck_tmp"]
        if members_from:
            args += ["--members-from", members_from]
        r = run_starter("build_series.py", *args)
        if r.returncode:
            raise RuntimeError(f"build_series.py failed ({r.returncode}): {r.stderr}")
    return series, catalog


@functools.lru_cache(maxsize=4)
def load_store(series_path: str | None = None) -> SeriesStore:
    path = series_path or str(build_series()[0])
    return SeriesStore(starter_common.read_series_csv(path))


@functools.lru_cache(maxsize=4)
def load_catalog(catalog_path: str | None = None) -> pd.DataFrame:
    path = catalog_path or str(build_series()[1])
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def series_path() -> str:
    return str(build_series()[0])


def catalog_ids(catalog: pd.DataFrame, tier: str = "headline", table: str | None = None) -> list[str]:
    """Series ids of an arbitrary catalog, in catalog order (tier 'all' keeps every tier)."""
    c = catalog if table is None else catalog[catalog["table"] == table]
    if tier != "all":
        c = c[c["tier"] == tier]
    return c["series_id"].tolist()


def universe(name_or_ids, catalog: pd.DataFrame | None = None) -> list[str]:
    """Protocol universes (catalog as of 2026-11-06): rental_headline = daily_statistics x headline tier,
    rental_all = daily_statistics x every tier. A list of ids passes through unchanged."""
    if not isinstance(name_or_ids, str):
        return list(name_or_ids)
    cat = load_catalog() if catalog is None else catalog
    if name_or_ids == "rental_headline":
        return catalog_ids(cat, "headline", "daily_statistics")
    if name_or_ids == "rental_all":
        return catalog_ids(cat, "all", "daily_statistics")
    raise ValueError(f"unknown universe {name_or_ids!r}; choose from {UNIVERSES} or pass a list of ids")
