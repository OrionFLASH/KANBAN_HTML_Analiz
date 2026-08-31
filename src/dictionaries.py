"""Построение справочников ТБ, стадий и продуктов."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger: logging.Logger = logging.getLogger("kanban.dictionaries")

_EMPTY_STAGE_VALUES: set[str] = {"", "-", "nan", "None"}


def extract_tb_list(df: pd.DataFrame) -> list[str]:
    """Уникальные значения ТБ."""
    values: list[str] = sorted(df["ТБ"].dropna().astype(str).unique().tolist())
    logger.info("Справочник ТБ: %d записей", len(values))
    return values


def extract_stages(df: pd.DataFrame) -> dict[str, list[str]]:
    """Стадии «Текущий статус» и связанные «Стадия сделки»."""
    stages: dict[str, set[str]] = {}
    for _, row in df[["Текущий статус", "Стадия сделки"]].drop_duplicates().iterrows():
        status: str = str(row["Текущий статус"]).strip()
        deal_stage: str = str(row["Стадия сделки"]).strip()
        if status not in stages:
            stages[status] = set()
        if deal_stage not in _EMPTY_STAGE_VALUES:
            stages[status].add(deal_stage)

    result: dict[str, list[str]] = {k: sorted(v) for k, v in sorted(stages.items())}
    logger.info("Справочник стадий: %d статусов", len(result))
    return result


def extract_products(df: pd.DataFrame) -> list[dict[str, str]]:
    """Уникальные пары группа + продукт."""
    pairs: pd.DataFrame = df[["Группа продукта", "Продукт"]].drop_duplicates()
    products: list[dict[str, str]] = [
        {"group": str(r["Группа продукта"]), "product": str(r["Продукт"])}
        for _, r in pairs.iterrows()
    ]
    logger.info("Справочник продуктов: %d пар", len(products))
    return products


def build_dimensions(df: pd.DataFrame) -> dict[str, Any]:
    """Собирает все справочники для экспорта."""
    return {
        "tb": extract_tb_list(df),
        "stages": extract_stages(df),
        "products": extract_products(df),
    }
