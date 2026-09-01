"""Экспорт больших листов в CSV вместо вкладки Excel (лимит ~1 млн строк)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

from src.excel_sanitize import sanitize_dataframe

logger: logging.Logger = logging.getLogger("kanban.export_overflow")

DEFAULT_EXCEL_MAX_ROWS: int = 900_000
_INVALID_CSV_STEM_RE: re.Pattern[str] = re.compile(r'[<>:"/\\|?*\n\r\t]+')


def csv_overflow_config(config: dict[str, Any]) -> dict[str, Any]:
    """Параметры overflow из output.csv_overflow с дефолтами."""
    raw: dict[str, Any] = dict(config.get("output", {}).get("csv_overflow") or {})
    return {
        "enabled": bool(raw.get("enabled", True)),
        "delimiter": str(raw.get("delimiter", ";")),
        "encoding": str(raw.get("encoding", "utf-8-sig")),
    }


def excel_max_rows_per_sheet(config: dict[str, Any]) -> int:
    """Макс. число строк данных на листе Excel; сверх — CSV."""
    raw: Any = config.get("output", {}).get("excel_max_rows_per_sheet", DEFAULT_EXCEL_MAX_ROWS)
    try:
        limit: int = int(raw)
    except (TypeError, ValueError):
        limit = DEFAULT_EXCEL_MAX_ROWS
    return max(1, limit)


def sheet_exceeds_excel_limit(frame: pd.DataFrame, config: dict[str, Any]) -> bool:
    """True — лист нужно выгрузить в CSV, а не во вкладку Excel."""
    overflow: dict[str, Any] = csv_overflow_config(config)
    if not overflow["enabled"] or frame.empty:
        return False
    return len(frame) > excel_max_rows_per_sheet(config)


def split_sheets_by_row_limit(
    sheets: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Делит листы на Excel и CSV по порогу строк."""
    excel_sheets: dict[str, pd.DataFrame] = {}
    csv_sheets: dict[str, pd.DataFrame] = {}
    limit: int = excel_max_rows_per_sheet(config)

    for key, frame in sheets.items():
        if sheet_exceeds_excel_limit(frame, config):
            csv_sheets[key] = frame
            logger.warning(
                "Лист '%s': %s строк > %s — экспорт в CSV вместо вкладки Excel",
                key,
                f"{len(frame):,}",
                f"{limit:,}",
            )
        else:
            excel_sheets[key] = frame

    return excel_sheets, csv_sheets


def csv_path_for_sheet(excel_path: Path, sheet_label: str) -> Path:
    """Путь CSV рядом с xlsx: {stem}_{безопасное_имя_листа}.csv"""
    stem: str = _INVALID_CSV_STEM_RE.sub("_", str(sheet_label).strip())
    stem = stem.strip("._ ") or "sheet"
    return excel_path.with_name(f"{excel_path.stem}_{stem}.csv")


def export_dataframe_csv(path: Path, frame: pd.DataFrame, config: dict[str, Any]) -> Path:
    """Сохраняет DataFrame в CSV с разделителем из config."""
    overflow: dict[str, Any] = csv_overflow_config(config)
    safe: pd.DataFrame = sanitize_dataframe(frame)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe.to_csv(
        path,
        index=False,
        sep=overflow["delimiter"],
        encoding=overflow["encoding"],
    )
    logger.info("CSV сохранён: %s (%s строк)", path, f"{len(safe):,}")
    return path


def export_overflow_csv_sheets(
    excel_path: Path,
    csv_sheets: dict[str, pd.DataFrame],
    sheet_titles: dict[str, str],
    config: dict[str, Any],
) -> list[Path]:
    """Записывает переполненные листы в отдельные CSV."""
    paths: list[Path] = []
    for key, frame in csv_sheets.items():
        label: str = sheet_titles.get(key, key)
        csv_path: Path = csv_path_for_sheet(excel_path, label)
        export_dataframe_csv(csv_path, frame, config)
        paths.append(csv_path)
    return paths


def build_csv_redirect_sheet(csv_paths: list[Path]) -> pd.DataFrame:
    """Служебный лист Excel со ссылками на CSV, если все данные ушли в файлы."""
    rows: list[dict[str, str]] = [
        {"Файл CSV": str(p.name), "Полный путь": str(p.resolve())} for p in csv_paths
    ]
    return pd.DataFrame(rows)
