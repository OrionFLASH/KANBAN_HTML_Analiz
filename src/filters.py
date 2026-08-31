"""Применение фильтров из config.json."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.settings import filter_column_name

logger: logging.Logger = logging.getLogger("kanban.filters")


def apply_filters(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Оставляет только строки, прошедшие все включённые фильтры (AND)."""
    result: pd.DataFrame = df.copy()
    filters_cfg: dict[str, Any] = config.get("filters", {})
    active: list[str] = []

    for name, flt in filters_cfg.items():
        if not flt.get("enabled", False):
            continue

        column: str | None = filter_column_name(config, flt)
        if not column:
            logger.warning("Фильтр '%s': не задан column_key/column, пропуск", name)
            continue
        if column not in result.columns:
            logger.warning("Колонка фильтра '%s' (%s) не найдена, пропуск", name, column)
            continue

        if "contains" in flt:
            case: bool = bool(flt.get("case_sensitive", False))
            mask = result[column].astype(str).str.contains(
                flt["contains"], case=case, na=False
            )
        else:
            value = flt.get("value", 1)
            mask = pd.to_numeric(result[column], errors="coerce") == value

        before: int = len(result)
        result = result[mask]
        active.append(name)
        logger.info("Фильтр '%s': %d -> %d строк", name, before, len(result))

    if active:
        logger.info("Применены фильтры (AND): %s", ", ".join(active))
    else:
        logger.info("Фильтры не активны, анализируются все строки")

    return result.reset_index(drop=True)
