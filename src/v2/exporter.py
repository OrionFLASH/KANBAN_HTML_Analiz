"""Экспорт Excel v2 на несколько листов (форматирование как в основном pipeline)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.utils.dataframe import dataframe_to_rows

from src.excel_format import format_multiline_columns, format_sheet, prepare_excel_frame
from src.excel_sanitize import sanitize_sheet_name
from src.export_overflow import (
    build_csv_redirect_sheet,
    export_overflow_csv_sheets,
    split_sheets_by_row_limit,
)

logger: logging.Logger = logging.getLogger("kanban.excel_v2.exporter")

# Колонки с переводами строк — ширина и wrap как у «Топ зон» в run.py
MULTILINE_BY_SHEET: dict[str, list[str]] = {
    "managers": ["Группа + Продукт"],
    "leads": [
        "ФИО Лидера лида",
        "Роль Лидера лида",
        "TN Лидера лида",
        "ТБ Лидера лида",
        "ФИО Лидера сделки",
        "Роль Лидера сделки",
        "TN Лидера сделки",
        "ТБ Лидера сделки",
        "Клиент",
    ],
    "violations": ["Клиент"],
}


def _write_dataframe_block(ws: Any, frame: pd.DataFrame, start_row: int) -> int:
    """Пишет DataFrame с заголовком начиная со start_row; возвращает следующую свободную строку."""
    if frame is None or frame.empty:
        return start_row
    n_header_rows: int = 0
    for r_idx, row in enumerate(dataframe_to_rows(frame, index=False, header=True)):
        for c_idx, value in enumerate(row, start=1):
            ws.cell(row=start_row + r_idx, column=c_idx, value=value)
        n_header_rows = r_idx + 1
    return start_row + n_header_rows


def _write_norms_sheet_with_funnel(
    ws: Any,
    norms_frame: pd.DataFrame,
    config: dict[str, Any],
    funnel_frame: pd.DataFrame | None,
    outlier_summary: pd.DataFrame | None,
) -> None:
    """Лист «Нормативы»: сверху воронка фильтров и свод выбросов, ниже — таблица групп."""
    row: int = 1
    ws.cell(
        row=row,
        column=1,
        value="Воронка отсечения по фильтрам (строки Kanban / уникальные лиды)",
    )
    row += 1
    if funnel_frame is not None and not funnel_frame.empty:
        row = _write_dataframe_block(ws, funnel_frame, row)
    else:
        ws.cell(row=row, column=1, value="(нет шагов фильтров)")
        row += 1

    row += 1
    ws.cell(
        row=row,
        column=1,
        value="Свод отсечения выбросов (сумма по группам; детали — колонки таблицы ниже)",
    )
    row += 1
    if outlier_summary is not None and not outlier_summary.empty:
        row = _write_dataframe_block(ws, outlier_summary, row)
    else:
        ws.cell(row=row, column=1, value="(нет данных по выбросам)")
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="Нормативы по группам")
    row += 1
    if norms_frame is None or norms_frame.empty:
        ws.cell(row=row, column=1, value="Нет данных")
    else:
        _write_dataframe_block(ws, norms_frame, row)


def export_excel_v2(
    path: Path,
    sheets: dict[str, pd.DataFrame],
    config: dict[str, Any],
    *,
    funnel_frame: pd.DataFrame | None = None,
    outlier_summary: pd.DataFrame | None = None,
) -> tuple[Path, list[Path]]:
    """
    Записывает листы в Excel; листы > excel_max_rows_per_sheet — в CSV (;).
    Возвращает (путь xlsx, список путей csv).
    На листе «Нормативы» сверху — воронка фильтров и свод выбросов.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    sheet_names: dict[str, str] = dict(config.get("output", {}).get("sheets") or {})
    max_len: int = int(config.get("output", {}).get("excel_max_sheet_name_length", 31))
    engine: str = str(config.get("excel", {}).get("engine", "openpyxl"))

    excel_sheets, csv_sheets = split_sheets_by_row_limit(sheets, config)
    csv_paths: list[Path] = export_overflow_csv_sheets(path, csv_sheets, sheet_names, config)

    used_sheet_names: set[str] = set()
    prepared: dict[str, pd.DataFrame] = {}
    sheet_key_by_title: dict[str, str] = {}

    if not excel_sheets and csv_paths:
        redirect_title: str = sanitize_sheet_name("Экспорт CSV", used_sheet_names, max_len)
        prepared[redirect_title] = build_csv_redirect_sheet(csv_paths)
        sheet_key_by_title[redirect_title] = "_csv_redirect"
    else:
        for key, frame in excel_sheets.items():
            title: str = sanitize_sheet_name(sheet_names.get(key, key), used_sheet_names, max_len)
            sheet_key_by_title[title] = key
            prepared[title] = prepare_excel_frame(frame, config)

    with pd.ExcelWriter(path, engine=engine) as writer:
        for title, frame in prepared.items():
            key: str = sheet_key_by_title.get(title, "")
            if key == "norms":
                pd.DataFrame({"_": []}).to_excel(writer, sheet_name=title, index=False)
                ws = writer.book[title]
                if ws.max_row >= 1:
                    ws.delete_rows(1, ws.max_row)
                _write_norms_sheet_with_funnel(
                    ws,
                    frame,
                    config,
                    funnel_frame,
                    outlier_summary,
                )
            elif frame.empty:
                pd.DataFrame({"Нет данных": []}).to_excel(writer, sheet_name=title, index=False)
            else:
                frame.to_excel(writer, sheet_name=title, index=False)

        wb = writer.book
        for title in wb.sheetnames:
            if title.startswith("_"):
                continue
            ws = wb[title]
            format_sheet(ws, config)
            sheet_key: str = sheet_key_by_title.get(title, "")
            markers: list[str] = MULTILINE_BY_SHEET.get(sheet_key, [])
            if markers:
                format_multiline_columns(ws, config, markers)

        wb.save(path)

    if csv_paths:
        logger.info(
            "Excel v2: %s (%s листов в xlsx, %s в CSV)",
            path,
            len(prepared),
            len(csv_paths),
        )
    else:
        logger.info("Excel v2 сохранён: %s (%s листов)", path, len(prepared))
    return path, csv_paths
