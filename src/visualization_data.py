"""Данные для графиков и сводной матрицы (Excel / HTML)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.percentile_stats import percentile_label, to_integer_days
from src.settings import analysis_row_key, col, group_only_product_label, is_group_only_analysis


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


def _pivot_row_value(record: dict[str, Any], config: dict[str, Any]) -> str | None:
    """Значение строки матрицы: группа или продукт в зависимости от режима."""
    if is_group_only_analysis(config):
        return record.get("product_group")
    return record.get("product")


def _indicator_column(metric: str, indicator: str) -> str:
    """Имя колонки агрегации для показателя."""
    if indicator == "min":
        return f"{metric}_min"
    if indicator == "max":
        return f"{metric}_max"
    return f"{metric}_{indicator}_days"


def series_chart_points(series: dict[str, Any]) -> list[dict[str, int]]:
    """Точки графика из points или компактного days_sorted."""
    points: list[dict[str, Any]] | None = series.get("points")
    if points:
        return [{"lead_index": int(p["lead_index"]), "days": int(p["days"])} for p in points]
    days_sorted: list[int] = list(series.get("days_sorted") or [])
    return [{"lead_index": idx + 1, "days": int(day)} for idx, day in enumerate(days_sorted)]


def stats_frame_to_pivot_flat(
    frame: pd.DataFrame,
    tb_value: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Длинный формат для сводной матрицы (itertuples, без to_dict)."""
    if frame.empty:
        return []

    group_col: str = col(config, "product_group")
    product_col: str = col(config, "product")
    metrics: list[str] = list(config["aggregation"].get("metrics", ["days_on_stage", "days_since_deal"]))
    group_only: bool = is_group_only_analysis(config)
    placeholder: str = group_only_product_label(config)
    id_cols: list[str] = [c for c in (group_col, product_col, "stage_key", "analysis_level") if c in frame.columns]

    flat: list[dict[str, Any]] = []
    for metric in metrics:
        for indicator in indicator_keys(config):
            value_col: str = _indicator_column(metric, indicator)
            if value_col not in frame.columns:
                continue
            chunk: pd.DataFrame = frame[id_cols + [value_col]].dropna(subset=[value_col])
            if chunk.empty:
                continue

            col_index: dict[str, int] = {name: idx for idx, name in enumerate(chunk.columns)}
            g_idx: int = col_index[group_col]
            p_idx: int | None = col_index.get(product_col)
            s_idx: int = col_index.get("stage_key", -1)
            a_idx: int = col_index.get("analysis_level", -1)
            v_idx: int = col_index[value_col]

            for row in chunk.itertuples(index=False, name=None):
                group_value = row[g_idx]
                product_value = placeholder if group_only else row[p_idx]  # type: ignore[index]
                row_key = group_value if group_only else product_value
                flat.append(
                    {
                        "tb": tb_value,
                        "product_group": group_value,
                        "product": product_value,
                        "row_key": row_key,
                        "stage_key": row[s_idx] if s_idx >= 0 else None,
                        "analysis_level": row[a_idx] if a_idx >= 0 else None,
                        "metric": metric,
                        "indicator": indicator,
                        "value": int(row[v_idx]),
                    }
                )
    return flat


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
    """Матрица строка × стадия (строка — продукт или группа)."""
    stages: list[str] = stage_order(config)
    row_dimension: str = analysis_row_key(config)
    filtered: list[dict[str, Any]] = [
        row
        for row in pivot_flat
        if row["tb"] == tb and row["metric"] == metric and row["indicator"] == indicator
    ]

    row_labels: list[str] = sorted(
        {str(row["row_key"]) for row in filtered if row.get("row_key") is not None},
        key=lambda value: value.lower(),
    )
    lookup: dict[tuple[str, str], int] = {
        (str(row.get("row_key")), str(row["stage_key"])): int(row["value"])
        for row in filtered
        if row.get("row_key") is not None and row.get("stage_key") is not None
    }
    values: dict[str, dict[str, int | None]] = {
        row_label: {stage: lookup.get((row_label, stage)) for stage in stages} for row_label in row_labels
    }

    return {
        "tb": tb,
        "metric": metric,
        "indicator": indicator,
        "row_dimension": row_dimension,
        "stages": stages,
        "rows": row_labels,
        "products": row_labels,
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
                if matrix["rows"]:
                    matrices.append(matrix)
    return matrices


def _append_distribution_series(
    series_list: list[dict[str, Any]],
    group: pd.DataFrame,
    tb_name: str,
    product_group: str,
    product: str,
    stage_key: str,
    config: dict[str, Any],
    metrics: list[str],
) -> None:
    """Добавляет серии распределения для одной группы лидов."""
    for metric in metrics:
        if metric not in group.columns:
            continue
        int_days: np.ndarray = to_integer_days(group[metric])
        if len(int_days) == 0:
            continue

        sorted_days: np.ndarray = np.sort(int_days)
        row_label: str = str(product_group if is_group_only_analysis(config) else product)
        series_entry: dict[str, Any] = {
            "tb": str(tb_name),
            "product_group": str(product_group),
            "product": str(product),
            "row_key": row_label,
            "row_dimension": analysis_row_key(config),
            "stage_key": str(stage_key),
            "analysis_level": str(group["analysis_level"].iloc[0]) if "analysis_level" in group.columns else None,
            "metric": metric,
            "total_leads": int(len(sorted_days)),
        }
        if config.get("performance", {}).get("compact_distribution_series", True):
            series_entry["days_sorted"] = [int(day) for day in sorted_days]
        else:
            series_entry["points"] = [
                {"lead_index": idx + 1, "days": int(day)} for idx, day in enumerate(sorted_days)
            ]
        series_list.append(series_entry)


def build_distribution_series(records: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Кумулятивные кривые для графика: X — номер лида (1..N), Y — срок в днях (сортировка по возрастанию).
    Серии по каждому ТБ и сводная серия с меткой all_tb_label (__ALL__).
    """
    if records.empty:
        return []

    tb_col: str = col(config, "tb")
    group_col: str = col(config, "product_group")
    product_col: str = col(config, "product")
    metrics: list[str] = list(config["aggregation"].get("metrics", ["days_on_stage", "days_since_deal"]))
    all_tb_label: str = str(config.get("dashboard", {}).get("all_tb_label", "__ALL__"))

    group_columns_tb: list[str] = [tb_col, group_col, "stage_key"]
    group_columns_all: list[str] = [group_col, "stage_key"]
    if not is_group_only_analysis(config):
        group_columns_tb.insert(2, product_col)
        group_columns_all.insert(1, product_col)

    series_list: list[dict[str, Any]] = []

    for keys, group in records.groupby(group_columns_tb, dropna=False, observed=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        if is_group_only_analysis(config):
            tb_name, product_group, stage_key = keys
            product = group_only_product_label(config)
        else:
            tb_name, product_group, product, stage_key = keys
        _append_distribution_series(
            series_list, group, tb_name, product_group, product, stage_key, config, metrics
        )

    for keys, group in records.groupby(group_columns_all, dropna=False, observed=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        if is_group_only_analysis(config):
            product_group, stage_key = keys
            product = group_only_product_label(config)
        else:
            product_group, product, stage_key = keys
        _append_distribution_series(
            series_list, group, all_tb_label, product_group, product, stage_key, config, metrics
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

    precompute_matrices: bool = bool(
        config.get("performance", {}).get("precompute_pivot_matrices", False)
    )
    pivot_matrices: list[dict[str, Any]] = []
    if precompute_matrices:
        pivot_matrices = build_all_pivot_matrices(pivot_flat, config)

    return {
        "stage_order": stage_order(config),
        "indicators": indicator_keys(config),
        "metrics": list(config["aggregation"].get("metrics", ["days_on_stage", "days_since_deal"])),
        "product_analysis_mode": config.get("product_analysis_mode", "group_product"),
        "row_dimension": analysis_row_key(config),
        "all_tb_label": all_tb_label,
        "default_view": {
            "tb": default_tb,
            "metric": default_metric,
            "indicator": default_indicator,
        },
        "distribution_series": build_distribution_series(records, config),
        "distribution_format": "days_sorted"
        if config.get("performance", {}).get("compact_distribution_series", True)
        else "points",
        "pivot_flat": pivot_flat,
        "pivot_matrices": pivot_matrices,
        "default_pivot_matrix": build_pivot_matrix(
            pivot_flat, default_tb, default_metric, default_indicator, config
        ),
    }
