"""Трекинг стадий лидов и расчёт сроков нахождения (векторизованная версия)."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.data_audit import audit_lead_coverage, log_missing_metrics
from src.progress import ProgressReporter
from src.settings import col, empty_stage_values, group_only_product_label, is_group_only_analysis

logger: logging.Logger = logging.getLogger("kanban.lead_tracker")


def _mask_empty_stage(series: pd.Series, config: dict[str, Any]) -> pd.Series:
    """Векторная проверка пустой подстадии."""
    empty: set[str] = empty_stage_values(config)
    lowered: set[str] = {v.lower() for v in empty}
    as_str: pd.Series = series.astype(str).str.strip()
    return as_str.isin(empty) | as_str.str.lower().isin(lowered)


def _prepare_duration_columns(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """
    Добавляет колонки сроков.
    При duration_source=dates и пустых датах — fallback на колонки отчёта (если включён в config).
    Строки не удаляются.
    """
    result: pd.DataFrame = df.copy()
    duration_source: str = config.get("duration_source", "columns")
    proc: dict[str, Any] = config.get("processing", {})
    use_fallback: bool = bool(proc.get("duration_fallback_to_columns", True))

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
    has_deal_stage: pd.Series = ~_mask_empty_stage(result[deal_stage_col], config)

    result["_days_dates"] = (result[report_date_col] - start_ref).dt.days
    if has_deal_stage.any():
        deal_days: pd.Series = (
            result.loc[has_deal_stage, report_date_col] - deal_ref.loc[has_deal_stage]
        ).dt.days
        result.loc[has_deal_stage, "_days_dates"] = deal_days

    result["_days_since_deal_dates"] = (
        result[report_date_col] - result[deal_created_col]
    ).dt.days

    if duration_source == "columns":
        result["days_on_stage"] = result["_days_col"]
        result["days_since_deal"] = result["_days_since_deal_col"]
    else:
        result["days_on_stage"] = result["_days_dates"]
        result["days_since_deal"] = result["_days_since_deal_dates"]
        if use_fallback:
            result["days_on_stage"] = result["days_on_stage"].fillna(result["_days_col"])
            result["days_since_deal"] = result["days_since_deal"].fillna(
                result["_days_since_deal_col"]
            )

    return result


def _build_level_records_vectorized(
    df: pd.DataFrame,
    config: dict[str, Any],
    level_name: str,
    progress: ProgressReporter | None = None,
) -> pd.DataFrame:
    """Векторизованное построение записей лид × стадия — без потери групп."""
    work: pd.DataFrame = df.copy()
    lead_id: str = col(config, "lead_id")
    product_group: str = col(config, "product_group")
    product: str = col(config, "product")
    tb: str = col(config, "tb")
    current_status: str = col(config, "current_status")
    deal_stage: str = col(config, "deal_stage")
    report_date: str = col(config, "report_date")
    agg_mode: str = config["processing"].get("dedup_same_date_agg", "max")

    rows_in: int = len(work)

    if level_name == "substage":
        work = work[~_mask_empty_stage(work[deal_stage], config)]
        key_cols: list[str] = [lead_id, product_group, tb, deal_stage]
        stage_label_col: str = deal_stage
        skip_reason: str = "режим substages — пустая «Стадия сделки»"
    else:
        key_cols = [lead_id, product_group, tb, current_status]
        stage_label_col = current_status
        skip_reason = ""

    if not is_group_only_analysis(config):
        key_cols.insert(2, product)

    if level_name == "substage" and rows_in > len(work):
        logger.info(
            "Аудит [трекинг/%s]: %s → %s строк (%s)",
            level_name,
            f"{rows_in:,}",
            f"{len(work):,}",
            skip_reason,
        )

    if work.empty:
        return pd.DataFrame()

    if progress:
        progress.step(f"Трекинг [{level_name}]: дедупликация по дате отчёта ({len(work):,} строк)…")

    dedup_cols: list[str] = key_cols + [report_date]
    meta_first: dict[str, str] = {
        current_status: "first",
        deal_stage: "first",
        product_group: "first",
        product: "first",
        tb: "first",
    }
    agg_map: dict[str, str] = {
        "days_on_stage": agg_mode,
        "days_since_deal": agg_mode,
        **{k: v for k, v in meta_first.items() if k in work.columns},
    }

    step1: pd.DataFrame = work.groupby(dedup_cols, dropna=False, as_index=False).agg(agg_map)

    if progress:
        progress.step(f"Трекинг [{level_name}]: выбор max дней / max дата ({len(step1):,} групп)…")

    # na_position='last' — при выборе max дней строки с NaN не вытесняют строки с данными
    step1 = step1.sort_values(
        ["days_on_stage", report_date],
        ascending=[False, False],
        na_position="last",
        kind="mergesort",
    )
    best: pd.DataFrame = step1.drop_duplicates(subset=key_cols, keep="first").copy()

    best["analysis_level"] = level_name
    best["stage_key"] = best[stage_label_col]
    best["current_status"] = best[current_status]
    best["deal_stage"] = "" if level_name == "status" else best[deal_stage].astype(str)
    if is_group_only_analysis(config):
        best[product] = group_only_product_label(config)

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
    return best[[c for c in keep_cols if c in best.columns]].reset_index(drop=True)


def build_lead_stage_records(
    df: pd.DataFrame,
    config: dict[str, Any],
    progress: ProgressReporter | None = None,
) -> pd.DataFrame:
    """Формирует таблицу: один лид — одна стадия — сроки нахождения. Все лиды сохраняются."""
    stage_mode: str = config.get("stage_analysis_mode", "status")

    if progress:
        progress.step(f"Расчёт сроков на {len(df):,} строках (все строки входа)…")

    prepared: pd.DataFrame = _prepare_duration_columns(df, config)
    frames: list[pd.DataFrame] = []

    if stage_mode in {"status", "both"}:
        status_df: pd.DataFrame = _build_level_records_vectorized(
            prepared, config, "status", progress
        )
        if not status_df.empty:
            frames.append(status_df)

    if stage_mode in {"substages", "both"}:
        sub_df: pd.DataFrame = _build_level_records_vectorized(
            prepared, config, "substage", progress
        )
        if not sub_df.empty:
            frames.append(sub_df)

    if not frames:
        logger.warning("Не сформировано записей lead_stage_records")
        audit_lead_coverage(df, pd.DataFrame(), config)
        return pd.DataFrame()

    result: pd.DataFrame = pd.concat(frames, ignore_index=True)

    # Не удаляем строки с пустым сроком — все лиды/стадии остаются в анализе
    log_missing_metrics(result, config)
    audit_lead_coverage(df, result, config)

    logger.info("Записей lead_stage_records: %d (все группы лид×стадия)", len(result))
    if progress:
        progress.step(f"Итого lead_stage_records: {len(result):,} (без отсечения по срокам)")
    return result
