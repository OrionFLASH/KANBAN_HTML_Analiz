"""Трекинг стадий лидов и расчёт сроков нахождения."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger: logging.Logger = logging.getLogger("kanban.lead_tracker")

_EMPTY_STAGE_VALUES: set[str] = {"", "-", "nan", "None", "None"}


def _is_empty_stage(value: object) -> bool:
    """Проверяет, что подстадия пустая."""
    text: str = str(value).strip()
    return text in _EMPTY_STAGE_VALUES or text.lower() == "nan"


def _prepare_duration_columns(df: pd.DataFrame, duration_source: str) -> pd.DataFrame:
    """Добавляет колонки сроков по колонкам отчёта и по датам."""
    result: pd.DataFrame = df.copy()

    result["_days_col"] = pd.to_numeric(
        result["Количество дней на текущей стадии"], errors="coerce"
    )
    result["_days_since_deal_col"] = pd.to_numeric(
        result["Количество дней с создания сделки"], errors="coerce"
    )

    start_ref: pd.Series = result["Дата начала работы"]
    deal_ref: pd.Series = result["Дата создания сделки"].fillna(start_ref)
    has_deal_stage: pd.Series = ~result["Стадия сделки"].apply(_is_empty_stage)

    result["_days_dates"] = (result["Дата отчета"] - start_ref).dt.days
    result.loc[has_deal_stage, "_days_dates"] = (
        result.loc[has_deal_stage, "Дата отчета"] - deal_ref.loc[has_deal_stage]
    ).dt.days

    result["_days_since_deal_dates"] = (
        result["Дата отчета"] - result["Дата создания сделки"]
    ).dt.days

    if duration_source == "columns":
        result["days_on_stage"] = result["_days_col"]
        result["days_since_deal"] = result["_days_since_deal_col"]
    else:
        result["days_on_stage"] = result["_days_dates"]
        result["days_since_deal"] = result["_days_since_deal_dates"]

    return result


def _deduplicate_same_date(group: pd.DataFrame) -> pd.DataFrame:
    """На одну дату отчёта и стадию — максимальное число дней."""
    agg_map: dict[str, str] = {
        "days_on_stage": "max",
        "days_since_deal": "max",
        "Группа продукта": "first",
        "Продукт": "first",
        "ТБ": "first",
        "Текущий статус": "first",
        "Стадия сделки": "first",
    }
    present: dict[str, str] = {k: v for k, v in agg_map.items() if k in group.columns}
    return group.groupby("Дата отчета", as_index=False).agg(present)


def _pick_best_across_dates(group: pd.DataFrame) -> pd.Series:
    """Выбирает запись с максимальным сроком; при равенстве — более поздняя дата отчёта."""
    max_days: float = group["days_on_stage"].max()
    candidates: pd.DataFrame = group[group["days_on_stage"] == max_days]
    row: pd.Series = candidates.sort_values("Дата отчета").iloc[-1]
    return row


def _build_level_records(
    df: pd.DataFrame,
    level_name: str,
    stage_col: str,
) -> pd.DataFrame:
    """Строит записи лид × стадия для одного уровня анализа."""
    work: pd.DataFrame = df.copy()
    if level_name == "substage":
        work = work[~work[stage_col].apply(_is_empty_stage)]
        key_cols: list[str] = ["ID ПрПр", "Группа продукта", "Продукт", "ТБ", stage_col]
        stage_label_col: str = stage_col
        status_col: str = "Стадия сделки"
    else:
        key_cols = ["ID ПрПр", "Группа продукта", "Продукт", "ТБ", "Текущий статус"]
        stage_label_col = "Текущий статус"
        status_col = "Текущий статус"

    if work.empty:
        return pd.DataFrame()

    records: list[pd.Series] = []
    grouped = work.groupby(key_cols, dropna=False)
    for _, group in grouped:
        deduped: pd.DataFrame = _deduplicate_same_date(group)
        best: pd.Series = _pick_best_across_dates(deduped)
        best = best.copy()
        best["analysis_level"] = level_name
        best["stage_key"] = best[stage_label_col]
        best["current_status"] = best["Текущий статус"]
        best["deal_stage"] = "" if level_name == "status" else str(best.get("Стадия сделки", ""))
        records.append(best)

    if not records:
        return pd.DataFrame()

    result: pd.DataFrame = pd.DataFrame(records)
    keep_cols: list[str] = [
        "ID ПрПр",
        "Группа продукта",
        "Продукт",
        "ТБ",
        "analysis_level",
        "current_status",
        "deal_stage",
        "stage_key",
        "days_on_stage",
        "days_since_deal",
        "Дата отчета",
    ]
    return result[[c for c in keep_cols if c in result.columns]].reset_index(drop=True)


def build_lead_stage_records(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Формирует таблицу: один лид — одна стадия — сроки нахождения."""
    duration_source: str = config.get("duration_source", "columns")
    stage_mode: str = config.get("stage_analysis_mode", "status")

    prepared: pd.DataFrame = _prepare_duration_columns(df, duration_source)
    frames: list[pd.DataFrame] = []

    if stage_mode in {"status", "both"}:
        status_df: pd.DataFrame = _build_level_records(prepared, "status", "Текущий статус")
        if not status_df.empty:
            frames.append(status_df)

    if stage_mode in {"substages", "both"}:
        sub_df: pd.DataFrame = _build_level_records(prepared, "substage", "Стадия сделки")
        if not sub_df.empty:
            frames.append(sub_df)

    if not frames:
        logger.warning("Не сформировано записей lead_stage_records")
        return pd.DataFrame()

    result: pd.DataFrame = pd.concat(frames, ignore_index=True)
    result = result.dropna(subset=["days_on_stage"])
    logger.info("Записей lead_stage_records: %d", len(result))
    return result
