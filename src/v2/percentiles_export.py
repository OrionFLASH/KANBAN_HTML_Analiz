"""Экспорт исходных строк под фильтры процентилей (+ split по ТБ при >1M строк)."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd

from src.manager_emails import (
    EmailLookup,
    enrich_snapshot_with_manager_emails,
    load_manager_email_lookup,
    manager_emails_enabled,
)
from src.settings import col
from src.v2.team_enrich import enrich_snapshot_with_team_dfs

logger: logging.Logger = logging.getLogger("kanban.excel_v2.percentiles_export")

_INVALID_SHEET_RE: re.Pattern[str] = re.compile(r"[\\/*?:\[\]]+")
_INVALID_FILE_RE: re.Pattern[str] = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')

SPLIT_MODE_FILES: str = "files"
SPLIT_MODE_SHEETS: str = "sheets"


def percentiles_export_cfg(config: dict[str, Any]) -> dict[str, Any]:
    """Блок output.percentiles_export."""
    raw: Any = (config.get("output") or {}).get("percentiles_export") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def percentiles_export_enabled(config: dict[str, Any]) -> bool:
    """Нужен ли файл percentiles (по умолчанию да, если report_parts включает)."""
    cfg: dict[str, Any] = percentiles_export_cfg(config)
    if "enabled" in cfg:
        return bool(cfg["enabled"])
    return True


def percentiles_split_threshold(config: dict[str, Any]) -> int:
    """Порог строк для разбиения по ТБ."""
    cfg: dict[str, Any] = percentiles_export_cfg(config)
    return int(cfg.get("split_by_tb_over_rows", 1_000_000))


def percentiles_split_mode(config: dict[str, Any]) -> str:
    """
    Режим split при превышении порога:
    - files (default) — отдельный Excel на каждый ТБ;
    - sheets — несколько листов в одном файле (старое поведение).
    """
    cfg: dict[str, Any] = percentiles_export_cfg(config)
    raw: str = str(cfg.get("split_mode") or SPLIT_MODE_FILES).strip().lower()
    if raw in {"sheet", "sheets", "листы", "лист"}:
        return SPLIT_MODE_SHEETS
    return SPLIT_MODE_FILES


def build_percentiles_export_frame(
    filtered_df: pd.DataFrame,
    config: dict[str, Any],
    *,
    lead_team_df: pd.DataFrame | None = None,
    deal_team_df: pd.DataFrame | None = None,
    email_lookup: EmailLookup | None = None,
) -> pd.DataFrame:
    """
    Строки после фильтров процентилей (analytics) + лидеры/почты.
    Данные уже отфильтрованы pipeline — здесь только обогащение.
    """
    if filtered_df.empty:
        return filtered_df.copy()

    result: pd.DataFrame = filtered_df.copy()
    lead_df: pd.DataFrame = lead_team_df if lead_team_df is not None else pd.DataFrame()
    deal_df: pd.DataFrame = deal_team_df if deal_team_df is not None else pd.DataFrame()
    if not lead_df.empty or not deal_df.empty:
        result = enrich_snapshot_with_team_dfs(result, lead_df, deal_df, config)

    if manager_emails_enabled(config):
        lookup: EmailLookup = (
            email_lookup if email_lookup is not None else load_manager_email_lookup(config)
        )
        result = enrich_snapshot_with_manager_emails(result, config, lookup=lookup)

    logger.info("Percentiles export: %s строк", f"{len(result):,}")
    return result.reset_index(drop=True)


def _safe_sheet_name(raw: str, max_len: int = 31) -> str:
    """Безопасное имя листа Excel."""
    text: str = _INVALID_SHEET_RE.sub("_", str(raw).strip()) or "ТБ"
    return text[:max_len]


def _safe_file_token(raw: str, max_len: int = 40) -> str:
    """Фрагмент имени файла без запрещённых символов ОС."""
    text: str = _INVALID_FILE_RE.sub("_", str(raw).strip())
    text = re.sub(r"\s+", "_", text).strip("._") or "TB"
    return text[:max_len]


def _tb_label(prefix: str, tb_value: Any) -> str:
    """Человекочитаемая метка ТБ."""
    if tb_value is None:
        text = ""
    else:
        try:
            text = "" if pd.isna(tb_value) else str(tb_value).strip()
        except (TypeError, ValueError):
            text = str(tb_value).strip()
    return f"{prefix} {text}" if text else f"{prefix} _"


def _tb_mask(series: pd.Series, tb_value: Any) -> pd.Series:
    """Маска строк для одного значения ТБ (включая NA)."""
    if tb_value is None:
        return series.isna()
    try:
        if pd.isna(tb_value):
            return series.isna()
    except (TypeError, ValueError):
        pass
    return series == tb_value


def _sheet_name_prefix(cfg: dict[str, Any]) -> str:
    """Префикс имени листа/файла ТБ."""
    return str(cfg.get("sheet_name_prefix") or "ТБ")


def count_percentiles_export_jobs(
    frame: pd.DataFrame,
    config: dict[str, Any],
) -> int:
    """Сколько файлов будет записано (без материализации чанков)."""
    threshold: int = percentiles_split_threshold(config)
    if frame.empty or len(frame) <= threshold:
        return 1
    if percentiles_split_mode(config) == SPLIT_MODE_SHEETS:
        return 1
    tb_col: str = col(config, "tb")
    if tb_col not in frame.columns:
        return 1
    return int(frame[tb_col].nunique(dropna=False))


def split_percentiles_sheets_by_tb(
    frame: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """
    Если строк > split_by_tb_over_rows — отдельные листы по ТБ.
    Иначе один лист «percentiles».
    """
    cfg: dict[str, Any] = percentiles_export_cfg(config)
    threshold: int = percentiles_split_threshold(config)
    prefix: str = _sheet_name_prefix(cfg)
    max_name: int = int(config.get("output", {}).get("excel_max_sheet_name_length", 31))

    if frame.empty or len(frame) <= threshold:
        return {"percentiles": frame}

    tb_col: str = col(config, "tb")
    if tb_col not in frame.columns:
        logger.warning(
            "Percentiles: строк %s > %s, но нет колонки ТБ — один лист",
            f"{len(frame):,}",
            f"{threshold:,}",
        )
        return {"percentiles": frame}

    sheets: dict[str, pd.DataFrame] = {}
    used_names: set[str] = set()
    for tb_value, group in frame.groupby(tb_col, sort=False, dropna=False):
        label_raw: str = _tb_label(prefix, tb_value)
        name: str = _safe_sheet_name(label_raw, max_name)
        base: str = name
        n: int = 2
        while name in used_names:
            suffix: str = f"_{n}"
            name = _safe_sheet_name(base[: max_name - len(suffix)] + suffix, max_name)
            n += 1
        used_names.add(name)
        sheets[name] = group.reset_index(drop=True)

    logger.info(
        "Percentiles: %s строк > %s — разбито на %s листов по ТБ",
        f"{len(frame):,}",
        f"{threshold:,}",
        len(sheets),
    )
    return sheets


def build_percentiles_tb_path(base_path: Path, tb_label: str) -> Path:
    """Путь файла percentiles для одного ТБ: `{stem}_{safe_tb}.xlsx`."""
    token: str = _safe_file_token(tb_label)
    return base_path.with_name(f"{base_path.stem}_{token}{base_path.suffix}")


def iter_percentiles_export_jobs(
    frame: pd.DataFrame,
    config: dict[str, Any],
    base_path: Path,
) -> Iterator[tuple[Path, dict[str, pd.DataFrame], str]]:
    """
    Задания на запись percentiles: (путь, {ключ_листа: frame}, метка для лога).

    При split_mode=files и превышении порога — по одному файлу на ТБ
    (чанк отдаётся по очереди). При sheets / ниже порога — один файл.
    """
    threshold: int = percentiles_split_threshold(config)
    mode: str = percentiles_split_mode(config)
    cfg: dict[str, Any] = percentiles_export_cfg(config)
    prefix: str = _sheet_name_prefix(cfg)

    if frame.empty or len(frame) <= threshold:
        yield base_path, {"percentiles": frame}, "single"
        return

    if mode == SPLIT_MODE_SHEETS:
        sheets = split_percentiles_sheets_by_tb(frame, config)
        yield base_path, sheets, f"sheets×{len(sheets)}"
        return

    tb_col: str = col(config, "tb")
    if tb_col not in frame.columns:
        logger.warning(
            "Percentiles files: строк %s > %s, но нет колонки ТБ — один файл",
            f"{len(frame):,}",
            f"{threshold:,}",
        )
        yield base_path, {"percentiles": frame}, "single"
        return

    tb_series: pd.Series = frame[tb_col]
    ordered_values: list[Any] = list(tb_series.drop_duplicates(keep="first").tolist())
    used_paths: set[str] = set()
    logger.info(
        "Percentiles: %s строк > %s — %s отдельных файлов по ТБ (split_mode=files)",
        f"{len(frame):,}",
        f"{threshold:,}",
        len(ordered_values),
    )

    for tb_value in ordered_values:
        label: str = _tb_label(prefix, tb_value)
        path: Path = build_percentiles_tb_path(base_path, label)
        if path.name in used_paths:
            n = 2
            while path.name in used_paths:
                path = base_path.with_name(
                    f"{base_path.stem}_{_safe_file_token(label)}_{n}{base_path.suffix}"
                )
                n += 1
        used_paths.add(path.name)
        chunk: pd.DataFrame = frame.loc[_tb_mask(tb_series, tb_value)].reset_index(drop=True)
        yield path, {"percentiles": chunk}, label
