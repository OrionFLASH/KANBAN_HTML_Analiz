"""Настройка логирования INFO/DEBUG в каталог log/."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config_loader import get_log_dir


def setup_logger(config: dict[str, Any] | None = None, level: int = logging.DEBUG) -> logging.Logger:
    """Создаёт логгер с выводом в файл и консоль."""
    log_cfg: dict[str, Any] = (config or {}).get("logging", {})
    logger_name: str = log_cfg.get("logger_name", "kanban")
    hour_fmt: str = log_cfg.get("hour_format", "%Y%m%d_%H")
    info_prefix: str = log_cfg.get("info_file_prefix", "INFO_kanban")
    debug_prefix: str = log_cfg.get("debug_file_prefix", "DEBUG_kanban")

    log_dir: Path
    if config is not None:
        log_dir = get_log_dir(config)
    else:
        from src.project_paths import resolve_path

        log_dir = resolve_path("log")
        log_dir.mkdir(parents=True, exist_ok=True)

    timestamp: str = datetime.now().strftime(hour_fmt)
    log_file: Path = log_dir / f"{info_prefix}_{timestamp}.log"
    debug_file: Path = log_dir / f"{debug_prefix}_{timestamp}.log"

    logger: logging.Logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.handlers.clear()

    fmt: logging.Formatter = logging.Formatter(
        "%(asctime)s - [%(levelname)s] - %(message)s [class: %(name)s | def: %(funcName)s]"
    )

    info_handler: logging.FileHandler = logging.FileHandler(log_file, encoding="utf-8")
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(fmt)
    logger.addHandler(info_handler)

    debug_handler: logging.FileHandler = logging.FileHandler(debug_file, encoding="utf-8")
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(fmt)
    logger.addHandler(debug_handler)

    console: logging.StreamHandler = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    logger.addHandler(console)

    return logger
