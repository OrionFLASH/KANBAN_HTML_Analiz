"""Экспорт агрегированной статистики в JSON."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.html_json_export import (
    build_manager_html_payload,
    export_split_html_bundle,
    html_json_settings,
    public_slice_payload,
)
from src.json_sanitize import dump_json_file
from src.percentile_stats import percentile_label
from src.settings import (
    analysis_row_key,
    col,
    group_only_product_label,
    is_group_only_analysis,
    with_product_analysis_mode,
)
from src.visualization_data import json_aggregation_modes

logger: logging.Logger = logging.getLogger("kanban.json_exporter")

PERCENTILE_METHOD: str = "empirical_bottom_tail_integer_days"
PERCENTILE_METHOD_DESCRIPTION: str = (
    "Сроки лидов сортируются по возрастанию. Перцентиль P — нижние p% лидов "
    "(округление вверх: ceil(p/100×N), минимум 1). Значение P — целое число дней "
    "на границе этой доли; min/max — среди этих же лидов."
)


def _active_pipeline_filters(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Список включённых фильтров config.filters для meta JSON."""
    active: list[dict[str, Any]] = []
    for name, flt in config.get("filters", {}).items():
        if not isinstance(flt, dict) or not flt.get("enabled"):
            continue
        entry: dict[str, Any] = {"name": name, "column_key": flt.get("column_key")}
        if "contains_all" in flt:
            entry["contains_all"] = list(flt.get("contains_all") or [])
            entry["case_sensitive"] = flt.get("case_sensitive", False)
        elif "contains" in flt:
            entry["contains"] = flt.get("contains")
            entry["case_sensitive"] = flt.get("case_sensitive", False)
        else:
            entry["value"] = flt.get("value", 1)
        active.append(entry)
    return active


def _config_locked_filters(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Фильтры только из config (html_slice: false) — инфо для UI, без переключателей."""
    from src.filters import is_exclude_filter, is_html_slice_filter

    locked: list[dict[str, Any]] = []
    columns: dict[str, str] = config.get("columns", {})
    short_titles: dict[str, str] = {
        "change_conditions": "Изм. условий",
        "data_entry": "Ввод данных",
        "efs_flag": "ЕФС",
        "exclude_deal_otkaz": "Без отказа",
        "exclude_deal_zakryta": "Без закрытых",
        "exclude_deal_zaklyuchen": "Без заключён.",
        "exclude_current_for_sale": "Без «К ПРОДАЖЕ»",
    }
    for name, flt in config.get("filters", {}).items():
        if not isinstance(flt, dict) or is_html_slice_filter(flt):
            continue
        column_key: str = str(flt.get("column_key", ""))
        enabled: bool = bool(flt.get("enabled", False))
        is_exclude: bool = is_exclude_filter(flt)
        value = flt.get("value", 1) if not is_exclude else None
        token: str = ""
        if is_exclude:
            token = str(flt.get("exclude_equals") or flt.get("exclude_contains") or "").strip()

        if is_exclude:
            ui_state: str = "on" if enabled else "off"
            match_kind: str = "равно" if flt.get("exclude_equals") else "содержит"
            tooltip: str = (
                f"Исключать «{token}» ({match_kind}) в {columns.get(column_key, column_key)}"
                + (" / доп. колонках" if flt.get("also_column_keys") else "")
                + (": да" if enabled else ": нет (фильтр выкл)")
            )
        elif not enabled:
            ui_state = "off"
            tooltip = f"{short_titles.get(name, name)}: фильтр выкл (все значения)"
        else:
            ui_state = "on" if int(value or 0) == 1 else "off"
            tooltip = (
                f"{short_titles.get(name, name)} = {value} "
                f"({'включено в выборке' if ui_state == 'on' else 'выключено в выборке'})"
            )

        locked.append(
            {
                "name": name,
                "column_key": column_key,
                "column_label": columns.get(column_key, column_key),
                "short_label": short_titles.get(name, name),
                "enabled": enabled,
                "value": value,
                "filter_mode": "exclude" if is_exclude else "include",
                "exclude_contains": token or None,
                "html_slice": False,
                "ui_state": ui_state,
                "tooltip": tooltip,
            }
        )
    return locked


def _extract_percentiles(row: dict[str, Any], metric: str, percentiles: list[float]) -> dict[str, Any]:
    """Собирает вложенный блок percentiles для одной метрики."""
    result: dict[str, Any] = {}
    for p in percentiles:
        label: str = percentile_label(p)
        result[label] = {
            "days": row.get(f"{metric}_{label}_days"),
            "count": row.get(f"{metric}_{label}_count"),
            "min": row.get(f"{metric}_{label}_min"),
            "max": row.get(f"{metric}_{label}_max"),
            "le_count": row.get(f"{metric}_{label}_le_count"),
            "gt_count": row.get(f"{metric}_{label}_gt_count"),
        }
    return result


def _frame_to_statistics(frame: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Преобразует DataFrame статистики в список словарей."""
    if frame.empty:
        return []

    tb_name: str = col(config, "tb")
    group_name: str = col(config, "product_group")
    product_name: str = col(config, "product")
    metrics: list[str] = list(config["aggregation"].get("metrics", ["days_on_stage", "days_since_deal"]))
    percentiles: list[float] = [float(p) for p in config.get("percentiles", [20, 50, 80])]

    group_only: bool = is_group_only_analysis(config)
    placeholder: str = group_only_product_label(config)
    row_dim: str = analysis_row_key(config)

    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        group_val = row.get(group_name)
        product_val = placeholder if group_only else row.get(product_name)
        row_key: str = str(group_val if group_only else (row.get(product_name) or group_val))
        item: dict[str, Any] = {
            "tb": row.get(tb_name),
            "product_group": group_val,
            "product": product_val,
            "row_key": row_key,
            "row_dimension": row_dim,
            "analysis_level": row.get("analysis_level"),
            "current_status": row.get("current_status"),
            "deal_stage": row.get("deal_stage") or None,
            "stage_key": row.get("stage_key"),
            "metrics": {},
        }
        for metric in metrics:
            item["metrics"][metric] = {
                "min": row.get(f"{metric}_min"),
                "max": row.get(f"{metric}_max"),
                "count": row.get(f"{metric}_count"),
                "percentiles": _extract_percentiles(row, metric, percentiles),
            }
        records.append(item)
    return records


def _statistics_block(stats: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Блок statistics для одного режима агрегации."""
    return {
        "overall": _frame_to_statistics(stats["overall"], config),
        "by_tb": _frame_to_statistics(stats["by_tb"], config),
        "tb_sheets": {
            tb: _frame_to_statistics(df, config)
            for tb, df in stats.get("tb_sheets", {}).items()
        },
    }


def _analysis_level_locked(config: dict[str, Any]) -> bool:
    """True — в JSON только один уровень (status/substages), фильтр уровня в UI не нужен."""
    mode: str = str(config.get("stage_analysis_mode", "status"))
    return mode in {"status", "substages"}


def _analysis_level_for_meta(config: dict[str, Any]) -> str | None:
    """Зафиксированный уровень анализа для meta JSON."""
    mode: str = str(config.get("stage_analysis_mode", "status"))
    if mode == "status":
        return "status"
    if mode == "substages":
        return "substage"
    return None


def _build_meta(
    config: dict[str, Any],
    filter_catalog: list[dict[str, Any]] | None,
    visualizations: dict[str, Any] | None,
    slice_keys: list[str],
) -> dict[str, Any]:
    """Блок meta для JSON."""
    from src.filters import excluded_analysis_stages
    from src.visualization_data import stage_order as resolve_stage_order

    excel_mode: str = str(config.get("product_analysis_mode", "group_product"))
    html_cfg: dict[str, Any] = html_json_settings(config)
    excluded_stages: list[str] = excluded_analysis_stages(config)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": config.get("mode"),
        "duration_source": config.get("duration_source"),
        "stage_analysis_mode": config.get("stage_analysis_mode"),
        "analysis_level": _analysis_level_for_meta(config),
        "analysis_level_locked": _analysis_level_locked(config),
        "product_analysis_mode": excel_mode,
        "excel_product_analysis_mode": excel_mode,
        "json_aggregation_modes": json_aggregation_modes(config),
        "aggregation_locked": True,
        "group_only_product_label": group_only_product_label(config),
        "percentiles": config.get("percentiles"),
        "percentile_method": PERCENTILE_METHOD,
        "percentile_method_description": PERCENTILE_METHOD_DESCRIPTION,
        "filters": config.get("filters"),
        "filters_applied": _active_pipeline_filters(config),
        "filters_active": bool(_active_pipeline_filters(config)),
        "config_locked_filters": _config_locked_filters(config),
        "data_scope_note": (
            "Один JSON для UI (file://): filter_slices и managers внутри файла. "
            "Каталоги *_html не создаются."
            if html_cfg.get("bundle_mode") != "split"
            else "HTML split-bundle: manifest + slices/*.json (нужен HTTP к slices/)."
        ),
        "json_bundle_mode": str(html_cfg.get("bundle_mode", "monolith")),
        "show_managers_tab": bool(config.get("dashboard", {}).get("show_managers_tab", False)),
        "filter_catalog": filter_catalog or ((visualizations or {}).get("filter_catalog")),
        "filter_slice_keys": slice_keys,
        "columns": config.get("columns"),
        "stages_order": resolve_stage_order(config),
        "excluded_stages": excluded_stages,
    }


def _json_dump(path: Path, payload: dict[str, Any], compact: bool) -> None:
    """Запись JSON без NaN/Infinity (валидно для браузера / file://)."""
    dump_json_file(path, payload, compact=compact)


def export_json(
    stats_by_mode: dict[str, dict[str, pd.DataFrame]],
    dimensions: dict[str, Any],
    config: dict[str, Any],
    output_path: Path,
    visualizations: dict[str, Any] | None = None,
    filter_catalog: list[dict[str, Any]] | None = None,
    filter_slices: dict[str, Any] | None = None,
    manager_payload: dict[str, Any] | None = None,
) -> None:
    """
    Сохраняет JSON для UI.
    По умолчанию monolith: один файл со срезами (+ managers), без каталога *_html.
    Режим split — только если явно bundle_mode=split (нужен HTTP к slices/).
    """
    html_cfg: dict[str, Any] = html_json_settings(config)
    bundle_mode: str = str(html_cfg.get("bundle_mode", "monolith"))
    compact: bool = bool(html_cfg.get("compact", True))
    include_statistics: bool = bool(html_cfg.get("include_statistics", False))

    viz: dict[str, Any] = dict(visualizations or {})
    slices: dict[str, Any] = filter_slices if filter_slices is not None else viz.get("filter_slices", {})
    public_slices: dict[str, Any] = {
        key: public_slice_payload(slice_data, config) for key, slice_data in slices.items()
    }
    slice_keys: list[str] = sorted(public_slices.keys())

    statistics: dict[str, Any] | None = None
    if include_statistics:
        statistics = {}
        for mode in json_aggregation_modes(config):
            mode_config: dict[str, Any] = with_product_analysis_mode(config, mode)
            statistics[mode] = _statistics_block(stats_by_mode[mode], mode_config)

    meta: dict[str, Any] = _build_meta(config, filter_catalog, viz, slice_keys)
    prefix: str = config.get("output", {}).get("report_prefix", "kanban_report")
    timestamp: str = output_path.stem.replace(f"{prefix}_", "", 1)

    if bundle_mode == "split" and public_slices:
        export_split_html_bundle(
            meta=meta,
            dimensions=dimensions,
            visualizations=viz,
            filter_slices=slices,
            config=config,
            output_dir=output_path.parent,
            prefix=prefix,
            timestamp=timestamp,
        )
        archive_payload: dict[str, Any] = {
            "meta": {
                **meta,
                "json_bundle_mode": "split",
                "archive_note": "Данные срезов — в каталоге *_html/slices/",
            },
            "dimensions": dimensions if html_cfg.get("include_dimensions", True) else {},
            "visualizations": {k: v for k, v in viz.items() if k != "filter_slices"},
        }
        if statistics is not None:
            archive_payload["statistics"] = statistics
        _json_dump(output_path, archive_payload, compact)
        logger.info("JSON-архив (split, без срезов): %s", output_path)
        return

    viz["filter_slices"] = public_slices
    # Не дублировать тяжёлые поля default-среза на верхнем уровне (они уже в filter_slices)
    for heavy_key in (
        "aggregations",
        "distribution_series",
        "pivot_flat",
        "default_pivot_matrix",
        "distribution_format",
        "row_dimension",
    ):
        viz.pop(heavy_key, None)

    default_key: str = str((viz.get("default_view") or {}).get("filter_slice") or "none")
    if default_key not in public_slices and public_slices:
        default_key = next(iter(public_slices))
        if isinstance(viz.get("default_view"), dict):
            viz["default_view"]["filter_slice"] = default_key

    payload: dict[str, Any] = {
        "meta": {**meta, "json_bundle_mode": "monolith"},
        "dimensions": dimensions if html_cfg.get("include_dimensions", True) else {},
        "visualizations": viz,
    }
    if statistics is not None:
        payload["statistics"] = statistics

    if manager_payload and bool(html_cfg.get("embed_managers", True)):
        payload["managers"] = build_manager_html_payload(manager_payload, config)
        meta_related: dict[str, Any] = {
            "managers_embedded": True,
            "ui_load": "Выберите этот один файл в дашборде (file://).",
        }
        payload["meta"] = {**payload["meta"], **meta_related}

    _json_dump(output_path, payload, compact)
    size_mb: float = output_path.stat().st_size / (1024 * 1024)
    logger.info("JSON monolith сохранён: %s (%.1f MB)", output_path.name, size_mb)
