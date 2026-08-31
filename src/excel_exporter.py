"""Экспорт результатов в форматированный Excel."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

logger: logging.Logger = logging.getLogger("kanban.excel_exporter")

GREEN_FILL: PatternFill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
RED_FILL: PatternFill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
HEADER_FONT: Font = Font(bold=True)


def _rename_columns_for_export(df: pd.DataFrame) -> pd.DataFrame:
    """Переименовывает колонки для читаемого Excel."""
    mapping: dict[str, str] = {
        "Группа продукта": "ГРУППА",
        "Продукт": "ПРОДУКТ",
        "ТБ": "ТБ",
        "current_status": "Текущий статус",
        "deal_stage": "Стадия сделки",
        "stage_key": "Ключ стадии",
        "analysis_level": "Уровень анализа",
        "days_on_stage_min": "Мин дней на стадии",
        "days_on_stage_max": "Макс дней на стадии",
        "days_on_stage_count": "Число лидов",
        "days_since_deal_min": "Мин дней с создания сделки",
        "days_since_deal_max": "Макс дней с создания сделки",
        "days_since_deal_count": "Число лидов (сделка)",
    }
    export_df: pd.DataFrame = df.rename(columns=mapping)
    return export_df


def _format_sheet(ws, theme: str) -> None:
    """Применяет автофильтр, закрепление, ширину и раскраску min/max."""
    if ws.max_row < 1 or ws.max_column < 1:
        return

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    headers: list[str] = [cell.value for cell in ws[1]]
    min_cols: list[int] = []
    max_cols: list[int] = []

    for idx, header in enumerate(headers, start=1):
        if header and "Мин" in str(header):
            min_cols.append(idx)
        if header and "Макс" in str(header):
            max_cols.append(idx)

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for col_idx in min_cols:
            cell = row[col_idx - 1]
            if theme == "green_red" and isinstance(cell.value, (int, float)):
                cell.fill = GREEN_FILL
        for col_idx in max_cols:
            cell = row[col_idx - 1]
            if theme == "green_red" and isinstance(cell.value, (int, float)):
                cell.fill = RED_FILL

    for col_idx in range(1, ws.max_column + 1):
        letter: str = get_column_letter(col_idx)
        max_len: int = 12
        for row_idx in range(1, min(ws.max_row, 200) + 1):
            value = ws.cell(row=row_idx, column=col_idx).value
            if value is not None:
                max_len = max(max_len, min(len(str(value)) + 2, 45))
        ws.column_dimensions[letter].width = max_len

    for cell in ws[1]:
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            if isinstance(cell.value, float):
                cell.number_format = "0.00"
            elif isinstance(cell.value, int):
                cell.number_format = "0"


def export_excel(
    stats: dict[str, Any],
    output_path: Path,
    config: dict[str, Any],
) -> None:
    """Записывает Excel с листами: Сводная, Общий, по ТБ."""
    theme: str = config.get("excel_theme", "green_red")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sheets: dict[str, pd.DataFrame] = {
        "Сводная": _rename_columns_for_export(stats["by_tb"]),
        "Общий": _rename_columns_for_export(stats["overall"]),
    }
    for tb_name, tb_df in stats.get("tb_sheets", {}).items():
        safe_name: str = str(tb_name)[:31]
        sheets[safe_name] = _rename_columns_for_export(tb_df)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            if frame.empty:
                continue
            frame.to_excel(writer, sheet_name=sheet_name, index=False)

    wb = load_workbook(output_path)
    for sheet_name in wb.sheetnames:
        _format_sheet(wb[sheet_name], theme)
    wb.save(output_path)

    logger.info("Excel сохранён: %s", output_path)
