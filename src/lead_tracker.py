"""Трекинг стадий лидов и расчёт сроков нахождения."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.settings import col, empty_stage_values

logger: logging.Logger = logging.getLogger("kanban.lead_tracker")


def _is_empty_stage(value: object, config: dict[str, Any]) -> bool:
    """Проверяет, что подстадия пустая."""
    text: str = str(value).strip()
    empty: set[str] = empty_stage_values(config)
    return text in empty or text.lower() == "nan"


def _prepare_duration_columns(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Добавляет колонки сроков по колонкам отчёта и по датам."""
    result: pd.DataFrame = df.copy()
    duration_source: str = config.get("duration_source", "columns")

    days_on_stage_col: str = col(config, "days_on_stage")
    days_since_deal_col: str = col(config, "days_since_deal")
    report_date_col: str = col(config, "report_date")
    work_start_col: str = col(config, "work_start_date")
    deal_created_col: str = col(config, "deal_created_date")
    deal_stage_col: str = col(config, "deal_stage")

    result["_days_col"] = pd.to_numeric(result[days_on_stage_col], errors="coerce")
    result["_days_since_deal_col"] = pd.to_numeric(result[days_since_deal_col], errors="coerce")

    start_ref: pd.Series = result[work_start_col]
    deal_ref: pd.Series = result[deal_created_col].fillna(start_ref)
    has_deal_stage: pd.Series = ~result[deal_stage_col].apply(lambda v: _is_empty_stage(v, config))

    result["_days_dates"] = (result[report_date_col] - start_ref).dt.days
    result.loc[has_deal_stage, "_days_dates"] = (
        result.loc[has_deal_stage, report_date_col] - deal_ref.loc[has_deal_stage]
    ).dt.days

    result["_days_since_deal_dates"] = (
        result[report_date_col] - result[deal_created_col]
    ).dt.days

    if duration_source == "columns":
        result["days_on_stage"] = result["_days_col"]
        result["days_since_deal"] = result["_days_since_deal_col"]
    else:
        result["days_on_stage"] = result["_days_dates"]
        result["days_since_deal"] = result["_days_since_deal_dates"]

    return result


def _deduplicate_same_date(group: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """На одну дату отчёта и стадию — агрегация из config.processing."""
    agg_mode: str = config["processing"].get("dedup_same_date_agg", "max")
    agg_map: dict[str, str] = {
        "days_on_stage": agg_mode,
        "days_since_deal": agg_mode,
        col(config, "product_group"): "first",
        col(config, "product"): "first",
        col(config, "tb"): "first",
        col(config, "current_status"): "first",
        col(config, "deal_stage"): "first",
    }
    present: dict[str, str] = {k: v for k, v in agg_map.items() if k in group.columns}
    report_date_col: str = col(config, "report_date")
    return group.groupby(report_date_col, as_index=False).agg(present)


def _pick_best_across_dates(group: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    """Выбирает запись с максимальным сроком; при равенстве — более поздняя дата отчёта."""
    max_days: float = group["days_on_stage"].max()
    candidates: pd.DataFrame = group[group["days_on_stage"] == max_days]
    report_date_col: str = col(config, "report_date")
    row: pd.Series = candidates.sort_values(report_date_col).iloc[-1]
    return row


def _build_level_records(
    df: pd.DataFrame,
    config: dict[str, Any],
    level_name: str,
) -> pd.DataFrame:
    """Строит записи лид × стадия для одного уровня анализа."""
    work: pd.DataFrame = df.copy()
    lead_id: str = col(config, "lead_id")
    product_group: str = col(config, "product_group")
    product: str = col(config, "product")
    tb: str = col(config, "tb")
    current_status: str = col(config, "current_status")
    deal_stage: str = col(config, "deal_stage")
    report_date: str = col(config, "report_date")

    if level_name == "substage":
        work = work[~work[deal_stage].apply(lambda v: _is_empty_stage(v, config))]
        key_cols: list[str] = [lead_id, product_group, product, tb, deal_stage]
        stage_label_col: str = deal_stage
    else:
        key_cols = [lead_id, product_group, product, tb, current_status]
        stage_label_col = current_status

    if work.empty:
        return pd.DataFrame()

    records: list[pd.Series] = []
    grouped = work.groupby(key_cols, dropna=False)
    for _, group in grouped:
        deduped: pd.DataFrame = _deduplicate_same_date(group, config)
        best: pd.Series = _pick_best_across_dates(deduped, config)
        best = best.copy()
        best["analysis_level"] = level_name
        best["stage_key"] = best[stage_label_col]
        best["current_status"] = best[current_status]
        best["deal_stage"] = "" if level_name == "status" else str(best.get(deal_stage, ""))
        records.append(best)

    if not records:
        return pd.DataFrame()

    result: pd.DataFrame = pd.DataFrame(records)
    keep_cols: list[str] = [
        lead_id,
        product_group,
        product,
        tb,
        "analysis_level",
        "current_status",
        "deal_stage",
        "stage_key",
        "days_on_stage",
        "days_since_deal",
        report_date,
    ]
    return result[[c for c in keep_cols if c in result.columns]].reset_index(drop=True)


def build_lead_stage_records(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Формирует таблицу: один лид — одна стадия — сроки нахождения."""
    stage_mode: str = config.get("stage_analysis_mode", "status")
    prepared: pd.DataFrame = _prepare_duration_columns(df, config)
    frames: list[pd.DataFrame] = []

    if stage_mode in {"status", "both"}:
        status_df: pd.DataFrame = _build_level_records(prepared, config, "status")
        if not status_df.empty:
            frames.append(status_df)

    if stage_mode in {"substages", "both"}:
        sub_df: pd.DataFrame = _build_level_records(prepared, config, "substage")
        if not sub_df.empty:
            frames.append(sub_df)

    if not frames:
        logger.warning("Не сформировано записей lead_stage_records")
        return pd.DataFrame()

    result: pd.DataFrame = pd.concat(frames, ignore_index=True)
    result = result.dropna(subset=["days_on_stage"])
    logger.info("Записей lead_stage_records: %d", len(result))
    return result
