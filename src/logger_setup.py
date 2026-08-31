"""Настройка логирования INFO/DEBUG в каталог log/."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = "kanban", level: int = logging.DEBUG) -> logging.Logger:
    """Создаёт логгер с выводом в файл и консоль."""
    log_dir: Path = Path("log")
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp: str = datetime.now().strftime("%Y%m%d_%H")
    log_file: Path = log_dir / f"INFO_kanban_{timestamp}.log"
    debug_file: Path = log_dir / f"DEBUG_kanban_{timestamp}.log"

    logger: logging.Logger = logging.getLogger(name)
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
