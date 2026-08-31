"""Применение фильтров из config.json."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.settings import filter_column_name

logger: logging.Logger = logging.getLogger("kanban.filters")


def _text_match_mask(series: pd.Series, flt: dict[str, Any]) -> pd.Series:
    """Маска для contains / contains_all."""
    case: bool = bool(flt.get("case_sensitive", False))
    text: pd.Series = series.astype(str)
    if "contains_all" in flt:
        tokens: list[str] = [str(t) for t in flt["contains_all"] if str(t)]
        if not tokens:
            return pd.Series(True, index=series.index)
        mask: pd.Series = pd.Series(True, index=series.index)
        for token in tokens:
            mask &= text.str.contains(token, case=case, na=False)
        return mask
    if "contains" in flt:
        return text.str.contains(str(flt["contains"]), case=case, na=False)
    raise ValueError("Фильтр не содержит contains или contains_all")


def is_html_slice_filter(flt: dict[str, Any]) -> bool:
    """True — фильтр участвует в комбинациях JSON/HTML (переключатель в UI)."""
    return bool(flt.get("html_slice", True))


def _apply_filter_subset(
    df: pd.DataFrame,
    config: dict[str, Any],
    filters_cfg: dict[str, Any],
    *,
    include_filter: Any,
) -> tuple[pd.DataFrame, list[str]]:
    """Общая логика AND-фильтрации с предикатом include_filter(name, flt)."""
    result: pd.DataFrame = df.copy()
    active: list[str] = []

    for name, flt in filters_cfg.items():
        if not isinstance(flt, dict) or not include_filter(name, flt):
            continue

        column: str | None = filter_column_name(config, flt)
        if not column:
            logger.warning("Фильтр '%s': не задан column_key/column, пропуск", name)
            continue
        if column not in result.columns:
            logger.warning("Колонка фильтра '%s' (%s) не найдена, пропуск", name, column)
            continue

        if "contains" in flt or "contains_all" in flt:
            mask = _text_match_mask(result[column], flt)
        else:
            value = flt.get("value", 1)
            mask = pd.to_numeric(result[column], errors="coerce") == value

        before: int = len(result)
        result = result[mask]
        active.append(name)
        logger.info("Фильтр '%s': %d -> %d строк", name, before, len(result))

    return result.reset_index(drop=True), active


def apply_filters(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Оставляет только строки, прошедшие все включённые фильтры (AND)."""
    filters_cfg: dict[str, Any] = config.get("filters", {})
    result, active = _apply_filter_subset(
        df,
        config,
        filters_cfg,
        include_filter=lambda _name, flt: bool(flt.get("enabled", False)),
    )

    if active:
        logger.info("Применены фильтры (AND): %s", ", ".join(active))
    else:
        logger.info("Фильтры не активны, анализируются все строки")

    return result


def apply_config_only_filters(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """
    Фильтры только из config (html_slice: false), без комбинаций в JSON/UI.
    По умолчанию enabled: false — строки с 0 и 1 не отсекаются.
    """
    filters_cfg: dict[str, Any] = config.get("filters", {})
    result, active = _apply_filter_subset(
        df,
        config,
        filters_cfg,
        include_filter=lambda _name, flt: bool(flt.get("enabled", False))
        and not is_html_slice_filter(flt),
    )

    if active:
        logger.info("Config-only фильтры (AND): %s", ", ".join(active))

    return result
