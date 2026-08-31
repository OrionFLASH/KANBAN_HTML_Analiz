"""Тесты исключения терминальных стадий сделки."""

from __future__ import annotations

import pandas as pd

from src.filter_slices import (
    apply_filter_subset,
    build_filter_catalog,
    default_filter_slice_key,
)
from src.filters import (
    apply_filters,
    default_html_active_filters,
    filter_terminal_deal_stage_rows,
    is_exclude_filter,
)
from src.lead_tracker import build_lead_stage_records


def _config() -> dict:
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
            "change_conditions": "_Изменение условий",
            "label": "Метка",
        },
        "processing": {
            "empty_stage_values": ["", "-", "nan", "None"],
            "dedup_same_date_agg": "max",
        },
        "duration_source": "columns",
        "stage_analysis_mode": "both",
        "product_analysis_mode": "group_product",
        "filters": {
            "exclude_deal_otkaz": {
                "enabled": True,
                "column_key": "deal_stage",
                "filter_mode": "exclude",
                "exclude_contains": "отказ",
                "case_sensitive": False,
                "html_slice": True,
                "default_active": True,
            },
            "exclude_deal_zakryta": {
                "enabled": True,
                "column_key": "deal_stage",
                "filter_mode": "exclude",
                "exclude_contains": "закрыта",
                "case_sensitive": False,
                "html_slice": True,
                "default_active": True,
            },
            "exclude_deal_zaklyuchen": {
                "enabled": True,
                "column_key": "deal_stage",
                "filter_mode": "exclude",
                "exclude_contains": "заключен",
                "case_sensitive": False,
                "html_slice": True,
                "default_active": True,
            },
        },
    }


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID ПрПр": ["L1", "L1", "L2"],
            "Группа продукта": ["G"] * 3,
            "Продукт": ["P"] * 3,
            "ТБ": ["TB"] * 3,
            "Текущий статус": ["В РАБОТЕ", "В РАБОТЕ", "К ПРОДАЖЕ"],
            "Стадия сделки": ["-", "ОТКАЗ клиента", "Подстадия"],
            "Дата отчета": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-01-01"]),
            "Дата начала работы": pd.to_datetime(["2025-12-01"] * 3),
            "Дата создания сделки": pd.to_datetime(["2025-12-01"] * 3),
            "Кол-во дней": [10, 99, 5],
            "Дней сделки": [10, 99, 5],
            "_Изменение условий": [0, 0, 0],
            "Метка": ["", "", ""],
        }
    )


def test_is_exclude_filter() -> None:
    flt = _config()["filters"]["exclude_deal_otkaz"]
    assert is_exclude_filter(flt)


def test_apply_filters_does_not_drop_terminal_rows() -> None:
    """Exclude-фильтры не в apply_filters — только конкретные строки в lead_tracker."""
    config = _config()
    df = pd.DataFrame(
        {
            "Стадия сделки": ["В работе", "ОТКАЗ клиента", "Сделка закрыта", "-", "Заключен договор"],
            "_Изменение условий": [0, 0, 0, 0, 0],
            "Метка": ["", "", "", "", ""],
        }
    )
    result = apply_filters(df, config)
    assert len(result) == len(df)


def test_filter_terminal_rows_only_matching_lines() -> None:
    config = _config()
    df = pd.DataFrame(
        {
            "Стадия сделки": ["В работе", "ОТКАЗ клиента", "Сделка закрыта", "-", "Заключен договор"],
        }
    )
    result = filter_terminal_deal_stage_rows(df, config)
    assert list(result["Стадия сделки"]) == ["В работе", "-"]


def test_lead_kept_on_other_report_dates() -> None:
    """Лид с терминальной стадией на одной дате остаётся в расчёте по другой дате."""
    config = _config()
    records = build_lead_stage_records(_sample_df(), config)
    assert not records.empty
    l1 = records[records["ID ПрПр"] == "L1"]
    assert not l1.empty
    assert l1["days_on_stage"].max() == 10
    assert "ОТКАЗ" not in " ".join(l1.get("deal_stage", pd.Series(dtype=str)).astype(str))


def test_apply_filter_subset_exclusion_active() -> None:
    config = _config()
    df = pd.DataFrame({"Стадия сделки": ["ОТКАЗ", "В работе"]})
    result = apply_filter_subset(df, config, ["exclude_deal_otkaz"])
    assert len(result) == 2


def test_default_html_active_filters() -> None:
    names = default_html_active_filters(_config())
    assert names == sorted(
        ["exclude_deal_otkaz", "exclude_deal_zakryta", "exclude_deal_zaklyuchen"]
    )


def test_default_filter_slice_key() -> None:
    key = default_filter_slice_key(_config())
    assert key == "+".join(
        sorted(["exclude_deal_otkaz", "exclude_deal_zakryta", "exclude_deal_zaklyuchen"])
    )


def test_empty_deal_stage_always_kept() -> None:
    """Пустая «Стадия сделки» не отсекается при включённых exclude."""
    config = _config()
    df = pd.DataFrame(
        {
            "Стадия сделки": ["-", "", "nan", "None", None, "   ", "ОТКАЗ", "В работе"],
        }
    )
    result = filter_terminal_deal_stage_rows(df, config)
    assert len(result) == 7
    assert "ОТКАЗ" not in list(result["Стадия сделки"].astype(str))


def test_filter_catalog_exclude_entry() -> None:
    catalog = build_filter_catalog(_config())
    otkaz = next(item for item in catalog if item["name"] == "exclude_deal_otkaz")
    assert otkaz["filter_mode"] == "exclude"
    assert otkaz["default_active"] is True
