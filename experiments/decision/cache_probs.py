"""Step 4 cache: LightGBM 3-way probabilities for every rental_headline (series, test origin, horizon).

Fitted once on the training-part cells (origins <= 2026-09-14, targets <= 2026-09-21), so every test
origin (>= 2026-09-22) sees a model built from data dated before it. Features at origin d use rows <= d.
Out: runs/decision/lgbm_probs.parquet (series_id, origin_day, horizon_days, p_down, p_flat, p_up)
"""
import sys, os
import numpy as np
import pandas as pd
import lightgbm as lgb

sys.path.insert(0, os.path.dirname(__file__))
from build import TEST_FIRST, TEST_LAST, ffill_window, panel_feats, H  # noqa: E402
from classify import CELLS, design  # noqa: E402
from gpuf import data, splits  # noqa: E402


def features(sids, origins):
    store, cat = data.load_store(), data.load_catalog().set_index("series_id")
    rows = []
    for sid in sids:
        m = cat.loc[sid]
        for d in origins:
            days, vals = store.history(sid, d)
            if len(days) < 2 or not (vals > 0).all():
                continue
            w = ffill_window(days, vals, d)
            pct = np.round(100 * (w[1:] / w[:-1] - 1), 2)
            ch = np.nonzero(vals[1:] != vals[:-1])[0]
            dsc = int(d - days[ch[-1] + 1]) if len(ch) else int(d - days[0])
            nprov, pos = panel_feats(sid, d) if days[-1] == d else (np.nan, np.nan)
            for h in H:
                rows.append(dict(series_id=sid, origin_day=d, horizon_days=h, collector=m["source_id"], cls=m["instrument_class"],
                                 dsc=min(dsc, 60), n_prov=nprov, pos=pos, **{f"c{i}": pct[i] for i in range(14)}))
    return pd.DataFrame(rows)


def main():
    tr = pd.read_parquet(CELLS).query("split == 'train'")
    Xtr = design(tr)
    g = lgb.LGBMClassifier(objective="multiclass", n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=40,
                           subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, n_jobs=2).fit(Xtr, tr["y3"])
    origins = [d for d in splits.DEV if TEST_FIRST <= d <= TEST_LAST]
    f = features(data.universe("rental_headline"), origins)
    p = g.predict_proba(design(f, Xtr.columns))
    out = f[["series_id", "origin_day", "horizon_days"]].assign(p_down=p[:, 0], p_flat=p[:, 1], p_up=p[:, 2])
    out.to_parquet("runs/decision/lgbm_probs.parquet")
    print(len(out), out[["p_down", "p_flat", "p_up"]].mean().round(3).to_dict())


if __name__ == "__main__":
    main()
