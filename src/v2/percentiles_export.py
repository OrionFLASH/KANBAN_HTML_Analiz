"""Экспорт исходных строк под фильтры процентилей (+ split по ТБ при >1M строк)."""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from src.manager_emails import (
    EmailLookup,
    enrich_snapshot_with_manager_emails,
    load_manager_email_lookup,
    manager_emails_enabled,
)
from src.settings import col
from src.v2.team_enrich import enrich_snapshot_with_team_dfs

logger: logging.Logger = logging.getLogger("kanban.excel_v2.percentiles_export")

_INVALID_SHEET_RE: re.Pattern[str] = re.compile(r'[\\/*?:\[\]]+')


def percentiles_export_cfg(config: dict[str, Any]) -> dict[str, Any]:
    """Блок output.percentiles_export."""
    raw: Any = (config.get("output") or {}).get("percentiles_export") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def percentiles_export_enabled(config: dict[str, Any]) -> bool:
    """Нужен ли файл percentiles (по умолчанию да, если report_parts включает)."""
    cfg: dict[str, Any] = percentiles_export_cfg(config)
    if "enabled" in cfg:
        return bool(cfg["enabled"])
    return True


def build_percentiles_export_frame(
    filtered_df: pd.DataFrame,
    config: dict[str, Any],
    *,
    lead_team_df: pd.DataFrame | None = None,
    deal_team_df: pd.DataFrame | None = None,
    email_lookup: EmailLookup | None = None,
) -> pd.DataFrame:
    """
    Строки после фильтров процентилей (analytics) + лидеры/почты.
    Данные уже отфильтрованы pipeline — здесь только обогащение.
    """
    if filtered_df.empty:
        return filtered_df.copy()

    result: pd.DataFrame = filtered_df.copy()
    lead_df: pd.DataFrame = lead_team_df if lead_team_df is not None else pd.DataFrame()
    deal_df: pd.DataFrame = deal_team_df if deal_team_df is not None else pd.DataFrame()
    if not lead_df.empty or not deal_df.empty:
        result = enrich_snapshot_with_team_dfs(result, lead_df, deal_df, config)

    if manager_emails_enabled(config):
        lookup: EmailLookup = (
            email_lookup if email_lookup is not None else load_manager_email_lookup(config)
        )
        result = enrich_snapshot_with_manager_emails(result, config, lookup=lookup)

    logger.info("Percentiles export: %s строк", f"{len(result):,}")
    return result.reset_index(drop=True)


def _safe_sheet_name(raw: str, max_len: int = 31) -> str:
    """Безопасное имя листа Excel."""
    text: str = _INVALID_SHEET_RE.sub("_", str(raw).strip()) or "ТБ"
    return text[:max_len]


def split_percentiles_sheets_by_tb(
    frame: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """
    Если строк > split_by_tb_over_rows — отдельные листы по ТБ.
    Иначе один лист «percentiles».
    """
    cfg: dict[str, Any] = percentiles_export_cfg(config)
    threshold: int = int(cfg.get("split_by_tb_over_rows", 1_000_000))
    prefix: str = str(cfg.get("sheet_name_prefix") or "ТБ")
    max_name: int = int(config.get("output", {}).get("excel_max_sheet_name_length", 31))

    if frame.empty or len(frame) <= threshold:
        return {"percentiles": frame}

    tb_col: str = col(config, "tb")
    if tb_col not in frame.columns:
        logger.warning(
            "Percentiles: строк %s > %s, но нет колонки ТБ — один лист",
            f"{len(frame):,}",
            f"{threshold:,}",
        )
        return {"percentiles": frame}

    sheets: dict[str, pd.DataFrame] = {}
    used_names: set[str] = set()
    for tb_value, group in frame.groupby(tb_col, sort=False, dropna=False):
        label_raw: str = f"{prefix} {tb_value}" if str(tb_value).strip() else f"{prefix} _"
        name: str = _safe_sheet_name(label_raw, max_name)
        base: str = name
        n: int = 2
        while name in used_names:
            suffix: str = f"_{n}"
            name = _safe_sheet_name(base[: max_name - len(suffix)] + suffix, max_name)
            n += 1
        used_names.add(name)
        sheets[name] = group.reset_index(drop=True)

    logger.info(
        "Percentiles: %s строк > %s — разбито на %s листов по ТБ",
        f"{len(frame):,}",
        f"{threshold:,}",
        len(sheets),
    )
    return sheets
