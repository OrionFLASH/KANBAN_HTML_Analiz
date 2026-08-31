"""Экспорт агрегированной статистики в JSON."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.html_json_export import export_split_html_bundle, html_json_settings
from src.percentile_stats import percentile_label
from src.settings import (
    analysis_row_key,
    col,
    group_only_product_label,
    is_group_only_analysis,
    with_product_analysis_mode,
)
from src.visualization_data import JSON_AGGREGATION_MODES

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


def _build_meta(
    config: dict[str, Any],
    filter_catalog: list[dict[str, Any]] | None,
    visualizations: dict[str, Any] | None,
    slice_keys: list[str],
) -> dict[str, Any]:
    """Блок meta для JSON."""
    excel_mode: str = str(config.get("product_analysis_mode", "group_product"))
    html_cfg: dict[str, Any] = html_json_settings(config)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": config.get("mode"),
        "duration_source": config.get("duration_source"),
        "stage_analysis_mode": config.get("stage_analysis_mode"),
        "product_analysis_mode": excel_mode,
        "excel_product_analysis_mode": excel_mode,
        "json_aggregation_modes": list(JSON_AGGREGATION_MODES),
        "group_only_product_label": group_only_product_label(config),
        "percentiles": config.get("percentiles"),
        "percentile_method": PERCENTILE_METHOD,
        "percentile_method_description": PERCENTILE_METHOD_DESCRIPTION,
        "filters": config.get("filters"),
        "filters_applied": _active_pipeline_filters(config),
        "filters_active": bool(_active_pipeline_filters(config)),
        "data_scope_note": (
            "Excel — по config.product_analysis_mode и filters.enabled. "
            "HTML split-bundle: manifest + slices/*.json (lazy load)."
            if html_cfg.get("bundle_mode") == "split"
            else "JSON содержит visualizations.filter_slices и обе агрегации."
        ),
        "filter_catalog": filter_catalog or ((visualizations or {}).get("filter_catalog")),
        "filter_slice_keys": slice_keys,
        "columns": config.get("columns"),
        "stages_order": config.get("stages_order"),
    }


def _json_dump(path: Path, payload: dict[str, Any], compact: bool) -> None:
    """Запись JSON (compact или pretty)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        if compact:
            json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"), default=str)
        else:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)


def export_json(
    stats_by_mode: dict[str, dict[str, pd.DataFrame]],
    dimensions: dict[str, Any],
    config: dict[str, Any],
    output_path: Path,
    visualizations: dict[str, Any] | None = None,
    filter_catalog: list[dict[str, Any]] | None = None,
    filter_slices: dict[str, Any] | None = None,
) -> None:
    """Сохраняет JSON: split-bundle для HTML или монолит (test)."""
    html_cfg: dict[str, Any] = html_json_settings(config)
    bundle_mode: str = str(html_cfg.get("bundle_mode", "split"))
    compact: bool = bool(html_cfg.get("compact", True))
    include_statistics: bool = bool(html_cfg.get("include_statistics", False))

    viz: dict[str, Any] = visualizations or {}
    slices: dict[str, Any] = filter_slices if filter_slices is not None else viz.get("filter_slices", {})
    slice_keys: list[str] = sorted(slices.keys())

    statistics: dict[str, Any] | None = None
    if include_statistics:
        statistics = {}
        for mode in JSON_AGGREGATION_MODES:
            mode_config: dict[str, Any] = with_product_analysis_mode(config, mode)
            statistics[mode] = _statistics_block(stats_by_mode[mode], mode_config)

    meta: dict[str, Any] = _build_meta(config, filter_catalog, viz, slice_keys)
    prefix: str = config.get("output", {}).get("report_prefix", "kanban_report")
    timestamp: str = output_path.stem.replace(f"{prefix}_", "", 1)

    if bundle_mode == "split" and slices:
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
            "meta": {**meta, "json_bundle_mode": "split", "archive_note": "Данные срезов — в каталоге *_html/slices/"},
            "dimensions": dimensions if html_cfg.get("include_dimensions", True) else {},
            "visualizations": {k: v for k, v in viz.items() if k != "filter_slices"},
        }
        if statistics is not None:
            archive_payload["statistics"] = statistics
        _json_dump(output_path, archive_payload, compact)
        logger.info("JSON-архив (split, без срезов): %s", output_path)
        return

    statistics_full: dict[str, Any] = statistics or {}
    if not statistics_full:
        for mode in JSON_AGGREGATION_MODES:
            mode_config = with_product_analysis_mode(config, mode)
            statistics_full[mode] = _statistics_block(stats_by_mode[mode], mode_config)

    payload: dict[str, Any] = {
        "meta": meta,
        "dimensions": dimensions,
        "statistics": statistics_full,
        "visualizations": viz,
    }
    _json_dump(output_path, payload, compact)
    logger.info("JSON сохранён (monolith): %s", output_path)
