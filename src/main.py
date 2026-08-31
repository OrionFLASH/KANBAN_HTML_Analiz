"""Точка входа: pipeline анализа Kanban-данных."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from src.aggregator import build_all_statistics
from src.config_loader import get_file_list, get_input_dir, get_output_dir, load_config
from src.dictionaries import build_dimensions
from src.excel_exporter import export_excel
from src.excel_loader import load_all_files
from src.filters import apply_filters
from src.json_exporter import export_json
from src.lead_tracker import build_lead_stage_records
from src.logger_setup import setup_logger


def run(config_path: str = "config.json") -> tuple[Path, Path]:
    """Запускает полный pipeline анализа."""
    logger = setup_logger()
    logger.info("Старт pipeline Kanban Analiz")

    config = load_config(config_path)
    input_dir: Path = get_input_dir(config)
    filenames: list[str] = get_file_list(config)
    output_dir: Path = get_output_dir(config)

    timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path: Path = output_dir / f"kanban_report_{timestamp}.xlsx"
    json_path: Path = output_dir / f"kanban_report_{timestamp}.json"

    logger.info("Режим: %s, файлов: %d", config["mode"], len(filenames))

    raw_df = load_all_files(config, input_dir, filenames)
    filtered_df = apply_filters(raw_df, config)
    dimensions = build_dimensions(filtered_df)
    records = build_lead_stage_records(filtered_df, config)

    if records.empty:
        logger.error("Нет данных для агрегации после обработки")
        sys.exit(1)

    stats = build_all_statistics(records, config)
    export_excel(stats, excel_path, config)
    export_json(stats, dimensions, config, json_path)

    logger.info("Готово. Excel: %s, JSON: %s", excel_path, json_path)
    return excel_path, json_path


if __name__ == "__main__":
    cfg: str = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    run(cfg)
