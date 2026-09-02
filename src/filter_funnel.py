# -*- coding: utf-8 -*-
"""Воронка отсечения: фильтры (строки/лиды) и свод по выбросам для листа «Нормативы»."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.outlier_clipping import (
    AUDIT_AFTER,
    AUDIT_BEFORE,
    AUDIT_CLIPPED,
    AUDIT_RULE_PREFIX,
    audit_column_keys,
    enabled_rules,
    outlier_clipping_config,
)
from src.settings import col


def _unique_leads(df: pd.DataFrame, config: dict[str, Any]) -> int:
    """Число уникальных ID ПрПр в кадре (0, если колонки нет)."""
    if df is None or df.empty:
        return 0
    lead_col: str = col(config, "lead_id")
    if lead_col not in df.columns:
        return 0
    series: pd.Series = df[lead_col].dropna().astype(str).str.strip()
    series = series[series != ""]
    return int(series.nunique())


def append_funnel_step(
    funnel: list[dict[str, Any]] | None,
    *,
    stage: str,
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    config: dict[str, Any],
    kind: str = "filter",
) -> None:
    """Добавляет шаг воронки (если funnel не None)."""
    if funnel is None:
        return
    before_rows: int = len(before_df)
    after_rows: int = len(after_df)
    before_leads: int = _unique_leads(before_df, config)
    after_leads: int = _unique_leads(after_df, config)
    funnel.append(
        {
            "stage": stage,
            "kind": kind,
            "before_rows": before_rows,
            "after_rows": after_rows,
            "dropped_rows": max(0, before_rows - after_rows),
            "before_leads": before_leads,
            "after_leads": after_leads,
            "dropped_leads": max(0, before_leads - after_leads),
        }
    )


def build_filter_funnel_frame(funnel: list[dict[str, Any]]) -> pd.DataFrame:
    """Таблица воронки фильтров для Excel."""
    if not funnel:
        return pd.DataFrame(
            columns=[
                "Этап",
                "До (строк)",
                "После (строк)",
                "Отсечено строк",
                "До (лидов)",
                "После (лидов)",
                "Отсечено лидов",
            ]
        )
    rows: list[dict[str, Any]] = []
    for step in funnel:
        rows.append(
            {
                "Этап": step["stage"],
                "До (строк)": step["before_rows"],
                "После (строк)": step["after_rows"],
                "Отсечено строк": step["dropped_rows"],
                "До (лидов)": step["before_leads"],
                "После (лидов)": step["after_leads"],
                "Отсечено лидов": step["dropped_leads"],
            }
        )
    return pd.DataFrame(rows)


def build_outlier_audit_summary(norms_internal: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """
    Свод по выбросам: сумма отсечений по всем группам нормативов.
    norms_internal — кадр до rename (внутренние имена outlier_*).
    """
    cfg: dict[str, Any] = outlier_clipping_config(config)
    if not cfg["enabled"]:
        return pd.DataFrame(
            [
                {
                    "Показатель": "Отсечение выбросов",
                    "Значение": "выключено (outlier_clipping.enabled=false)",
                }
            ]
        )

    keys: list[str] = audit_column_keys(config)
    if not keys or norms_internal.empty:
        return pd.DataFrame(
            [
                {
                    "Показатель": "Отсечение выбросов",
                    "Значение": "включено, но колонок аудита нет",
                }
            ]
        )

    labels: dict[str, str] = dict(config.get("output", {}).get("column_labels") or {})
    rows: list[dict[str, Any]] = []
    n_groups: int = len(norms_internal)
    rows.append({"Показатель": "Групп в нормативах", "Значение": n_groups})

    for key in keys:
        if key not in norms_internal.columns:
            continue
        total: int = int(pd.to_numeric(norms_internal[key], errors="coerce").fillna(0).sum())
        if key == AUDIT_BEFORE:
            title: str = labels.get(key, "До отсечения (сумма по группам)")
        elif key == AUDIT_AFTER:
            title = labels.get(key, "После отсечения (сумма по группам)")
        elif key == AUDIT_CLIPPED:
            title = labels.get(key, "Отсечено выбросами (всего, сумма)")
        elif key.startswith(AUDIT_RULE_PREFIX):
            rule_name: str = key[len(AUDIT_RULE_PREFIX) :]
            title = labels.get(key, f"Отсечено правилом: {rule_name}")
        else:
            title = key
        rows.append({"Показатель": title, "Значение": total})

    # Подсказка: детализация по группам — в колонках основной таблицы
    rule_names: list[str] = [r["name"] for r in enabled_rules(config)]
    if rule_names:
        rows.append(
            {
                "Показатель": "Правила (колонки в таблице ниже)",
                "Значение": ", ".join(rule_names),
            }
        )
    return pd.DataFrame(rows)
