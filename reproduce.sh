#!/usr/bin/env bash
# Rebuild the series and the Sunday submission (origin 2026-11-06, horizons 1, 3, 7) from the pack.
# Usage: bash reproduce.sh [method, default drift] [params JSON, default {}]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
METHOD="${1:-drift}"
PARAMS="${2:-}"; [ -n "$PARAMS" ] || PARAMS='{}'
PY="${PYTHON:-$ROOT/.venv/bin/python}"
PACK="$ROOT/data/pack/gpu-price-pack-v0.1.1-handover"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/src"
echo "== 1. pack integrity (MANIFEST.sha256)"
if command -v sha256sum >/dev/null; then (cd "$PACK" && sha256sum -c --quiet MANIFEST.sha256)
else (cd "$PACK" && shasum -a 256 -c MANIFEST.sha256 | { grep -v ': OK$' || true; }) ; fi
echo "== 2. series and catalog as of 2026-11-06 (starter build_series.py --cutoff 2026-11-06)"
rm -rf "$ROOT/runs/series" "$ROOT/runs/submission"
"$PY" -B -c "from gpuf import data; print(*data.build_series(force=True))"
echo "== 3. submission for method $METHOD, validated with the starter scorer in frozen-cutoff mode"
"$PY" -B -m gpuf.submit --method "$METHOD" --params "$PARAMS"
