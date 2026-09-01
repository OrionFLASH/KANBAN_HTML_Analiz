"""Контроль полноты данных: ни одна строка/лид не теряется без явной причины."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.settings import col

logger: logging.Logger = logging.getLogger("kanban.data_audit")


def _audit_enabled(config: dict[str, Any]) -> bool:
    """Включён ли аудит строк в config."""
    return bool(config.get("processing", {}).get("audit_row_counts", True))


def audit_rows(
    stage: str,
    before: int,
    after: int,
    config: dict[str, Any],
    reason: str | None = None,
) -> None:
    """
    Логирует изменение числа строк.
    Потеря строк без reason — предупреждение (недопустимо при оптимизации).
    """
    if not _audit_enabled(config):
        return

    if after == before:
        logger.info("Аудит [%s]: %s строк (без изменений)", stage, f"{before:,}")
        return

    if after < before:
        if reason:
            logger.info(
                "Аудит [%s]: %s → %s строк (%s)",
                stage,
                f"{before:,}",
                f"{after:,}",
                reason,
            )
        else:
            logger.warning(
                "Аудит [%s]: ПОТЕРЯ СТРОК %s → %s без явной причины — проверьте обработку!",
                stage,
                f"{before:,}",
                f"{after:,}",
            )
    else:
        logger.info(
            "Аудит [%s]: %s → %s строк",
            stage,
            f"{before:,}",
            f"{after:,}",
        )


def audit_lead_coverage(
    input_df: pd.DataFrame,
    records: pd.DataFrame,
    config: dict[str, Any],
) -> None:
    """Проверяет, что каждый ID ПрПр из входа попал в lead_stage_records."""
    if not _audit_enabled(config) or input_df.empty:
        return

    lead_col: str = col(config, "lead_id")
    in_leads: set[str] = set(input_df[lead_col].dropna().astype(str).unique())
    out_leads: set[str] = (
        set(records[lead_col].dropna().astype(str).unique()) if not records.empty else set()
    )

    missing: set[str] = in_leads - out_leads
    if missing:
        sample: list[str] = sorted(missing)[:5]
        logger.error(
            "Аудит [лиды]: %d из %d ID ПрПр НЕ попали в анализ! Примеры: %s",
            len(missing),
            len(in_leads),
            sample,
        )
    else:
        logger.info(
            "Аудит [лиды]: все %s уникальных ID ПрПр учтены в lead_stage_records",
            f"{len(in_leads):,}",
        )

    extra: set[str] = out_leads - in_leads
    if extra:
        logger.warning(
            "Аудит [лиды]: %d ID в records отсутствуют во входе (неожиданно)",
            len(extra),
        )


def audit_snapshot_coverage(
    filtered_df: pd.DataFrame,
    snapshot: pd.DataFrame,
    config: dict[str, Any],
) -> None:
    """Проверяет, что каждый ID ПрПр после фильтров есть в снимке лидов."""
    if not _audit_enabled(config) or filtered_df.empty:
        return

    lead_col: str = col(config, "lead_id")
    in_leads: set[str] = {
        str(v).strip()
        for v in filtered_df[lead_col].dropna().astype(str)
        if str(v).strip()
    }
    if not in_leads:
        return

    if snapshot.empty:
        logger.error(
            "Аудит [снимок]: 0 строк, ожидалось %s уникальных ID ПрПр после фильтров",
            f"{len(in_leads):,}",
        )
        return

    snap_key: str = lead_col if lead_col in snapshot.columns else "lead_id"
    if snap_key not in snapshot.columns and "lead_id" in snapshot.columns:
        snap_key = "lead_id"

    out_leads: set[str] = {
        str(v).strip()
        for v in snapshot[snap_key].dropna().astype(str)
        if str(v).strip()
    }
    missing: set[str] = in_leads - out_leads
    if missing:
        sample: list[str] = sorted(missing)[:5]
        logger.error(
            "Аудит [снимок]: %d из %d ID ПрПр после фильтров НЕ попали в снимок! Примеры: %s",
            len(missing),
            len(in_leads),
            sample,
        )
    else:
        logger.info(
            "Аудит [снимок]: все %s уникальных ID ПрПр после фильтров в листе уникальных ID",
            f"{len(in_leads):,}",
        )

    dropped_empty: int = int(
        filtered_df[lead_col].isna().sum()
        + (filtered_df[lead_col].astype(str).str.strip() == "").sum()
    )
    if dropped_empty:
        logger.warning(
            "Аудит [снимок]: %s строк Kanban без ID ПрПр — не попадают в лист уникальных ID",
            f"{dropped_empty:,}",
        )


def log_missing_metrics(records: pd.DataFrame, config: dict[str, Any]) -> None:
    """Сообщает о записях без сроков — они остаются в анализе, не удаляются."""
    if records.empty:
        return

    missing_days: int = int(records["days_on_stage"].isna().sum())
    total: int = len(records)
    if missing_days > 0:
        logger.warning(
            "Аудит [сроки]: %s/%s записей без «days_on_stage» — сохранены в анализе (метрики могут быть пустыми)",
            f"{missing_days:,}",
            f"{total:,}",
        )
    else:
        logger.info("Аудит [сроки]: у всех %s записей есть days_on_stage", f"{total:,}")
