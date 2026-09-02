"""Санитизация значений перед записью JSON (браузер не парсит NaN/Infinity)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def sanitize_for_json(obj: Any) -> Any:
    """
    Рекурсивно заменяет NaN/±Inf на None и приводит numpy-скаляры к Python.
    Иначе json.dump пишет невалидный для браузера литерал NaN.
    """
    if obj is None:
        return None

    if isinstance(obj, bool):
        return obj

    if isinstance(obj, int) and not isinstance(obj, bool):
        return obj

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    # numpy / pandas скаляры
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            return sanitize_for_json(item())
        except (ValueError, TypeError):
            pass

    if isinstance(obj, dict):
        return {str(key): sanitize_for_json(value) for key, value in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(value) for value in obj]

    return obj


def dump_json_file(path: Path, payload: Any, *, compact: bool = True) -> int:
    """Пишет JSON с allow_nan=False после санитизации. Возвращает размер в байтах."""
    clean: Any = sanitize_for_json(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "ensure_ascii": False,
        "default": str,
        "allow_nan": False,
    }
    if compact:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = 2
    with path.open("w", encoding="utf-8") as fh:
        json.dump(clean, fh, **kwargs)
    return path.stat().st_size
