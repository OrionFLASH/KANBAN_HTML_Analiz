"""Тесты экспорта больших листов в CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.export_overflow import (
    csv_path_for_sheet,
    export_dataframe_csv,
    sheet_exceeds_excel_limit,
    split_sheets_by_row_limit,
)


def test_sheet_exceeds_limit_at_900k() -> None:
    """Порог по умолчанию — 900 000 строк данных."""
    config: dict = {"output": {"excel_max_rows_per_sheet": 900_000, "csv_overflow": {"enabled": True}}}
    small: pd.DataFrame = pd.DataFrame({"a": range(100)})
    large: pd.DataFrame = pd.DataFrame({"a": range(900_001)})

    assert not sheet_exceeds_excel_limit(small, config)
    assert sheet_exceeds_excel_limit(large, config)


def test_split_sheets_by_row_limit() -> None:
    """Большой лист уходит в CSV, малый остаётся в Excel."""
    config: dict = {"output": {"excel_max_rows_per_sheet": 10, "csv_overflow": {"enabled": True}}}
    sheets: dict[str, pd.DataFrame] = {
        "small": pd.DataFrame({"x": [1, 2]}),
        "big": pd.DataFrame({"x": range(11)}),
    }
    excel_part, csv_part = split_sheets_by_row_limit(sheets, config)
    assert "small" in excel_part
    assert "big" in csv_part
    assert len(excel_part) == 1
    assert len(csv_part) == 1


def test_export_csv_semicolon(tmp_path: Path) -> None:
    """CSV с разделителем «;» и BOM для Excel."""
    config: dict = {"output": {"csv_overflow": {"delimiter": ";", "encoding": "utf-8-sig"}}}
    frame: pd.DataFrame = pd.DataFrame({"col": ["a;b", "c"]})
    path: Path = tmp_path / "test.csv"
    export_dataframe_csv(path, frame, config)
    text: str = path.read_text(encoding="utf-8-sig")
    assert text.startswith("col")
    assert ";" in text.splitlines()[1]


def test_csv_path_for_sheet() -> None:
    """Имя CSV строится от stem xlsx и названия листа."""
    xlsx: Path = Path("/out/report_20260101.xlsx")
    csv_path: Path = csv_path_for_sheet(xlsx, "Уникальные ID")
    assert csv_path.name == "report_20260101_Уникальные ID.csv"
