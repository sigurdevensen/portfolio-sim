"""Strategy registry: exposes constructor parameters to the UI and builds instances."""
from __future__ import annotations

import inspect
from typing import Any

from strategies import BuyAndHold, EqualWeight, MeanReversion, Momentum
from strategies.base import Strategy

STRATEGY_CLASSES: dict[str, type[Strategy]] = {
    cls.name: cls for cls in (BuyAndHold, EqualWeight, Momentum, MeanReversion)
}

_TYPE_NAMES = {int: "int", float: "float", str: "str", bool: "bool"}
_CASTERS = {
    "int": lambda v: int(float(v)),
    "float": float,
    "str": str,
    "bool": lambda v: v if isinstance(v, bool) else str(v).lower() in {"1", "true", "yes", "on"},
}


def strategy_specs() -> list[dict[str, Any]]:
    """Describe every registered strategy: name, description and typed parameters."""
    specs = []
    for name, cls in STRATEGY_CLASSES.items():
        specs.append({
            "name": name,
            "description": (inspect.getdoc(cls) or "").split("\n")[0],
            "params": _params(cls),
        })
    return specs


def build(name: str, params: dict[str, Any] | None = None) -> Strategy:
    """Instantiate a strategy by registry name with type-coerced parameters."""
    cls = STRATEGY_CLASSES.get(name)
    if cls is None:
        raise ValueError(f"Unknown strategy '{name}'. Available: {sorted(STRATEGY_CLASSES)}")
    spec = {p["name"]: p for p in _params(cls)}
    kwargs: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if key not in spec:
            raise ValueError(f"Unknown parameter '{key}' for strategy '{name}'. Expected: {sorted(spec)}")
        caster = _CASTERS.get(spec[key]["type"], lambda v: v)
        try:
            kwargs[key] = caster(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Parameter '{key}' must be {spec[key]['type']}, got {value!r}") from exc
    return cls(**kwargs)


def _params(cls: type[Strategy]) -> list[dict[str, Any]]:
    sig = inspect.signature(cls.__init__)
    out = []
    for pname, param in sig.parameters.items():
        if pname == "self" or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        default = None if param.default is inspect.Parameter.empty else param.default
        annotation = param.annotation
        if isinstance(annotation, str):
            type_name = annotation
        elif annotation in _TYPE_NAMES:
            type_name = _TYPE_NAMES[annotation]
        elif default is not None:
            type_name = _TYPE_NAMES.get(type(default), "str")
        else:
            type_name = "str"
        out.append({"name": pname, "type": type_name, "default": default})
    return out
