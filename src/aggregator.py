"""Агрегация min/max/перцентилей по группам."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.settings import aggregation_group_columns, col

logger: logging.Logger = logging.getLogger("kanban.aggregator")


def _percentile_label(p: float) -> str:
    """Имя колонки для перцентиля."""
    if float(p).is_integer():
        return f"p{int(p)}"
    return f"p{str(p).replace('.', '_')}"


def aggregate_statistics(
    records: pd.DataFrame,
    config: dict[str, Any],
    percentiles: list[float],
    include_tb: bool = True,
) -> pd.DataFrame:
    """Считает min, max, перцентили и count через groupby.agg."""
    if records.empty:
        return pd.DataFrame()

    record_cols: set[str] = set(records.columns)
    base_cols: list[str] = aggregation_group_columns(config, record_cols)

    if include_tb:
        tb_col: str = col(config, "tb")
        if tb_col in record_cols and tb_col not in base_cols:
            base_cols = [tb_col] + base_cols

    metrics: list[str] = list(config["aggregation"].get("metrics", ["days_on_stage", "days_since_deal"]))

    named: dict[str, tuple[str, str]] = {}
    for metric in metrics:
        if metric not in records.columns:
            continue
        named[f"{metric}_min"] = (metric, "min")
        named[f"{metric}_max"] = (metric, "max")
        named[f"{metric}_count"] = (metric, "count")

    if not named:
        return pd.DataFrame()

    grouped = records.groupby(base_cols, dropna=False, observed=True)
    result: pd.DataFrame = grouped.agg(**named).reset_index()

    for metric in metrics:
        if metric not in records.columns:
            continue
        for p in percentiles:
            label: str = _percentile_label(p)
            col_name: str = f"{metric}_{label}"
            quantile_series: pd.Series = grouped[metric].quantile(p / 100.0)
            result[col_name] = quantile_series.values

    logger.info("Агрегировано групп: %d (include_tb=%s)", len(result), include_tb)
    return result


def build_all_statistics(
    records: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Формирует общую сводку, сводку без ТБ и разрез по каждому ТБ."""
    percentiles: list[float] = [float(p) for p in config.get("percentiles", [20, 50, 80])]
    tb_col: str = col(config, "tb")

    overall: pd.DataFrame = aggregate_statistics(records, config, percentiles, include_tb=False)
    by_tb: pd.DataFrame = aggregate_statistics(records, config, percentiles, include_tb=True)

    tb_sheets: dict[str, pd.DataFrame] = {}
    if tb_col in records.columns:
        for tb_name in sorted(records[tb_col].dropna().unique()):
            tb_records: pd.DataFrame = records[records[tb_col] == tb_name]
            tb_sheets[str(tb_name)] = aggregate_statistics(
                tb_records, config, percentiles, include_tb=False
            )

    return {
        "overall": overall,
        "by_tb": by_tb,
        "tb_sheets": tb_sheets,
    }
