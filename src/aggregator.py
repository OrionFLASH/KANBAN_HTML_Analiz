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
    """Считает min, max, перцентили и count для метрик из config."""
    if records.empty:
        return pd.DataFrame()

    record_cols: set[str] = set(records.columns)
    base_cols: list[str] = aggregation_group_columns(config, record_cols)

    if include_tb:
        tb_col: str = col(config, "tb")
        if tb_col in record_cols and tb_col not in base_cols:
            base_cols = [tb_col] + base_cols

    metrics: list[str] = list(config["aggregation"].get("metrics", ["days_on_stage", "days_since_deal"]))

    rows: list[dict[str, Any]] = []
    grouped = records.groupby(base_cols, dropna=False)

    for keys, group in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)
        row: dict[str, Any] = dict(zip(base_cols, keys))

        for metric in metrics:
            if metric not in group.columns:
                continue
            series: pd.Series = pd.to_numeric(group[metric], errors="coerce").dropna()
            prefix: str = metric
            if series.empty:
                row[f"{prefix}_min"] = None
                row[f"{prefix}_max"] = None
                row[f"{prefix}_count"] = 0
                for p in percentiles:
                    row[f"{prefix}_{_percentile_label(p)}"] = None
                continue

            row[f"{prefix}_min"] = float(series.min())
            row[f"{prefix}_max"] = float(series.max())
            row[f"{prefix}_count"] = int(len(series))
            for p in percentiles:
                row[f"{prefix}_{_percentile_label(p)}"] = float(series.quantile(p / 100.0))

        rows.append(row)

    result: pd.DataFrame = pd.DataFrame(rows)
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
