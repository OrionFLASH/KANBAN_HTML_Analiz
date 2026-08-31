"""Тест режима анализа только по группам."""

from __future__ import annotations

import pandas as pd

from src.aggregator import aggregate_statistics
from src.settings import aggregation_group_columns, is_group_only_analysis


def _base_config() -> dict:
    return {
        "columns": {
            "product_group": "Группа продукта",
            "product": "Продукт",
            "tb": "ТБ",
        },
        "aggregation": {
            "group_keys": [
                "product_group",
                "product",
                "analysis_level",
                "current_status",
                "deal_stage",
                "stage_key",
            ],
            "metrics": ["days_on_stage"],
        },
        "percentiles": [50],
        "product_analysis_mode": "group_only",
        "dashboard": {"all_tb_label": "__ALL__"},
        "excel": {"category_markers": {}},
        "stages_order": ["S1"],
    }


def test_group_only_aggregation_excludes_product_column() -> None:
    """В режиме group_only продукт не входит в группировку."""
    config = _base_config()
    records = pd.DataFrame(
        {
            "Группа продукта": ["G1", "G1"],
            "Продукт": ["P1", "P2"],
            "ТБ": ["T1", "T1"],
            "analysis_level": ["status", "status"],
            "current_status": ["S1", "S1"],
            "deal_stage": ["", ""],
            "stage_key": ["S1", "S1"],
            "days_on_stage": [10, 30],
            "days_since_deal": [5, 5],
        }
    )
    group_cols = aggregation_group_columns(config, set(records.columns))
    assert "Продукт" not in group_cols
    assert is_group_only_analysis(config)

    result = aggregate_statistics(records, config, [50.0], include_tb=False)
    assert len(result) == 1
    assert result.iloc[0]["days_on_stage_count"] == 2
    assert result.iloc[0]["days_on_stage_p50_days"] == 10
