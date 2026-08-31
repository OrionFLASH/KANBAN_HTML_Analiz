"""Экспорт агрегированной статистики в JSON."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.percentile_stats import percentile_label
from src.settings import col

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
        if "contains" in flt:
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

    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        item: dict[str, Any] = {
            "tb": row.get(tb_name),
            "product_group": row.get(group_name),
            "product": row.get(product_name),
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


def export_json(
    stats: dict[str, Any],
    dimensions: dict[str, Any],
    config: dict[str, Any],
    output_path: Path,
    visualizations: dict[str, Any] | None = None,
) -> None:
    """Сохраняет JSON с агрегатами и данными для HTML-дашборда."""
    payload: dict[str, Any] = {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": config.get("mode"),
            "duration_source": config.get("duration_source"),
            "stage_analysis_mode": config.get("stage_analysis_mode"),
            "product_analysis_mode": config.get("product_analysis_mode", "group_product"),
            "percentiles": config.get("percentiles"),
            "percentile_method": PERCENTILE_METHOD,
            "percentile_method_description": PERCENTILE_METHOD_DESCRIPTION,
            "filters": config.get("filters"),
            "filters_applied": _active_pipeline_filters(config),
            "filters_active": bool(_active_pipeline_filters(config)),
            "data_scope_note": (
                "Все агрегаты и visualizations построены после pipeline-фильтров "
                "(config.filters с enabled=true). HTML-фильтры работают внутри этого среза."
            ),
            "columns": config.get("columns"),
            "stages_order": config.get("stages_order"),
        },
        "dimensions": dimensions,
        "statistics": {
            "overall": _frame_to_statistics(stats["overall"], config),
            "by_tb": _frame_to_statistics(stats["by_tb"], config),
            "tb_sheets": {
                tb: _frame_to_statistics(df, config)
                for tb, df in stats.get("tb_sheets", {}).items()
            },
        },
        "visualizations": visualizations or {},
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)

    latest_path: Path = output_path.parent / "kanban_report_latest.json"
    shutil.copy2(output_path, latest_path)

    logger.info("JSON сохранён: %s", output_path)
