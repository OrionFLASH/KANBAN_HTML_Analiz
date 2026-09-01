"""Оркестрация Excel-only pipeline v2."""

from __future__ import annotations

import gc
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.data_audit import audit_rows
from src.excel_loader import load_all_files
from src.excel_report.config_loader import (
    config_for_shared_modules,
    get_excel_v2_file_list,
    get_excel_v2_input_dir,
    get_excel_v2_output_dir,
    load_excel_v2_config,
)
from src.excel_report.exceedance import attach_p80_exceedance
from src.excel_report.exporter import export_excel_v2
from src.excel_report.manager_summary import build_manager_reports
from src.excel_report.norms import build_norms_tables, build_p80_lookup_frames, norms_to_export_frame
from src.excel_report.parallel_utils import run_snapshot_records_teams_parallel
from src.excel_report.snapshot import snapshot_to_export_frame
from src.excel_report.team_enrich import enrich_snapshot_with_team_dfs
from src.filters import apply_filters, filter_terminal_deal_stage_rows
from src.input_files_check import InputFilesMissingError, ensure_input_files_exist
from src.logger_setup import setup_logger
from src.performance import resolve_parallel_workers
from src.progress import ProgressReporter

logger: logging.Logger = logging.getLogger("kanban.excel_v2.pipeline")


def _maybe_free_memory(config: dict[str, Any]) -> None:
    """Освобождает память между этапами при больших объёмах."""
    if config.get("performance", {}).get("free_memory_between_stages", True):
        gc.collect()


def run_excel_pipeline(config_path: str | Path = "config_excel_v2.json") -> Path:
    """Запускает полный Excel v2 pipeline и возвращает путь к отчёту."""
    t_start: float = time.monotonic()
    config: dict[str, Any] = load_excel_v2_config(config_path)
    shared_config: dict[str, Any] = config_for_shared_modules(config)
    log = setup_logger(config)
    progress = ProgressReporter(config, log)

    workers: int = resolve_parallel_workers(config)
    log.info("Старт Excel v2 pipeline (режим=%s, workers=%d)", config["mode"], workers)

    input_dir: Path = get_excel_v2_input_dir(config)
    filenames: list[str] = get_excel_v2_file_list(config)
    output_dir: Path = get_excel_v2_output_dir(config)

    try:
        ensure_input_files_exist(shared_config, log)
    except InputFilesMissingError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

    out_cfg: dict[str, Any] = config["output"]
    timestamp: str = datetime.now().strftime(out_cfg.get("timestamp_format", "%Y%m%d_%H%M%S"))
    prefix: str = out_cfg.get("report_prefix", "kanban_excel_v2")
    excel_path: Path = output_dir / f"{prefix}_{timestamp}.xlsx"

    log.info("Режим: %s, файлов: %d, workers: %d", config["mode"], len(filenames), workers)

    progress.stage("Загрузка Kanban", f"{len(filenames)} файлов")
    raw_df: pd.DataFrame = load_all_files(config, input_dir, filenames, progress)
    rows_loaded: int = len(raw_df)
    _maybe_free_memory(config)

    progress.stage("Фильтрация", f"{rows_loaded:,} строк")
    filtered_df: pd.DataFrame = apply_filters(raw_df, config)
    filtered_df = filter_terminal_deal_stage_rows(filtered_df, config)
    filters_active: bool = any(
        f.get("enabled") for f in config.get("filters", {}).values() if isinstance(f, dict)
    )
    audit_rows(
        "фильтрация v2",
        rows_loaded,
        len(filtered_df),
        config,
        reason="активные фильтры в config_excel_v2" if filters_active else None,
    )
    progress.done(f"После фильтров: {len(filtered_df):,} строк")

    del raw_df
    _maybe_free_memory(config)

    progress.stage("Снимок + нормативы (параллельно)", f"{len(filtered_df):,} строк")
    snapshot, records, lead_team_df, deal_team_df = run_snapshot_records_teams_parallel(
        filtered_df,
        config,
        shared_config,
    )
    snapshot = enrich_snapshot_with_team_dfs(snapshot, lead_team_df, deal_team_df, config)
    progress.done(f"Уникальных ID: {len(snapshot):,}, записей стадий: {len(records):,}")

    del lead_team_df
    del deal_team_df
    _maybe_free_memory(config)

    progress.stage("Нормативы перцентилей", "")
    if records.empty:
        log.error("Нет данных для агрегации после обработки")
        progress.step("ОШИБКА: нет данных для агрегации")
        raise RuntimeError("Нет данных для агрегации после трекинга лидов")

    combined_norms, by_tb, overall = build_norms_tables(records, config)
    tb_p80, all_p80 = build_p80_lookup_frames(by_tb, overall, config)
    snapshot = attach_p80_exceedance(snapshot, tb_p80, all_p80, config)
    progress.done(f"Нормативных групп: {len(combined_norms):,}")

    del records
    del by_tb
    del overall
    _maybe_free_memory(config)

    progress.stage("Своды по менеджерам", "")
    manager_summary, violations_detail = build_manager_reports(snapshot, config)
    progress.done(
        f"Менеджеров: {len(manager_summary):,}, нарушений: {len(violations_detail):,}"
    )

    leads_export: pd.DataFrame = snapshot_to_export_frame(snapshot, config)
    norms_export: pd.DataFrame = norms_to_export_frame(combined_norms, config)

    del filtered_df
    del combined_norms
    del snapshot
    _maybe_free_memory(config)

    progress.stage("Экспорт Excel", str(excel_path.name))
    _, csv_paths = export_excel_v2(
        excel_path,
        {
            "norms": norms_export,
            "leads": leads_export,
            "managers": manager_summary,
            "violations": violations_detail,
        },
        config,
    )
    if csv_paths:
        progress.done(
            f"Excel: {excel_path.name}; CSV: {', '.join(p.name for p in csv_paths)}"
        )
    else:
        progress.done(f"Excel: {excel_path.name}")

    elapsed: float = time.monotonic() - t_start
    progress.timing_summary(total_wall=elapsed)
    log.info("Excel v2 завершён за %.1f с: %s", elapsed, excel_path)
    return excel_path
