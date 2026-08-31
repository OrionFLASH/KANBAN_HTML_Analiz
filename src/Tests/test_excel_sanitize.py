"""Тесты санитизации Excel."""

from __future__ import annotations

import math

import pandas as pd

from src.excel_sanitize import sanitize_cell_value, sanitize_dataframe, sanitize_sheet_name


def test_sanitize_sheet_name_invalid_chars() -> None:
    used: set[str] = set()
    assert sanitize_sheet_name('ТБ/ЮЗБ[1]', used) == "ТБ ЮЗБ 1"


def test_sanitize_sheet_name_collision() -> None:
    used: set[str] = set()
    first: str = sanitize_sheet_name("A" * 40, used, max_len=31)
    second: str = sanitize_sheet_name("A" * 40, used, max_len=31)
    assert first != second
    assert len(first) <= 31
    assert len(second) <= 31


def test_sanitize_cell_value_nan() -> None:
    assert sanitize_cell_value(float("nan")) is None
    assert sanitize_cell_value(float("inf")) is None
    assert sanitize_cell_value("nan") is None


def test_sanitize_cell_value_illegal_xml() -> None:
    assert sanitize_cell_value("OK\x07BAD") == "OKBAD"


def test_sanitize_dataframe() -> None:
    frame: pd.DataFrame = pd.DataFrame({"a": [1, math.nan], "b": ["x\x01", "y"]})
    clean: pd.DataFrame = sanitize_dataframe(frame)
    assert clean.loc[1, "a"] is None
    assert clean.loc[0, "b"] == "x"
