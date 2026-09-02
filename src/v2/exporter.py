"""Экспорт Excel v2 на несколько листов (форматирование как в основном pipeline)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
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


def _write_dataframe_block(
    ws: Any,
    frame: pd.DataFrame,
    start_row: int,
    *,
    thousands_format: str | None = None,
) -> int:
    """Пишет DataFrame с заголовком начиная со start_row; возвращает следующую свободную строку."""
    if frame is None or frame.empty:
        return start_row
    n_header_rows: int = 0
    for r_idx, row in enumerate(dataframe_to_rows(frame, index=False, header=True)):
        for c_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=start_row + r_idx, column=c_idx, value=value)
            # Заголовок (r_idx==0) не форматируем; числа — с разделителем разрядов
            if (
                thousands_format
                and r_idx > 0
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            ):
                cell.number_format = thousands_format
        n_header_rows = r_idx + 1
    return start_row + n_header_rows


def _style_block_header(ws: Any, header_row: int, n_cols: int) -> None:
    """Жирный заголовок таблицы на указанной строке."""
    header_font: Font = Font(bold=True)
    header_align: Alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for col_idx in range(1, max(n_cols, 1) + 1):
        cell = ws.cell(row=header_row, column=col_idx)
        cell.font = header_font
        cell.alignment = header_align


def _autosize_columns(ws: Any, max_col: int, max_row: int, config: dict[str, Any]) -> None:
    """Простая ширина колонок для листа «Статистика»."""
    fmt_cfg: dict[str, Any] = config.get("output", {}).get("excel_format", {})
    min_width: int = int(fmt_cfg.get("min_column_width", 12))
    max_width: int = int(fmt_cfg.get("max_column_width", 45))
    for col_idx in range(1, max_col + 1):
        letter: str = get_column_letter(col_idx)
        width: int = min_width
        for row_idx in range(1, min(max_row, 200) + 1):
            value = ws.cell(row=row_idx, column=col_idx).value
            if value is None:
                continue
            # С разделителем разрядов число визуально длиннее
            text: str = f"{value:,}".replace(",", " ") if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)
            width = max(width, min(len(text) + 2, max_width))
        ws.column_dimensions[letter].width = width


def _write_statistics_sheet(
    ws: Any,
    config: dict[str, Any],
    funnel_frame: pd.DataFrame | None,
    outlier_summary: pd.DataFrame | None,
) -> None:
    """
    Лист «Статистика»: воронка фильтров + свод выбросов.
    Не использует format_sheet (несколько блоков) — своё оформление.
    Числа — формат с разделителем разрядов (# ##0).
    """
    row: int = 1
    title_font: Font = Font(bold=True, size=12)
    fmt_cfg: dict[str, Any] = config.get("output", {}).get("excel_format", {})
    # Пробел как разделитель тысяч (Excel: # ##0)
    thousands_format: str = str(fmt_cfg.get("thousands_format", "# ##0"))

    ws.cell(row=row, column=1, value="Воронка отсечения по фильтрам (строки Kanban / уникальные лиды)")
    ws.cell(row=row, column=1).font = title_font
    row += 1
    funnel_header_row: int = row
    if funnel_frame is not None and not funnel_frame.empty:
        row = _write_dataframe_block(
            ws, funnel_frame, row, thousands_format=thousands_format
        )
        _style_block_header(ws, funnel_header_row, len(funnel_frame.columns))
        # Автофильтр только на таблицу воронки
        end_col: str = get_column_letter(len(funnel_frame.columns))
        end_row: int = row - 1
        ws.auto_filter.ref = f"A{funnel_header_row}:{end_col}{end_row}"
        ws.freeze_panes = f"A{funnel_header_row + 1}"
    else:
        ws.cell(row=row, column=1, value="(нет шагов фильтров)")
        row += 1

    row += 1
    ws.cell(
        row=row,
        column=1,
        value="Свод отсечения выбросов (сумма по группам; детали по ТБ/группе/продукту/стадии — на листе «Нормативы»)",
    )
    ws.cell(row=row, column=1).font = title_font
    row += 1
    summary_header_row: int = row
    if outlier_summary is not None and not outlier_summary.empty:
        row = _write_dataframe_block(
            ws, outlier_summary, row, thousands_format=thousands_format
        )
        _style_block_header(ws, summary_header_row, len(outlier_summary.columns))
    else:
        ws.cell(row=row, column=1, value="(нет данных по выбросам)")
        row += 1

    _autosize_columns(ws, max(ws.max_column or 1, 1), max(ws.max_row or 1, 1), config)


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

    «Нормативы» — обычная таблица групп (+ колонки отсечения выбросов по строке).
    «Статистика» — воронка фильтров и свод выбросов.
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

    # Порядок листов: нормативы, статистика, остальные
    preferred_order: list[str] = ["norms", "statistics", "leads", "managers", "violations"]
    ordered_keys: list[str] = [k for k in preferred_order if k in excel_sheets]
    ordered_keys.extend([k for k in excel_sheets if k not in ordered_keys])

    if not excel_sheets and csv_paths:
        redirect_title: str = sanitize_sheet_name("Экспорт CSV", used_sheet_names, max_len)
        prepared[redirect_title] = build_csv_redirect_sheet(csv_paths)
        sheet_key_by_title[redirect_title] = "_csv_redirect"
    else:
        for key in ordered_keys:
            frame = excel_sheets[key]
            title: str = sanitize_sheet_name(sheet_names.get(key, key), used_sheet_names, max_len)
            sheet_key_by_title[title] = key
            if key == "statistics":
                # Плейсхолдер — содержимое пишется блоками
                prepared[title] = pd.DataFrame({"_": []})
            else:
                prepared[title] = prepare_excel_frame(frame, config)

        # Если в sheets не передали statistics, но есть funnel — всё равно создаём лист
        if "statistics" not in excel_sheets and (
            (funnel_frame is not None and not funnel_frame.empty)
            or (outlier_summary is not None and not outlier_summary.empty)
        ):
            title = sanitize_sheet_name(
                sheet_names.get("statistics", "Статистика"), used_sheet_names, max_len
            )
            sheet_key_by_title[title] = "statistics"
            prepared[title] = pd.DataFrame({"_": []})

    with pd.ExcelWriter(path, engine=engine) as writer:
        for title, frame in prepared.items():
            key: str = sheet_key_by_title.get(title, "")
            if key == "statistics":
                pd.DataFrame({"_": []}).to_excel(writer, sheet_name=title, index=False)
                ws = writer.book[title]
                if ws.max_row >= 1:
                    ws.delete_rows(1, ws.max_row)
                _write_statistics_sheet(ws, config, funnel_frame, outlier_summary)
            elif frame.empty:
                pd.DataFrame({"Нет данных": []}).to_excel(writer, sheet_name=title, index=False)
            else:
                frame.to_excel(writer, sheet_name=title, index=False)

        wb = writer.book
        for title in wb.sheetnames:
            if title.startswith("_"):
                continue
            ws = wb[title]
            sheet_key: str = sheet_key_by_title.get(title, "")
            if sheet_key == "statistics":
                # Уже оформлен в _write_statistics_sheet
                continue
            format_sheet(ws, config)
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
