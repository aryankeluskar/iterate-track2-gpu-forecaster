"""Method registry. Add a module in this package that does

    from gpuf.methods import register

    @register("my_method")
    def make(**params):
        def f(sid, days, vals, origin_day, horizons, ctx):
            return {h: (q10, q50, q90) for h in horizons}
        return f

Every module in the package is imported on first use, so the name becomes available to
`python -m gpuf.run --method my_method --params '{"k": 3}'`.
"""
from __future__ import annotations

import importlib
import pkgutil

REGISTRY: dict = {}
_loaded = False


def register(name: str):
    def deco(factory):
        if name in REGISTRY:
            raise ValueError(f"method {name!r} registered twice")
        REGISTRY[name] = factory
        return factory
    return deco


def _load_all() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    for m in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{m.name}")


def get(name: str, **params):
    _load_all()
    if name not in REGISTRY:
        raise KeyError(f"unknown method {name!r}; registered: {sorted(REGISTRY)}")
    f = REGISTRY[name](**params)
    f.__name__ = name
    return f


def names() -> list[str]:
    _load_all()
    return sorted(REGISTRY)


@register("drift")
def _drift(min_samples: int = 20, lookback_days: int | None = None):
    from gpuf.baselines import starter_method
    return starter_method("drift", min_samples, lookback_days)


@register("last_value")
def _last_value():
    from gpuf.baselines import starter_method
    return starter_method("last_value")
