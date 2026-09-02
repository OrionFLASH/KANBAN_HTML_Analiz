"""Параллельный запуск независимых этапов Excel v2 pipeline."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pandas as pd

from src.v2.snapshot import build_lead_snapshot
from src.lead_tracker import build_lead_stage_records
from src.performance import resolve_parallel_workers
from src.team_loader import load_team_kind_frames

logger: logging.Logger = logging.getLogger("kanban.excel_v2.parallel")


def parallel_pipeline_enabled(config: dict[str, Any]) -> bool:
    """Включено ли распараллеливание загрузки файлов команд (I/O)."""
    return bool(config.get("performance", {}).get("parallel_pipeline_stages", True))


def stage_workers(config: dict[str, Any], task_count: int) -> int:
    """Число workers для параллельных этапов (не больше числа задач)."""
    explicit: int = int(config.get("performance", {}).get("parallel_stage_workers", 0))
    base: int = explicit if explicit > 0 else resolve_parallel_workers(config)
    return max(1, min(task_count, base))


def run_snapshot_records_teams_parallel(
    filtered_df: pd.DataFrame,
    config: dict[str, Any],
    shared_config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Снимок и трекинг — последовательно в основном процессе (без pickle DataFrame).
    Файлы команд — параллельно в ThreadPool (I/O).
    Возвращает (snapshot, records, lead_team_df, deal_team_df).
    """
    workers: int = stage_workers(config, 2)
    terminal_applied: bool = True

    if parallel_pipeline_enabled(config) and workers > 1:
        logger.info(
            "Параллельная загрузка команд (ThreadPool, workers=%d); snapshot+records — последовательно",
            workers,
        )
        with ThreadPoolExecutor(max_workers=workers) as io_pool:
            fut_lead = io_pool.submit(load_team_kind_frames, shared_config, "lead_team")
            fut_deal = io_pool.submit(load_team_kind_frames, shared_config, "deal_team")
            snapshot: pd.DataFrame = build_lead_snapshot(filtered_df, config)
            records: pd.DataFrame = build_lead_stage_records(
                filtered_df,
                config,
                None,
                terminal_filters_already_applied=terminal_applied,
            )
            lead_team_df: pd.DataFrame = fut_lead.result()
            deal_team_df: pd.DataFrame = fut_deal.result()
    else:
        snapshot = build_lead_snapshot(filtered_df, config)
        records = build_lead_stage_records(
            filtered_df,
            config,
            None,
            terminal_filters_already_applied=terminal_applied,
        )
        lead_team_df = load_team_kind_frames(shared_config, "lead_team")
        deal_team_df = load_team_kind_frames(shared_config, "deal_team")

    return snapshot, records, lead_team_df, deal_team_df
