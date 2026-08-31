"""Данные для графиков и сводной матрицы (Excel / HTML)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.percentile_stats import percentile_label, to_integer_days
from src.settings import col


def stage_order(config: dict[str, Any]) -> list[str]:
    """Порядок статусов для сводной матрицы."""
    configured: list[str] = list(config.get("stages_order", []))
    if configured:
        return configured
    markers: dict[str, str] = config.get("excel", {}).get("category_markers", {})
    ordered: list[str] = []
    for key in ("for_sale", "in_work", "unknown"):
        value: str | None = markers.get(key)
        if value and value not in ordered:
            ordered.append(value)
    return ordered or ["К ПРОДАЖЕ", "В РАБОТЕ"]


def indicator_keys(config: dict[str, Any]) -> list[str]:
    """Доступные показатели: min, max, p20, p50, …"""
    keys: list[str] = ["min", "max"]
    for p in config.get("percentiles", [20, 50, 80]):
        keys.append(percentile_label(float(p)))
    return keys


def _indicator_value(row: dict[str, Any], metric: str, indicator: str) -> int | None:
    """Значение показателя из строки агрегации."""
    if indicator == "min":
        return row.get(f"{metric}_min")
    if indicator == "max":
        return row.get(f"{metric}_max")
    return row.get(f"{metric}_{indicator}_days")


def stats_frame_to_pivot_flat(
    frame: pd.DataFrame,
    tb_value: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Длинный формат для сводной матрицы и lookup в Excel."""
    if frame.empty:
        return []

    group_col: str = col(config, "product_group")
    product_col: str = col(config, "product")
    metrics: list[str] = list(config["aggregation"].get("metrics", ["days_on_stage", "days_since_deal"]))
    rows: list[dict[str, Any]] = []

    for record in frame.to_dict(orient="records"):
        base: dict[str, Any] = {
            "tb": tb_value,
            "product_group": record.get(group_col),
            "product": record.get(product_col),
            "stage_key": record.get("stage_key"),
            "analysis_level": record.get("analysis_level"),
        }
        for metric in metrics:
            for indicator in indicator_keys(config):
                value = _indicator_value(record, metric, indicator)
                if value is None:
                    continue
                rows.append(
                    {
                        **base,
                        "metric": metric,
                        "indicator": indicator,
                        "value": int(value),
                    }
                )
    return rows


def build_pivot_flat(stats: dict[str, pd.DataFrame], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Сводка по всем ТБ + каждому ТБ отдельно."""
    all_tb_label: str = str(config.get("dashboard", {}).get("all_tb_label", "__ALL__"))
    flat: list[dict[str, Any]] = stats_frame_to_pivot_flat(stats.get("overall", pd.DataFrame()), all_tb_label, config)
    tb_col: str = col(config, "tb")
    by_tb: pd.DataFrame = stats.get("by_tb", pd.DataFrame())
    if tb_col in by_tb.columns:
        for tb_name in sorted(by_tb[tb_col].dropna().unique(), key=str):
            tb_frame: pd.DataFrame = by_tb[by_tb[tb_col] == tb_name].drop(columns=[tb_col])
            flat.extend(stats_frame_to_pivot_flat(tb_frame, str(tb_name), config))
    return flat


def build_pivot_matrix(
    pivot_flat: list[dict[str, Any]],
    tb: str,
    metric: str,
    indicator: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Матрица продукт × стадия для выбранного среза."""
    stages: list[str] = stage_order(config)
    filtered: list[dict[str, Any]] = [
        row
        for row in pivot_flat
        if row["tb"] == tb and row["metric"] == metric and row["indicator"] == indicator
    ]

    products: list[str] = sorted({str(row["product"]) for row in filtered if row.get("product")})
    values: dict[str, dict[str, int | None]] = {}
    for product in products:
        values[product] = {}
        for stage in stages:
            match: list[dict[str, Any]] = [
                row for row in filtered if str(row["product"]) == product and str(row["stage_key"]) == stage
            ]
            values[product][stage] = int(match[0]["value"]) if match else None

    return {
        "tb": tb,
        "metric": metric,
        "indicator": indicator,
        "stages": stages,
        "products": products,
        "values": values,
    }


def build_all_pivot_matrices(
    pivot_flat: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Предрасчёт матриц для частых срезов (HTML / JSON)."""
    all_tb_label: str = str(config.get("dashboard", {}).get("all_tb_label", "__ALL__"))
    tb_values: list[str] = sorted({str(row["tb"]) for row in pivot_flat})
    if all_tb_label not in tb_values:
        tb_values.insert(0, all_tb_label)

    metrics: list[str] = list(config["aggregation"].get("metrics", ["days_on_stage", "days_since_deal"]))
    indicators: list[str] = indicator_keys(config)
    matrices: list[dict[str, Any]] = []

    for tb in tb_values:
        for metric in metrics:
            for indicator in indicators:
                matrix: dict[str, Any] = build_pivot_matrix(pivot_flat, tb, metric, indicator, config)
                if matrix["products"]:
                    matrices.append(matrix)
    return matrices


def build_distribution_series(records: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Кумулятивные кривые для графика: X — номер лида (1..N), Y — срок в днях (сортировка по возрастанию).
    """
    if records.empty:
        return []

    tb_col: str = col(config, "tb")
    group_col: str = col(config, "product_group")
    product_col: str = col(config, "product")
    metrics: list[str] = list(config["aggregation"].get("metrics", ["days_on_stage", "days_since_deal"]))
    group_columns: list[str] = [tb_col, group_col, product_col, "stage_key"]

    series_list: list[dict[str, Any]] = []
    grouped = records.groupby(group_columns, dropna=False, observed=True)

    for keys, group in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)
        tb_name, product_group, product, stage_key = keys

        for metric in metrics:
            if metric not in group.columns:
                continue
            int_days: np.ndarray = to_integer_days(group[metric])
            if len(int_days) == 0:
                continue

            sorted_days: np.ndarray = np.sort(int_days)
            points: list[dict[str, int]] = [
                {"lead_index": idx + 1, "days": int(day)} for idx, day in enumerate(sorted_days)
            ]
            series_list.append(
                {
                    "tb": str(tb_name),
                    "product_group": str(product_group),
                    "product": str(product),
                    "stage_key": str(stage_key),
                    "analysis_level": str(group["analysis_level"].iloc[0]) if "analysis_level" in group.columns else None,
                    "metric": metric,
                    "total_leads": int(len(sorted_days)),
                    "points": points,
                }
            )

    return series_list


def build_visualization_payload(
    records: pd.DataFrame,
    stats: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Полный блок visualizations для JSON."""
    pivot_flat: list[dict[str, Any]] = build_pivot_flat(stats, config)
    dash_cfg: dict[str, Any] = config.get("dashboard", {})
    all_tb_label: str = str(dash_cfg.get("all_tb_label", "__ALL__"))
    default_tb: str = str(dash_cfg.get("default_tb", all_tb_label))
    default_metric: str = str(dash_cfg.get("default_metric", "days_on_stage"))
    default_indicator: str = str(dash_cfg.get("default_indicator", "p80"))

    return {
        "stage_order": stage_order(config),
        "indicators": indicator_keys(config),
        "metrics": list(config["aggregation"].get("metrics", ["days_on_stage", "days_since_deal"])),
        "all_tb_label": all_tb_label,
        "default_view": {
            "tb": default_tb,
            "metric": default_metric,
            "indicator": default_indicator,
        },
        "distribution_series": build_distribution_series(records, config),
        "pivot_flat": pivot_flat,
        "pivot_matrices": build_all_pivot_matrices(pivot_flat, config),
        "default_pivot_matrix": build_pivot_matrix(
            pivot_flat, default_tb, default_metric, default_indicator, config
        ),
    }
