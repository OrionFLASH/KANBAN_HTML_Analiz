"""Экспорт Excel v2 на несколько листов (форматирование как в основном pipeline)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.excel_exporter import _format_multiline_columns, _format_sheet
from src.excel_sanitize import sanitize_dataframe, sanitize_sheet_name

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


def export_excel_v2(
    path: Path,
    sheets: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> Path:
    """Записывает листы в Excel с тем же форматированием, что export_excel."""
    path.parent.mkdir(parents=True, exist_ok=True)

    sheet_names: dict[str, str] = dict(config.get("output", {}).get("sheets") or {})
    max_len: int = int(config.get("output", {}).get("excel_max_sheet_name_length", 31))
    engine: str = str(config.get("excel", {}).get("engine", "openpyxl"))
    used_sheet_names: set[str] = set()

    prepared: dict[str, pd.DataFrame] = {}
    sheet_key_by_title: dict[str, str] = {}

    for key, frame in sheets.items():
        title: str = sanitize_sheet_name(sheet_names.get(key, key), used_sheet_names, max_len)
        sheet_key_by_title[title] = key
        prepared[title] = sanitize_dataframe(frame)

    with pd.ExcelWriter(path, engine=engine) as writer:
        for title, frame in prepared.items():
            if frame.empty:
                pd.DataFrame({"Нет данных": []}).to_excel(writer, sheet_name=title, index=False)
            else:
                frame.to_excel(writer, sheet_name=title, index=False)

        wb = writer.book
        for title in wb.sheetnames:
            if title.startswith("_"):
                continue
            ws = wb[title]
            _format_sheet(ws, config)
            sheet_key: str = sheet_key_by_title.get(title, "")
            markers: list[str] = MULTILINE_BY_SHEET.get(sheet_key, [])
            if markers:
                _format_multiline_columns(ws, config, markers)

        wb.save(path)

    logger.info("Excel v2 сохранён: %s (%s листов)", path, len(prepared))
    return path
