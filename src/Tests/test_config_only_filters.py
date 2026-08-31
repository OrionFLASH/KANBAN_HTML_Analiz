"""Тесты config-only фильтров (html_slice: false)."""

from __future__ import annotations

import pandas as pd

from src.filters import apply_config_only_filters, apply_filters


def _config(*, efs_enabled: bool) -> dict:
    return {
        "columns": {
            "efs_flag": "ЕФС флаг",
            "change_conditions": "_Изменение условий",
        },
        "filters": {
            "efs_flag": {
                "enabled": efs_enabled,
                "column_key": "efs_flag",
                "value": 1,
                "html_slice": False,
            },
            "change_conditions": {
                "enabled": efs_enabled,
                "column_key": "change_conditions",
                "value": 1,
            },
        },
    }


def test_config_only_efs_disabled_keeps_all_rows() -> None:
    """enabled:false — строки с 0 и 1 остаются."""
    df = pd.DataFrame({"ЕФС флаг": [0, 1, 1]})
    result = apply_config_only_filters(df, _config(efs_enabled=False))
    assert len(result) == 3


def test_config_only_efs_enabled_filters_value_one() -> None:
    """enabled:true, value:1 — только ЕФС=1."""
    df = pd.DataFrame({"ЕФС флаг": [0, 1, 1]})
    result = apply_config_only_filters(df, _config(efs_enabled=True))
    assert len(result) == 2


def test_apply_filters_includes_html_slice_when_enabled() -> None:
    """Excel-путь: enabled применяется и к html_slice-фильтрам."""
    df = pd.DataFrame(
        {
            "ЕФС флаг": [1, 1],
            "_Изменение условий": [1, 0],
        }
    )
    result = apply_filters(df, _config(efs_enabled=True))
    assert len(result) == 1
