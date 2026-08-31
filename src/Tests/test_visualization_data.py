"""Тесты данных визуализации."""

from __future__ import annotations

import pandas as pd

from src.visualization_data import (
    build_distribution_series,
    build_pivot_flat,
    build_pivot_matrix,
    build_visualization_payload,
    series_chart_points,
)


def test_distribution_points_sorted() -> None:
    """Кривая распределения отсортирована по возрастанию дней (компактный days_sorted)."""
    records = pd.DataFrame(
        {
            "ТБ": ["T1", "T1", "T1"],
            "Группа продукта": ["G", "G", "G"],
            "Продукт": ["P", "P", "P"],
            "stage_key": ["S", "S", "S"],
            "analysis_level": ["status", "status", "status"],
            "days_on_stage": [30, 10, 20],
            "days_since_deal": [5, 5, 5],
        }
    )
    config = {
        "columns": {
            "tb": "ТБ",
            "product_group": "Группа продукта",
            "product": "Продукт",
        },
        "aggregation": {"metrics": ["days_on_stage"]},
        "percentiles": [20, 50],
        "stages_order": ["S"],
        "dashboard": {"all_tb_label": "__ALL__"},
        "excel": {"category_markers": {}},
        "performance": {"compact_distribution_series": True},
    }
    series = build_distribution_series(records, config)
    assert len(series) == 2
    by_tb = [s for s in series if s["tb"] == "T1"]
    by_all = [s for s in series if s["tb"] == "__ALL__"]
    assert len(by_tb) == 1
    assert len(by_all) == 1
    assert by_tb[0]["days_sorted"] == [10, 20, 30]
    assert by_all[0]["days_sorted"] == [10, 20, 30]


def test_distribution_series_all_tb_multiple_banks() -> None:
    """Сводные серии __ALL__ объединяют лиды всех ТБ."""
    records = pd.DataFrame(
        {
            "ТБ": ["T1", "T2"],
            "Группа продукта": ["G", "G"],
            "Продукт": ["P", "P"],
            "stage_key": ["S", "S"],
            "analysis_level": ["status", "status"],
            "days_on_stage": [10, 30],
            "days_since_deal": [1, 1],
        }
    )
    config = {
        "columns": {"tb": "ТБ", "product_group": "Группа продукта", "product": "Продукт"},
        "aggregation": {"metrics": ["days_on_stage"]},
        "percentiles": [50],
        "stages_order": ["S"],
        "dashboard": {"all_tb_label": "__ALL__"},
        "excel": {"category_markers": {}},
        "performance": {"compact_distribution_series": True},
    }
    series = build_distribution_series(records, config)
    all_series = [s for s in series if s["tb"] == "__ALL__"]
    assert len(all_series) == 1
    assert all_series[0]["days_sorted"] == [10, 30]
    assert all_series[0]["total_leads"] == 2


def test_series_chart_points_from_days_sorted() -> None:
    """series_chart_points восстанавливает lead_index из days_sorted."""
    series = {"days_sorted": [5, 10, 15], "total_leads": 3}
    points = series_chart_points(series)
    assert points == [{"lead_index": 1, "days": 5}, {"lead_index": 2, "days": 10}, {"lead_index": 3, "days": 15}]


def test_pivot_matrix_value() -> None:
    """Матрица возвращает значение перцентиля для продукта и стадии."""
    flat = [
        {
            "tb": "__ALL__",
            "product_group": "G",
            "product": "ProdA",
            "row_key": "ProdA",
            "stage_key": "К ПРОДАЖЕ",
            "metric": "days_on_stage",
            "indicator": "p80",
            "value": 42,
        }
    ]
    config = {
        "stages_order": ["К ПРОДАЖЕ", "В РАБОТЕ"],
        "percentiles": [80],
        "product_analysis_mode": "group_product",
        "dashboard": {"all_tb_label": "__ALL__"},
        "excel": {"category_markers": {}},
        "aggregation": {"metrics": ["days_on_stage"]},
    }
    matrix = build_pivot_matrix(flat, "__ALL__", "days_on_stage", "p80", config)
    assert matrix["values"]["ProdA"]["К ПРОДАЖЕ"] == 42
    assert matrix["values"]["ProdA"]["В РАБОТЕ"] is None


def test_distribution_series_group_only_merges_products() -> None:
    """В group_only серии строятся по группе, продукты объединены."""
    records = pd.DataFrame(
        {
            "ТБ": ["T1", "T1"],
            "Группа продукта": ["G1", "G1"],
            "Продукт": ["P1", "P2"],
            "stage_key": ["S", "S"],
            "analysis_level": ["status", "status"],
            "days_on_stage": [10, 30],
            "days_since_deal": [1, 1],
        }
    )
    config = {
        "columns": {"tb": "ТБ", "product_group": "Группа продукта", "product": "Продукт"},
        "aggregation": {"metrics": ["days_on_stage"]},
        "percentiles": [50],
        "stages_order": ["S"],
        "product_analysis_mode": "group_only",
        "processing": {"group_only_product_label": "—"},
        "dashboard": {"all_tb_label": "__ALL__"},
        "excel": {"category_markers": {}},
        "performance": {"compact_distribution_series": True},
    }
    series = build_distribution_series(records, config)
    tb_series = [s for s in series if s["tb"] == "T1"]
    assert len(tb_series) == 1
    assert tb_series[0]["row_key"] == "G1"
    assert tb_series[0]["row_dimension"] == "product_group"
    assert tb_series[0]["product"] == "—"
    assert tb_series[0]["days_sorted"] == [10, 30]
    assert tb_series[0]["total_leads"] == 2
