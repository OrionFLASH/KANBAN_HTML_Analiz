"""Оркестрация Excel-only pipeline v2."""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.data_audit import audit_rows, audit_snapshot_coverage
from src.excel_loader import load_all_files
from src.filter_funnel import (
    GroupFilterAuditor,
    append_funnel_step,
    build_filter_funnel_frame,
    build_outlier_audit_summary,
    merge_filter_audit_into_norms,
)
from src.v2.config_loader import (
    config_for_shared_modules,
    get_excel_v2_file_list,
    get_excel_v2_input_dir,
    get_excel_v2_output_dir,
    load_excel_v2_config,
)
from src.v2.exceedance import attach_p80_exceedance
from src.v2.duration_matrix import build_duration_matrix, duration_matrix_enabled
from src.v2.exporter import export_excel_v2
from src.v2.manager_summary import build_manager_reports
from src.manager_emails import (
    attach_emails_by_tab_column,
    enrich_snapshot_with_manager_emails,
    load_manager_email_lookup,
    manager_emails_enabled,
)
from src.v2.norms import build_norms_tables, build_p80_lookup_frames, norms_to_export_frame
from src.v2.parallel_utils import run_snapshot_records_teams_parallel
from src.v2.snapshot import snapshot_to_export_frame
from src.v2.team_enrich import enrich_snapshot_with_team_dfs
from src.filters import apply_filters, filter_terminal_deal_stage_rows
from src.input_files_check import InputFilesMissingError, ensure_input_files_exist
from src.resource_guard import apply_adaptive_resources, maybe_free_memory_between_stages
from src.logger_setup import setup_logger
from src.performance import resolve_parallel_workers
from src.progress import ProgressReporter
from src.statistics_config import filter_and_order_statistics_frame
from src.debug_trace import debug_event

logger: logging.Logger = logging.getLogger("kanban.excel_v2.pipeline")


def _maybe_free_memory(config: dict[str, Any]) -> None:
    """Освобождает память между этапами при больших объёмах."""
    maybe_free_memory_between_stages(config)


def _enabled_filter_names(config: dict[str, Any]) -> list[str]:
    """Имена включённых фильтров (без значений/содержимого)."""
    names: list[str] = []
    for name, flt in (config.get("filters") or {}).items():
        if isinstance(flt, dict) and flt.get("enabled"):
            names.append(str(name))
    return names


def run_excel_pipeline(config_path: str | Path = "config_excel_v2.json") -> Path:
    """Запускает полный Excel v2 pipeline и возвращает путь к отчёту."""
    t_start: float = time.monotonic()
    config: dict[str, Any] = load_excel_v2_config(config_path)
    shared_config: dict[str, Any] = config_for_shared_modules(config)
    log = setup_logger(config)
    progress = ProgressReporter(config, log)

    input_dir: Path = get_excel_v2_input_dir(config)
    filenames: list[str] = get_excel_v2_file_list(config)
    output_dir: Path = get_excel_v2_output_dir(config)

    progress.debug(
        f"Инициализация: mode={config.get('mode')}, "
        f"kanban_files={len(filenames)}, "
        f"team_enabled={bool((config.get('team_files') or {}).get('enabled'))}, "
        f"debug_detail={progress.debug_detail}"
    )

    try:
        with progress.timed("ensure_input_files_exist", kanban_files=len(filenames)):
            ensure_input_files_exist(shared_config, log)
    except InputFilesMissingError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

    with progress.timed("apply_adaptive_resources"):
        apply_adaptive_resources(config, input_dir, filenames, log)
    workers: int = resolve_parallel_workers(config)
    log.info("Старт Excel v2 pipeline (режим=%s, workers=%d)", config["mode"], workers)
    progress.debug(
        f"Ресурсы: workers={workers}, "
        f"parallel_stages={bool(config.get('performance', {}).get('parallel_pipeline_stages', True))}"
    )

    out_cfg: dict[str, Any] = config["output"]
    timestamp: str = datetime.now().strftime(out_cfg.get("timestamp_format", "%Y%m%d_%H%M%S"))
    prefix: str = out_cfg.get("report_prefix", "kanban_excel_v2")
    excel_path: Path = output_dir / f"{prefix}_{timestamp}.xlsx"

    log.info("Режим: %s, файлов: %d, workers: %d", config["mode"], len(filenames), workers)

    progress.stage("Загрузка Kanban", f"{len(filenames)} файлов")
    with progress.timed("load_all_files", files=len(filenames)):
        raw_df: pd.DataFrame = load_all_files(config, input_dir, filenames, progress)
    rows_loaded: int = len(raw_df)
    progress.debug(f"После загрузки Kanban: rows={rows_loaded:,}, cols={raw_df.shape[1]}")
    _maybe_free_memory(config)

    progress.stage("Фильтрация", f"{rows_loaded:,} строк")
    enabled_filters: list[str] = _enabled_filter_names(config)
    progress.substage(
        "подготовка фильтров",
        f"включено={len(enabled_filters)}: {', '.join(enabled_filters) or '—'}",
    )
    audit_filters: bool = bool(config.get("processing", {}).get("audit_row_counts", True))
    funnel_steps: list[dict[str, Any]] = []
    group_auditor: GroupFilterAuditor = GroupFilterAuditor(config)
    append_funnel_step(
        funnel_steps,
        stage="Загрузка Kanban",
        before_df=raw_df,
        after_df=raw_df,
        config=config,
        kind="load",
        group_auditor=group_auditor,
    )
    progress.substage("apply_filters", f"вход={rows_loaded:,}")
    with progress.timed("apply_filters", rows_in=rows_loaded, filters=len(enabled_filters)):
        after_inclusion: pd.DataFrame = apply_filters(
            raw_df,
            config,
            audit_each_filter=audit_filters,
            funnel=funnel_steps,
            group_auditor=group_auditor,
        )
    progress.debug(f"После inclusion-фильтров: rows={len(after_inclusion):,}")
    progress.substage("filter_terminal_deal_stage_rows", f"вход={len(after_inclusion):,}")
    with progress.timed("filter_terminal_deal_stage_rows", rows_in=len(after_inclusion)):
        filtered_df: pd.DataFrame = filter_terminal_deal_stage_rows(
            after_inclusion,
            config,
            audit_each_filter=audit_filters,
            funnel=funnel_steps,
            group_auditor=group_auditor,
        )
    filters_active: bool = bool(enabled_filters)
    audit_rows(
        "фильтрация v2 (итого)",
        rows_loaded,
        len(filtered_df),
        config,
        reason="активные фильтры в config_excel_v2" if filters_active else None,
    )
    progress.done(f"После фильтров: {len(filtered_df):,} строк")

    del raw_df
    del after_inclusion
    _maybe_free_memory(config)

    progress.stage("Снимок + нормативы (параллельно)", f"{len(filtered_df):,} строк")
    progress.substage("snapshot + records + team_files")
    with progress.timed(
        "run_snapshot_records_teams_parallel",
        rows_in=len(filtered_df),
    ):
        snapshot, records, lead_team_df, deal_team_df = run_snapshot_records_teams_parallel(
            filtered_df,
            config,
            shared_config,
        )
    progress.step(
        f"Команда: лид={len(lead_team_df):,} строк, сделка={len(deal_team_df):,} строк"
    )
    progress.debug(
        f"Кадры после параллели: snapshot={len(snapshot):,}, "
        f"records={len(records):,}, lead_team={len(lead_team_df):,}, "
        f"deal_team={len(deal_team_df):,}"
    )

    progress.substage("enrich_snapshot_with_team_dfs")
    with progress.timed(
        "enrich_snapshot_with_team_dfs",
        snapshot_rows=len(snapshot),
        lead_rows=len(lead_team_df),
        deal_rows=len(deal_team_df),
    ):
        snapshot = enrich_snapshot_with_team_dfs(snapshot, lead_team_df, deal_team_df, config)

    email_lookup = None
    if manager_emails_enabled(config):
        progress.substage("manager_emails")
        with progress.timed("load_manager_email_lookup"):
            email_lookup = load_manager_email_lookup(config)
        with progress.timed("enrich_snapshot_with_manager_emails", snapshot_rows=len(snapshot)):
            snapshot = enrich_snapshot_with_manager_emails(snapshot, config, email_lookup)
    else:
        progress.debug("manager_emails: выключены в config")

    with progress.timed("audit_snapshot_coverage"):
        audit_snapshot_coverage(filtered_df, snapshot, config)
    progress.done(f"Уникальных ID: {len(snapshot):,}, записей стадий: {len(records):,}")

    del lead_team_df
    del deal_team_df
    _maybe_free_memory(config)

    progress.stage("Нормативы перцентилей", "")
    if records.empty:
        log.error("Нет данных для агрегации после обработки")
        progress.step("ОШИБКА: нет данных для агрегации")
        raise RuntimeError("Нет данных для агрегации после трекинга лидов")

    progress.substage("build_norms_tables", f"records={len(records):,}")
    with progress.timed("build_norms_tables", records=len(records)):
        combined_norms, by_tb, overall = build_norms_tables(records, config)
    with progress.timed("merge_filter_audit_into_norms", norms=len(combined_norms)):
        combined_norms = merge_filter_audit_into_norms(combined_norms, group_auditor, config)
    progress.substage("build_p80_lookup + exceedance")
    with progress.timed("build_p80_lookup_frames"):
        tb_p80, all_p80 = build_p80_lookup_frames(by_tb, overall, config)
    with progress.timed("attach_p80_exceedance", snapshot_rows=len(snapshot)):
        snapshot = attach_p80_exceedance(snapshot, tb_p80, all_p80, config)
    progress.done(f"Нормативных групп: {len(combined_norms):,}")

    del records
    del by_tb
    del overall
    _maybe_free_memory(config)

    progress.stage("Своды по менеджерам", "")
    progress.substage("build_manager_reports", f"snapshot={len(snapshot):,}")
    with progress.timed("build_manager_reports", snapshot_rows=len(snapshot)):
        manager_summary, violations_detail = build_manager_reports(snapshot, config)
    if email_lookup is not None:
        with progress.timed("attach_emails_managers_violations"):
            manager_summary = attach_emails_by_tab_column(
                manager_summary, config, lookup=email_lookup
            )
            violations_detail = attach_emails_by_tab_column(
                violations_detail, config, lookup=email_lookup
            )
    progress.done(
        f"Менеджеров: {len(manager_summary):,}, нарушений: {len(violations_detail):,}"
    )

    progress.substage("подготовка кадров к экспорту")
    with progress.timed("snapshot_to_export_frame", rows=len(snapshot)):
        leads_export: pd.DataFrame = snapshot_to_export_frame(snapshot, config)
    # Внутренний кадр с outlier_* до rename — для свода выбросов
    with progress.timed("filter_and_order_statistics_frame", norms=len(combined_norms)):
        norms_internal: pd.DataFrame = filter_and_order_statistics_frame(combined_norms, config)
    with progress.timed("norms_to_export_frame"):
        norms_export: pd.DataFrame = norms_to_export_frame(combined_norms, config)
    with progress.timed("build_filter_funnel_frame", steps=len(funnel_steps)):
        funnel_frame: pd.DataFrame = build_filter_funnel_frame(funnel_steps)
    with progress.timed("build_outlier_audit_summary"):
        outlier_summary: pd.DataFrame = build_outlier_audit_summary(norms_internal, config)
    duration_matrix = None
    if duration_matrix_enabled(config):
        progress.substage("build_duration_matrix")
        with progress.timed("build_duration_matrix", snapshot_rows=len(snapshot)):
            duration_matrix = build_duration_matrix(snapshot, config)
        progress.debug(
            f"Матрица сроков: rows={0 if duration_matrix is None else len(duration_matrix):,}"
        )
    else:
        progress.debug("Матрица сроков: выключена")

    del filtered_df
    del combined_norms
    del snapshot
    _maybe_free_memory(config)

    progress.stage("Экспорт Excel", str(excel_path.name))
    # Пустой кадр-плейсхолдер: содержимое листа «Статистика» пишется из funnel/summary
    statistics_placeholder: pd.DataFrame = pd.DataFrame()
    sheets_payload: dict[str, pd.DataFrame] = {
        "norms": norms_export,
        "statistics": statistics_placeholder,
        "leads": leads_export,
        "managers": manager_summary,
        "violations": violations_detail,
    }
    if duration_matrix is not None and not duration_matrix.empty:
        sheets_payload["duration_matrix"] = pd.DataFrame()
    sheet_sizes: dict[str, int] = {
        key: (0 if frame is None else len(frame)) for key, frame in sheets_payload.items()
    }
    progress.debug(f"Листы к записи (строк): {sheet_sizes}")
    progress.substage("export_excel_v2", f"sheets={len(sheets_payload)}")
    with progress.timed("export_excel_v2", sheets=len(sheets_payload)):
        _, csv_paths = export_excel_v2(
            excel_path,
            sheets_payload,
            config,
            funnel_frame=funnel_frame,
            outlier_summary=outlier_summary,
            duration_matrix=duration_matrix,
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
    debug_event(logger, "pipeline finished", elapsed_sec=round(elapsed, 2))
    return excel_path
