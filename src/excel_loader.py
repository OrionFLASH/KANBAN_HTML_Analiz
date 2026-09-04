"""Параллельная загрузка Excel-файлов Kanban."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd

from src.date_utils import parse_date_column
from src.performance import resolve_parallel_workers
from src.progress import ProgressReporter
from src.resource_guard import release_memory_if_needed
from src.settings import col, load_column_names, required_column_names

logger: logging.Logger = logging.getLogger("kanban.excel_loader")


def _detect_category(filename: str, config: dict[str, Any]) -> str:
    """Определяет категорию файла по имени (не используется в аналитике)."""
    markers: dict[str, str] = config["excel"]["category_markers"]
    if markers["for_sale"] in filename:
        return markers["for_sale"]
    if markers["in_work"] in filename:
        return markers["in_work"]
    return markers.get("unknown", "UNKNOWN")


def _openpyxl_engine_kwargs(config: dict[str, Any]) -> dict[str, Any]:
    """Параметры openpyxl: потоковое чтение листа с заголовком."""
    excel_cfg: dict[str, Any] = config.get("excel") or {}
    return {
        "read_only": bool(excel_cfg.get("read_only", True)),
        "data_only": bool(excel_cfg.get("data_only", True)),
        "keep_links": bool(excel_cfg.get("keep_links", False)),
    }


def _read_excel_dataframe(
    file_path: Path,
    config: dict[str, Any],
    use_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Читает лист Excel целиком (первая строка — заголовок), без именованных таблиц."""
    excel_cfg: dict[str, Any] = config["excel"]
    sheet_name: str = excel_cfg["sheet_name"]
    engine: str = str(excel_cfg.get("engine", "openpyxl"))
    na_values: list[str] = list(excel_cfg.get("na_values", [""]))

    read_kwargs: dict[str, Any] = {
        "sheet_name": sheet_name,
        "engine": engine,
        "na_values": na_values,
    }
    if engine == "openpyxl":
        read_kwargs["engine_kwargs"] = _openpyxl_engine_kwargs(config)

    if use_columns:
        wanted: set[str] = {str(c) for c in use_columns}
        # Callable — один проход, без отдельного открытия за шапкой
        read_kwargs["usecols"] = lambda c, _w=wanted: str(c) in _w

    return pd.read_excel(file_path, **read_kwargs)


def read_single_file(args: tuple[str, dict[str, Any]]) -> pd.DataFrame:
    """Читает один Excel-файл (для ProcessPoolExecutor)."""
    file_path_str, config = args
    file_path: Path = Path(file_path_str)
    perf: dict[str, Any] = config.get("performance", {})

    use_columns: list[str] | None = None
    if perf.get("read_only_required_columns", True):
        # Обязательные + опциональные; отсутствующие optional просто не попадут в usecols-callable
        use_columns = load_column_names(config)

    df: pd.DataFrame = _read_excel_dataframe(file_path, config, use_columns)
    _validate_columns(df, file_path, config)
    df = _normalize_types(df, config)

    if perf.get("downcast_numeric", True):
        df = _downcast_frame(df, config)

    df["source_file"] = file_path.name
    df["source_category"] = _detect_category(file_path.name, config)
    return df


def _validate_columns(df: pd.DataFrame, file_path: Path, config: dict[str, Any]) -> None:
    """Проверяет наличие обязательных колонок."""
    required: list[str] = required_column_names(config)
    missing: list[str] = [name for name in required if name not in df.columns]
    if missing:
        raise ValueError(f"{file_path.name}: отсутствуют колонки: {missing}")


def _downcast_frame(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """
    Уменьшает типы флагов для экономии памяти.
    Колонки сроков (days_*) не downcast — сохраняем точные значения из Excel.
    """
    c: dict[str, str] = config["columns"]
    flag_keys: tuple[str, ...] = ("change_conditions", "data_entry", "efs_flag")
    for key in flag_keys:
        name: str = c[key]
        if name in df.columns:
            df[name] = pd.to_numeric(df[name], errors="coerce", downcast="integer")
    return df


def _normalize_types(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Приводит ключевые колонки к нужным типам (без лишней копии DataFrame)."""
    c: dict[str, str] = config["columns"]

    for key in ("report_date", "work_start_date", "deal_created_date"):
        name: str = c[key]
        if name in df.columns:
            df[name] = parse_date_column(df[name], config, name)

    for key in ("days_on_stage", "days_since_deal", "change_conditions", "data_entry", "efs_flag"):
        name = c[key]
        if name in df.columns:
            df[name] = pd.to_numeric(df[name], errors="coerce")

    for key in ("current_status", "deal_stage", "product_group", "product", "tb", "lead_id"):
        name = c[key]
        if name in df.columns:
            df[name] = df[name].astype(str).str.strip()

    km_key: str | None = c.get("km")
    if km_key and km_key in df.columns:
        df[km_key] = df[km_key].astype(str).str.strip()

    deal_stage_col: str = c["deal_stage"]
    if deal_stage_col in df.columns:
        df[deal_stage_col] = df[deal_stage_col].replace("nan", "")

    return df


def load_all_files(
    config: dict[str, Any],
    input_dir: Path,
    filenames: list[str],
    progress: ProgressReporter | None = None,
) -> pd.DataFrame:
    """Параллельно загружает все файлы и объединяет в один DataFrame."""
    paths: list[Path] = [input_dir / name for name in filenames]
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Входной файл не найден: {path}")

    workers: int = resolve_parallel_workers(config)
    total: int = len(paths)

    if progress:
        progress.stage(
            "Загрузка Excel",
            f"{total} файл(ов), workers={workers}",
        )

    frames: list[pd.DataFrame] = []

    if workers == 1 or total == 1:
        for idx, path in enumerate(paths, start=1):
            size_mb: float = path.stat().st_size / (1024 * 1024)
            if progress:
                progress.step(
                    f"[{idx}/{total}] Чтение {path.name} ({size_mb:.1f} МБ)…"
                )
            t0: float = time.monotonic()
            frame: pd.DataFrame = read_single_file((str(path), config))
            frames.append(frame)
            elapsed: float = time.monotonic() - t0
            msg: str = f"[{idx}/{total}] {path.name}: {len(frame):,} строк за {elapsed:.1f} сек"
            logger.info(msg)
            if progress:
                progress.step(msg)
            release_memory_if_needed(config, logger, checkpoint=path.name)
    else:
        args_list: list[tuple[str, dict[str, Any]]] = [(str(p), config) for p in paths]
        done: int = 0
        if progress:
            for path in paths:
                size_mb = path.stat().st_size / (1024 * 1024)
                progress.step(f"В очереди: {path.name} ({size_mb:.1f} МБ)")

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(read_single_file, args): args[0] for args in args_list}
            for future in as_completed(futures):
                path_str: str = futures[future]
                done += 1
                try:
                    frame = future.result()
                    frames.append(frame)
                    msg = (
                        f"[{done}/{total}] {Path(path_str).name}: "
                        f"{len(frame):,} строк загружено"
                    )
                    logger.info(msg)
                    if progress:
                        progress.step(msg)
                    release_memory_if_needed(config, logger, checkpoint=Path(path_str).name)
                except Exception as exc:
                    logger.error("Ошибка загрузки %s: %s", path_str, exc)
                    raise

    if not frames:
        raise ValueError("Не удалось загрузить ни одного файла")

    if progress:
        progress.step(f"Объединение {len(frames)} таблиц…")

    combined: pd.DataFrame = pd.concat(frames, ignore_index=True, copy=False)
    logger.info(
        "Объединено строк: %d из %d файлов (все строки файлов сохранены)",
        len(combined),
        len(frames),
    )
    if progress:
        progress.done(f"Загрузка: {len(combined):,} строк из {len(frames)} файлов — полный объём")
    return combined
