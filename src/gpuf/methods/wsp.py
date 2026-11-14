"""A small, directly editable residual quantile network around reference mix."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from gpuf.methods import register

BASE = {"pool": "cc", "k": 20, "state": "chgk", "sk": 3, "hl": 30}
FEATURES = (
    "horizon", "age", "changes3", "changes7", "changes14", "vol", "peer_vol",
    "last_sign", "last_size", "providers", "median_position", "panel_spread",
    "fastgpu", "gpurentalprices", "afhubbard", "rate_card", "neocloud_spot",
    "hyperscaler_spot", "marketplace_ask", "history",
)
HIDDEN = 24


def zero_weights():
    return {"w1": np.zeros((len(FEATURES), HIDDEN)), "b1": np.zeros(HIDDEN),
            "w2": np.zeros((HIDDEN, 3)), "b2": np.zeros(3)}


def load_weights(path):
    with np.load(path, allow_pickle=False) as z:
        weights = {key: z[key].astype(float) for key in zero_weights()}
    for key, template in zero_weights().items():
        if weights[key].shape != template.shape or not np.isfinite(weights[key]).all():
            raise ValueError(f"invalid {key} in {path}")
    return weights


def qnet(x, weights):
    h = np.maximum(0, np.asarray(x) @ weights["w1"] + weights["b1"])
    return np.clip(h @ weights["w2"] + weights["b2"], [-2, -2, -.5], [2, 2, .5])


def adjust(base, output):
    base, output = np.asarray(base, float), np.asarray(output, float)
    logq = np.log(base)
    centre = logq[..., 1] + output[..., 2] * (logq[..., 2] - logq[..., 0])
    q = np.stack((
        np.exp(centre + (logq[..., 0] - logq[..., 1]) * np.exp(output[..., 0])),
        np.exp(centre),
        np.exp(centre + (logq[..., 2] - logq[..., 1]) * np.exp(output[..., 1])),
    ), axis=-1)
    # Exact identity, including degenerate intervals and floating-point round trips.
    return np.where(np.all(output == 0, axis=-1)[..., None], base, q)


def ewma_vol(days, vals, origin):
    if len(vals) < 2:
        return 0.
    daily = np.diff(days) == 1
    changes = np.abs(np.diff(np.log(vals)))[daily]
    w = .5 ** ((origin - days[1:][daily]) / 7.)
    return float(w @ changes / w.sum()) if len(w) else 0.


class Features:
    def __init__(self, panel_path=None):
        from gpuf.data import PACK
        self.panel_path = str(panel_path or PACK / "daily_statistics.csv")
        self.origin = None
        self.panels = {}
        self.peers = {}

    def prepare(self, ctx, origin):
        if self.origin == origin:
            return
        import duckdb
        from gpuf.data import starter_common
        # Filter in the reader, before returning any data to the forecaster.
        with duckdb.connect(config={"threads": 2}) as con:
            rows = con.execute("""
                SELECT source_id, instrument_class, gpu_model, pricing_tier,
                       n_providers, median_usd_per_gpu_hour, p25_usd_per_gpu_hour,
                       p75_usd_per_gpu_hour
                FROM read_csv_auto(?)
                WHERE CAST(date AS DATE) <= CAST(? AS DATE)
                QUALIFY row_number() OVER (
                    PARTITION BY source_id, instrument_class, gpu_model, pricing_tier
                    ORDER BY CAST(date AS DATE) DESC) = 1
            """, [self.panel_path, starter_common.iso(origin)]).fetchall()
        self.panels = {(r[0], r[1], r[2], r[3]): r[4:] for r in rows}
        groups = {}
        for sid in ctx.ids():
            meta = ctx.meta(sid)
            if meta.get("table") != "daily_statistics":
                continue
            group = (meta.get("source_id"), meta.get("instrument_class"))
            groups.setdefault(group, []).append((sid, ewma_vol(*ctx.history(sid), origin)))
        self.peers = groups
        self.origin = origin

    def cell(self, sid, days, vals, origin, horizon, ctx):
        self.prepare(ctx, origin)
        meta = ctx.meta(sid)
        collector, cls = meta.get("source_id"), meta.get("instrument_class")
        moves = np.diff(np.log(vals))
        changed = np.flatnonzero(moves != 0)
        change_days = days[1:][changed]
        age = origin - change_days[-1] if len(changed) else origin - days[0]
        last = moves[changed[-1]] if len(changed) else 0.
        peer = [v for s, v in self.peers.get((collector, cls), []) if s != sid]
        panel = self.panels.get((collector, cls, meta.get("gpu_model"), meta.get("pricing_tier")))
        providers, position, spread = 0., 0., 0.
        if panel is not None:
            n, median, p25, p75 = (float(v or 0) for v in panel)
            providers = n / 20.
            if p75 > p25 > 0:
                position = 2 * (median - p25) / (p75 - p25) - 1
                spread = np.log(p75 / p25)
        x = [
            horizon / 7., min(age / 14., 2.),
            *[np.sum(change_days > origin - k) / k for k in (3, 7, 14)],
            min(ewma_vol(days, vals, origin) / .05, 4.),
            min(float(np.mean(peer)) / .05, 4.) if peer else 0.,
            np.sign(last), min(abs(last) / .1, 4.), providers,
            float(np.clip(position, -1, 1)), min(spread, 4.),
            *[float(collector == c) for c in ("fastgpu_daily", "gpurentalprices", "afhubbard")],
            *[float(cls == c) for c in ("neocloud_rate_card", "neocloud_spot",
                                       "hyperscaler_spot", "marketplace_ask")],
            min((origin - days[0] + 1) / 30., 2.),
        ]
        return np.asarray(x, float)


@register("wsp")
def make(base=None, weights=None):
    from gpuf.methods import get
    if weights is None:
        raise ValueError("wsp requires a frozen weights .npz path")
    params = BASE if base is None else base
    model = load_weights(Path(weights))
    base_method = get("mix", **params)
    features = Features()

    def forecast(sid, days, vals, origin_day, horizons, ctx):
        q = base_method(sid, days, vals, origin_day, horizons, ctx)
        if not any(np.any(v) for v in model.values()):
            return q
        return {h: tuple(adjust(q[h], qnet(features.cell(
            sid, days, vals, origin_day, h, ctx), model))) for h in horizons}

    return forecast
