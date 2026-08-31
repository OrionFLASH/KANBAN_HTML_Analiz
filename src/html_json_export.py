"""Экспорт JSON для HTML: split-bundle, компактный формат, прореживание серий."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

logger: logging.Logger = logging.getLogger("kanban.html_json_export")

BUNDLE_VERSION: str = "2"
DEFAULT_SLICES_SUBDIR: str = "slices"


def html_json_settings(config: dict[str, Any]) -> dict[str, Any]:
    """Настройки HTML JSON из dashboard.html_json с умолчаниями."""
    dash: dict[str, Any] = config.get("dashboard", {})
    defaults: dict[str, Any] = {
        "bundle_mode": "split",
        "compact": True,
        "include_statistics": False,
        "include_dimensions": True,
        "max_distribution_points": 800,
        "slices_subdir": DEFAULT_SLICES_SUBDIR,
        "write_monolith_archive": True,
    }
    raw: dict[str, Any] = dash.get("html_json") or {}
    return {**defaults, **raw}


def _json_dump_kwargs(compact: bool) -> dict[str, Any]:
    """Параметры json.dump: compact без indent экономит 30–40 %."""
    if compact:
        return {"ensure_ascii": False, "separators": (",", ":"), "default": str}
    return {"ensure_ascii": False, "indent": 2, "default": str}


def downsample_days_sorted(days: list[int], max_points: int) -> list[int]:
    """Равномерное прореживание шкалы дней для HTML (граница сохраняется)."""
    if max_points <= 0 or len(days) <= max_points:
        return days
    step: int = max(1, math.ceil(len(days) / max_points))
    sampled: list[int] = days[::step]
    if sampled[-1] != days[-1]:
        sampled.append(days[-1])
    return sampled


def optimize_aggregation_for_html(aggregation: dict[str, Any], max_points: int) -> dict[str, Any]:
    """Уменьшает distribution_series для браузера; pivot_flat не трогаем."""
    if max_points <= 0:
        return aggregation
    series: list[dict[str, Any]] = list(aggregation.get("distribution_series") or [])
    if not series:
        return aggregation
    optimized: list[dict[str, Any]] = []
    for item in series:
        copy_item: dict[str, Any] = dict(item)
        days: list[int] = list(copy_item.get("days_sorted") or [])
        if days and len(days) > max_points:
            copy_item["days_sorted"] = downsample_days_sorted(days, max_points)
            copy_item["days_sorted_full_count"] = len(days)
        optimized.append(copy_item)
    result: dict[str, Any] = dict(aggregation)
    result["distribution_series"] = optimized
    return result


def public_slice_payload(slice_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Срез без служебных полей; опционально прореживает серии."""
    cfg: dict[str, Any] = html_json_settings(config)
    max_points: int = int(cfg.get("max_distribution_points", 0))
    aggregations: dict[str, Any] = {}
    for mode, agg in (slice_data.get("aggregations") or {}).items():
        aggregations[mode] = optimize_aggregation_for_html(agg, max_points)
    return {
        k: v
        for k, v in slice_data.items()
        if k not in ("_stats_by_mode", "aggregations")
    } | {"aggregations": aggregations}


def write_json_file(path: Path, payload: dict[str, Any], compact: bool) -> int:
    """Записывает JSON; возвращает размер файла в байтах."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, **_json_dump_kwargs(compact))
    return path.stat().st_size


def build_manifest_payload(
    meta: dict[str, Any],
    dimensions: dict[str, Any],
    visualizations: dict[str, Any],
    slice_keys: list[str],
    config: dict[str, Any],
    slices_base: str,
) -> dict[str, Any]:
    """Манифест: meta + dimensions + visualizations без тяжёлых filter_slices."""
    cfg: dict[str, Any] = html_json_settings(config)
    viz: dict[str, Any] = dict(visualizations)
    viz["filter_slices"] = {}
    meta_out: dict[str, Any] = {
        **meta,
        "json_bundle_version": BUNDLE_VERSION,
        "json_bundle_mode": "split",
        "default_slice": str(
            visualizations.get("default_view", {}).get("filter_slice", "none")
        ),
        "slice_keys": slice_keys,
        "slices_base": slices_base,
        "html_json": cfg,
    }
    payload: dict[str, Any] = {
        "meta": meta_out,
        "visualizations": viz,
    }
    if cfg.get("include_dimensions", True):
        payload["dimensions"] = dimensions
    return payload


def export_split_html_bundle(
    meta: dict[str, Any],
    dimensions: dict[str, Any],
    visualizations: dict[str, Any],
    filter_slices: dict[str, Any],
    config: dict[str, Any],
    output_dir: Path,
    prefix: str,
    timestamp: str,
) -> tuple[Path, dict[str, int]]:
    """
    Пишет manifest + slices/*.json в каталог {prefix}_{timestamp}_html/.
    Возвращает путь манифеста и размеры файлов (байты).
    """
    cfg: dict[str, Any] = html_json_settings(config)
    compact: bool = bool(cfg.get("compact", True))
    slices_subdir: str = str(cfg.get("slices_subdir", DEFAULT_SLICES_SUBDIR))

    bundle_dir: Path = output_dir / f"{prefix}_{timestamp}_html"
    slices_dir: Path = bundle_dir / slices_subdir
    manifest_path: Path = bundle_dir / f"{prefix}_{timestamp}.manifest.json"

    slice_keys: list[str] = sorted(filter_slices.keys())
    sizes: dict[str, int] = {}

    for key, slice_data in filter_slices.items():
        public: dict[str, Any] = public_slice_payload(slice_data, config)
        slice_path: Path = slices_dir / f"{key}.json"
        sizes[f"slice:{key}"] = write_json_file(
            slice_path,
            {"key": key, **public},
            compact,
        )

    manifest: dict[str, Any] = build_manifest_payload(
        meta,
        dimensions,
        visualizations,
        slice_keys,
        config,
        slices_base=f"{slices_subdir}/",
    )
    sizes["manifest"] = write_json_file(manifest_path, manifest, compact)

    total_slices: int = sum(v for k, v in sizes.items() if k.startswith("slice:"))
    logger.info(
        "Split JSON: manifest %d KB, срезы суммарно %d MB (%d файлов)",
        sizes["manifest"] // 1024,
        total_slices // (1024 * 1024),
        len(slice_keys),
    )
    return manifest_path, sizes


def build_manager_html_payload(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """JSON менеджеров для HTML: records, exceedances, агрегаты."""
    return {
        "meta": payload.get("meta", {}),
        "dimensions": payload.get("dimensions") or {"product_groups": [], "products": []},
        "records": payload.get("records") or [],
        "exceedances": payload.get("exceedances") or [],
        "top_by_tb": payload.get("top_by_tb") or [],
        "top_by_tb_grouped": payload.get("top_by_tb_grouped") or [],
        "detail_by_product": payload.get("detail_by_product") or [],
        "manager_totals": payload.get("manager_totals") or [],
        "charts": payload.get("charts") or {"by_tb": [], "facts": []},
        "thresholds_count": payload.get("thresholds_count"),
    }
