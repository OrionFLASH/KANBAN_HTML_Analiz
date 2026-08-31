"""Точка входа: pipeline анализа Kanban-данных."""

from __future__ import annotations

import gc
import sys
import time
from datetime import datetime
from pathlib import Path

from src.data_audit import audit_rows
from src.aggregator import build_all_statistics
from src.config_loader import get_file_list, get_input_dir, get_output_dir, load_config
from src.dictionaries import build_dimensions
from src.excel_exporter import export_excel
from src.excel_loader import load_all_files
from src.filters import apply_filters
from src.json_exporter import export_json
from src.lead_tracker import build_lead_stage_records
from src.logger_setup import setup_logger
from src.performance import resolve_parallel_workers
from src.progress import ProgressReporter
from src.project_paths import resolve_path


def _maybe_free_memory(config: dict) -> None:
    """Освобождает память между этапами при больших объёмах."""
    if config.get("performance", {}).get("free_memory_between_stages", True):
        gc.collect()


def run(config_path: str | Path = "config.json") -> tuple[Path, Path]:
    """Запускает полный pipeline анализа."""
    t_pipeline: float = time.monotonic()
    config_file: Path = resolve_path(config_path)
    config = load_config(config_file)
    logger = setup_logger(config)
    progress = ProgressReporter(config, logger)

    workers: int = resolve_parallel_workers(config)
    progress.stage("Старт", f"режим={config['mode']}, workers={workers}")
    logger.info("Старт pipeline Kanban Analiz")

    input_dir: Path = get_input_dir(config)
    filenames: list[str] = get_file_list(config)
    output_dir: Path = get_output_dir(config)

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
    progress.done(f"После фильтров: {len(filtered_df):,} строк")
    del raw_df
    _maybe_free_memory(config)

    progress.stage("Справочники")
    dimensions = build_dimensions(filtered_df, config)
    progress.done("Справочники построены")

    progress.stage("Трекинг лидов по стадиям")
    records = build_lead_stage_records(filtered_df, config, progress)
    del filtered_df
    _maybe_free_memory(config)

    if records.empty:
        logger.error("Нет данных для агрегации после обработки")
        progress.step("ОШИБКА: нет данных для агрегации")
        sys.exit(1)

    progress.stage("Агрегация статистики", f"{len(records):,} записей")
    stats = build_all_statistics(records, config)
    progress.done(f"Агрегировано групп: {len(stats['overall'])}")

    progress.stage("Экспорт Excel")
    export_excel(stats, excel_path, config)
    progress.done(f"Excel: {excel_path.name}")

    progress.stage("Экспорт JSON")
    export_json(stats, dimensions, config, json_path)
    progress.done(f"JSON: {json_path.name}")

    elapsed: float = time.monotonic() - t_pipeline
    progress.done(f"Pipeline завершён за {elapsed:.1f} сек")
    logger.info("Готово за %.1f сек. Excel: %s, JSON: %s", elapsed, excel_path, json_path)
    return excel_path, json_path


if __name__ == "__main__":
    cfg: str = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    run(cfg)
