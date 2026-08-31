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

    stages: dict[str, set[str]] = {}
    for _, row in df[[status_col, deal_stage_col]].drop_duplicates().iterrows():
        status: str = str(row[status_col]).strip()
        deal_stage: str = str(row[deal_stage_col]).strip()
        if status not in stages:
            stages[status] = set()
        if deal_stage not in empty:
            stages[status].add(deal_stage)

    result: dict[str, list[str]] = {k: sorted(v) for k, v in sorted(stages.items())}
    logger.info("Справочник стадий: %d статусов", len(result))
    return result


def extract_products(df: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, str]]:
    """Уникальные пары группа + продукт."""
    group_col: str = col(config, "product_group")
    product_col: str = col(config, "product")
    pairs: pd.DataFrame = df[[group_col, product_col]].drop_duplicates()
    products: list[dict[str, str]] = [
        {"group": str(r[group_col]), "product": str(r[product_col])}
        for _, r in pairs.iterrows()
    ]
    logger.info("Справочник продуктов: %d пар", len(products))
    return products


def build_dimensions(df: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """Собирает все справочники для экспорта."""
    return {
        "tb": extract_tb_list(df, config),
        "stages": extract_stages(df, config),
        "products": extract_products(df, config),
    }
