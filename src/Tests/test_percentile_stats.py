"""Тесты эмпирических перцентилей."""

from __future__ import annotations

import numpy as np

from src.percentile_stats import compute_metric_percentiles, empirical_percentile_stats


def test_empirical_p20_ten_leads() -> None:
    """10 лидов: нижние 20% = 2 лида с минимальными сроками."""
    values: np.ndarray = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], dtype=np.int64)
    stats = empirical_percentile_stats(values, 20.0)
    assert stats["days"] == 20
    assert stats["count"] == 2
    assert stats["min"] == 10
    assert stats["max"] == 20
    assert stats["le_count"] == 2
    assert stats["gt_count"] == 8


def test_empirical_p50_ten_leads() -> None:
    """Медиана по шкале лидов — 5-й по счёту срок."""
    values: np.ndarray = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], dtype=np.int64)
    stats = empirical_percentile_stats(values, 50.0)
    assert stats["days"] == 50
    assert stats["count"] == 5
    assert stats["le_count"] == 5
    assert stats["gt_count"] == 5


def test_le_gt_with_ties_at_threshold() -> None:
    """При равенстве порогу лиды входят в le_count."""
    values: np.ndarray = np.array([1, 2, 5, 5, 5, 9], dtype=np.int64)
    stats = empirical_percentile_stats(values, 50.0)
    assert stats["days"] == 5
    assert stats["le_count"] == 5
    assert stats["gt_count"] == 1


def test_integer_days_only() -> None:
    """Колонки перцентилей содержат только целые дни."""
    values: np.ndarray = np.array([1, 2, 3, 4, 5], dtype=np.int64)
    row = compute_metric_percentiles(values, [20, 50], "days_on_stage")
    assert row["days_on_stage_p20_days"] == 1
    assert row["days_on_stage_p50_days"] == 3
    assert isinstance(row["days_on_stage_p20_days"], int)


def test_empty_group() -> None:
    """Пустая выборка — нули и None без дробей."""
    row = compute_metric_percentiles(np.array([], dtype=np.int64), [20], "days_on_stage")
    assert row["days_on_stage_count"] == 0
    assert row["days_on_stage_p20_days"] is None
    assert row["days_on_stage_p20_count"] == 0
