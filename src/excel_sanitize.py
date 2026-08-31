"""Санитизация данных и имён листов для совместимости с Microsoft Excel."""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

# Символы, запрещённые в именах листов Excel
_INVALID_SHEET_CHARS_RE: re.Pattern[str] = re.compile(r"[\[\]\*\?/\\:]")

# Управляющие символы, недопустимые в XML SpreadsheetML (кроме tab, LF, CR)
_ILLEGAL_XML_CHAR_RE: re.Pattern[str] = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufeff\ufffe\uffff]"
)

# Excel: не более 31 символа в имени листа, не более 32767 символов в ячейке
MAX_SHEET_NAME_LEN: int = 31
MAX_CELL_TEXT_LEN: int = 32767


def sanitize_sheet_name(name: str, used_names: set[str], max_len: int = MAX_SHEET_NAME_LEN) -> str:
    """Приводит имя листа к допустимому виду; при коллизии добавляет суффикс _2, _3…"""
    cleaned: str = _INVALID_SHEET_CHARS_RE.sub(" ", str(name).strip())
    cleaned = cleaned.strip().strip("'")
    if not cleaned:
        cleaned = "Sheet"
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip()

    candidate: str = cleaned
    suffix: int = 2
    while candidate in used_names:
        tail: str = f"_{suffix}"
        base_len: int = max(1, max_len - len(tail))
        candidate = f"{cleaned[:base_len].rstrip()}{tail}"
        suffix += 1

    used_names.add(candidate)
    return candidate


def sanitize_cell_value(value: Any) -> Any:
    """Убирает NaN/Inf и недопустимые XML-символы из значения ячейки."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (int, bool)):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().replace(tzinfo=None)
    text: str = str(value)
    if text in {"nan", "None", "NaT", "<NA>"}:
        return None
    text = _ILLEGAL_XML_CHAR_RE.sub("", text)
    if len(text) > MAX_CELL_TEXT_LEN:
        text = text[:MAX_CELL_TEXT_LEN]
    return text


def sanitize_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Копия DataFrame с безопасными для Excel значениями."""
    if frame.empty:
        return frame.copy()
    out: pd.DataFrame = frame.copy()
    for col_name in out.columns:
        out[col_name] = pd.Series(
            [sanitize_cell_value(value) for value in frame[col_name]],
            dtype=object,
            index=frame.index,
        )
    return out
