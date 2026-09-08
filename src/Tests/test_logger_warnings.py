"""Тесты перенаправления Python warnings в лог-файлы."""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

from src.logger_setup import setup_logger


def test_python_warnings_go_to_log_file(tmp_path: Path) -> None:
    """FutureWarning и др. попадают в INFO/DEBUG лог, а не только в stderr."""
    log_dir: Path = tmp_path / "log"
    log_dir.mkdir()
    config: dict = {
        "paths": {"log": str(log_dir)},
        "logging": {
            "logger_name": "kanban_test_warn",
            "info_file_prefix": "INFO_warn",
            "debug_file_prefix": "DEBUG_warn",
            "hour_format": "%Y%m%d_%H",
        },
    }
    logger: logging.Logger = setup_logger(config)
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        warnings.warn("тестовое предупреждение fillna", FutureWarning)

    for handler in logger.handlers:
        handler.flush()

    info_files: list[Path] = list(log_dir.glob("INFO_warn_*.log"))
    assert info_files, "INFO лог не создан"
    text: str = info_files[0].read_text(encoding="utf-8")
    assert "тестовое предупреждение fillna" in text
    assert "WARNING" in text
