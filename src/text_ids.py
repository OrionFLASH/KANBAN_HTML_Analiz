"""Текстовые идентификаторы для Excel (без потери хвоста длинных чисел)."""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

_EMPTY_TOKENS: frozenset[str] = frozenset({"", "-", "—", "nan", "none", "null", "nat", "<na>"})
_SCI_RE: re.Pattern[str] = re.compile(r"^[+-]?\d+\.?\d*[eE][+-]?\d+$")


def format_id_as_text(value: Any) -> str | None:
    """
    Приводит идентификатор к строке для Excel.

    Длинные числа из Excel/float не должны уходить в scientific notation
    и не должны оставаться float (иначе хвост заменяется нулями).
    """
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        as_int: int = int(value)
        if float(as_int) == value:
            return str(as_int)
        text_f: str = format(value, "f").rstrip("0").rstrip(".")
        return text_f or None
    if isinstance(value, pd.Timestamp):
        return None
    text: str = str(value).strip()
    if not text or text.casefold() in _EMPTY_TOKENS:
        return None
    if _SCI_RE.fullmatch(text):
        try:
            as_float: float = float(text)
            as_int = int(as_float)
            if float(as_int) == as_float:
                return str(as_int)
            return format(as_float, "f").rstrip("0").rstrip(".")
        except (ValueError, OverflowError):
            return text
    if re.fullmatch(r"[+-]?\d+\.0+", text):
        return text.split(".", 1)[0].lstrip("+") or "0"
    return text


def text_id_column_labels(config: dict[str, Any]) -> list[str]:
    """Заголовки Excel-колонок, которые нужно писать как текст."""
    labels: list[str] = []
    seen: set[str] = set()
    snap: dict[str, Any] = dict(config.get("output", {}).get("snapshot_columns") or {})
    columns: dict[str, Any] = dict(config.get("columns") or {})
    # client_id — длинный идентификатор; lead_id тоже лучше текстом
    for key in ("client_id", "lead_id", "deal_id", "inn"):
        label: str | None = None
        if key in snap and snap[key]:
            label = str(snap[key])
        elif key in columns and columns[key]:
            label = str(columns[key])
        if label and label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def format_text_id_columns(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Преобразует известные ID-колонки DataFrame в строки."""
    labels: list[str] = text_id_column_labels(config)
    if frame.empty or not labels:
        return frame
    out: pd.DataFrame = frame.copy()
    for col_name in out.columns:
        if str(col_name) not in labels:
            continue
        out[col_name] = [
            format_id_as_text(value) for value in out[col_name].tolist()
        ]
    return out
