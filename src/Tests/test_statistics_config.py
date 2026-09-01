"""Тесты конфигурации экспорта статистики."""

from __future__ import annotations

import pandas as pd

from src.config_loader import load_config
from src.statistics_config import (
    export_columns_for_metric,
    extract_metric_json,
    filter_and_order_statistics_frame,
    statistics_config,
)


def test_default_export_p80_extended() -> None:
    """По умолчанию P80 — le/gt/min/max, P20/P50 — только days."""
    config: dict = load_config("config.json")
    cols: list[str] = export_columns_for_metric("days_on_stage", config)
    assert "days_on_stage_count" in cols
    assert "days_on_stage_p20_days" in cols
    assert "days_on_stage_p50_days" in cols
    assert "days_on_stage_p80_le_count" in cols
    assert "days_on_stage_p80_days" in cols
    assert "days_on_stage_p80_gt_count" in cols
    assert "days_on_stage_p80_min" in cols
    assert "days_on_stage_p80_max" in cols
    assert "days_on_stage_min" not in cols
    assert "days_on_stage_max" not in cols
    assert "days_on_stage_p20_le_count" not in cols


def test_p80_le_count_left_of_days() -> None:
    """Счётчики лидов слева от границы перцентиля (attach_counts_left)."""
    config: dict = load_config("config.json")
    cols: list[str] = export_columns_for_metric("days_on_stage", config)
    le_idx: int = cols.index("days_on_stage_p80_le_count")
    days_idx: int = cols.index("days_on_stage_p80_days")
    assert le_idx < days_idx


def test_filter_and_order_statistics_frame() -> None:
    """Скрывает min/max, оставляет count и выбранные перцентили."""
    config: dict = load_config("config.json")
    frame: pd.DataFrame = pd.DataFrame(
        {
            "ТБ": ["A"],
            "ГРУППА": ["G"],
            "days_on_stage_min": [1],
            "days_on_stage_max": [100],
            "days_on_stage_count": [10],
            "days_on_stage_p20_days": [5],
            "days_on_stage_p80_le_count": [8],
            "days_on_stage_p80_days": [20],
        }
    )
    out: pd.DataFrame = filter_and_order_statistics_frame(frame, config)
    assert "days_on_stage_min" not in out.columns
    assert "days_on_stage_max" not in out.columns
    assert "days_on_stage_count" in out.columns
    assert "days_on_stage_p20_days" in out.columns
    assert "days_on_stage_p80_le_count" in out.columns


def test_extract_metric_json_respects_export_flags() -> None:
    """JSON metrics содержит только экспортируемые поля."""
    config: dict = load_config("config.json")
    row: dict = {
        "days_on_stage_min": 1,
        "days_on_stage_max": 100,
        "days_on_stage_count": 10,
        "days_on_stage_p20_days": 5,
        "days_on_stage_p20_le_count": 2,
        "days_on_stage_p80_days": 20,
        "days_on_stage_p80_le_count": 8,
        "days_on_stage_p80_gt_count": 2,
        "days_on_stage_p80_min": 1,
        "days_on_stage_p80_max": 20,
    }
    block: dict = extract_metric_json(row, "days_on_stage", config)
    assert "min" not in block
    assert "max" not in block
    assert block["count"] == 10
    assert block["percentiles"]["p20"] == {"days": 5}
    assert block["percentiles"]["p80"]["le_count"] == 8
    assert block["percentiles"]["p80"]["min"] == 1
