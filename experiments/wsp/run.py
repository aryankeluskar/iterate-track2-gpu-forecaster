"""Reproducible WSP experiment. Run from track_2 with PYTHONPATH=src."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from gpuf import compare, data, harness, methods, scoring, splits
from gpuf.methods.wsp import BASE, FEATURES, HIDDEN, Features, adjust, load_weights, qnet, zero_weights

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
WEIGHTS = ROOT / "weights"
SCRATCH = data.ROOT / "runs/wsp"
KEY = compare.KEY
CUTOFF = data.starter_common.day_of(data.starter_common.parse_date("2026-09-11"))
PURGED = CUTOFF + 8


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def append(path, obj):
    with Path(path).open("a") as f:
        f.write(json.dumps(obj, allow_nan=False) + "\n")


def read_log(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines()] if Path(path).exists() else []


def with_outcomes(cells):
    cells = cells.copy()
    r = np.log(cells.y / cells.baseline)
    cells["outcome"] = np.select(
        [r == 0, abs(r) < .01, abs(r) < .05, r > 0],
        ["no_change", "under_1pct", "1_to_5pct", "up_over_5pct"], "down_over_5pct")
    return cells


def metrics(cells):
    out = scoring._pooled(cells)
    for name in ("horizon_days", "outcome", "source_id"):
        out["by_" + name] = {str(k): scoring._pooled(g) for k, g in cells.groupby(name)}
    out["by_outcome_horizon"] = {
        f"{k[0]}_h{k[1]}": scoring._pooled(g)
        for k, g in cells.groupby(["outcome", "horizon_days"])
    }
    return out


def replace_quantiles(cells, q):
    cells = cells.copy()
    for i, (col, tau) in enumerate(zip(("q10", "q50", "q90"), scoring.TAUS)):
        cells[col] = q[:, i]
        cells["loss_" + col] = scoring.pinball(cells.y.to_numpy(), q[:, i], tau)
    cells["loss"] = cells[["loss_q10", "loss_q50", "loss_q90"]].mean(axis=1)
    return cells


def prepare():
    if (SCRATCH / "practice.parquet").exists():
        raise RuntimeError("practice cache already exists")
    features, rows = Features(), {}
    base = methods.get("mix", **BASE)

    def collect(sid, days, vals, origin, horizons, ctx):
        for h in horizons:
            rows[(sid, origin, h)] = features.cell(sid, days, vals, origin, h, ctx)
        return base(sid, days, vals, origin, horizons, ctx)

    origins = [o for o in splits.origins("dev") if o <= CUTOFF]
    result = harness.evaluate(collect, origins)
    cells = with_outcomes(result.cells)
    x = np.stack([rows[tuple(r)] for r in cells[KEY].itertuples(index=False, name=None)])
    cells.to_parquet(SCRATCH / "practice.parquet", index=False)
    np.save(SCRATCH / "practice_features.npy", x)
    np.savez(WEIGHTS / "zero.npz", **zero_weights())
    write_json(RESULTS / "practice_cache.json", {
        "created_at": now(), "origins": ["2026-08-18", "2026-09-11"],
        "features": list(FEATURES), "n_cells": len(cells),
        "cache_sha256": digest(SCRATCH / "practice.parquet"),
        "feature_sha256": digest(SCRATCH / "practice_features.npy"),
        "loss_shares": (cells.groupby("outcome").baseline_loss.sum()
                        / cells.baseline_loss.sum()).to_dict(),
    })
    print(json.dumps({"prepared": len(cells), "features": x.shape[1]}))


def practice():
    return pd.read_parquet(SCRATCH / "practice.parquet"), np.load(SCRATCH / "practice_features.npy")


def score(path, label, ledger="passes.jsonl", budget=40):
    if ledger == "passes.jsonl" and (RESULTS / "freeze.json").exists():
        raise RuntimeError("hand edits frozen; practice tool closed")
    log = RESULTS / ledger
    with (SCRATCH / (ledger + ".lock")).open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        calls = read_log(log)
        if len(calls) >= budget:
            raise RuntimeError(f"budget exhausted: {len(calls)}/{budget}")
        record = {"call": len(calls) + 1, "timestamp": now(), "label": label,
                  "weights": str(Path(path).resolve().relative_to(data.ROOT)),
                  "sha256": digest(path), "budget": budget}
        try:
            cells, x = practice()
            model = load_weights(path)
            q = adjust(cells[["q10", "q50", "q90"]].to_numpy(), qnet(x, model))
            record["metrics"] = metrics(replace_quantiles(cells, q))
        except Exception as exc:
            record["error"] = str(exc)
            append(log, record)
            raise
        append(log, record)
    return record


def concise(record):
    return {"call": record["call"], "label": record["label"],
            "skill": record["metrics"]["pooled_skill"],
            "coverage": record["metrics"]["coverage"],
            "by_h": {h: m["pooled_skill"] for h, m in record["metrics"]["by_horizon_days"].items()}}


def install_rule(parent, patch, variant="candidate"):
    weights = {k: v.copy() for k, v in parent.items()}
    unit = patch["unit"]
    if np.any(weights["w1"][:, unit]) or np.any(weights["w2"][unit]) or weights["b1"][unit]:
        raise ValueError("each rule needs an unused hidden unit")
    read = np.array([patch["read_direction"].get(f, 0.) for f in FEATURES])
    bias = float(patch["bias"])
    write = patch["magnitude"] * np.array(patch["write_direction"])
    if variant == "sign":
        write = -write
    elif variant == "random":
        rng = np.random.default_rng(patch["control_seed"])
        rb = rng.normal(size=len(FEATURES) + 1)
        rb *= np.linalg.norm(np.r_[read, bias]) / np.linalg.norm(rb)
        read, bias = rb[:-1], rb[-1]
        rw = rng.normal(size=3)
        write = rw * np.linalg.norm(write) / np.linalg.norm(rw)
    weights["w1"][:, unit], weights["b1"][unit], weights["w2"][unit] = read, bias, write
    return weights


def apply_rule(path):
    if (RESULTS / "freeze.json").exists():
        raise RuntimeError("frozen")
    patch = json.loads(Path(path).read_text())
    records = read_log(RESULTS / "decisions.jsonl")
    if any(r["name"] == patch["name"] for r in records):
        raise RuntimeError("patch already tested")
    parent_path = WEIGHTS / (records[-1]["incumbent"] if records else "zero.npz")
    parent = load_weights(parent_path)
    previous = records[-1]["incumbent_skill"] if records else read_log(RESULTS / "passes.jsonl")[0]["metrics"]["pooled_skill"]
    model = install_rule(parent, patch)
    path_out = WEIGHTS / f'{patch["name"]}.npz'
    np.savez(path_out, **model)
    result = score(path_out, patch["name"])
    skill = result["metrics"]["pooled_skill"]
    keep = skill > previous
    decision = {"name": patch["name"], "timestamp": now(), "patch_sha256": digest(path),
                "parent": parent_path.name, "parent_sha256": digest(parent_path),
                "candidate": path_out.name, "kept": keep, "practice_gain": skill - previous,
                "practice_skill": skill, "incumbent": path_out.name if keep else parent_path.name,
                "incumbent_skill": skill if keep else previous, "controls": {}}
    if keep:
        for variant in ("sign", "random"):
            ctrl = install_rule(parent, patch, variant)
            delta_norm = lambda w: float(np.sqrt(sum(np.sum((w[k] - parent[k]) ** 2) for k in w)))
            assert np.isclose(delta_norm(ctrl), delta_norm(model), rtol=1e-12)
            ctrlpath = WEIGHTS / f'{patch["name"]}_{variant}.npz'
            np.savez(ctrlpath, **ctrl)
            result_ctrl = score(ctrlpath, patch["name"] + "_" + variant)
            decision["controls"][variant] = {
                "practice_skill": result_ctrl["metrics"]["pooled_skill"],
                "gain": result_ctrl["metrics"]["pooled_skill"] - previous,
                "delta_norm": delta_norm(ctrl), "weights_sha256": digest(ctrlpath)}
    append(RESULTS / "decisions.jsonl", decision)
    print(json.dumps(decision))


def freeze():
    if (RESULTS / "freeze.json").exists():
        raise RuntimeError("already frozen")
    decisions = read_log(RESULTS / "decisions.jsonl")
    incumbent = decisions[-1]["incumbent"]
    np.savez(WEIGHTS / "hand.npz", **load_weights(WEIGHTS / incumbent))
    write_json(RESULTS / "freeze.json", {
        "timestamp": now(), "incumbent": incumbent, "hand_sha256": digest(WEIGHTS / "hand.npz"),
        "passes_sha256": digest(RESULTS / "passes.jsonl"),
        "decisions_sha256": digest(RESULTS / "decisions.jsonl"),
        "protocol_sha256": digest(ROOT / "protocol.yaml"),
        "patch_hashes": {p.name: digest(p) for p in sorted((ROOT / "patches").glob("*.json"))},
        "hand_forward_calls": len(read_log(RESULTS / "passes.jsonl")),
        "kept": [r["candidate"] for r in decisions if r["kept"]],
    })


def train():
    import torch
    torch.set_num_threads(2)
    if not (RESULTS / "freeze.json").exists():
        raise RuntimeError("freeze hand edits before training")
    cells, x = practice()
    early_start = CUTOFF - 6
    fit = (cells.origin_day < early_start) & (cells.target_day < early_start)
    valid = cells.origin_day >= early_start
    tx = torch.tensor(x, dtype=torch.float64)
    base = torch.tensor(np.log(cells[["q10", "q50", "q90"]].to_numpy()), dtype=torch.float64)
    y = torch.tensor(cells.y.to_numpy(), dtype=torch.float64)[:, None]
    taus = torch.tensor([.1, .5, .9], dtype=torch.float64)
    report = {}
    for mode in ("adam_zero", "adam_function_zero"):
        w = zero_weights()
        if mode == "adam_function_zero":
            rng = np.random.default_rng(31415)
            w["w1"] = rng.normal(0, 1 / np.sqrt(len(FEATURES)), w["w1"].shape)
            w["b1"] = rng.normal(0, .1, w["b1"].shape)
        initial = {k: v.copy() for k, v in w.items()}
        p = {k: torch.nn.Parameter(torch.tensor(v, dtype=torch.float64)) for k, v in w.items()}
        optimizer = torch.optim.Adam(list(p.values()), lr=.01)

        def losses():
            out = torch.relu(tx @ p["w1"] + p["b1"]) @ p["w2"] + p["b2"]
            out = torch.maximum(torch.minimum(out, torch.tensor([2., 2., .5])),
                                torch.tensor([-2., -2., -.5]))
            centre = base[:, 1] + out[:, 2] * (base[:, 2] - base[:, 0])
            q = torch.stack((
                torch.exp(centre + (base[:, 0] - base[:, 1]) * torch.exp(out[:, 0])),
                torch.exp(centre),
                torch.exp(centre + (base[:, 2] - base[:, 1]) * torch.exp(out[:, 1])),
            ), dim=1)
            diff = y - q
            return torch.maximum(taus * diff, (taus - 1) * diff).mean(dim=1)

        best, best_epoch, stale, history = float("inf"), 0, 0, []
        best_weights = initial
        for epoch in range(501):
            loss = losses()
            validation = float(loss[valid.to_numpy()].mean().detach())
            training = float(loss[fit.to_numpy()].mean().detach())
            history.append({"epoch": epoch, "fit_loss": training, "early_stop_loss": validation})
            if validation < best - 1e-10:
                best, best_epoch, stale = validation, epoch, 0
                best_weights = {k: v.detach().numpy().copy() for k, v in p.items()}
            else:
                stale += 1
            if epoch == 500 or stale >= 40:
                break
            optimizer.zero_grad()
            loss[fit.to_numpy()].mean().backward()
            optimizer.step()
        np.savez(WEIGHTS / f"{mode}.npz", **best_weights)
        write_json(RESULTS / f"{mode}_training.json", history)
        changed = {k: int(np.count_nonzero(best_weights[k] - initial[k])) for k in w}
        report[mode] = {"best_epoch": best_epoch, "epochs": epoch,
                        "best_early_stop_loss": best, "changed_weights": changed,
                        "n_fit": int(fit.sum()), "n_early_stop": int(valid.sum()),
                        "n_purged": int((~fit & ~valid).sum())}
    write_json(RESULTS / "training.json", report)
    print(json.dumps(report))


def random_search():
    if not (RESULTS / "freeze.json").exists():
        raise RuntimeError("freeze hand edits before random control")
    if (RESULTS / "random_passes.jsonl").exists():
        raise RuntimeError("random search already run")
    rng = np.random.default_rng(2718)
    current = zero_weights()
    cells, _ = practice()
    best = scoring._pooled(cells)["pooled_skill"]
    trajectory = []
    for step in range(1, 51):
        candidate = {k: v.copy() for k, v in current.items()}
        unit = (step - 1) % HIDDEN
        direction = rng.normal(size=len(FEATURES) + 1)
        direction /= np.linalg.norm(direction)
        write = rng.normal(size=3)
        write *= .2 / np.linalg.norm(write)
        candidate["w1"][:, unit] += direction[:-1]
        candidate["b1"][unit] += direction[-1]
        candidate["w2"][unit] += write
        path = WEIGHTS / f"random_step_{step:02d}.npz"
        np.savez(path, **candidate)
        record = score(path, f"random_{step:02d}", "random_passes.jsonl", 50)
        value = record["metrics"]["pooled_skill"]
        kept = value > best
        if kept:
            current, best = candidate, value
        trajectory.append({"step": step, "skill": value, "kept": kept, "incumbent_skill": best})
        if step in (40, 50):
            np.savez(WEIGHTS / f"random{step}.npz", **current)
    write_json(RESULTS / "random_search.json", trajectory)
    print(json.dumps({"random40": trajectory[39], "random50": trajectory[49]}))


def contribution(a, b, field):
    m = a[[*KEY, field, "loss", "baseline_loss"]].merge(
        b[[*KEY, "loss"]], on=KEY, suffixes=("_a", "_b"), validate="one_to_one")
    m["gain"] = m.loss_b - m.loss_a
    grouped = m.groupby(field).agg(n_cells=("gain", "size"), gain=("gain", "sum"))
    grouped["pooled_skill_contribution"] = grouped.gain / m.baseline_loss.sum()
    return grouped.sort_values("gain", ascending=False).to_dict("index")


def final():
    frozen = json.loads((RESULTS / "freeze.json").read_text())
    if digest(WEIGHTS / "hand.npz") != frozen["hand_sha256"]:
        raise RuntimeError("frozen hand weights changed")
    guard = RESULTS / "heldout_started.json"
    with guard.open("x") as f:
        json.dump({"timestamp": now(), "policy": "one final evaluation; never tune afterward"}, f)
    names = {"mix": None, "drift": None, "zero": "zero.npz", "hand": "hand.npz",
             "adam_zero": "adam_zero.npz", "adam_function_zero": "adam_function_zero.npz",
             "random40": "random40.npz", "random50": "random50.npz"}
    for filename in frozen["kept"]:
        if filename != frozen["incumbent"]:
            names["prefix_" + Path(filename).stem] = filename
    all_cells = {}
    for name, filename in names.items():
        params = ({"weights": str(WEIGHTS / filename), "base": BASE} if filename else
                  BASE if name == "mix" else {})
        result = harness.evaluate(methods.get("wsp" if filename else name, **params), "dev",
                                  name="wsp_" + name, params=params)
        all_cells[name] = with_outcomes(result.cells)
        all_cells[name].to_parquet(SCRATCH / f"final_{name}.parquet", index=False)
        print(json.dumps({"evaluated": name, "n_cells": len(result.cells)}), flush=True)
    np.testing.assert_array_equal(all_cells["mix"][["q10", "q50", "q90"]],
                                  all_cells["zero"][["q10", "q50", "q90"]])
    mixq = all_cells["mix"][["q10", "q50", "q90"]].to_numpy()
    handq = all_cells["hand"][["q10", "q50", "q90"]].to_numpy()
    all_cells["blend"] = replace_quantiles(all_cells["mix"], np.exp((np.log(mixq) + np.log(handq)) / 2))
    all_cells["blend"].to_parquet(SCRATCH / "final_blend.parquet", index=False)
    output = {"timestamp": now(), "zero_identity": {
        "max_abs_quantile_difference": 0., "mix_dev_skill": scoring._pooled(all_cells["mix"])["pooled_skill"],
        "zero_dev_skill": scoring._pooled(all_cells["zero"])["pooled_skill"]},
        "nonzero_weights": {n: sum(int(np.count_nonzero(v)) for v in load_weights(WEIGHTS / f).values())
                            for n, f in names.items() if f}}
    for period in ("heldout", "heldout_purged", "dev"):
        selected = {name: c[c.origin_day >= (PURGED if period == "heldout_purged" else CUTOFF + 1)]
                    if period != "dev" else c for name, c in all_cells.items()}
        output[period] = {
            "metrics": {n: metrics(c) for n, c in selected.items()},
            "comparisons": {f"{n}_minus_{bar}": compare.paired(c, selected[bar])
                            for n, c in selected.items()
                            for bar in ("mix", "drift", "adam_function_zero", "adam_zero", "random40")
                            if n != bar and n in ("hand", "blend", "adam_zero", "adam_function_zero",
                                                  "random40", "random50", "mix")},
            "hand_vs_mix_breakdown": {field: contribution(selected["hand"], selected["mix"], field)
                                      for field in ("source_id", "horizon_days", "outcome", "series_id")},
        }
    write_json(RESULTS / "final.json", output)
    print(json.dumps({"heldout": {k: v["pooled_skill"] for k, v in output["heldout"]["metrics"].items()},
                      "zero_identity": output["zero_identity"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "score", "patch", "freeze", "train", "random", "final"])
    parser.add_argument("path", nargs="?")
    parser.add_argument("--label", default="zero")
    args = parser.parse_args()
    if args.command == "score":
        print(json.dumps(score(args.path, args.label)))
    elif args.command == "patch":
        apply_rule(args.path)
    else:
        {"prepare": prepare, "freeze": freeze, "train": train,
         "random": random_search, "final": final}[args.command]()


if __name__ == "__main__":
    main()
