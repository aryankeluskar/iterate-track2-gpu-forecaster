"""Audit frozen artifacts and cached reports without new forecasting queries."""
import json

import numpy as np
import pandas as pd

from run import RESULTS, ROOT, SCRATCH, WEIGHTS, digest, install_rule, read_log, write_json
from gpuf.methods.wsp import load_weights
from gpuf.scoring import _pooled


def main():
    passes = read_log(RESULTS / "passes.jsonl")
    decisions = read_log(RESULTS / "decisions.jsonl")
    freeze = json.loads((RESULTS / "freeze.json").read_text())
    assert len(passes) <= 40
    assert len(passes) == 1 + len(decisions) + 2 * sum(d["kept"] for d in decisions)
    assert digest(RESULTS / "passes.jsonl") == freeze["passes_sha256"]
    assert digest(RESULTS / "decisions.jsonl") == freeze["decisions_sha256"]
    assert digest(ROOT / "protocol.yaml") == freeze["protocol_sha256"]
    for record in passes + read_log(RESULTS / "random_passes.jsonl"):
        assert digest(ROOT.parents[1] / record["weights"]) == record["sha256"]
    checks = {}
    for decision in decisions:
        path = ROOT / "patches" / (decision["name"] + ".json")
        assert digest(path) == decision["patch_sha256"] == freeze["patch_hashes"][path.name]
        patch = json.loads(path.read_text())
        parent = load_weights(WEIGHTS / decision["parent"])
        for variant in ("candidate", "sign", "random"):
            if variant != "candidate" and not decision["kept"]:
                continue
            expected = install_rule(parent, patch, variant)
            filename = decision["name"] + ("" if variant == "candidate" else "_" + variant) + ".npz"
            actual = load_weights(WEIGHTS / filename)
            for key in expected:
                np.testing.assert_array_equal(actual[key], expected[key])
        checks[decision["name"]] = "exact reconstruction"
    frozen = load_weights(WEIGHTS / "hand.npz")
    for key, value in load_weights(WEIGHTS / freeze["incumbent"]).items():
        np.testing.assert_array_equal(value, frozen[key])
    cached_practice = pd.read_parquet(SCRATCH / "practice.parquet")
    cached_mix = pd.read_parquet(SCRATCH / "final_mix.parquet")
    cached_hand = pd.read_parquet(SCRATCH / "final_hand.parquet")
    cutoff = cached_practice.origin_day.max()
    np.testing.assert_array_equal(cached_mix[cached_mix.origin_day <= cutoff][["q10", "q50", "q90"]],
                                  cached_practice[["q10", "q50", "q90"]])
    practice_skill = _pooled(cached_hand[cached_hand.origin_day <= cutoff])["pooled_skill"]
    assert abs(practice_skill - decisions[-1]["incumbent_skill"]) < 1e-12
    coverage = {}
    for name in ("mix", "hand", "blend", "adam_zero", "adam_function_zero", "random40"):
        cells = pd.read_parquet(SCRATCH / f"final_{name}.parquet")
        cells = cells[cells.origin_day > cutoff]
        below = (cells.y < cells.q10) & ~np.isclose(cells.y, cells.q10, rtol=1e-12, atol=1e-12)
        above = (cells.y > cells.q90) & ~np.isclose(cells.y, cells.q90, rtol=1e-12, atol=1e-12)
        coverage[name] = {"below_q10": float(below.mean()), "above_q90": float(above.mean()),
                          "within_q10_q90": float((~(below | above)).mean())}
    write_json(RESULTS / "audit.json", {
        "patch_reconstruction": checks, "practice_cache_registered_method_parity": True,
        "hand_calls": len(passes), "random_calls": len(read_log(RESULTS / "random_passes.jsonl")),
        "heldout_tolerance_coverage": coverage,
        "tolerance_note": "Diagnostic on saved forecasts only; absolute and relative tolerance 1e-12. "
                          "Official strict coverage remains primary. No new held-out forecasts.",
    })
    print("Frozen hashes, all edits/controls, budget and registered-method parity verified.")


if __name__ == "__main__":
    main()
