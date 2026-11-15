"""One dev-only hypothesis. Horizon 1 keeps the blend's q50 and takes drift's relative width.

Fit nothing. The ratio is drift's own interval at that cell, not a tuned constant.
Origins on or after 2026-10-13 are refused by aggregates._load.

Accept only if both halves show all of:
- h=1 mean skill above drift and above the submitted blend
- overall pooled skill no lower than the blend
- overall mean skill no lower than the blend
Otherwise the hypothesis is rejected and final.py stays unchanged.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from aggregates import HALF, _blend, _frame, _load, _losses, _report


def _apply(q: np.ndarray, drift: np.ndarray, horizon: np.ndarray) -> np.ndarray:
    out = q.copy()
    m = np.flatnonzero(horizon == 1)
    d50 = drift[m, 1]
    ok = d50 > 1e-12
    rel_lo = np.ones(len(m))
    rel_hi = np.ones(len(m))
    rel_lo[ok] = drift[m, 0][ok] / d50[ok]
    rel_hi[ok] = drift[m, 2][ok] / d50[ok]
    center = q[m, 1]
    lo = np.minimum(center * rel_lo, center)
    hi = np.maximum(center * rel_hi, center)
    out[m, 0] = np.maximum(lo, 1e-9)
    out[m, 1] = center
    out[m, 2] = hi
    return out


def _one(df: pd.DataFrame, q: np.ndarray, mask: pd.Series) -> dict:
    sub = df.loc[mask].reset_index(drop=True)
    qq = q[mask.to_numpy()]
    loss = _losses(sub["y"].to_numpy(float), qq)
    return _report(_frame(sub, qq, loss))


def main() -> int:
    df = _load()
    q = _blend(df)
    drift = df[["drift_q10", "drift_q50", "drift_q90"]].to_numpy(float)
    alt = _apply(q, drift, df["horizon_days"].to_numpy(int))
    masks = {
        "all": pd.Series(True, index=df.index),
        "first_half": df["origin_day"] < HALF,
        "second_half": df["origin_day"] >= HALF,
        "h1": df["horizon_days"] == 1,
        "h1_first": (df["horizon_days"] == 1) & (df["origin_day"] < HALF),
        "h1_second": (df["horizon_days"] == 1) & (df["origin_day"] >= HALF),
    }
    out = {}
    for name, mask in masks.items():
        out[name] = {"final": _one(df, q, mask), "alt": _one(df, alt, mask), "drift": _one(df, drift, mask)}
        a, f, d = out[name]["alt"], out[name]["final"], out[name]["drift"]
        print(
            f"{name:12} alt mean {a['mean']:.4f} pooled {a['pooled']:.4f} | "
            f"final mean {f['mean']:.4f} pooled {f['pooled']:.4f} | "
            f"drift mean {d['mean']:.4f}"
        )
    accept = True
    reasons = []
    for half in ("first_half", "second_half"):
        if out[half]["alt"]["pooled"] < out[half]["final"]["pooled"] - 1e-4:
            accept = False
            reasons.append(f"{half} pooled fell")
        if out[half]["alt"]["mean"] < out[half]["final"]["mean"] - 1e-4:
            accept = False
            reasons.append(f"{half} mean fell")
    for half in ("h1_first", "h1_second"):
        if out[half]["alt"]["mean"] <= out[half]["drift"]["mean"]:
            accept = False
            reasons.append(f"{half} mean did not beat drift")
        if out[half]["alt"]["mean"] <= out[half]["final"]["mean"]:
            accept = False
            reasons.append(f"{half} mean did not beat final")
    out["accept"] = accept
    out["reasons"] = reasons
    print("ACCEPT" if accept else "REJECT", "; ".join(reasons) or "both halves cleared")
    with open("experiments/hill/width_h1.json", "w") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
