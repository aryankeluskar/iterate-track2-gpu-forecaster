"""Step 3b: short Laya fine-tune on training-part cells (laya.train.finetune), then score the test subsample.

usage: finetune.py N_TRAIN EPOCHS [freeze]
Train rows: stratified sample of split=="train" (origins <= 2026-09-14, targets <= 2026-09-21).
Test rows: the same test subsample the zero-shot run scored (runs/decision/laya_zs_test.parquet keys).
"""
import json, os, sys, time
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, os.path.dirname(__file__))
from classify import CELLS, K, OUT, questions, state, subsample, run_laya  # noqa: E402

torch.set_num_threads(2)
LAB3 = ("lower", "unchanged", "higher")


def main():
    import laya
    from laya.train import TrainConfig, finetune, resolve_checkpoint_dir
    ntr, epochs = int(sys.argv[1]), int(sys.argv[2])
    freeze = len(sys.argv) > 3 and sys.argv[3] == "freeze"
    df = pd.read_parquet(CELLS)
    tr = subsample(df[df.split == "train"], ntr, 1)
    path = f"{OUT}/ft_train.jsonl"
    with open(path, "w") as f:
        for r in tr.itertuples():
            f.write(json.dumps({"state": state(r), "questions": questions(r.horizon_days),
                                "expected": {"y3": LAB3[r.y3], "y5": int(r.y5)}}) + "\n")
    base = resolve_checkpoint_dir("convaiinnovations/laya")
    out_dir = f"{OUT}/ft_ckpt"
    cfg = TrainConfig(epochs=epochs, micro_batch=8, grad_accum=4, loss="soft-ce", freeze_encoder=freeze,
                      calib_max=400, calib_frac=0.1, head_lr=3e-4 if freeze else 1e-4, log_every=50)
    t = time.time()
    summ = finetune(path, base, out_dir, cfg, device="mps")
    print("finetune", round(time.time() - t, 1), "s", flush=True)
    print(json.dumps({k: v for k, v in summ.items() if not isinstance(v, (list, dict)) or k in ("history",)}, default=str)[:1500])
    agent = laya.load(out_dir, device="mps")
    agent.temperature = [1.0, 1.0, 1.0]; agent.temperature_by_options = {}
    key = ["series_id", "origin_day", "horizon_days"]
    for name in ("train", "test"):
        keys = pd.read_parquet(f"{OUT}/laya_zs_{name}.parquet")[key]
        sub = keys.merge(df, on=key)
        if name == "train":  # temperature fit must not reuse rows the head was trained on
            sub = sub[~sub.set_index(key).index.isin(tr.set_index(key).index)]
        lp = run_laya(sub, agent)
        o = sub[key].copy()
        for yk, k in K.items():
            for j in range(k):
                o[f"{yk}_lp{j}"] = lp[yk][:, j]
        o.to_parquet(f"{OUT}/laya_ft_{name}.parquet")
        print(name, len(o), flush=True)


if __name__ == "__main__":
    main()
