"""Параллельный запуск независимых этапов Excel v2 pipeline."""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any

import pandas as pd

from src.lead_tracker import build_lead_stage_records
from src.performance import resolve_parallel_workers
from src.team_loader import load_team_kind_frames

logger: logging.Logger = logging.getLogger("kanban.excel_v2.parallel")


def parallel_pipeline_enabled(config: dict[str, Any]) -> bool:
    """Включено ли распараллеливание независимых этапов."""
    return bool(config.get("performance", {}).get("parallel_pipeline_stages", True))


def stage_workers(config: dict[str, Any], task_count: int) -> int:
    """Число workers для параллельных этапов (не больше числа задач)."""
    explicit: int = int(config.get("performance", {}).get("parallel_stage_workers", 0))
    base: int = explicit if explicit > 0 else resolve_parallel_workers(config)
    return max(1, min(task_count, base))


def _build_snapshot_task(args: tuple[pd.DataFrame, dict[str, Any]]) -> pd.DataFrame:
    """Обёртка для ProcessPoolExecutor: снимок лидов."""
    from src.excel_report.snapshot import build_lead_snapshot

    df, cfg = args
    return build_lead_snapshot(df, cfg)


def _build_records_task(args: tuple[pd.DataFrame, dict[str, Any]]) -> pd.DataFrame:
    """Обёртка для ProcessPoolExecutor: lead×стадия."""
    df, cfg = args
    return build_lead_stage_records(df, cfg, None)


def run_snapshot_records_teams_parallel(
    filtered_df: pd.DataFrame,
    config: dict[str, Any],
    shared_config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Параллельно: снимок лидов, трекинг стадий, загрузка команд лида и сделки.
    Возвращает (snapshot, records, lead_team_df, deal_team_df).
    """
    workers: int = stage_workers(config, 4)

    if not parallel_pipeline_enabled(config) or workers <= 1:
        from src.excel_report.snapshot import build_lead_snapshot

        snapshot: pd.DataFrame = build_lead_snapshot(filtered_df, config)
        records: pd.DataFrame = build_lead_stage_records(filtered_df, config, None)
        lead_team_df: pd.DataFrame = load_team_kind_frames(shared_config, "lead_team")
        deal_team_df: pd.DataFrame = load_team_kind_frames(shared_config, "deal_team")
        return snapshot, records, lead_team_df, deal_team_df

    logger.info("Параллельные этапы: snapshot + records + команды (workers=%d)", workers)

    cpu_workers: int = min(2, workers)
    io_workers: int = min(2, workers)

    with ProcessPoolExecutor(max_workers=cpu_workers) as cpu_pool, ThreadPoolExecutor(
        max_workers=io_workers
    ) as io_pool:
        fut_snapshot = cpu_pool.submit(_build_snapshot_task, (filtered_df, config))
        fut_records = cpu_pool.submit(_build_records_task, (filtered_df, config))
        fut_lead = io_pool.submit(load_team_kind_frames, shared_config, "lead_team")
        fut_deal = io_pool.submit(load_team_kind_frames, shared_config, "deal_team")

        snapshot = fut_snapshot.result()
        records = fut_records.result()
        lead_team_df = fut_lead.result()
        deal_team_df = fut_deal.result()

    return snapshot, records, lead_team_df, deal_team_df
