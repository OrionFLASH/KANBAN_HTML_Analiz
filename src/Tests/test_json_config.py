"""Тесты загрузки JSON-конфига с контекстом ошибки."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.json_config import load_json_file
from src.v2.config_loader import load_excel_v2_config


def test_load_json_file_ok(tmp_path: Path) -> None:
    path: Path = tmp_path / "ok.json"
    path.write_text('{"mode": "test", "a": 1}\n', encoding="utf-8")
    data = load_json_file(path)
    assert data["mode"] == "test"


def test_load_json_file_missing_comma_shows_context(tmp_path: Path) -> None:
    """Пропущенная запятая — сообщение со строкой и контекстом."""
    path: Path = tmp_path / "bad.json"
    path.write_text(
        '{\n  "a": 1\n  "b": 2\n}\n',
        encoding="utf-8",
    )
    with pytest.raises(json.JSONDecodeError) as exc_info:
        load_json_file(path)
    msg: str = str(exc_info.value)
    assert "bad.json" in msg
    assert "строка" in msg
    assert "пропущена запятая" in msg.lower() or "Частые причины" in msg


def test_load_excel_v2_config_rejects_broken_json(tmp_path: Path) -> None:
    """load_excel_v2_config пробрасывает понятную JSON-ошибку."""
    broken: Path = tmp_path / "config_excel_v2.json"
    broken.write_text('{"mode": "prod"\n "paths": {}}\n', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError) as exc_info:
        load_excel_v2_config(broken)
    assert "config_excel_v2.json" in str(exc_info.value)
