"""Срезы данных по комбинациям pipeline-фильтров для JSON/HTML."""

from __future__ import annotations

import itertools
import logging
from typing import Any, Iterator

import pandas as pd

from src.aggregator import build_all_statistics
from src.filters import apply_config_only_filters, is_html_slice_filter
from src.settings import col, filter_column_name, with_product_analysis_mode
from src.visualization_data import (
    JSON_AGGREGATION_MODES,
    build_aggregation_visualization,
)

logger: logging.Logger = logging.getLogger("kanban.filter_slices")

FILTER_DISPLAY_NAMES: dict[str, str] = {
    "change_conditions": "Изменение условий",
    "data_entry": "Ввод данных",
    "strategy_label": "Все стратегии",
    "strategy_label_2026": "Стратегия · 2026",
}

TOGGLE_LABELS: dict[str, str] = {
    "change_conditions": "Изменение условий = 1",
    "data_entry": "Ввод данных = 1",
    "strategy_label": "Метка содержит «Стратегия»",
    "strategy_label_2026": "Метка: «Стратегия» и «2026»",
}


def html_filter_names(config: dict[str, Any]) -> list[str]:
    """Имена фильтров config.filters для HTML (html_slice, не только enabled)."""
    return [
        name
        for name, flt in config.get("filters", {}).items()
        if isinstance(flt, dict)
        and is_html_slice_filter(flt)
        and filter_column_name(config, flt)
    ]


def filter_slice_key(active_names: list[str]) -> str:
    """Ключ среза: none или name1+name2 (сортировка)."""
    if not active_names:
        return "none"
    return "+".join(sorted(active_names))


def iter_filter_combinations(config: dict[str, Any]) -> Iterator[list[str]]:
    """Все комбинации включённых HTML-фильтров (2^N, включая пустую)."""
    names: list[str] = html_filter_names(config)
    for size in range(len(names) + 1):
        for combo in itertools.combinations(names, size):
            yield list(combo)


def _filter_mask(df: pd.DataFrame, flt: dict[str, Any], column: str) -> pd.Series:
    """Маска строк для одного фильтра."""
    from src.filters import _text_match_mask

    if "contains" in flt or "contains_all" in flt:
        return _text_match_mask(df[column], flt)
    value = flt.get("value", 1)
    return pd.to_numeric(df[column], errors="coerce") == value


def apply_filter_subset(
    df: pd.DataFrame,
    config: dict[str, Any],
    active_names: list[str],
) -> pd.DataFrame:
    """Оставляет строки, прошедшие указанные фильтры (AND). Пустой список — без отсечения."""
    if not active_names:
        return df.copy().reset_index(drop=True)

    result: pd.DataFrame = df.copy()
    filters_cfg: dict[str, Any] = config.get("filters", {})

    for name in active_names:
        flt: dict[str, Any] | None = filters_cfg.get(name)
        if not isinstance(flt, dict):
            continue
        column: str | None = filter_column_name(config, flt)
        if not column or column not in result.columns:
            logger.warning("HTML-фильтр '%s': колонка не найдена", name)
            return result.iloc[0:0].copy()
        result = result[_filter_mask(result, flt, column)]

    return result.reset_index(drop=True)


def build_filter_catalog(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Каталог фильтров для meta JSON и HTML."""
    catalog: list[dict[str, Any]] = []
    filters_cfg: dict[str, Any] = config.get("filters", {})
    columns: dict[str, str] = config.get("columns", {})

    for name in html_filter_names(config):
        flt: dict[str, Any] = filters_cfg[name]
        column_key: str = str(flt.get("column_key", ""))
        entry: dict[str, Any] = {
            "name": name,
            "column_key": column_key,
            "column_label": columns.get(column_key, column_key),
            "display_name": FILTER_DISPLAY_NAMES.get(name, columns.get(column_key, name)),
            "toggle_label": TOGGLE_LABELS.get(name, FILTER_DISPLAY_NAMES.get(name, name)),
            "ui_mode": "toggle",
        }
        exclusive: str | None = flt.get("exclusive_group")
        if exclusive:
            entry["exclusive_group"] = str(exclusive)
        if "contains_all" in flt:
            entry["type"] = "contains_all"
            entry["contains_all"] = list(flt.get("contains_all") or [])
            entry["case_sensitive"] = flt.get("case_sensitive", False)
            parts = " и ".join(f"«{t}»" for t in entry["contains_all"])
            entry["html_label"] = f"Метка: {parts}"
        elif "contains" in flt:
            entry["type"] = "contains"
            entry["contains"] = flt.get("contains")
            entry["case_sensitive"] = flt.get("case_sensitive", False)
            entry["html_label"] = f"Метка содержит «{flt.get('contains')}»"
        else:
            entry["type"] = "eq"
            entry["value"] = flt.get("value", 1)
            entry["html_label"] = f"{entry['display_name']} = {flt.get('value', 1)}"
        catalog.append(entry)
    return catalog


def slice_label(active_names: list[str], catalog: list[dict[str, Any]]) -> str:
    """Человекочитаемая подпись среза."""
    if not active_names:
        return "Без pipeline-фильтров"
    by_name: dict[str, str] = {item["name"]: item["html_label"] for item in catalog}
    return " + ".join(by_name.get(n, n) for n in sorted(active_names))


def build_slice_aggregations(
    records: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Агрегации group_product и group_only для одного среза записей."""
    aggregations: dict[str, Any] = {}
    stats_by_mode: dict[str, dict[str, pd.DataFrame]] = {}
    for mode in JSON_AGGREGATION_MODES:
        mode_config: dict[str, Any] = with_product_analysis_mode(config, mode)
        mode_stats: dict[str, pd.DataFrame] = build_all_statistics(records, mode_config)
        stats_by_mode[mode] = mode_stats
        aggregations[mode] = build_aggregation_visualization(records, mode_stats, mode_config)
    series_count: int = len(aggregations.get("group_product", {}).get("distribution_series", []))
    return {
        "aggregations": aggregations,
        "record_count": int(len(records)),
        "series_count": series_count,
        "_stats_by_mode": stats_by_mode,
    }


def build_all_filter_slices(
    raw_df: pd.DataFrame,
    config: dict[str, Any],
    progress: Any | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Строит visualizations.filter_slices для всех комбинаций HTML-фильтров.
    Фильтрация выполняется на сырых строках до трекинга лидов.
    """
    from src.lead_tracker import build_lead_stage_records

    catalog: list[dict[str, Any]] = build_filter_catalog(config)
    combinations: list[list[str]] = list(iter_filter_combinations(config))
    slices: dict[str, Any] = {}

    base_df: pd.DataFrame = apply_config_only_filters(raw_df, config)
    if base_df.empty:
        logger.warning("После config-only фильтров не осталось строк для JSON-срезов")
        return catalog, slices

    for index, active in enumerate(combinations):
        key: str = filter_slice_key(active)
        label: str = slice_label(active, catalog)
        if progress:
            progress.step(f"JSON-срез {index + 1}/{len(combinations)}: {label}")

        slice_df: pd.DataFrame = apply_filter_subset(base_df, config, active)
        if slice_df.empty:
            logger.info("Срез '%s': нет строк после фильтров", key)
            continue

        slice_records: pd.DataFrame = build_lead_stage_records(slice_df, config, progress=None)
        if slice_records.empty:
            logger.info("Срез '%s': нет lead_stage_records", key)
            continue

        payload: dict[str, Any] = build_slice_aggregations(slice_records, config)
        slices[key] = {
            "active_filters": active,
            "label": label,
            **payload,
        }
        logger.info(
            "Срез '%s': %d записей, %d серий (product)",
            key,
            payload["record_count"],
            payload["series_count"],
        )

    return catalog, slices
