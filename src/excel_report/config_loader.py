"""Загрузка config_excel_v2.json."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.config_loader import get_file_list, get_input_dir, get_output_dir
from src.performance import resolve_parallel_workers
from src.project_paths import resolve_path
from src.settings import normalize_config


def load_excel_v2_config(config_path: str | Path = "config_excel_v2.json") -> dict[str, Any]:
    """Загружает и нормализует конфиг Excel v2."""
    path: Path = resolve_path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Конфиг Excel v2 не найден: {path}")

    with path.open(encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)

    config: dict[str, Any] = normalize_config(raw)
    _validate_excel_v2_config(config)
    config["parallel_workers"] = resolve_parallel_workers(config)
    return config


def _validate_excel_v2_config(config: dict[str, Any]) -> None:
    """Минимальная валидация конфига v2."""
    if config.get("mode") not in {"test", "prod"}:
        raise ValueError("mode должен быть 'test' или 'prod'")
    for key in ("input_test", "input_prod", "output", "log"):
        if key not in config.get("paths", {}):
            raise ValueError(f"paths.{key} обязателен")
    if not config.get("percentiles"):
        raise ValueError("percentiles не может быть пустым")


def config_for_shared_modules(config: dict[str, Any]) -> dict[str, Any]:
    """
    Адаптирует v2-конфиг для общих модулей (team_loader, excel_loader).
    team_files в v2 лежит в корне, team_loader ожидает manager_analytics.team_files.
    """
    merged: dict[str, Any] = deepcopy(config)
    team_files: dict[str, Any] = dict(config.get("team_files") or {})
    merged.setdefault("manager_analytics", {})["team_files"] = team_files
    return merged


def get_excel_v2_input_dir(config: dict[str, Any]) -> Path:
    """Каталог входных Excel по режиму."""
    return get_input_dir(config)


def get_excel_v2_file_list(config: dict[str, Any]) -> list[str]:
    """Список файлов Kanban по режиму."""
    return get_file_list(config)


def get_excel_v2_output_dir(config: dict[str, Any]) -> Path:
    """Каталог выходных Excel v2."""
    return get_output_dir(config)
