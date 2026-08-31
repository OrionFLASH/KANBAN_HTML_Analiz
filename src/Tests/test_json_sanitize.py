"""Тесты санитизации JSON (NaN → null)."""

from __future__ import annotations

import json
import math
from pathlib import Path

from src.json_sanitize import dump_json_file, sanitize_for_json


def test_sanitize_nan_inf_to_none() -> None:
    payload = {
        "ok": 1.5,
        "bad": float("nan"),
        "inf": float("inf"),
        "nested": [{"x": float("nan")}, math.nan],
    }
    clean = sanitize_for_json(payload)
    assert clean["ok"] == 1.5
    assert clean["bad"] is None
    assert clean["inf"] is None
    assert clean["nested"][0]["x"] is None
    assert clean["nested"][1] is None


def test_dump_json_file_browser_valid(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    dump_json_file(path, {"days_int": float("nan"), "v": 1}, compact=True)
    text = path.read_text(encoding="utf-8")
    assert "NaN" not in text
    data = json.loads(text)
    assert data["days_int"] is None
    assert data["v"] == 1
