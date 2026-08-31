"""Экспорт агрегированной статистики в JSON."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.settings import col

logger: logging.Logger = logging.getLogger("kanban.json_exporter")


def _frame_to_statistics(frame: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Преобразует DataFrame статистики в список словарей."""
    if frame.empty:
        return []

    tb_name: str = col(config, "tb")
    group_name: str = col(config, "product_group")
    product_name: str = col(config, "product")
    metrics: list[str] = list(config["aggregation"].get("metrics", ["days_on_stage", "days_since_deal"]))

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
            }
        for key, value in row.items():
            key_str: str = str(key)
            for metric in metrics:
                prefix = f"{metric}_"
                if key_str.startswith(prefix) and key_str not in {
                    f"{metric}_min",
                    f"{metric}_max",
                    f"{metric}_count",
                }:
                    item["metrics"][metric][key_str.replace(prefix, "")] = value
        records.append(item)
    return records


def export_json(
    stats: dict[str, Any],
    dimensions: dict[str, Any],
    config: dict[str, Any],
    output_path: Path,
) -> None:
    """Сохраняет JSON только с агрегатами для HTML-дашборда."""
    payload: dict[str, Any] = {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": config.get("mode"),
            "duration_source": config.get("duration_source"),
            "stage_analysis_mode": config.get("stage_analysis_mode"),
            "percentiles": config.get("percentiles"),
            "filters": config.get("filters"),
            "columns": config.get("columns"),
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
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)

    logger.info("JSON сохранён: %s", output_path)
