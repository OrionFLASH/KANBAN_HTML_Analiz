"""Настройка логирования INFO/DEBUG в каталог log/."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config_loader import get_log_dir

# Дочерние модули пишут в kanban.* / kanban.excel_v2.* — их нужно
# подключить к тем же handlers, что и основной logger_name из config.
_SHARED_LOGGER_ROOTS: tuple[str, ...] = ("kanban", "kanban.excel_v2")


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
    logger.propagate = False

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

    _attach_shared_module_loggers(logger, level)
    _capture_python_warnings(logger)
    return logger


def _capture_python_warnings(primary: logging.Logger) -> None:
    """
    Перенаправляет warnings (FutureWarning и др.) в те же handlers, что и pipeline.
    Иначе они только в stderr консоли и не видны в INFO/DEBUG логах.
    """
    logging.captureWarnings(True)
    warn_logger: logging.Logger = logging.getLogger("py.warnings")
    warn_logger.setLevel(logging.WARNING)
    warn_logger.handlers.clear()
    for handler in primary.handlers:
        warn_logger.addHandler(handler)
    warn_logger.propagate = False


def _attach_shared_module_loggers(primary: logging.Logger, level: int) -> None:
    """
    Подключает семейство kanban.* к handlers основного логгера.
    Иначе team_loader / team_enrich / snapshot пишут «в никуда»
    при logger_name=kanban_excel_v2.
    """
    for root_name in _SHARED_LOGGER_ROOTS:
        if root_name == primary.name:
            continue
        shared: logging.Logger = logging.getLogger(root_name)
        shared.setLevel(level)
        shared.handlers.clear()
        for handler in primary.handlers:
            shared.addHandler(handler)
        # Дети (kanban.team_loader и т.п.) propagate → shared
        shared.propagate = False
