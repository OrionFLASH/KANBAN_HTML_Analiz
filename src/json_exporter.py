"""Экспорт агрегированной статистики в JSON."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger: logging.Logger = logging.getLogger("kanban.json_exporter")


def _frame_to_statistics(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Преобразует DataFrame статистики в список словарей."""
    if frame.empty:
        return []

    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        item: dict[str, Any] = {
            "tb": row.get("ТБ"),
            "product_group": row.get("Группа продукта"),
            "product": row.get("Продукт"),
            "analysis_level": row.get("analysis_level"),
            "current_status": row.get("current_status"),
            "deal_stage": row.get("deal_stage") or None,
            "stage_key": row.get("stage_key"),
            "metrics": {
                "days_on_stage": {
                    "min": row.get("days_on_stage_min"),
                    "max": row.get("days_on_stage_max"),
                    "count": row.get("days_on_stage_count"),
                },
                "days_since_deal": {
                    "min": row.get("days_since_deal_min"),
                    "max": row.get("days_since_deal_max"),
                    "count": row.get("days_since_deal_count"),
                },
            },
        }
        for key, value in row.items():
            key_str: str = str(key)
            if key_str.startswith("days_on_stage_p"):
                item["metrics"]["days_on_stage"][key_str.replace("days_on_stage_", "")] = value
            elif key_str.startswith("days_since_deal_p"):
                item["metrics"]["days_since_deal"][key_str.replace("days_since_deal_", "")] = value
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
        },
        "dimensions": dimensions,
        "statistics": {
            "overall": _frame_to_statistics(stats["overall"]),
            "by_tb": _frame_to_statistics(stats["by_tb"]),
            "tb_sheets": {
                tb: _frame_to_statistics(df)
                for tb, df in stats.get("tb_sheets", {}).items()
            },
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)

    logger.info("JSON сохранён: %s", output_path)
