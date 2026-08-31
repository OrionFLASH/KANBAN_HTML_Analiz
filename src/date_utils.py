"""Устойчивый разбор дат из Excel с разными форматами и пропусками."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger: logging.Logger = logging.getLogger("kanban.date_utils")


def _empty_date_mask(series: pd.Series, empty_values: set[str]) -> pd.Series:
    """Маска пустых / не-дата значений."""
    as_str: pd.Series = series.astype(str).str.strip().str.lower()
    return series.isna() | as_str.isin(empty_values) | (as_str == "")


def parse_date_column(series: pd.Series, config: dict[str, Any], column_label: str) -> pd.Series:
    """
    Преобразует колонку в datetime.
    Поддерживает: уже datetime64, Excel-числа, ISO, dd.mm.yyyy, пустые → NaT.
    """
    dates_cfg: dict[str, Any] = config.get("dates", {})
    empty_values: set[str] = {str(v).lower() for v in dates_cfg.get("empty_values", ["", "-", "nan", "none", "nat"])}

    # Колонка уже datetime (openpyxl) — не интерпретировать как Excel serial days.
    if pd.api.types.is_datetime64_any_dtype(series):
        as_series: pd.Series = pd.Series(series, copy=False)
        result = pd.to_datetime(as_series, errors="coerce")
        empty_mask = _empty_date_mask(as_series, empty_values)
        result = result.mask(empty_mask, pd.NaT)
        nat_count: int = int(result.isna().sum())
        if nat_count > 0:
            logger.debug(
                "Колонка '%s': %d/%d значений без даты (NaT)",
                column_label,
                nat_count,
                len(result),
            )
        return result

    dayfirst: bool = bool(dates_cfg.get("dayfirst", True))
    extra_formats: list[str] = list(dates_cfg.get("formats", []))

    work: pd.Series = series.copy()
    empty_mask = _empty_date_mask(work, empty_values)
    work = work.mask(empty_mask, pd.NA)

    numeric: pd.Series = pd.to_numeric(work, errors="coerce")
    numeric_mask: pd.Series = numeric.notna() & work.notna()
    result = pd.Series(pd.NaT, index=work.index, dtype="datetime64[ns]")

    if numeric_mask.any():
        excel_origin: str = dates_cfg.get("excel_origin", "1899-12-30")
        result.loc[numeric_mask] = pd.to_datetime(
            numeric.loc[numeric_mask],
            unit="D",
            origin=excel_origin,
            errors="coerce",
        )

    text_mask: pd.Series = work.notna() & ~numeric_mask
    if text_mask.any():
        text_values: pd.Series = work.loc[text_mask].astype(str).str.strip()
        parsed: pd.Series = pd.to_datetime(text_values, errors="coerce", dayfirst=dayfirst)
        result.loc[text_mask] = parsed

        still_nat_idx = text_values.index[parsed.isna() & text_values.notna()]
        if len(still_nat_idx) > 0 and extra_formats:
            for fmt in extra_formats:
                if len(still_nat_idx) == 0:
                    break
                attempt: pd.Series = pd.to_datetime(
                    text_values.loc[still_nat_idx],
                    format=fmt,
                    errors="coerce",
                )
                ok: pd.Series = attempt.notna()
                if ok.any():
                    result.loc[still_nat_idx[ok]] = attempt.loc[still_nat_idx[ok]]
                still_nat_idx = text_values.index[result.loc[text_mask].isna() & text_values.notna()]

    nat_count: int = int(result.isna().sum())
    if nat_count > 0:
        logger.debug(
            "Колонка '%s': %d/%d значений без даты (NaT)",
            column_label,
            nat_count,
            len(result),
        )
    return result
