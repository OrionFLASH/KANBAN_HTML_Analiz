"""Тесты разбора дат из Excel."""

from __future__ import annotations

import pandas as pd

from src.date_utils import parse_date_column


def _config() -> dict:
    return {
        "dates": {
            "dayfirst": True,
            "excel_origin": "1899-12-30",
            "formats": ["%d.%m.%Y"],
            "empty_values": ["", "-", "nan"],
        }
    }


def test_parse_date_column_preserves_datetime64() -> None:
    """Уже datetime64 из openpyxl не ломается при повторном parse."""
    series = pd.to_datetime(["2026-06-30", "2026-07-31", "2026-08-07"])
    parsed = parse_date_column(series, _config(), "Дата отчета")
    assert parsed.notna().all()
    assert parsed.iloc[0].date().isoformat() == "2026-06-30"
    assert parsed.iloc[-1].date().isoformat() == "2026-08-07"


def test_parse_date_column_text_and_excel_serial() -> None:
    """Строки dd.mm.yyyy и Excel serial days."""
    config = _config()
    text = parse_date_column(pd.Series(["31.07.2026", "-"]), config, "d")
    assert text.iloc[0].date().isoformat() == "2026-07-31"
    assert pd.isna(text.iloc[1])

    serial = parse_date_column(pd.Series([45838.0]), config, "d")
    assert serial.notna().all()
