"""Исключение текущего статуса «К ПРОДАЖЕ» из анализа (config-only)."""

from __future__ import annotations

import pandas as pd

from src.filters import (
    excluded_analysis_stages,
    filter_terminal_deal_stage_rows,
    is_exclude_filter,
)
from src.lead_tracker import build_lead_stage_records
from src.v1.visualization_data import stage_order


def _base_config(*, enabled: bool = True) -> dict:
    return {
        "columns": {
            "lead_id": "ID ПрПр",
            "deal_stage": "Стадия сделки",
            "current_status": "Текущий статус",
            "product_group": "Группа продукта",
            "product": "Продукт",
            "tb": "ТБ",
            "report_date": "Дата отчета",
            "work_start_date": "Дата начала работы",
            "deal_created_date": "Дата создания сделки",
            "days_on_stage": "Кол-во дней",
            "days_since_deal": "Дней сделки",
        },
        "processing": {
            "empty_stage_values": ["", "-", "nan", "None"],
            "dedup_same_date_agg": "max",
        },
        "duration_source": "columns",
        "stage_analysis_mode": "status",
        "product_analysis_mode": "group_product",
        "stages_order": [
            "К ПРОДАЖЕ",
            "ВЫЯВЛЕНИЕ ПОТРЕБНОСТИ",
            "ОБСУЖДЕНИЕ УСЛОВИЙ",
        ],
        "filters": {
            "exclude_current_for_sale": {
                "enabled": enabled,
                "column_key": "current_status",
                "filter_mode": "exclude",
                "exclude_equals": "К ПРОДАЖЕ",
                "case_sensitive": False,
                "html_slice": False,
            },
        },
    }


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID ПрПр": ["L1", "L2", "L3"],
            "Группа продукта": ["G"] * 3,
            "Продукт": ["P"] * 3,
            "ТБ": ["TB"] * 3,
            "Текущий статус": ["К ПРОДАЖЕ", "ВЫЯВЛЕНИЕ ПОТРЕБНОСТИ", "ОБСУЖДЕНИЕ УСЛОВИЙ"],
            "Стадия сделки": ["-", "-", "-"],
            "Дата отчета": pd.to_datetime(["2026-01-01"] * 3),
            "Дата начала работы": pd.to_datetime(["2025-12-01"] * 3),
            "Дата создания сделки": pd.to_datetime(["2025-12-01"] * 3),
            "Кол-во дней": [10, 20, 30],
            "Дней сделки": [10, 20, 30],
        }
    )


def test_is_exclude_filter_equals() -> None:
    flt = _base_config()["filters"]["exclude_current_for_sale"]
    assert is_exclude_filter(flt)


def test_excluded_analysis_stages_when_enabled() -> None:
    assert excluded_analysis_stages(_base_config(enabled=True)) == ["К ПРОДАЖЕ"]
    assert excluded_analysis_stages(_base_config(enabled=False)) == []


def test_filter_drops_for_sale_status() -> None:
    config = _base_config(enabled=True)
    result = filter_terminal_deal_stage_rows(_sample_df(), config)
    assert list(result["Текущий статус"]) == [
        "ВЫЯВЛЕНИЕ ПОТРЕБНОСТИ",
        "ОБСУЖДЕНИЕ УСЛОВИЙ",
    ]


def test_lead_records_without_for_sale() -> None:
    config = _base_config(enabled=True)
    records = build_lead_stage_records(_sample_df(), config)
    assert set(records["stage_key"]) == {
        "ВЫЯВЛЕНИЕ ПОТРЕБНОСТИ",
        "ОБСУЖДЕНИЕ УСЛОВИЙ",
    }
    assert "К ПРОДАЖЕ" not in set(records["stage_key"])


def test_stage_order_strips_for_sale() -> None:
    config = _base_config(enabled=True)
    order = stage_order(config)
    assert "К ПРОДАЖЕ" not in order
    assert order[0] == "ВЫЯВЛЕНИЕ ПОТРЕБНОСТИ"

    order_off = stage_order(_base_config(enabled=False))
    assert order_off[0] == "К ПРОДАЖЕ"
