"""
Эмпирические перцентили по шкале лидов (целые дни).

Модель: все сроки лидов сортируются по возрастанию.
Перцентиль P — нижние p% лидов по счёту (горизонтальная шкала количества).
Значение P — срок (дней, целое) на границе этой доли; также min/max среди этих лидов.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def percentile_label(p: float) -> str:
    """Имя суффикса колонки для перцентиля (p20, p50)."""
    if float(p).is_integer():
        return f"p{int(p)}"
    return f"p{str(p).replace('.', '_')}"


def to_integer_days(series: pd.Series) -> np.ndarray:
    """Приводит сроки к целым дням (округление), отбрасывает NaN."""
    numeric: pd.Series = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return np.array([], dtype=np.int64)
    return np.round(numeric).astype(np.int64)


def empirical_percentile_stats(values: np.ndarray, p: float) -> dict[str, int | None]:
    """
    Статистика нижних p% лидов на отсортированной шкале сроков.

    - days: срок на границе (максимум среди нижних p% лидов)
    - count: сколько лидов вошло в нижние p%
    - min / max: мин и макс срок среди этих лидов
    """
    n: int = len(values)
    if n == 0:
        return {"days": None, "count": 0, "min": None, "max": None}

    sorted_vals: np.ndarray = np.sort(values)
    count: int = max(1, math.ceil(p / 100.0 * n))
    bottom: np.ndarray = sorted_vals[:count]

    return {
        "days": int(bottom[-1]),
        "count": int(count),
        "min": int(bottom[0]),
        "max": int(bottom[-1]),
    }


def compute_metric_percentiles(
    values: np.ndarray,
    percentiles: list[float],
    metric_prefix: str,
) -> dict[str, Any]:
    """Min/max/count + колонки для каждого перцентиля."""
    result: dict[str, Any] = {}

    if len(values) == 0:
        result[f"{metric_prefix}_min"] = None
        result[f"{metric_prefix}_max"] = None
        result[f"{metric_prefix}_count"] = 0
        for p in percentiles:
            label: str = percentile_label(p)
            for suffix in ("days", "count", "min", "max"):
                result[f"{metric_prefix}_{label}_{suffix}"] = None if suffix != "count" else 0
        return result

    result[f"{metric_prefix}_min"] = int(values.min())
    result[f"{metric_prefix}_max"] = int(values.max())
    result[f"{metric_prefix}_count"] = int(len(values))

    for p in percentiles:
        stats: dict[str, int | None] = empirical_percentile_stats(values, p)
        label = percentile_label(p)
        result[f"{metric_prefix}_{label}_days"] = stats["days"]
        result[f"{metric_prefix}_{label}_count"] = stats["count"]
        result[f"{metric_prefix}_{label}_min"] = stats["min"]
        result[f"{metric_prefix}_{label}_max"] = stats["max"]

    return result


def count_unique_km_at_or_above_p80(
    group: pd.DataFrame,
    metric: str,
    threshold: int | None,
    km_col: str | None,
) -> int:
    """
    Число уникальных КМ, у которых срок по метрике >= порога P80 в группе.
    """
    if threshold is None or not km_col or km_col not in group.columns or group.empty:
        return 0
    days_numeric: pd.Series = pd.to_numeric(group[metric], errors="coerce")
    valid: pd.Series = days_numeric.notna() & (days_numeric.round() >= threshold)
    if not valid.any():
        return 0
    km_values: pd.Series = group.loc[valid, km_col].fillna("").astype(str).str.strip()
    empty: set[str] = {"", "-", "nan", "none", "None"}
    km_values = km_values[~km_values.str.lower().isin({v.lower() for v in empty})]
    return int(km_values.nunique())
