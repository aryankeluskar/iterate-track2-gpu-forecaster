#!/usr/bin/env bash
# Rebuild the series and the Sunday submission (origin 2026-11-06, horizons 1, 3, 7) from the pack.
# Usage: bash reproduce.sh [method, default drift] [params JSON, default {}]
#        bash reproduce.sh final      the submitted forecaster: equal-weight blend of mix, gbm, chronos, analog,
#                                     prov, fm2, fragility (src/gpuf/methods/final.py) for every posted rental series
# Network: none for data. `final` needs the Chronos-Bolt-small weights (amazon/chronos-bolt-small) in the local
# Hugging Face cache (~/.cache/huggingface/hub, or $HF_HOME); the script runs with HF_HUB_OFFLINE=1, so it fails
# rather than downloads if they are missing. To fetch them once on a new machine run, with network:
#   .venv/bin/python -c "from chronos import BaseChronosPipeline as P; P.from_pretrained('amazon/chronos-bolt-small')"
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
METHOD="${1:-drift}"
PARAMS="${2:-}"; [ -n "$PARAMS" ] || PARAMS='{}'
PY="${PYTHON:-$ROOT/.venv/bin/python}"
PACK="$ROOT/data/pack/gpu-price-pack-v0.1.1-handover"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/src"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONHASHSEED=0 TOKENIZERS_PARALLELISM=false
T0=$SECONDS
echo "== 1. pack integrity (MANIFEST.sha256)"
if command -v sha256sum >/dev/null; then (cd "$PACK" && sha256sum -c --quiet MANIFEST.sha256)
else (cd "$PACK" && shasum -a 256 -c MANIFEST.sha256 | { grep -v ': OK$' || true; }) ; fi
echo "== 2. series and catalog as of 2026-11-06 (starter build_series.py --cutoff 2026-11-06)"
rm -rf "$ROOT/runs/series" "$ROOT/runs/submission"
"$PY" -B -c "from gpuf import data; print(*data.build_series(force=True))"
if [ "$METHOD" != "final" ]; then
  echo "== 3. submission for method $METHOD, validated with the starter scorer in frozen-cutoff mode"
  "$PY" -B -m gpuf.submit --method "$METHOD" --params "$PARAMS"
  exit 0
fi
ORIGIN=2026-11-06
echo "== 3. pretrained members (chronos, fm2) for origin $ORIGIN, rental_all, each in its own process"
rm -f "$ROOT"/runs/final/*_"$ORIGIN"_rental_all.parquet
"$PY" -B -m gpuf.final_build --origin "$ORIGIN" --universe rental_all
echo "== 4. final blend for every posted rental series, validated with the starter scorer in frozen-cutoff mode"
# membership and gate fixed on dev by EVAL_PROTOCOL.md Amendment 3 (experiments/final/results/dev.txt): all seven
# members kept; activity gate [14, 1] on non-headline series only
[ "$PARAMS" != '{}' ] || PARAMS="{\"members\": [\"mix\", \"gbm\", \"chronos\", \"analog\", \"prov\", \"fm2\", \"fragility\"], \"gate\": [14, 1], \"gate_scope\": \"nonhead\", \"cap\": \"$ORIGIN\", \"tag\": \"$ORIGIN\", \"universe\": \"rental_all\"}"
mkdir -p "$ROOT/submissions"
ALL="$ROOT/submissions/forecast_final_all.csv"; HEAD="$ROOT/submissions/forecast_final_headline.csv"
"$PY" -B -m gpuf.submit --method final --params "$PARAMS" --universe rental_all --out "$ALL" --headline-out "$HEAD" \
  > "$ROOT/runs/submission/final_validation.json" || true  # the check below prints the result and sets the exit code
"$PY" -B - "$ROOT/runs/submission/final_validation.json" <<'EOF'
import json, sys
v = json.load(open(sys.argv[1]))
for lab, x in (("all", v), ("headline", v["headline"])):
    c = x["scorer_cells"] or {}
    print(f"{lab:<9} {x['path']}\n          rows {x['rows']}  series {x['series']}  zero-width series {x['series_zero_width']}  "
          f"schema problems {x['schema_problems']}  scorer {x['scorer_status']} (exit {x['scorer_exit']}, "
          f"scored cells {c.get('scored')}, refusals {len(x['scorer_refusals'] or [])})  ok {x['ok']}\n          sha256 {x['sha256']}")
print(f"universe {v['universe']} size {v['universe_size']}, without history {v['series_without_history']}, "
      f"filled from baseline {v['filled_from_baseline']}, quantiles clipped {v['quantiles_clipped']}")
print("members per series:", v.get("members_sidecar"))
sys.exit(0 if v["ok"] else 1)
EOF
echo "== done in $((SECONDS - T0))s"
