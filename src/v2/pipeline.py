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
from src.v2.duration_matrix import build_all_duration_matrices, duration_matrix_enabled
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
from src.v2.report_parts import (
    REPORT_PART_ANALYTICS,
    REPORT_PART_DETAIL,
    REPORT_PART_SOURCE,
    build_report_path,
    resolve_report_parts,
    want_analytics,
    want_detail,
    want_source,
)
from src.v2.source_export import build_source_export_frame
from src.v2.snapshot import snapshot_to_export_frame
from src.v2.status_durations import attach_status_duration_columns
from src.v2.team_enrich import enrich_snapshot_with_team_dfs
from src.filters import apply_filters, filter_terminal_deal_stage_rows
from src.input_files_check import InputFilesMissingError, ensure_input_files_exist
from src.resource_guard import apply_adaptive_resources, maybe_free_memory_between_stages
from src.logger_setup import setup_logger
from src.performance import resolve_parallel_workers
from src.progress import ProgressReporter
from src.statistics_config import filter_and_order_statistics_frame
from src.debug_trace import debug_event
from src.team_loader import load_team_frames

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


def _run_source_only_pipeline(
    *,
    config: dict[str, Any],
    shared_config: dict[str, Any],
    log: logging.Logger,
    progress: ProgressReporter,
    raw_df: pd.DataFrame,
    output_dir: Path,
    timestamp: str,
    t_start: float,
) -> list[Path]:
    """
    Только третий Excel: исходные строки + фильтры source_export + лидеры/почты.
    Без нормативов, снимка и analytics/detail.
    """
    progress.stage("Source-only: команды и почты", f"{len(raw_df):,} строк")
    with progress.timed("load_team_frames"):
        lead_team_df, deal_team_df = load_team_frames(shared_config)
    progress.step(
        f"Команда: лид={len(lead_team_df):,} строк, сделка={len(deal_team_df):,} строк"
    )

    email_lookup = None
    if manager_emails_enabled(config):
        with progress.timed("load_manager_email_lookup"):
            email_lookup = load_manager_email_lookup(config)
    else:
        progress.debug("manager_emails: выключены в config")

    with progress.timed("build_source_export_frame", rows_in=len(raw_df)):
        source_frame: pd.DataFrame = build_source_export_frame(
            raw_df,
            config,
            lead_team_df=lead_team_df,
            deal_team_df=deal_team_df,
            email_lookup=email_lookup,
        )
    progress.done(f"Source export: {len(source_frame):,} строк")

    del raw_df
    del lead_team_df
    del deal_team_df
    _maybe_free_memory(config)

    source_path: Path = build_report_path(
        output_dir, config, REPORT_PART_SOURCE, timestamp
    )
    progress.stage("Экспорт source", str(source_path.name))
    with progress.timed("export_excel_v2_source", rows=len(source_frame)):
        _, csv_paths = export_excel_v2(
            source_path,
            {"source": source_frame},
            config,
        )
    if csv_paths:
        progress.step(f"CSV overflow: {', '.join(p.name for p in csv_paths)}")
    progress.done(f"Excel source: {source_path.name}")

    elapsed: float = time.monotonic() - t_start
    progress.timing_summary(total_wall=elapsed)
    log.info("Excel v2 (source-only) завершён за %.1f с: %s", elapsed, source_path.name)
    debug_event(
        logger,
        "pipeline finished",
        elapsed_sec=round(elapsed, 2),
        files=1,
        parts=REPORT_PART_SOURCE,
    )
    return [source_path]


def run_excel_pipeline(config_path: str | Path = "config_excel_v2.json") -> list[Path]:
    """
    Запускает Excel v2 pipeline.

    Возвращает список созданных xlsx (1–3 файла в зависимости от report_parts).
    """
    t_start: float = time.monotonic()
    config: dict[str, Any] = load_excel_v2_config(config_path)
    shared_config: dict[str, Any] = config_for_shared_modules(config)
    log = setup_logger(config)
    progress = ProgressReporter(config, log)

    report_parts: frozenset[str] = resolve_report_parts(config)
    need_analytics: bool = want_analytics(report_parts)
    need_detail: bool = want_detail(report_parts)
    need_source: bool = want_source(report_parts)

    input_dir: Path = get_excel_v2_input_dir(config)
    filenames: list[str] = get_excel_v2_file_list(config)
    output_dir: Path = get_excel_v2_output_dir(config)

    progress.debug(
        f"Инициализация: mode={config.get('mode')}, "
        f"kanban_files={len(filenames)}, "
        f"report_parts={sorted(report_parts)}, "
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
    log.info(
        "Старт Excel v2 pipeline (режим=%s, workers=%d, report_parts=%s)",
        config["mode"],
        workers,
        ",".join(sorted(report_parts)),
    )
    progress.debug(
        f"Ресурсы: workers={workers}, "
        f"parallel_stages={bool(config.get('performance', {}).get('parallel_pipeline_stages', True))}"
    )

    out_cfg: dict[str, Any] = config["output"]
    timestamp: str = datetime.now().strftime(out_cfg.get("timestamp_format", "%Y%m%d_%H%M%S"))

    log.info("Режим: %s, файлов: %d, workers: %d", config["mode"], len(filenames), workers)

    progress.stage("Загрузка Kanban", f"{len(filenames)} файлов")
    with progress.timed("load_all_files", files=len(filenames)):
        raw_df: pd.DataFrame = load_all_files(config, input_dir, filenames, progress)
    rows_loaded: int = len(raw_df)
    progress.debug(f"После загрузки Kanban: rows={rows_loaded:,}, cols={raw_df.shape[1]}")
    _maybe_free_memory(config)

    # Независимые ветки данных:
    # - analytics/detail: config.filters (+ terminal exclude) на raw_df
    # - source: output.source_export.filters на отдельной копии raw_for_source
    # Одна ветка НЕ режет и НЕ ограничивает другую (не «сначала одни, потом другие»).
    raw_for_source: pd.DataFrame | None = raw_df.copy() if need_source else None

    # Только source — без нормативов/снимка и без корневых filters
    if need_source and not need_analytics and not need_detail:
        return _run_source_only_pipeline(
            config=config,
            shared_config=shared_config,
            log=log,
            progress=progress,
            raw_df=raw_df,
            output_dir=output_dir,
            timestamp=timestamp,
            t_start=t_start,
        )

    progress.stage("Фильтрация (analytics/detail)", f"{rows_loaded:,} строк")
    enabled_filters: list[str] = _enabled_filter_names(config)
    progress.substage(
        "подготовка фильтров",
        f"включено={len(enabled_filters)}: {', '.join(enabled_filters) or '—'}",
    )
    audit_filters: bool = bool(config.get("processing", {}).get("audit_row_counts", True))
    # Воронка и аудит по группам нужны только для analytics (лист «Статистика» / колонки на Нормативах)
    funnel_steps: list[dict[str, Any]] = []
    group_auditor: GroupFilterAuditor | None = (
        GroupFilterAuditor(config) if need_analytics else None
    )
    if need_analytics:
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
            funnel=funnel_steps if need_analytics else None,
            group_auditor=group_auditor,
        )
    progress.debug(f"После inclusion-фильтров: rows={len(after_inclusion):,}")
    progress.substage("filter_terminal_deal_stage_rows", f"вход={len(after_inclusion):,}")
    with progress.timed("filter_terminal_deal_stage_rows", rows_in=len(after_inclusion)):
        filtered_df: pd.DataFrame = filter_terminal_deal_stage_rows(
            after_inclusion,
            config,
            audit_each_filter=audit_filters,
            funnel=funnel_steps if need_analytics else None,
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

    # Команды / почты — для detail и/или source
    load_teams: bool = need_detail or need_source
    progress.stage(
        "Снимок + нормативы",
        f"{len(filtered_df):,} строк; teams={'да' if load_teams else 'нет'}",
    )
    progress.substage("snapshot + records + team_files")
    with progress.timed(
        "run_snapshot_records_teams_parallel",
        rows_in=len(filtered_df),
        load_teams=load_teams,
    ):
        snapshot, records, lead_team_df, deal_team_df = run_snapshot_records_teams_parallel(
            filtered_df,
            config,
            shared_config,
            load_teams=load_teams,
        )
    progress.step(
        f"Команда: лид={len(lead_team_df):,} строк, сделка={len(deal_team_df):,} строк"
    )
    progress.debug(
        f"Кадры после параллели: snapshot={len(snapshot):,}, "
        f"records={len(records):,}, lead_team={len(lead_team_df):,}, "
        f"deal_team={len(deal_team_df):,}"
    )

    email_lookup = None
    if need_detail or need_source:
        if need_detail:
            progress.substage("enrich_snapshot_with_team_dfs")
            with progress.timed(
                "enrich_snapshot_with_team_dfs",
                snapshot_rows=len(snapshot),
                lead_rows=len(lead_team_df),
                deal_rows=len(deal_team_df),
            ):
                snapshot = enrich_snapshot_with_team_dfs(
                    snapshot, lead_team_df, deal_team_df, config
                )

        if manager_emails_enabled(config):
            progress.substage("manager_emails")
            with progress.timed("load_manager_email_lookup"):
                email_lookup = load_manager_email_lookup(config)
            if need_detail:
                with progress.timed(
                    "enrich_snapshot_with_manager_emails", snapshot_rows=len(snapshot)
                ):
                    snapshot = enrich_snapshot_with_manager_emails(
                        snapshot, config, email_lookup
                    )
        else:
            progress.debug("manager_emails: выключены в config")
    else:
        progress.debug("Детализация/source выключены — лидеры и почты пропущены")

    with progress.timed("audit_snapshot_coverage"):
        audit_snapshot_coverage(filtered_df, snapshot, config)
    progress.done(f"Уникальных ID: {len(snapshot):,}, записей стадий: {len(records):,}")

    # Source: только output.source_export на полной копии загрузки (не filtered_df)
    source_export_frame: pd.DataFrame = pd.DataFrame()
    if need_source and raw_for_source is not None:
        progress.stage(
            "Исходные строки (source)",
            f"{len(raw_for_source):,} строк до source_export-фильтров",
        )
        with progress.timed("build_source_export_frame", rows_in=len(raw_for_source)):
            source_export_frame = build_source_export_frame(
                raw_for_source,
                config,
                lead_team_df=lead_team_df,
                deal_team_df=deal_team_df,
                email_lookup=email_lookup,
            )
        progress.done(f"Source export: {len(source_export_frame):,} строк")
        del raw_for_source

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
    if need_analytics and group_auditor is not None:
        with progress.timed("merge_filter_audit_into_norms", norms=len(combined_norms)):
            combined_norms = merge_filter_audit_into_norms(
                combined_norms, group_auditor, config
            )

    # Exceedance нужен для detail (лиды / менеджеры / нарушения)
    status_duration_cols: list[str] = []
    if need_detail:
        progress.substage("build_p80_lookup + exceedance")
        with progress.timed("build_p80_lookup_frames"):
            tb_p80, all_p80 = build_p80_lookup_frames(by_tb, overall, config)
        with progress.timed("attach_p80_exceedance", snapshot_rows=len(snapshot)):
            snapshot = attach_p80_exceedance(snapshot, tb_p80, all_p80, config)
        progress.substage("attach_status_duration_columns")
        with progress.timed("attach_status_duration_columns", snapshot_rows=len(snapshot)):
            snapshot, status_duration_cols = attach_status_duration_columns(
                snapshot, records, config
            )
        progress.debug(f"Колонки сроков по статусам: {len(status_duration_cols)}")
    else:
        progress.debug("Exceedance / сроки по статусам пропущены (detail выключен)")
    progress.done(f"Нормативных групп: {len(combined_norms):,}")

    del records
    del by_tb
    del overall
    _maybe_free_memory(config)

    manager_summary: pd.DataFrame = pd.DataFrame()
    violations_detail: pd.DataFrame = pd.DataFrame()
    leads_export: pd.DataFrame = pd.DataFrame()
    if need_detail:
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
        progress.substage("snapshot_to_export_frame")
        with progress.timed("snapshot_to_export_frame", rows=len(snapshot)):
            leads_export = snapshot_to_export_frame(
                snapshot,
                config,
                status_duration_columns=status_duration_cols,
            )
    else:
        progress.debug("Своды менеджеров и экспорт лидов пропущены")

    norms_export: pd.DataFrame = pd.DataFrame()
    funnel_frame: pd.DataFrame = pd.DataFrame()
    outlier_summary: pd.DataFrame = pd.DataFrame()
    duration_matrices: dict = {}
    if need_analytics:
        progress.substage("подготовка analytics к экспорту")
        with progress.timed("filter_and_order_statistics_frame", norms=len(combined_norms)):
            norms_internal: pd.DataFrame = filter_and_order_statistics_frame(
                combined_norms, config
            )
        with progress.timed("norms_to_export_frame"):
            norms_export = norms_to_export_frame(combined_norms, config)
        with progress.timed("build_filter_funnel_frame", steps=len(funnel_steps)):
            funnel_frame = build_filter_funnel_frame(funnel_steps)
        with progress.timed("build_outlier_audit_summary"):
            outlier_summary = build_outlier_audit_summary(norms_internal, config)
        if duration_matrix_enabled(config):
            progress.substage("build_duration_matrix")
            with progress.timed("build_duration_matrix", snapshot_rows=len(snapshot)):
                duration_matrices = build_all_duration_matrices(snapshot, config)
            n_matrix_rows: int = 0
            for mtx in duration_matrices.values():
                if mtx is not None and not mtx.empty:
                    n_matrix_rows = max(n_matrix_rows, len(mtx.rows))
            progress.debug(
                f"Матрица сроков: sheets={len(duration_matrices)}, rows={n_matrix_rows:,}"
            )
        else:
            progress.debug("Матрица сроков: выключена")
    else:
        progress.debug("Analytics выключен — нормативы/матрицы/воронка не экспортируются")

    del filtered_df
    del combined_norms
    del snapshot
    _maybe_free_memory(config)

    created_paths: list[Path] = []
    all_csv_paths: list[Path] = []

    if need_analytics:
        analytics_path: Path = build_report_path(
            output_dir, config, REPORT_PART_ANALYTICS, timestamp
        )
        progress.stage("Экспорт analytics", str(analytics_path.name))
        statistics_placeholder: pd.DataFrame = pd.DataFrame()
        analytics_sheets: dict[str, pd.DataFrame] = {
            "norms": norms_export,
            "statistics": statistics_placeholder,
        }
        for m_key, mtx in duration_matrices.items():
            if mtx is not None and not mtx.empty:
                analytics_sheets[m_key] = pd.DataFrame()
        progress.debug(
            f"Analytics листы (строк): "
            f"{ {k: (0 if v is None else len(v)) for k, v in analytics_sheets.items()} }"
        )
        with progress.timed("export_excel_v2_analytics", sheets=len(analytics_sheets)):
            _, csv_a = export_excel_v2(
                analytics_path,
                analytics_sheets,
                config,
                funnel_frame=funnel_frame,
                outlier_summary=outlier_summary,
                duration_matrices=duration_matrices,
            )
        created_paths.append(analytics_path)
        all_csv_paths.extend(csv_a)
        progress.done(f"Excel analytics: {analytics_path.name}")

    if need_detail:
        detail_path: Path = build_report_path(
            output_dir, config, REPORT_PART_DETAIL, timestamp
        )
        progress.stage("Экспорт detail", str(detail_path.name))
        detail_sheets: dict[str, pd.DataFrame] = {
            "leads": leads_export,
            "managers": manager_summary,
            "violations": violations_detail,
        }
        progress.debug(
            f"Detail листы (строк): "
            f"{ {k: (0 if v is None else len(v)) for k, v in detail_sheets.items()} }"
        )
        with progress.timed("export_excel_v2_detail", sheets=len(detail_sheets)):
            _, csv_d = export_excel_v2(
                detail_path,
                detail_sheets,
                config,
            )
        created_paths.append(detail_path)
        all_csv_paths.extend(csv_d)
        progress.done(f"Excel detail: {detail_path.name}")

    if need_source:
        source_path: Path = build_report_path(
            output_dir, config, REPORT_PART_SOURCE, timestamp
        )
        progress.stage("Экспорт source", str(source_path.name))
        progress.debug(f"Source лист: rows={len(source_export_frame):,}")
        with progress.timed("export_excel_v2_source", rows=len(source_export_frame)):
            _, csv_s = export_excel_v2(
                source_path,
                {"source": source_export_frame},
                config,
            )
        created_paths.append(source_path)
        all_csv_paths.extend(csv_s)
        progress.done(f"Excel source: {source_path.name}")
        del source_export_frame

    if all_csv_paths:
        progress.step(f"CSV overflow: {', '.join(p.name for p in all_csv_paths)}")

    elapsed: float = time.monotonic() - t_start
    progress.timing_summary(total_wall=elapsed)
    names: str = ", ".join(p.name for p in created_paths) or "(нет файлов)"
    log.info("Excel v2 завершён за %.1f с: %s", elapsed, names)
    debug_event(
        logger,
        "pipeline finished",
        elapsed_sec=round(elapsed, 2),
        files=len(created_paths),
        parts=",".join(sorted(report_parts)),
    )
    return created_paths
