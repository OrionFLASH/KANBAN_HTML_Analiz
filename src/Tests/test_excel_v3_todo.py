"""Тесты ToDo v3: stage_key, sales_method, filters_order, percentiles export, catalog."""

from __future__ import annotations

import warnings

import pandas as pd

from src.filter_funnel import (
    build_filter_audit_mapping,
    build_filters_catalog_frame,
    filter_description,
)
from src.filters import apply_ordered_filters, resolve_filters_order
from src.v2.config_loader import load_excel_v2_config
from src.v2.norms import norms_to_export_frame
from src.v2.percentiles_export import split_percentiles_sheets_by_tb
from src.v2.report_parts import resolve_report_parts, want_percentiles
from src.v2.snapshot import build_lead_snapshot, snapshot_to_export_frame


def test_config_v3_basics() -> None:
    config = load_excel_v2_config("config_excel_v2.json")
    assert "stage_key" not in config["aggregation"]["group_keys"]
    assert config["columns"]["sales_method"] == "Метод продаж"
    snap = config["output"]["snapshot_columns"]
    keys = list(snap.keys())
    assert keys.index("sales_method") < keys.index("deal_stage")
    assert "filters_order" in config
    assert config["filters"]["exclude_current_for_sale"]["description"]
    parts = resolve_report_parts(config)
    assert want_percentiles(parts)


def test_norms_drops_stage_key() -> None:
    config = load_excel_v2_config("config_excel_v2.json")
    frame = pd.DataFrame(
        {
            "Группа продукта": ["G"],
            "Продукт": ["P"],
            "current_status": ["В РАБОТЕ"],
            "ТБ": ["ТБ1"],
            "stage_key": ["В РАБОТЕ"],
            "days_on_stage_count": [1],
            "days_on_stage_p50_days": [5],
        }
    )
    exported = norms_to_export_frame(frame, config)
    assert "stage_key" not in exported.columns
    assert "Ключ стадии" not in exported.columns


def test_sales_method_from_latest_report_date() -> None:
    config = load_excel_v2_config("config_excel_v2.json")
    df = pd.DataFrame(
        {
            "ID ПрПр": ["L1", "L1"],
            "Дата отчета": pd.to_datetime(["2026-09-01", "2026-09-10"]),
            "Количество дней на текущей стадии": [1, 2],
            "Группа продукта": ["G", "G"],
            "Продукт": ["P", "P"],
            "Текущий статус": ["А", "Б"],
            "Метод продаж": ["СТАРОЕ", "НОВОЕ"],
            "Стадия сделки": ["-", "Сделка"],
            "ТБ": ["ТБ1", "ТБ1"],
        }
    )
    snap = build_lead_snapshot(df, config)
    assert snap.loc[snap["lead_id"] == "L1", "sales_method"].iloc[0] == "НОВОЕ"
    exported = snapshot_to_export_frame(snap, config)
    cols = list(exported.columns)
    assert "Метод продаж" in cols
    assert "Текущая стадия сделки" in cols
    assert cols.index("Метод продаж") < cols.index("Текущая стадия сделки")


def test_filters_order_sequential() -> None:
    config = {
        "columns": {"efs_flag": "ЕФС флаг", "current_status": "Текущий статус"},
        "filters_order": ["keep_efs", "drop_sale"],
        "filters": {
            "drop_sale": {
                "enabled": True,
                "column_key": "current_status",
                "action": "exclude",
                "match": "equals",
                "values": ["К ПРОДАЖЕ"],
                "value_type": "string",
                "case_sensitive": False,
            },
            "keep_efs": {
                "enabled": True,
                "column_key": "efs_flag",
                "action": "include",
                "match": "equals",
                "values": [1],
                "value_type": "number",
            },
        },
        "processing": {"empty_stage_values": ["", "-"]},
    }
    assert resolve_filters_order(config)[:2] == ["keep_efs", "drop_sale"]
    df = pd.DataFrame(
        {
            "ЕФС флаг": [1, 1, 0],
            "Текущий статус": ["К ПРОДАЖЕ", "В РАБОТЕ", "В РАБОТЕ"],
        }
    )
    out = apply_ordered_filters(df, config, config["filters"], resolve_filters_order(config))
    assert len(out) == 1
    assert out["Текущий статус"].iloc[0] == "В РАБОТЕ"


def test_filter_description_in_norms_labels() -> None:
    config = load_excel_v2_config("config_excel_v2.json")
    assert "К ПРОДАЖЕ" in filter_description(config, "exclude_current_for_sale")
    mapping = build_filter_audit_mapping(config)
    key = "filter_dropped_exclude_current_for_sale"
    assert key in mapping
    assert "К ПРОДАЖЕ" in mapping[key]


def test_filters_catalog_includes_disabled() -> None:
    config = load_excel_v2_config("config_excel_v2.json")
    catalog = build_filters_catalog_frame(config, scope="filters", funnel=None)
    assert not catalog.empty
    assert set(catalog["Включён"]) >= {"да", "нет"}
    src = build_filters_catalog_frame(config, scope="source", funnel=None)
    assert not src.empty


def test_percentiles_split_by_tb() -> None:
    config = {
        "columns": {"tb": "ТБ"},
        "output": {
            "percentiles_export": {"split_by_tb_over_rows": 5, "sheet_name_prefix": "ТБ"},
            "excel_max_sheet_name_length": 31,
        },
    }
    frame = pd.DataFrame(
        {
            "ТБ": ["А"] * 4 + ["Б"] * 4,
            "x": range(8),
        }
    )
    sheets = split_percentiles_sheets_by_tb(frame, config)
    assert len(sheets) == 2
    assert sum(len(v) for v in sheets.values()) == 8


def test_snapshot_no_futurewarning_object_fillna() -> None:
    series = pd.Series([1, None, "x"], dtype=object)
    from src.v2.snapshot import _nonempty_mask

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        _nonempty_mask(series, {"", "nan"})
