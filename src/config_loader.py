"""Загрузка и валидация config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


VALID_DURATION_SOURCES: set[str] = {"columns", "dates"}
VALID_STAGE_MODES: set[str] = {"status", "substages", "both"}
VALID_EXCEL_THEMES: set[str] = {"green_red", "minimal"}


def load_config(config_path: str | Path = "config.json") -> dict[str, Any]:
    """Загружает config.json и применяет значения по умолчанию."""
    path: Path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {path}")

    with path.open(encoding="utf-8") as fh:
        config: dict[str, Any] = json.load(fh)

    _validate_config(config)
    _apply_defaults(config)
    return config


def _apply_defaults(config: dict[str, Any]) -> None:
    """Заполняет значения по умолчанию."""
    workers: int = int(config.get("parallel_workers", 0))
    if workers <= 0:
        config["parallel_workers"] = os.cpu_count() or 4


def _validate_config(config: dict[str, Any]) -> None:
    """Проверяет обязательные ключи и допустимые значения."""
    required_roots: list[str] = ["mode", "paths", "sheet_name", "percentiles"]
    for key in required_roots:
        if key not in config:
            raise ValueError(f"В config.json отсутствует ключ: {key}")

    mode: str = config["mode"]
    if mode not in {"test", "prod"}:
        raise ValueError("mode должен быть 'test' или 'prod'")

    duration: str = config.get("duration_source", "columns")
    if duration not in VALID_DURATION_SOURCES:
        raise ValueError(f"duration_source должен быть одним из: {VALID_DURATION_SOURCES}")

    stage_mode: str = config.get("stage_analysis_mode", "status")
    if stage_mode not in VALID_STAGE_MODES:
        raise ValueError(f"stage_analysis_mode должен быть одним из: {VALID_STAGE_MODES}")

    theme: str = config.get("excel_theme", "green_red")
    if theme not in VALID_EXCEL_THEMES:
        raise ValueError(f"excel_theme должен быть одним из: {VALID_EXCEL_THEMES}")

    percentiles: list[Any] = config.get("percentiles", [])
    if not percentiles:
        raise ValueError("percentiles не может быть пустым")


def get_input_dir(config: dict[str, Any]) -> Path:
    """Возвращает каталог входных файлов по режиму."""
    paths: dict[str, str] = config["paths"]
    if config["mode"] == "test":
        return Path(paths["input_test"])
    return Path(paths["input_prod"])


def get_file_list(config: dict[str, Any]) -> list[str]:
    """Возвращает список имён файлов по режиму."""
    if config["mode"] == "test":
        return list(config.get("test_files", []))
    return list(config.get("prod_files", []))


def get_output_dir(config: dict[str, Any]) -> Path:
    """Возвращает каталог выходных файлов."""
    out: Path = Path(config["paths"]["output"])
    out.mkdir(parents=True, exist_ok=True)
    return out
