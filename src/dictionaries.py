"""Построение справочников ТБ, стадий и продуктов."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.settings import col, empty_stage_values

logger: logging.Logger = logging.getLogger("kanban.dictionaries")


def extract_tb_list(df: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    """Уникальные значения ТБ."""
    tb_col: str = col(config, "tb")
    values: list[str] = sorted(df[tb_col].dropna().astype(str).unique().tolist())
    logger.info("Справочник ТБ: %d записей", len(values))
    return values


def extract_stages(df: pd.DataFrame, config: dict[str, Any]) -> dict[str, list[str]]:
    """Стадии «Текущий статус» и связанные «Стадия сделки»."""
    status_col: str = col(config, "current_status")
    deal_stage_col: str = col(config, "deal_stage")
    empty: set[str] = empty_stage_values(config)

    pairs: pd.DataFrame = df[[status_col, deal_stage_col]].drop_duplicates()
    result: dict[str, list[str]] = {}

    for status in sorted(pairs[status_col].dropna().unique(), key=str):
        status_str: str = str(status).strip()
        substages: pd.Series = pairs.loc[pairs[status_col] == status, deal_stage_col]
        valid: pd.Series = substages.astype(str).str.strip()
        valid = valid[~valid.isin(empty) & ~valid.str.lower().eq("nan")]
        result[status_str] = sorted({str(v) for v in valid.unique() if str(v).strip() not in empty})

    logger.info("Справочник стадий: %d статусов", len(result))
    return result


def extract_products(df: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, str]]:
    """Уникальные пары группа + продукт."""
    group_col: str = col(config, "product_group")
    product_col: str = col(config, "product")
    pairs: pd.DataFrame = df[[group_col, product_col]].drop_duplicates()
    products: list[dict[str, str]] = [
        {"group": str(r[group_col]), "product": str(r[product_col])}
        for r in pairs.to_dict(orient="records")
    ]
    logger.info("Справочник продуктов: %d пар", len(products))
    return products


def extract_filter_dimensions(df: pd.DataFrame, config: dict[str, Any]) -> dict[str, list[str]]:
    """Уникальные значения колонок фильтров в уже отфильтрованных данных."""
    from src.settings import filter_column_name

    result: dict[str, list[str]] = {}
    for name, flt in config.get("filters", {}).items():
        if not isinstance(flt, dict):
            continue
        column: str | None = filter_column_name(config, flt)
        if not column or column not in df.columns:
            continue
        values: list[str] = sorted(df[column].dropna().astype(str).unique().tolist(), key=str)
        result[name] = values
    return result


def build_dimensions(df: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """Собирает все справочники для экспорта."""
    from src.settings import is_group_only_analysis

    dimensions: dict[str, Any] = {
        "tb": extract_tb_list(df, config),
        "stages": extract_stages(df, config),
        "products": extract_products(df, config),
        "product_analysis_mode": config.get("product_analysis_mode", "group_product"),
        "filter_dimensions": extract_filter_dimensions(df, config),
    }
    if is_group_only_analysis(config):
        group_col: str = col(config, "product_group")
        dimensions["product_groups"] = sorted(df[group_col].dropna().astype(str).unique().tolist())
    return dimensions
