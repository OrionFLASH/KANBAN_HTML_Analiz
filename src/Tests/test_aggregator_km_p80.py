"""Тесты: число уникальных КМ с сроком ≥ P80 в Excel-сводке."""

from __future__ import annotations

import pandas as pd

from src.aggregator import aggregate_statistics
from src.percentile_stats import count_unique_km_at_or_above_p80
from src.settings import build_percentile_column_mapping


def _config() -> dict:
    return {
        "columns": {
            "product_group": "Группа продукта",
            "product": "Продукт",
            "tb": "ТБ",
            "km": "КМ",
            "current_status": "Текущий статус",
            "deal_stage": "Стадия сделки",
            "analysis_level": "analysis_level",
            "stage_key": "stage_key",
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
        "percentiles": [80],
        "product_analysis_mode": "group_product",
        "output": {
            "percentile_column_labels": {
                "days_on_stage": {
                    "days": "П{p} дней",
                    "count": "П{p} лидов",
                    "min": "П{p} мин",
                    "max": "П{p} макс",
                    "km_count": "П{p} КМ ≥",
                }
            }
        },
    }


def test_count_unique_km_deduplicates() -> None:
    df = pd.DataFrame(
        {
            "days_on_stage": [80, 90, 95],
            "КМ": ["Иванов", "Иванов", "Петров"],
        }
    )
    assert count_unique_km_at_or_above_p80(df, "days_on_stage", 80, "КМ") == 2


def test_aggregate_statistics_p80_km_count() -> None:
    """В сводке Excel есть колонка days_on_stage_p80_km_count."""
    records = pd.DataFrame(
        {
            "Группа продукта": ["G"] * 10,
            "Продукт": ["P"] * 10,
            "ТБ": ["TB"] * 10,
            "analysis_level": ["status"] * 10,
            "current_status": ["В РАБОТЕ"] * 10,
            "deal_stage": [""] * 10,
            "stage_key": ["В РАБОТЕ"] * 10,
            "days_on_stage": list(range(10, 110, 10)),
            "days_since_deal": list(range(10, 110, 10)),
            "КМ": [f"KM{i % 4}" for i in range(10)],
        }
    )
    stats = aggregate_statistics(records, _config(), [80.0], include_tb=False)
    assert "days_on_stage_p80_km_count" in stats.columns
    row = stats.iloc[0]
    assert row["days_on_stage_p80_days"] == 80
    assert row["days_on_stage_p80_km_count"] >= 1


def test_excel_mapping_includes_p80_km_only() -> None:
    mapping = build_percentile_column_mapping(_config())
    assert mapping["days_on_stage_p80_km_count"] == "П80 КМ ≥"
    assert "days_on_stage_p20_km_count" not in mapping
