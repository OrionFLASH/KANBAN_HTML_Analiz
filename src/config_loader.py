"""Загрузка и валидация config.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.performance import resolve_parallel_workers
from src.project_paths import resolve_path
from src.settings import normalize_config

VALID_DURATION_SOURCES: set[str] = {"columns", "dates"}
VALID_PRODUCT_ANALYSIS_MODES: set[str] = {"group_product", "group_only"}
VALID_STAGE_MODES: set[str] = {"status", "substages", "both"}
VALID_EXCEL_THEMES: set[str] = {"green_red", "minimal"}


def load_config(config_path: str | Path = "config.json") -> dict[str, Any]:
    """Загружает config.json, дополняет defaults и валидирует."""
    path: Path = resolve_path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {path}")

    with path.open(encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)

    config: dict[str, Any] = normalize_config(raw)
    _validate_config(config)
    _apply_defaults(config)
    return config


def _apply_defaults(config: dict[str, Any]) -> None:
    """Заполняет вычисляемые значения по умолчанию."""
    config["_parallel_workers_explicit"] = int(config.get("parallel_workers", 0))
    config["parallel_workers"] = resolve_parallel_workers(config)


def _validate_config(config: dict[str, Any]) -> None:
    """Проверяет обязательные ключи и допустимые значения."""
    if "mode" not in config:
        raise ValueError("В config.json отсутствует ключ: mode")
    if "paths" not in config:
        raise ValueError("В config.json отсутствует ключ: paths")
    if "columns" not in config:
        raise ValueError("В config.json отсутствует ключ: columns")

    mode: str = config["mode"]
    if mode not in {"test", "prod"}:
        raise ValueError("mode должен быть 'test' или 'prod'")

    duration: str = config.get("duration_source", "columns")
    if duration not in VALID_DURATION_SOURCES:
        raise ValueError(f"duration_source должен быть одним из: {VALID_DURATION_SOURCES}")

    stage_mode: str = config.get("stage_analysis_mode", "status")
    if stage_mode not in VALID_STAGE_MODES:
        raise ValueError(f"stage_analysis_mode должен быть одним из: {VALID_STAGE_MODES}")

    product_mode: str = config.get("product_analysis_mode", "group_product")
    if product_mode not in VALID_PRODUCT_ANALYSIS_MODES:
        raise ValueError(
            f"product_analysis_mode должен быть одним из: {VALID_PRODUCT_ANALYSIS_MODES}"
        )

    theme: str = config.get("excel_theme", "green_red")
    if theme not in VALID_EXCEL_THEMES:
        raise ValueError(f"excel_theme должен быть одним из: {VALID_EXCEL_THEMES}")

    percentiles: list[Any] = config.get("percentiles", [])
    if not percentiles:
        raise ValueError("percentiles не может быть пустым")

    for path_key in ("input_test", "input_prod", "output", "log"):
        if path_key not in config["paths"]:
            raise ValueError(f"paths.{path_key} обязателен")


def get_input_dir(config: dict[str, Any]) -> Path:
    """Возвращает каталог входных файлов по режиму."""
    paths: dict[str, str] = config["paths"]
    if config["mode"] == "test":
        return resolve_path(paths["input_test"])
    return resolve_path(paths["input_prod"])


def get_file_list(config: dict[str, Any]) -> list[str]:
    """Возвращает список имён файлов по режиму."""
    if config["mode"] == "test":
        return list(config.get("test_files", []))
    return list(config.get("prod_files", []))


def get_output_dir(config: dict[str, Any]) -> Path:
    """Возвращает каталог выходных файлов."""
    out: Path = resolve_path(config["paths"]["output"])
    out.mkdir(parents=True, exist_ok=True)
    return out


def get_log_dir(config: dict[str, Any]) -> Path:
    """Возвращает каталог логов."""
    log_dir: Path = resolve_path(config["paths"]["log"])
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir
