"""Срезы данных по комбинациям pipeline-фильтров для JSON/HTML."""

from __future__ import annotations

import itertools
import logging
from typing import Any, Iterator

import pandas as pd

from src.aggregator import build_all_statistics
from src.filters import (
    apply_config_only_filters,
    default_html_active_filters,
    enabled_terminal_exclusion_names,
    is_exclude_filter,
    is_html_slice_filter,
    row_keep_mask,
    split_active_filter_names,
)
from src.settings import col, filter_column_name, with_product_analysis_mode
from src.v1.visualization_data import (
    build_aggregation_visualization,
    json_aggregation_modes,
)

logger: logging.Logger = logging.getLogger("kanban.filter_slices")

FILTER_DISPLAY_NAMES: dict[str, str] = {
    "change_conditions": "Изменение условий",
    "data_entry": "Ввод данных",
    "strategy_label": "Все стратегии",
    "strategy_label_2026": "Стратегия · 2026",
    "exclude_deal_otkaz": "Искл. отказ",
    "exclude_deal_zakryta": "Искл. закрыта",
    "exclude_deal_zaklyuchen": "Искл. заключен",
}

TOGGLE_LABELS: dict[str, str] = {
    "change_conditions": "Изменение условий = 1",
    "data_entry": "Ввод данных = 1",
    "strategy_label": "Метка содержит «Стратегия»",
    "strategy_label_2026": "Метка: «Стратегия» и «2026»",
    "exclude_deal_otkaz": "Исключить «отказ» (стадия сделки / текущий статус)",
    "exclude_deal_zakryta": "Исключить «закрыта» в стадии сделки",
    "exclude_deal_zaklyuchen": "Исключить «заключен» в стадии сделки",
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


def default_filter_slice_key(config: dict[str, Any]) -> str:
    """Ключ среза по умолчанию для HTML (default_active фильтры)."""
    return filter_slice_key(default_html_active_filters(config))


def iter_filter_combinations(config: dict[str, Any]) -> Iterator[list[str]]:
    """
    Комбинации HTML-фильтров (включая пустую).
    Два фильтра одной exclusive_group вместе не комбинируются.
    """
    names: list[str] = html_filter_names(config)
    filters_cfg: dict[str, Any] = config.get("filters", {})
    for size in range(len(names) + 1):
        for combo in itertools.combinations(names, size):
            if _combo_respects_exclusive_groups(list(combo), filters_cfg):
                yield list(combo)


def _combo_respects_exclusive_groups(
    active_names: list[str],
    filters_cfg: dict[str, Any],
) -> bool:
    """False — в комбинации два фильтра одной exclusive_group."""
    seen: set[str] = set()
    for name in active_names:
        flt: dict[str, Any] | None = filters_cfg.get(name)
        if not isinstance(flt, dict):
            continue
        group = flt.get("exclusive_group")
        if not group:
            continue
        key: str = str(group)
        if key in seen:
            return False
        seen.add(key)
    return True


def _filter_mask(df: pd.DataFrame, flt: dict[str, Any], column: str, config: dict[str, Any]) -> pd.Series:
    """Маска строк для одного активного HTML-фильтра."""
    return row_keep_mask(df, column, flt, config)


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
        if not isinstance(flt, dict) or is_exclude_filter(flt):
            continue
        column: str | None = filter_column_name(config, flt)
        if not column or column not in result.columns:
            logger.warning("HTML-фильтр '%s': колонка не найдена", name)
            return result.iloc[0:0].copy()
        result = result[_filter_mask(result, flt, column, config)]

    return result.reset_index(drop=True)


def build_filter_catalog(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Каталог фильтров для meta JSON и HTML."""
    from src.filters import normalize_filter

    catalog: list[dict[str, Any]] = []
    filters_cfg: dict[str, Any] = config.get("filters", {})
    columns: dict[str, str] = config.get("columns", {})

    for name in html_filter_names(config):
        flt: dict[str, Any] = filters_cfg[name]
        uni: dict[str, Any] = normalize_filter(flt)
        column_key: str = str(uni.get("column_key", ""))
        values: list[Any] = list(uni.get("values") or [])
        entry: dict[str, Any] = {
            "name": name,
            "column_key": column_key,
            "column_label": columns.get(column_key, column_key),
            "display_name": FILTER_DISPLAY_NAMES.get(name, columns.get(column_key, name)),
            "toggle_label": TOGGLE_LABELS.get(name, FILTER_DISPLAY_NAMES.get(name, name)),
            "ui_mode": "toggle",
            "default_active": bool(flt.get("default_active", False)),
            "action": uni.get("action"),
            "match": uni.get("match"),
            "values": values,
            "values_mode": uni.get("values_mode"),
            "value_type": uni.get("value_type"),
        }
        exclusive: str | None = flt.get("exclusive_group")
        if exclusive:
            entry["exclusive_group"] = str(exclusive)
        if is_exclude_filter(uni):
            entry["type"] = "exclude_contains"
            entry["filter_mode"] = "exclude"
            token: str = ", ".join(str(v) for v in values)
            entry["exclude_contains"] = token
            entry["case_sensitive"] = uni.get("case_sensitive", False)
            entry["html_label"] = f"Исключить стадии с «{token}»"
            entry["ui_group"] = flt.get("ui_group", "terminal_deal_stages")
            also_keys = [str(k) for k in (uni.get("column_keys") or uni.get("also_column_keys") or [])]
            if also_keys:
                entry["also_column_keys"] = also_keys
                also_labels = [columns.get(k, k) for k in also_keys]
                entry["html_label"] = (
                    f"Исключить «{token}» "
                    f"({entry['column_label']} / {' / '.join(also_labels)})"
                )
        elif uni.get("match") == "contains" and uni.get("values_mode") == "all":
            entry["type"] = "contains_all"
            entry["contains_all"] = values
            entry["case_sensitive"] = uni.get("case_sensitive", False)
            parts = " и ".join(f"«{t}»" for t in values)
            entry["html_label"] = f"Метка: {parts}"
        elif uni.get("match") == "contains":
            entry["type"] = "contains"
            entry["contains"] = values[0] if len(values) == 1 else values
            entry["case_sensitive"] = uni.get("case_sensitive", False)
            if len(values) == 1:
                entry["html_label"] = f"Метка содержит «{values[0]}»"
            else:
                parts_any = " или ".join(f"«{t}»" for t in values)
                entry["html_label"] = f"Метка содержит {parts_any}"
        else:
            entry["type"] = "eq"
            entry["value"] = values[0] if values else 1
            entry["html_label"] = f"{entry['display_name']} = {entry['value']}"
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
    """Агрегация для одного среза — только режим из config.product_analysis_mode."""
    aggregations: dict[str, Any] = {}
    stats_by_mode: dict[str, dict[str, pd.DataFrame]] = {}
    modes: list[str] = json_aggregation_modes(config)
    for mode in modes:
        mode_config: dict[str, Any] = with_product_analysis_mode(config, mode)
        mode_stats: dict[str, pd.DataFrame] = build_all_statistics(records, mode_config)
        stats_by_mode[mode] = mode_stats
        aggregations[mode] = build_aggregation_visualization(records, mode_stats, mode_config)
    primary: str = modes[0] if modes else "group_product"
    series_count: int = len(aggregations.get(primary, {}).get("distribution_series", []))
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

        inclusion_active, exclusion_active = split_active_filter_names(config, active)
        # Config-only exclude (html_slice: false) всегда из config.enabled
        config_excludes: list[str] = [
            name
            for name in enabled_terminal_exclusion_names(config)
            if not is_html_slice_filter(config.get("filters", {}).get(name) or {})
        ]
        exclusion_merged: list[str] = sorted(set(exclusion_active) | set(config_excludes))

        slice_df: pd.DataFrame = apply_filter_subset(base_df, config, inclusion_active)
        if slice_df.empty:
            logger.info("Срез '%s': нет строк после фильтров", key)
            continue

        slice_records: pd.DataFrame = build_lead_stage_records(
            slice_df,
            config,
            progress=None,
            exclusion_filter_names=exclusion_merged,
        )
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
