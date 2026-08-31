"""Тесты данных визуализации."""

from __future__ import annotations

import pandas as pd

from src.visualization_data import (
    build_distribution_series,
    build_pivot_flat,
    build_pivot_matrix,
    build_visualization_payload,
)


def test_distribution_points_sorted() -> None:
    """Точки кривой отсортированы по возрастанию дней."""
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
    }
    series = build_distribution_series(records, config)
    assert len(series) == 1
    days = [p["days"] for p in series[0]["points"]]
    assert days == [10, 20, 30]
    assert [p["lead_index"] for p in series[0]["points"]] == [1, 2, 3]


def test_pivot_matrix_value() -> None:
    """Матрица возвращает значение перцентиля для продукта и стадии."""
    flat = [
        {
            "tb": "__ALL__",
            "product_group": "G",
            "product": "ProdA",
            "stage_key": "К ПРОДАЖЕ",
            "metric": "days_on_stage",
            "indicator": "p80",
            "value": 42,
        }
    ]
    config = {
        "stages_order": ["К ПРОДАЖЕ", "В РАБОТЕ"],
        "percentiles": [80],
        "dashboard": {"all_tb_label": "__ALL__"},
        "excel": {"category_markers": {}},
        "aggregation": {"metrics": ["days_on_stage"]},
    }
    matrix = build_pivot_matrix(flat, "__ALL__", "days_on_stage", "p80", config)
    assert matrix["values"]["ProdA"]["К ПРОДАЖЕ"] == 42
    assert matrix["values"]["ProdA"]["В РАБОТЕ"] is None
