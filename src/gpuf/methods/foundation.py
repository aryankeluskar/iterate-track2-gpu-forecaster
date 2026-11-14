"""foundation: zero-shot pretrained time-series models. Context = the series' own history up to the origin on a
daily grid (gaps carried forward). No fitting. Weights come from Hugging Face; no price data is fetched.

params: model (HF id), centre "model" | "last", log (forecast log price), ctx_len
"""
from __future__ import annotations

import numpy as np

from gpuf.methods import register

_PIPE = {}


def _grid(days, vals, ctx_len):
    full = np.arange(days[0], days[-1] + 1)
    idx = np.searchsorted(days, full, side="right") - 1
    return vals[idx][-ctx_len:]


@register("chronos")
def make(model="amazon/chronos-bolt-small", centre="model", log=False, ctx_len=512):
    import torch
    from chronos import BaseChronosPipeline
    if model not in _PIPE:
        _PIPE[model] = BaseChronosPipeline.from_pretrained(model, device_map="cpu")
    pipe = _PIPE[model]
    cache = {}

    def f(sid, days, vals, origin_day, horizons, ctx):
        last = float(vals[-1])
        if len(vals) < 8:
            return {h: (last, last, last) for h in horizons}
        x = _grid(days, vals, ctx_len)
        if log:
            x = np.log(x)
        H = max(horizons)
        q, _ = pipe.predict_quantiles(torch.tensor(x, dtype=torch.float32), prediction_length=H,
                                      quantile_levels=[0.1, 0.5, 0.9])
        q = q[0].numpy()
        out = {}
        for h in horizons:
            a, b, c = (float(v) for v in q[h - 1])
            if log:
                a, b, c = np.exp(a), np.exp(b), np.exp(c)
            if centre == "last":
                a, b, c = last + (a - b), last, last + (c - b)
            out[h] = (a, b, c)
        return out

    return f


@register("timesfm")
def make_timesfm(model="google/timesfm-2.5-200m-pytorch", centre="model", ctx_len=512):
    import timesfm
    if model not in _PIPE:
        m = timesfm.TimesFM_2p5_200M_torch.from_pretrained(model)
        m.compile(timesfm.ForecastConfig(max_context=ctx_len, max_horizon=32, normalize_inputs=True,
                                         use_continuous_quantile_head=True, force_flip_invariance=True,
                                         infer_is_positive=True, fix_quantile_crossing=True))
        _PIPE[model] = m
    tfm = _PIPE[model]

    def f(sid, days, vals, origin_day, horizons, ctx):
        last = float(vals[-1])
        if len(vals) < 8:
            return {h: (last, last, last) for h in horizons}
        x = _grid(days, vals, ctx_len).astype(np.float32)
        _, q = tfm.forecast(horizon=max(horizons), inputs=[x])
        q = np.asarray(q)[0]  # (H, 10): mean, q10 .. q90
        out = {}
        for h in horizons:
            a, b, c = float(q[h - 1, 1]), float(q[h - 1, 5]), float(q[h - 1, 9])
            if centre == "last":
                a, b, c = last + (a - b), last, last + (c - b)
            out[h] = (a, b, c)
        return out

    return f
