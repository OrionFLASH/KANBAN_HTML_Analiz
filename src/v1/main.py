"""Точка входа: pipeline анализа Kanban-данных."""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from src.data_audit import audit_rows
from src.aggregator import build_all_statistics
from src.config_loader import get_file_list, get_input_dir, get_output_dir, load_config
from src.v1.dictionaries import build_dimensions
from src.v1.excel_exporter import export_excel
from src.excel_loader import load_all_files
from src.v1.filter_slices import build_all_filter_slices, default_filter_slice_key, filter_slice_key
from src.filters import apply_filters
from src.input_files_check import InputFilesMissingError, ensure_input_files_exist
from src.v1.json_exporter import export_json
from src.lead_tracker import build_lead_stage_records
from src.v1.manager_analytics import (
    build_manager_analytics,
    build_manager_records,
    export_manager_json,
)
from src.v1.visualization_data import (
    build_json_visualization_payload,
    json_aggregation_modes,
)
from src.settings import with_product_analysis_mode
from src.logger_setup import setup_logger
from src.resource_guard import apply_adaptive_resources, maybe_free_memory_between_stages
from src.performance import resolve_parallel_workers
from src.progress import ProgressReporter
from src.project_paths import resolve_path


def _maybe_free_memory(config: dict) -> None:
    """Освобождает память между этапами при больших объёмах."""
    maybe_free_memory_between_stages(config)


def run(config_path: str | Path = "config.json") -> tuple[Path, Path]:
    """Запускает полный pipeline анализа."""
    t_pipeline: float = time.monotonic()
    config_file: Path = resolve_path(config_path)
    config = load_config(config_file)
    logger = setup_logger(config)
    progress = ProgressReporter(config, logger)

    input_dir: Path = get_input_dir(config)
    filenames: list[str] = get_file_list(config)
    output_dir: Path = get_output_dir(config)

    try:
        ensure_input_files_exist(config, logger)
    except InputFilesMissingError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

    apply_adaptive_resources(config, input_dir, filenames, logger)
    workers: int = resolve_parallel_workers(config)
    logger.info("Старт pipeline Kanban Analiz (режим=%s, workers=%d)", config["mode"], workers)

    out_cfg: dict = config["output"]
    timestamp: str = datetime.now().strftime(out_cfg.get("timestamp_format", "%Y%m%d_%H%M%S"))
    prefix: str = out_cfg.get("report_prefix", "kanban_report")
    excel_path: Path = output_dir / f"{prefix}_{timestamp}.xlsx"
    json_path: Path = output_dir / f"{prefix}_{timestamp}.json"

    logger.info("Режим: %s, файлов: %d, workers: %d", config["mode"], len(filenames), workers)

    raw_df = load_all_files(config, input_dir, filenames, progress)
    rows_loaded: int = len(raw_df)
    _maybe_free_memory(config)

    progress.stage("Фильтрация", f"{rows_loaded:,} строк")
    filtered_df = apply_filters(raw_df, config)
    filters_active: bool = any(
        f.get("enabled") for f in config.get("filters", {}).values() if isinstance(f, dict)
    )
    audit_rows(
        "фильтрация",
        rows_loaded,
        len(filtered_df),
        config,
        reason="активные фильтры в config" if filters_active else None,
    )
    progress.done(f"После фильтров Excel: {len(filtered_df):,} строк")

    progress.stage("Справочники")
    dimensions = build_dimensions(filtered_df, config)
    progress.done("Справочники построены")

    progress.stage("Трекинг лидов по стадиям (Excel)", f"{len(filtered_df):,} строк")
    records = build_lead_stage_records(filtered_df, config, progress)
    progress.done(f"Записей lead×стадия: {len(records):,}")

    if records.empty:
        logger.error("Нет данных для агрегации после обработки")
        progress.step("ОШИБКА: нет данных для агрегации")
        sys.exit(1)

    progress.stage("Агрегация статистики (Excel)", f"{len(records):,} записей")
    stats: dict = build_all_statistics(records, config)
    progress.done(f"Агрегировано групп: {len(stats['overall'])}")

    progress.stage("JSON: срезы фильтров и агрегаций")
    precompute_slices: bool = bool(
        config.get("dashboard", {}).get("precompute_html_filter_slices", True)
    )
    filter_catalog: list[dict[str, Any]] = []
    filter_slices: dict[str, Any] = {}
    if precompute_slices:
        filter_catalog, filter_slices = build_all_filter_slices(raw_df, config, progress)
    else:
        stats_by_mode_json: dict[str, dict] = {
            config.get("product_analysis_mode", "group_product"): stats
        }
        for mode in json_aggregation_modes(config):
            if mode not in stats_by_mode_json:
                stats_by_mode_json[mode] = build_all_statistics(
                    records, with_product_analysis_mode(config, mode)
                )
        from src.v1.filter_slices import build_slice_aggregations, build_filter_catalog

        filter_catalog = build_filter_catalog(config)
        filter_slices = {
            "none": {
                "active_filters": [],
                "label": "Без pipeline-фильтров",
                **build_slice_aggregations(records, config),
            }
        }

    default_slice_key: str = default_filter_slice_key(config) if precompute_slices else "none"
    if default_slice_key not in filter_slices:
        if "none" in filter_slices:
            default_slice_key = "none"
        elif filter_slices:
            default_slice_key = next(iter(filter_slices))

    html_json_cfg: dict[str, Any] = config.get("dashboard", {}).get("html_json") or {}
    bundle_mode: str = str(html_json_cfg.get("bundle_mode", "monolith"))
    json_visualizations: dict = build_json_visualization_payload(
        config,
        filter_slices,
        filter_catalog,
        default_slice_key=default_slice_key,
        embed_filter_slices=bundle_mode != "split",
    )
    primary_slice: dict[str, Any] = filter_slices.get(default_slice_key, filter_slices.get("none", {}))
    stats_by_mode: dict[str, dict] = primary_slice.get("_stats_by_mode", {})
    if not stats_by_mode:
        stats_by_mode = {config.get("product_analysis_mode", "group_product"): stats}
        for mode in json_aggregation_modes(config):
            if mode not in stats_by_mode:
                stats_by_mode[mode] = build_all_statistics(
                    records, with_product_analysis_mode(config, mode)
                )
    progress.done(f"JSON-срезов: {len(filter_slices)}")

    progress.stage("Аналитика менеджеров (КМ)")
    manager_records, snapshot_date = build_manager_records(filtered_df, config, progress)
    manager_payload: dict[str, Any] | None = build_manager_analytics(
        manager_records, stats, config, snapshot_date=snapshot_date
    )
    managers_json_path: Path = output_dir / f"{prefix}_managers_{timestamp}.json"
    write_managers_file: bool = bool(html_json_cfg.get("write_separate_managers_json", False))
    if manager_payload:
        if write_managers_file:
            export_manager_json(manager_payload, managers_json_path, config)
            progress.done(
                f"Менеджеры: топ {len(manager_payload.get('top_by_tb', []))} "
                f"(отдельный JSON + вложение в отчёт)"
            )
        else:
            progress.done(
                f"Менеджеры: топ {len(manager_payload.get('top_by_tb', []))} "
                f"(вложены в monolith JSON)"
            )
    else:
        progress.done("Аналитика менеджеров пропущена (нет КМ или порогов)")

    del filtered_df
    del raw_df
    _maybe_free_memory(config)

    progress.stage("Экспорт Excel")
    export_excel(stats, excel_path, config, manager_payload=manager_payload)
    progress.done(f"Excel: {excel_path.name}")

    progress.stage("Экспорт JSON")
    export_json(
        stats_by_mode,
        dimensions,
        config,
        json_path,
        visualizations=json_visualizations,
        filter_catalog=filter_catalog,
        filter_slices=filter_slices,
        manager_payload=manager_payload,
    )
    progress.done(f"JSON: {json_path.name}")

    elapsed: float = time.monotonic() - t_pipeline
    progress.timing_summary(total_wall=elapsed)
    logger.info(
        "Готово за %.1f сек. Excel: %s, JSON (UI — этот файл): %s",
        elapsed,
        excel_path,
        json_path,
    )
    return excel_path, json_path


if __name__ == "__main__":
    cfg: str = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    run(cfg)
