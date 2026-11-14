"""Labelled (series, origin, horizon) cells for the decision-model test. Reads rows dated <= 2026-10-13 only.

Features at origin d use rows dated <= d (series history via store.history, panel via panel.offers).
Label for (d, h) is the value at d+h vs the last value at d; it exists only if d+h <= 2026-10-13 and
the series has a row on day d+h. Out: runs/decision/cells.parquet
"""
import json
import numpy as np
import pandas as pd

from gpuf import data, panel, splits
from gpuf.data import starter_common

END = splits._day("2026-10-13")
TRAIN_LAST, TRAIN_TGT, TEST_FIRST, TEST_LAST = (splits._day(s) for s in ("2026-09-14", "2026-09-21", "2026-09-22", "2026-10-06"))
H = (1, 3, 7)
EPS = 1e-6


def ffill_window(days, vals, d, n=15):
    """Values on calendar days d-n+1..d, carried forward from the last row on or before each day."""
    grid = np.arange(d - n + 1, d + 1)
    k = np.searchsorted(days, grid, side="right") - 1
    out = np.where(k >= 0, vals[np.clip(k, 0, None)], np.nan)
    return out


def panel_feats(sid, d):
    if not panel.supported(sid):
        return np.nan, np.nan
    o = panel.offers(sid, d)
    o = o[o["day"] == d]
    if o.empty:
        return np.nan, np.nan
    p = o["price"].to_numpy()
    p25, p50, p75 = np.percentile(p, [25, 50, 75])
    pos = 0.5 if p75 - p25 < 1e-12 else float(np.clip((p50 - p25) / (p75 - p25), 0, 1))
    return float(o["provider"].nunique()), pos


def ord5(r):
    return np.select([r < -0.05, r < -EPS, r <= EPS, r <= 0.05], [0, 1, 2, 3], 4)


def main():
    store, cat = data.load_store(), data.load_catalog().set_index("series_id")
    rows = []
    for sid in data.universe("rental_all"):
        days_all, vals_all = store.history(sid, END)
        if len(days_all) < 3 or not (vals_all > 0).all():
            continue
        m = cat.loc[sid]
        for d in splits.DEV:
            if not (d <= TRAIN_LAST or TEST_FIRST <= d <= TEST_LAST):
                continue
            days, vals = store.history(sid, d)
            if len(days) < 2 or days[-1] != d:
                continue
            w = ffill_window(days, vals, d)
            pct = np.round(100 * (w[1:] / w[:-1] - 1), 2)
            ch = np.nonzero(vals[1:] != vals[:-1])[0]
            dsc = int(d - days[ch[-1] + 1]) if len(ch) else int(d - days[0])
            nprov, pos = panel_feats(sid, d)
            for h in H:
                if d + h > END:
                    continue
                if d <= TRAIN_LAST and d + h > TRAIN_TGT:
                    continue
                y = store.value_at(sid, d + h)
                if y is None:
                    continue
                r = y / vals[-1] - 1
                rows.append(dict(series_id=sid, origin_day=d, horizon_days=h, split="train" if d <= TRAIN_LAST else "test",
                                 collector=m["source_id"], cls=m["instrument_class"], gpu=m["gpu_model"], tier=m["pricing_tier"],
                                 headline=m["tier"] == "headline", last=float(vals[-1]), dsc=min(dsc, 60), n_prov=nprov, pos=pos,
                                 n_hist=len(days), **{f"c{i}": pct[i] for i in range(14)},
                                 ret=r, y3=int(np.sign(r) if abs(r) > EPS else 0) + 1, y5=int(ord5(r))))
    df = pd.DataFrame(rows)
    df.to_parquet("runs/decision/cells.parquet")
    print(len(df), df.groupby("split").size().to_dict())
    for s, g in df.groupby("split"):
        print(s, "y3", g["y3"].value_counts(normalize=True).sort_index().round(3).to_dict(),
              "y5", g["y5"].value_counts(normalize=True).sort_index().round(3).to_dict())
    print(df.groupby(["split", "collector", "horizon_days"])["y3"].agg(
        n="size", down=lambda s: (s == 0).mean(), flat=lambda s: (s == 1).mean(), up=lambda s: (s == 2).mean()).round(3).to_string())
    hl = df[df.headline]
    print("headline", hl.groupby("split")["y3"].value_counts(normalize=True).round(3).to_dict(), len(hl))


if __name__ == "__main__":
    main()
