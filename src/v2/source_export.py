"""Сборка третьего Excel: исходные строки Kanban + лидеры/почты по отдельным фильтрам."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.filters import apply_ordered_filters
from src.manager_emails import (
    EmailLookup,
    enrich_snapshot_with_manager_emails,
    load_manager_email_lookup,
    manager_emails_enabled,
)
from src.v2.team_enrich import enrich_snapshot_with_team_dfs

logger: logging.Logger = logging.getLogger("kanban.excel_v2.source_export")


def source_export_cfg(config: dict[str, Any]) -> dict[str, Any]:
    """Блок output.source_export (может быть пустым)."""
    raw: Any = (config.get("output") or {}).get("source_export") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def build_source_export_frame(
    raw_df: pd.DataFrame,
    config: dict[str, Any],
    *,
    lead_team_df: pd.DataFrame | None = None,
    deal_team_df: pd.DataFrame | None = None,
    email_lookup: EmailLookup | None = None,
) -> pd.DataFrame:
    """
    Исходные колонки как после загрузки → фильтры source_export по порядку →
    подливка лидеров лида/сделки и почт.
    """
    if raw_df.empty:
        return raw_df.copy()

    cfg: dict[str, Any] = source_export_cfg(config)
    filters_cfg: dict[str, Any] = dict(cfg.get("filters") or {})
    order_raw: Any = cfg.get("filters_order")
    if isinstance(order_raw, list) and order_raw:
        order: list[str] = [str(x) for x in order_raw]
    else:
        # Если порядок не задан — ключи filters в порядке JSON
        order = list(filters_cfg.keys())

    rows_in: int = len(raw_df)
    filtered: pd.DataFrame = apply_ordered_filters(
        raw_df,
        config,
        filters_cfg,
        order,
        audit_each_filter=bool(
            config.get("processing", {}).get("audit_row_counts", True)
        ),
    )
    logger.info(
        "Source export: фильтры по порядку %s — %s → %s строк",
        order,
        f"{rows_in:,}",
        f"{len(filtered):,}",
    )

    result: pd.DataFrame = filtered
    lead_df: pd.DataFrame = lead_team_df if lead_team_df is not None else pd.DataFrame()
    deal_df: pd.DataFrame = deal_team_df if deal_team_df is not None else pd.DataFrame()
    if not lead_df.empty or not deal_df.empty:
        result = enrich_snapshot_with_team_dfs(result, lead_df, deal_df, config)

    if manager_emails_enabled(config):
        lookup: EmailLookup = (
            email_lookup if email_lookup is not None else load_manager_email_lookup(config)
        )
        result = enrich_snapshot_with_manager_emails(result, config, lookup=lookup)

    return result.reset_index(drop=True)
