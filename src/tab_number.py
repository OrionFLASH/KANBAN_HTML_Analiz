"""Нормализация табельных номеров для сравнения и вывода в Excel."""

from __future__ import annotations

from typing import Any

import pandas as pd

TAB_NUMBER_WIDTH: int = 8

_EMPTY_TOKENS: frozenset[str] = frozenset({"", "-", "—", "nan", "none", "null", "nat"})


def _extract_digits(value: Any) -> str:
    """Извлекает цифры из значения (в т.ч. float из Excel)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text: str = str(value).strip()
    if text.casefold() in _EMPTY_TOKENS:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            as_float: float = float(value)
            if as_float == int(as_float):
                return str(int(as_float))
        except (ValueError, OverflowError):
            pass
    if "." in text:
        try:
            as_float = float(text.replace(",", "."))
            if as_float == int(as_float):
                return str(int(as_float))
        except ValueError:
            pass
    digits: str = "".join(ch for ch in text if ch.isdigit())
    return digits


def normalize_tab_number(value: Any) -> str:
    """
    Нормативный формат табельного номера:
    - до 8 цифр — 8 знаков с ведущими нулями;
    - более 8 цифр — число без ведущих нулей.
    """
    digits: str = _extract_digits(value)
    if not digits:
        return ""
    canonical: str = digits.lstrip("0") or "0"
    if len(canonical) <= TAB_NUMBER_WIDTH:
        return canonical.zfill(TAB_NUMBER_WIDTH)
    return canonical


def normalize_tab_number_multiline(value: Any) -> str | None:
    """Нормализует табельный номер или многострочный блок TN (через \\n)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text: str = str(value).strip()
    if not text or text.casefold() in _EMPTY_TOKENS:
        return None
    if "\n" not in text:
        normalized: str = normalize_tab_number(text)
        return normalized or None
    lines: list[str] = [normalize_tab_number(part) for part in text.splitlines()]
    cleaned: list[str] = [line for line in lines if line]
    if not cleaned:
        return None
    return "\n".join(cleaned)


def tab_number_column_labels(config: dict[str, Any]) -> list[str]:
    """Заголовки Excel-колонок с табельными номерами из config."""
    labels: list[str] = ["Табельный номер"]
    team_cfg: dict[str, Any] = dict(
        config.get("team_files")
        or config.get("manager_analytics", {}).get("team_files")
        or {}
    )
    out_cols: dict[str, Any] = dict(team_cfg.get("output_columns") or {})
    for block in ("lead", "deal"):
        block_labels: dict[str, Any] = dict(out_cols.get(block) or {})
        tn_label: str = str(block_labels.get("member_tab_number") or "").strip()
        if tn_label and tn_label not in labels:
            labels.append(tn_label)
    return labels


def format_tab_number_columns(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Приводит колонки табельных номеров к нормативному виду перед экспортом."""
    if frame.empty:
        return frame
    target_cols: set[str] = set(tab_number_column_labels(config))
    out: pd.DataFrame = frame.copy()
    for col_name in out.columns:
        if str(col_name) not in target_cols:
            continue
        out[col_name] = out[col_name].map(normalize_tab_number_multiline)
    return out


def normalize_team_tab_column(df: pd.DataFrame, column_name: str) -> pd.DataFrame:
    """Нормализует колонку табельного номера в загруженном файле команды."""
    if df.empty or column_name not in df.columns:
        return df
    out: pd.DataFrame = df.copy()
    out[column_name] = out[column_name].map(normalize_tab_number)
    return out
