"""Экспорт результатов в форматированный Excel (pipeline v1)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.excel_format import format_multiline_columns, format_sheet, prepare_excel_frame
from src.excel_sanitize import sanitize_sheet_name
from src.export_overflow import (
    build_csv_redirect_sheet,
    export_overflow_csv_sheets,
    split_sheets_by_row_limit,
)
from src.v1.manager_analytics import manager_analytics_to_excel_frame
from src.settings import col
from src.statistics_config import build_statistics_export_mapping, filter_and_order_statistics_frame

logger: logging.Logger = logging.getLogger("kanban.excel_exporter")

def _build_export_mapping(config: dict[str, Any]) -> dict[str, str]:
    """Строит mapping колонок DataFrame → заголовки Excel из config."""
    labels: dict[str, str] = config["output"]["column_labels"]
    mapping: dict[str, str] = {
        col(config, "product_group"): labels.get("product_group", "ГРУППА"),
        col(config, "product"): labels.get("product", "ПРОДУКТ"),
        col(config, "tb"): labels.get("tb", "ТБ"),
        "current_status": labels.get("current_status", "Текущий статус"),
        "deal_stage": labels.get("deal_stage", "Стадия сделки"),
        "stage_key": labels.get("stage_key", "Ключ стадии"),
        "analysis_level": labels.get("analysis_level", "Уровень анализа"),
    }
    mapping.update(build_statistics_export_mapping(config))
    return mapping


def _prepare_excel_frame(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Санитизация и нормализация табельных номеров перед записью в Excel."""
    return prepare_excel_frame(frame, config)


def _rename_columns_for_export(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Переименовывает и упорядочивает колонки для читаемого Excel."""
    trimmed: pd.DataFrame = filter_and_order_statistics_frame(df, config)
    return trimmed.rename(columns=_build_export_mapping(config))


def _format_sheet(ws, config: dict[str, Any]) -> None:
    """Применяет автофильтр, закрепление, ширину и раскраску min/max."""
    format_sheet(ws, config)


def _format_multiline_columns(
    ws,
    config: dict[str, Any],
    header_markers: list[str],
) -> None:
    """Перенос по словам и высота строк для колонок с многострочным текстом."""
    format_multiline_columns(ws, config, header_markers)


def _format_managers_hotspots_column(ws, config: dict[str, Any]) -> None:
    """Перенос по словам и высота строк для колонки «Топ зон превышения»."""
    format_multiline_columns(ws, config, ["Топ зон"])


def export_excel(
    stats: dict[str, Any],
    output_path: Path,
    config: dict[str, Any],
    manager_payload: dict[str, Any] | None = None,
) -> None:
    """Записывает Excel с листами статистики и менеджеров (без «Графики»)."""
    out_cfg: dict[str, Any] = config["output"]
    sheet_names: dict[str, str] = out_cfg["excel_sheets"]
    max_len: int = int(out_cfg.get("excel_max_sheet_name_length", 31))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    used_sheet_names: set[str] = set()
    sheets: dict[str, pd.DataFrame] = {
        sanitize_sheet_name(sheet_names["summary"], used_sheet_names, max_len): _prepare_excel_frame(
            _rename_columns_for_export(stats["by_tb"], config),
            config,
        ),
        sanitize_sheet_name(sheet_names["overall"], used_sheet_names, max_len): _prepare_excel_frame(
            _rename_columns_for_export(stats["overall"], config),
            config,
        ),
    }
    for tb_name, tb_df in stats.get("tb_sheets", {}).items():
        safe_name: str = sanitize_sheet_name(str(tb_name), used_sheet_names, max_len)
        sheets[safe_name] = _prepare_excel_frame(_rename_columns_for_export(tb_df, config), config)

    managers_sheet: str | None = None
    if manager_payload:
        managers_sheet = sanitize_sheet_name(
            sheet_names.get("managers", "Менеджеры"), used_sheet_names, max_len
        )
        mgr_frame: pd.DataFrame = manager_analytics_to_excel_frame(manager_payload, config)
        if not mgr_frame.empty:
            sheets[managers_sheet] = _prepare_excel_frame(mgr_frame, config)
        else:
            managers_sheet = None

    # Листы > excel_max_rows_per_sheet — в CSV (;), не во вкладку Excel
    excel_sheets, csv_sheets = split_sheets_by_row_limit(sheets, config)
    csv_titles: dict[str, str] = {name: name for name in csv_sheets}
    csv_paths: list[Path] = export_overflow_csv_sheets(
        output_path, csv_sheets, csv_titles, config
    )

    if not excel_sheets and csv_paths:
        redirect_used: set[str] = set()
        redirect_title: str = sanitize_sheet_name("Экспорт CSV", redirect_used, max_len)
        excel_sheets = {redirect_title: build_csv_redirect_sheet(csv_paths)}

    with pd.ExcelWriter(output_path, engine=config["excel"].get("engine", "openpyxl")) as writer:
        for sheet_name, frame in excel_sheets.items():
            if frame.empty:
                continue
            frame.to_excel(writer, sheet_name=sheet_name, index=False)

        wb = writer.book

        for sheet_name in wb.sheetnames:
            if sheet_name.startswith("_"):
                continue
            _format_sheet(wb[sheet_name], config)

        if managers_sheet and managers_sheet in wb.sheetnames:
            _format_managers_hotspots_column(wb[managers_sheet], config)

        wb.save(output_path)

    if csv_paths:
        logger.info("Excel сохранён: %s (%s листов в xlsx, %s CSV)", output_path, len(excel_sheets), len(csv_paths))
    else:
        logger.info("Excel сохранён: %s", output_path)
