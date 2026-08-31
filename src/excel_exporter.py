"""Экспорт результатов в форматированный Excel."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.pivot_excel import add_visualization_sheets
from src.settings import build_percentile_column_mapping, col
from src.visualization_data import build_visualization_payload

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
        "days_on_stage_min": labels.get("days_on_stage_min", "Мин дней на стадии"),
        "days_on_stage_max": labels.get("days_on_stage_max", "Макс дней на стадии"),
        "days_on_stage_count": labels.get("days_on_stage_count", "Число лидов"),
        "days_since_deal_min": labels.get("days_since_deal_min", "Мин дней с создания сделки"),
        "days_since_deal_max": labels.get("days_since_deal_max", "Макс дней с создания сделки"),
        "days_since_deal_count": labels.get("days_since_deal_count", "Число лидов (сделка)"),
    }
    mapping.update(build_percentile_column_mapping(config))
    return mapping


def _rename_columns_for_export(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Переименовывает колонки для читаемого Excel."""
    return df.rename(columns=_build_export_mapping(config))


def _format_sheet(ws, config: dict[str, Any]) -> None:
    """Применяет автофильтр, закрепление, ширину и раскраску min/max."""
    if ws.max_row < 1 or ws.max_column < 1:
        return

    fmt_cfg: dict[str, Any] = config["output"]["excel_format"]
    labels: dict[str, str] = config["output"]["column_labels"]
    theme: str = config.get("excel_theme", "green_red")
    colors: dict[str, str] = fmt_cfg.get("colors", {"min": "C6EFCE", "max": "FFC7CE"})

    green_fill: PatternFill = PatternFill(
        start_color=colors["min"], end_color=colors["min"], fill_type="solid"
    )
    red_fill: PatternFill = PatternFill(
        start_color=colors["max"], end_color=colors["max"], fill_type="solid"
    )

    ws.freeze_panes = fmt_cfg.get("freeze_panes", "A2")
    ws.auto_filter.ref = ws.dimensions

    min_marker: str = labels.get("min_header_marker", "Мин")
    max_marker: str = labels.get("max_header_marker", "Макс")
    headers: list[str] = [cell.value for cell in ws[1]]
    min_cols: list[int] = []
    max_cols: list[int] = []

    for idx, header in enumerate(headers, start=1):
        if header and min_marker in str(header):
            min_cols.append(idx)
        if header and max_marker in str(header):
            max_cols.append(idx)

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for col_idx in min_cols:
            cell = row[col_idx - 1]
            if theme == "green_red" and isinstance(cell.value, (int, float)):
                cell.fill = green_fill
        for col_idx in max_cols:
            cell = row[col_idx - 1]
            if theme == "green_red" and isinstance(cell.value, (int, float)):
                cell.fill = red_fill

    min_width: int = int(fmt_cfg.get("min_column_width", 12))
    max_width: int = int(fmt_cfg.get("max_column_width", 45))
    sample_rows: int = int(fmt_cfg.get("sample_rows_for_width", 200))

    for col_idx in range(1, ws.max_column + 1):
        letter: str = get_column_letter(col_idx)
        width: int = min_width
        for row_idx in range(1, min(ws.max_row, sample_rows) + 1):
            value = ws.cell(row=row_idx, column=col_idx).value
            if value is not None:
                width = max(width, min(len(str(value)) + 2, max_width))
        ws.column_dimensions[letter].width = width

    header_font: Font = Font(bold=True)
    for cell in ws[1]:
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    float_fmt: str = fmt_cfg.get("float_format", "0.00")
    int_fmt: str = fmt_cfg.get("int_format", "0")
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            if isinstance(cell.value, float):
                cell.number_format = float_fmt
            elif isinstance(cell.value, int):
                cell.number_format = int_fmt


def export_excel(
    stats: dict[str, Any],
    output_path: Path,
    config: dict[str, Any],
    records: pd.DataFrame | None = None,
) -> None:
    """Записывает Excel с листами из config.output.excel_sheets."""
    out_cfg: dict[str, Any] = config["output"]
    sheet_names: dict[str, str] = out_cfg["excel_sheets"]
    max_len: int = int(out_cfg.get("excel_max_sheet_name_length", 31))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    sheets: dict[str, pd.DataFrame] = {
        sheet_names["summary"]: _rename_columns_for_export(stats["by_tb"], config),
        sheet_names["overall"]: _rename_columns_for_export(stats["overall"], config),
    }
    for tb_name, tb_df in stats.get("tb_sheets", {}).items():
        safe_name: str = str(tb_name)[:max_len]
        sheets[safe_name] = _rename_columns_for_export(tb_df, config)

    with pd.ExcelWriter(output_path, engine=config["excel"].get("engine", "openpyxl")) as writer:
        for sheet_name, frame in sheets.items():
            if frame.empty:
                continue
            frame.to_excel(writer, sheet_name=sheet_name, index=False)

    wb = load_workbook(output_path)
    for sheet_name in wb.sheetnames:
        if sheet_name.startswith("_"):
            continue
        if sheet_name in {out_cfg["excel_sheets"].get("matrix", "Матрица"), out_cfg["excel_sheets"].get("charts", "Графики")}:
            continue
        _format_sheet(wb[sheet_name], config)

    if records is not None and not records.empty:
        viz_payload: dict[str, Any] = build_visualization_payload(records, stats, config)
        add_visualization_sheets(
            wb,
            viz_payload.get("pivot_flat", []),
            viz_payload.get("distribution_series", []),
            config,
        )

    wb.save(output_path)

    logger.info("Excel сохранён: %s", output_path)
