"""Тесты загрузки Excel (без зависимости от IN/)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.excel_loader import _read_excel_dataframe, read_single_file
from src.settings import normalize_config


def _minimal_config() -> dict:
    return normalize_config(
        {
            "mode": "test",
            "paths": {
                "input_test": "IN/TEST",
                "input_prod": "IN/PROD",
                "output": "OUT",
                "log": "log",
            },
            "columns": {
                "report_date": "Дата отчета",
                "lead_id": "ID ПрПр",
                "current_status": "Текущий статус",
                "product_group": "Группа продукта",
                "product": "Продукт",
                "tb": "ТБ",
                "days_on_stage": "Дней на текущем статусе",
                "days_since_deal": "Дней с создания сделки",
                "deal_stage": "Стадия сделки",
                "change_conditions": "Изменение условий",
                "data_entry": "Ввод данных",
                "efs_flag": "ЕФС",
                "work_start_date": "Дата начала работы",
                "deal_created_date": "Дата создания сделки",
                "km": "КМ",
            },
            "required_column_keys": [
                "report_date",
                "lead_id",
                "current_status",
                "product_group",
                "product",
                "tb",
                "days_on_stage",
            ],
            "optional_column_keys": [],
            "excel": {
                "sheet_name": "Sheet1",
                "engine": "openpyxl",
                "read_only": True,
                "data_only": True,
                "keep_links": False,
                "na_values": [""],
                "category_markers": {
                    "for_sale": "К ПРОДАЖЕ",
                    "in_work": "В РАБОТЕ",
                    "unknown": "UNKNOWN",
                },
            },
            "performance": {
                "read_only_required_columns": True,
                "downcast_numeric": True,
            },
            "dates": {
                "dayfirst": True,
                "formats": ["%d.%m.%Y", "%Y-%m-%d"],
                "empty_values": ["", "-", "nan"],
            },
        }
    )


def test_normalize_config_drops_table_auto() -> None:
    cfg = normalize_config(
        {
            "mode": "test",
            "paths": {"input_test": "x", "input_prod": "y", "output": "z", "log": "l"},
            "excel": {"table_name": "Base", "table_auto": True, "sheet_name": "Sheet1"},
        }
    )
    assert "table_name" not in cfg["excel"]
    assert "table_auto" not in cfg["excel"]
    assert cfg["excel"].get("read_only", True) is True


def test_read_sheet_with_header_read_only(tmp_path: Path) -> None:
    """Лист с заголовком читается в read_only без именованной таблицы."""
    path: Path = tmp_path / "kanban.xlsx"
    frame: pd.DataFrame = pd.DataFrame(
        {
            "Дата отчета": ["01.09.2026", "02.09.2026"],
            "ID ПрПр": ["L1", "L2"],
            "Текущий статус": ["С1", "С2"],
            "Группа продукта": ["G", "G"],
            "Продукт": ["P", "P"],
            "ТБ": ["ТБ1", "ТБ1"],
            "Дней на текущем статусе": [10, 20],
            "Дней с создания сделки": [1, 2],
            "Стадия сделки": ["", ""],
            "Изменение условий": [0, 0],
            "Ввод данных": [0, 0],
            "ЕФС": [1, 1],
            "Дата начала работы": ["01.08.2026", "01.08.2026"],
            "Дата создания сделки": ["01.07.2026", "01.07.2026"],
            "КМ": ["Иванов", "Петров"],
            "Лишняя колонка": ["x", "y"],
        }
    )
    frame.to_excel(path, sheet_name="Sheet1", index=False)

    config = _minimal_config()
    raw = _read_excel_dataframe(path, config, use_columns=["ID ПрПр", "Продукт", "Лишняя колонка"])
    assert list(raw.columns) == ["ID ПрПр", "Продукт", "Лишняя колонка"]
    assert len(raw) == 2

    loaded = read_single_file((str(path), config))
    assert "ID ПрПр" in loaded.columns
    assert "Лишняя колонка" not in loaded.columns  # не в required/optional
    assert len(loaded) == 2
    assert loaded.loc[0, "source_file"] == "kanban.xlsx"
