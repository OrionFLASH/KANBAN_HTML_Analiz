"""Параллельная загрузка Excel-файлов Kanban."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import load_workbook

from src.settings import required_column_names

logger: logging.Logger = logging.getLogger("kanban.excel_loader")


def _detect_category(filename: str, config: dict[str, Any]) -> str:
    """Определяет категорию файла по имени (не используется в аналитике)."""
    markers: dict[str, str] = config["excel"]["category_markers"]
    if markers["for_sale"] in filename:
        return markers["for_sale"]
    if markers["in_work"] in filename:
        return markers["in_work"]
    return markers.get("unknown", "UNKNOWN")


def _resolve_table_range(
    file_path: Path,
    sheet_name: str,
    table_name: str,
) -> str | None:
    """Возвращает диапазон именованной таблицы Excel или None."""
    wb = load_workbook(file_path, read_only=False, data_only=True)
    try:
        if sheet_name not in wb.sheetnames:
            return None
        ws = wb[sheet_name]
        for tbl in ws.tables.values():
            if tbl.name == table_name:
                return tbl.ref
        return None
    finally:
        wb.close()


def _read_table_range(
    file_path: Path,
    sheet_name: str,
    cell_range: str,
    engine: str,
    na_values: list[str],
) -> pd.DataFrame:
    """Читает именованную таблицу Excel по диапазону ref."""
    match = re.match(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", cell_range.replace("$", ""))
    if not match:
        raise ValueError(f"Некорректный диапазон таблицы: {cell_range}")

    start_row: int = int(match.group(2))
    end_row: int = int(match.group(4))
    return pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        engine=engine,
        header=start_row - 1,
        nrows=end_row - start_row,
        na_values=na_values,
    )


def read_single_file(args: tuple[str, dict[str, Any]]) -> pd.DataFrame:
    """Читает один Excel-файл (для ProcessPoolExecutor)."""
    file_path_str, config = args
    file_path: Path = Path(file_path_str)
    excel_cfg: dict[str, Any] = config["excel"]
    sheet_name: str = excel_cfg["sheet_name"]
    table_name: str = excel_cfg["table_name"]
    use_auto: bool = bool(excel_cfg.get("table_auto", True))
    engine: str = excel_cfg.get("engine", "openpyxl")
    na_values: list[str] = list(excel_cfg.get("na_values", [""]))

    df: pd.DataFrame
    if use_auto:
        cell_range: str | None = _resolve_table_range(file_path, sheet_name, table_name)
        if cell_range:
            df = _read_table_range(file_path, sheet_name, cell_range, engine, na_values)
        else:
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                engine=engine,
                na_values=na_values,
            )
    else:
        df = pd.read_excel(
            file_path,
            sheet_name=sheet_name,
            engine=engine,
            na_values=na_values,
        )

    _validate_columns(df, file_path, config)
    df = _normalize_types(df, config)
    df["source_file"] = file_path.name
    df["source_category"] = _detect_category(file_path.name, config)
    return df


def _validate_columns(df: pd.DataFrame, file_path: Path, config: dict[str, Any]) -> None:
    """Проверяет наличие обязательных колонок."""
    required: list[str] = required_column_names(config)
    missing: list[str] = [name for name in required if name not in df.columns]
    if missing:
        raise ValueError(f"{file_path.name}: отсутствуют колонки: {missing}")


def _normalize_types(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Приводит ключевые колонки к нужным типам."""
    result: pd.DataFrame = df.copy()
    c = config["columns"]

    date_keys: list[str] = ["report_date", "work_start_date", "deal_created_date"]
    for key in date_keys:
        name: str = c[key]
        if name in result.columns:
            result[name] = pd.to_datetime(result[name], errors="coerce")

    numeric_keys: list[str] = [
        "days_on_stage",
        "days_since_deal",
        "change_conditions",
        "data_entry",
        "efs_flag",
    ]
    for key in numeric_keys:
        name = c[key]
        if name in result.columns:
            result[name] = pd.to_numeric(result[name], errors="coerce")

    text_keys: list[str] = [
        "current_status",
        "deal_stage",
        "product_group",
        "product",
        "tb",
        "lead_id",
    ]
    for key in text_keys:
        name = c[key]
        if name in result.columns:
            result[name] = result[name].astype(str).str.strip()

    deal_stage_col: str = c["deal_stage"]
    if deal_stage_col in result.columns:
        result[deal_stage_col] = result[deal_stage_col].replace("nan", "")

    return result


def load_all_files(config: dict[str, Any], input_dir: Path, filenames: list[str]) -> pd.DataFrame:
    """Параллельно загружает все файлы и объединяет в один DataFrame."""
    paths: list[Path] = [input_dir / name for name in filenames]
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Входной файл не найден: {path}")

    workers: int = int(config.get("parallel_workers", 4))
    args_list: list[tuple[str, dict[str, Any]]] = [(str(p), config) for p in paths]

    frames: list[pd.DataFrame] = []
    if workers == 1 or len(paths) == 1:
        for args in args_list:
            frames.append(read_single_file(args))
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(read_single_file, args): args[0] for args in args_list}
            for future in as_completed(futures):
                path_str: str = futures[future]
                try:
                    frames.append(future.result())
                    logger.info("Загружен файл: %s", Path(path_str).name)
                except Exception as exc:
                    logger.error("Ошибка загрузки %s: %s", path_str, exc)
                    raise

    if not frames:
        raise ValueError("Не удалось загрузить ни одного файла")

    combined: pd.DataFrame = pd.concat(frames, ignore_index=True)
    logger.info("Объединено строк: %d из %d файлов", len(combined), len(frames))
    return combined
