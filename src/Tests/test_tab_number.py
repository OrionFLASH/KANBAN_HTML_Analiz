"""Тесты нормализации табельных номеров."""

from __future__ import annotations

import pandas as pd

from src.tab_number import (
    format_tab_number_columns,
    normalize_tab_number,
    normalize_tab_number_multiline,
    tab_number_column_labels,
)


def test_normalize_short_with_leading_zeros() -> None:
    assert normalize_tab_number(12345) == "00012345"
    assert normalize_tab_number("12345") == "00012345"
    assert normalize_tab_number(12345.0) == "00012345"


def test_normalize_exactly_eight_digits() -> None:
    assert normalize_tab_number("12345678") == "12345678"
    assert normalize_tab_number("01234567") == "01234567"


def test_normalize_more_than_eight_digits() -> None:
    assert normalize_tab_number("123456789") == "123456789"
    assert normalize_tab_number("000123456789") == "123456789"


def test_normalize_empty() -> None:
    assert normalize_tab_number("") == ""
    assert normalize_tab_number(None) == ""
    assert normalize_tab_number("-") == ""


def test_normalize_multiline() -> None:
    assert normalize_tab_number_multiline("12345\n678") == "00012345\n00000678"
    assert normalize_tab_number_multiline(None) is None


def test_format_tab_number_columns() -> None:
    config: dict = {
        "team_files": {
            "output_columns": {
                "lead": {"member_tab_number": "TN Лидера лида"},
            }
        }
    }
    frame = pd.DataFrame(
        {
            "Табельный номер": [12345, None],
            "TN Лидера лида": ["678\n9", ""],
            "ФИО": ["A", "B"],
        }
    )
    out = format_tab_number_columns(frame, config)
    assert out.loc[0, "Табельный номер"] == "00012345"
    assert out.loc[0, "TN Лидера лида"] == "00000678\n00000009"
    assert tab_number_column_labels(config) == ["Табельный номер", "TN Лидера лида"]
