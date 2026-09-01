"""Тесты проверки наличия входных файлов."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.input_files_check import (
    InputFilesMissingError,
    collect_required_input_files,
    ensure_input_files_exist,
    find_missing_input_files,
)


def _base_config(tmp_path: Path) -> dict:
    """Минимальный config для проверки файлов."""
    input_dir: Path = tmp_path / "IN" / "PROD"
    input_dir.mkdir(parents=True)
    return {
        "mode": "prod",
        "paths": {
            "input_test": str(tmp_path / "IN" / "TEST"),
            "input_prod": str(input_dir),
            "output": str(tmp_path / "OUT"),
            "log": str(tmp_path / "log"),
        },
        "test_files": ["test_kanban.xlsx"],
        "prod_files": ["kanban_a.xlsx", "kanban_b.xlsx"],
        "manager_analytics": {
            "team_files": {
                "enabled": True,
                "lead_team": {"prod": ["team_lead.xlsx"]},
                "deal_team": {"prod": ["team_deal.xlsx"]},
            }
        },
    }


def test_collect_required_input_files_prod(tmp_path: Path) -> None:
    """Собирает Kanban и файлы команд для prod."""
    config: dict = _base_config(tmp_path)
    items: list[tuple[str, str]] = collect_required_input_files(config)
    assert items == [
        ("Kanban", "kanban_a.xlsx"),
        ("Kanban", "kanban_b.xlsx"),
        ("Команда лида", "team_lead.xlsx"),
        ("Команда сделки", "team_deal.xlsx"),
    ]


def test_ensure_input_files_exist_ok(tmp_path: Path) -> None:
    """Все файлы на месте — ошибки нет."""
    config: dict = _base_config(tmp_path)
    input_dir: Path = Path(config["paths"]["input_prod"])
    for _, name in collect_required_input_files(config):
        (input_dir / name).write_text("x", encoding="utf-8")
    ensure_input_files_exist(config, logging.getLogger("test"))


def test_ensure_input_files_exist_missing(tmp_path: Path) -> None:
    """Отсутствующие файлы — InputFilesMissingError и остановка."""
    config: dict = _base_config(tmp_path)
    input_dir: Path = Path(config["paths"]["input_prod"])
    (input_dir / "kanban_a.xlsx").write_text("x", encoding="utf-8")

    with pytest.raises(InputFilesMissingError) as exc_info:
        ensure_input_files_exist(config)

    err: InputFilesMissingError = exc_info.value
    missing_names: set[str] = {name for _, name in err.missing}
    assert "kanban_b.xlsx" in missing_names
    assert "team_lead.xlsx" in missing_names
    assert "Обработка остановлена" in str(err)


def test_find_missing_test_mode(tmp_path: Path) -> None:
    """В test-режиме проверяются test_files из input_test."""
    config: dict = _base_config(tmp_path)
    config["mode"] = "test"
    test_dir: Path = tmp_path / "IN" / "TEST"
    test_dir.mkdir(parents=True)
    config["paths"]["input_test"] = str(test_dir)
    config["manager_analytics"]["team_files"]["lead_team"] = {"test": ["team_lead.xlsx"]}
    config["manager_analytics"]["team_files"]["deal_team"] = {"test": []}

    missing: list[tuple[str, str]] = find_missing_input_files(config)
    assert ("Kanban", "test_kanban.xlsx") in missing
    assert ("Команда лида", "team_lead.xlsx") in missing
