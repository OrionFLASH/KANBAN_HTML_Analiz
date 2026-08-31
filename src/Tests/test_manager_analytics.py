"""Тесты аналитики менеджеров (превышения P80)."""

from __future__ import annotations

import pandas as pd

from src.aggregator import build_all_statistics
from src.lead_tracker import build_lead_stage_records
from src.manager_analytics import build_manager_analytics, build_p80_thresholds


def _config() -> dict:
    return {
        "columns": {
            "report_date": "Дата отчета",
            "lead_id": "ID ПрПр",
            "product_group": "Группа продукта",
            "product": "Продукт",
            "work_start_date": "Дата начала работы",
            "current_status": "Текущий статус",
            "days_on_stage": "Количество дней на текущей стадии",
            "deal_created_date": "Дата создания сделки",
            "deal_stage": "Стадия сделки",
            "days_since_deal": "Количество дней с создания сделки",
            "tb": "ТБ",
            "km": "КМ",
        },
        "required_column_keys": [
            "report_date",
            "lead_id",
            "product_group",
            "product",
            "work_start_date",
            "current_status",
            "days_on_stage",
            "deal_created_date",
            "deal_stage",
            "days_since_deal",
            "tb",
        ],
        "processing": {
            "empty_stage_values": ["", "-"],
            "dedup_same_date_agg": "max",
            "duration_fallback_to_columns": True,
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
            "metrics": ["days_on_stage", "days_since_deal"],
        },
        "duration_source": "columns",
        "stage_analysis_mode": "status",
        "product_analysis_mode": "group_product",
        "percentiles": [80],
        "manager_analytics": {
            "enabled": True,
            "metric": "days_on_stage",
            "percentile": 80,
            "top_managers_per_tb": 3,
        },
    }


def _raw_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Дата отчета": pd.to_datetime(["2026-01-01"] * 8),
            "ID ПрПр": ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"],
            "Группа продукта": ["G1"] * 8,
            "Продукт": ["P1"] * 8,
            "Дата начала работы": pd.to_datetime(["2026-01-01"] * 8),
            "Текущий статус": ["В РАБОТЕ"] * 8,
            "Количество дней на текущей стадии": [5, 7, 8, 9, 10, 15, 3, 12],
            "Дата создания сделки": pd.to_datetime(["2026-01-01"] * 8),
            "Стадия сделки": [""] * 8,
            "Количество дней с создания сделки": [5, 7, 8, 9, 10, 15, 3, 12],
            "ТБ": ["ТБ1", "ТБ1", "ТБ1", "ТБ1", "ТБ1", "ТБ2", "ТБ2", "ТБ2"],
            "КМ": ["Иванов", "Иванов", "Петров", "Петров", "Сидоров", "Иванов", "Петров", "Петров"],
        }
    )


def test_build_manager_analytics_top3() -> None:
    """Топ менеджеров по превышениям P80 в каждом ТБ."""
    config = _config()
    records = build_lead_stage_records(_raw_df(), config)
    stats = build_all_statistics(records, config)
    payload = build_manager_analytics(records, stats, config)

    assert payload is not None
    top = payload["top_by_tb"]
    assert len(top) >= 1
    tb2 = [row for row in top if row["tb"] == "ТБ2" and row["exceedance_count"] > 0]
    assert tb2
    assert tb2[0]["km"] == "Иванов"
    charts = payload.get("charts") or {}
    assert "by_tb" in charts
    assert isinstance(charts.get("facts"), list)
    with_viol = [row for row in charts["by_tb"] if row["km_with_violations"] > 0]
    assert with_viol


def test_p80_thresholds_built() -> None:
    """Пороги P80 строятся из overall."""
    config = _config()
    records = build_lead_stage_records(_raw_df(), config)
    stats = build_all_statistics(records, config)
    thresholds = build_p80_thresholds(stats["overall"], config)
    assert not thresholds.empty
    assert "threshold_days" in thresholds.columns
