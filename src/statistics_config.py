"""Конфигурация расчёта и экспорта min/max/перцентилей."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.percentile_stats import percentile_label
from src.settings import percentile_display_value

# Порядок суффиксов: счётчики лидов слева от границы (days), затем справа
_SUFFIX_ORDER_LEFT: tuple[str, ...] = ("le_count", "days", "gt_count", "min", "max", "count", "km_count")
_SUFFIX_ORDER_DEFAULT: tuple[str, ...] = ("days", "le_count", "gt_count", "min", "max", "count", "km_count")

_DEFAULT_P20_P50: dict[str, Any] = {
    "compute": True,
    "export_days": True,
    "export_count": False,
    "export_le_count": False,
    "export_gt_count": False,
    "export_min": False,
    "export_max": False,
    "export_km_count": False,
}

_DEFAULT_P80: dict[str, Any] = {
    "compute": True,
    "export_days": True,
    "export_count": False,
    "export_le_count": True,
    "export_gt_count": True,
    "export_min": True,
    "export_max": True,
    "export_km_count": True,
}

DEFAULT_STATISTICS_CONFIG: dict[str, Any] = {
    "attach_counts_left": True,
    "min": {
        "compute": True,
        "export": False,
        "export_le_count": False,
        "export_gt_count": False,
    },
    "max": {
        "compute": True,
        "export": False,
        "export_le_count": False,
        "export_gt_count": False,
    },
    "total_count": {
        "compute": True,
        "export": True,
    },
    "percentiles": [
        {"p": 20, **_DEFAULT_P20_P50},
        {"p": 50, **_DEFAULT_P20_P50},
        {"p": 80, **_DEFAULT_P80},
    ],
}


def statistics_config(config: dict[str, Any]) -> dict[str, Any]:
    """Нормализованный блок output.statistics с дефолтами."""
    raw: dict[str, Any] = dict(config.get("output", {}).get("statistics") or {})
    merged: dict[str, Any] = deepcopy(DEFAULT_STATISTICS_CONFIG)

    for key in ("attach_counts_left",):
        if key in raw:
            merged[key] = bool(raw[key])

    for block in ("min", "max", "total_count"):
        if block in raw and isinstance(raw[block], dict):
            merged[block].update(raw[block])

    # Профили перцентилей: из config или синхронизация с top-level percentiles
    if raw.get("percentiles"):
        profiles: list[dict[str, Any]] = []
        for item in raw["percentiles"]:
            if not isinstance(item, dict) or "p" not in item:
                continue
            p_val: float = float(item["p"])
            base: dict[str, Any] = deepcopy(_DEFAULT_P80 if abs(p_val - 80.0) < 1e-9 else _DEFAULT_P20_P50)
            base.update(item)
            base["p"] = p_val
            profiles.append(base)
        if profiles:
            merged["percentiles"] = profiles
    else:
        top_level: list[float] = [float(p) for p in config.get("percentiles", [20, 50, 80])]
        merged["percentiles"] = [
            {"p": p, **(deepcopy(_DEFAULT_P80) if abs(p - 80.0) < 1e-9 else deepcopy(_DEFAULT_P20_P50))}
            for p in top_level
        ]

    return merged


def active_percentiles(config: dict[str, Any]) -> list[float]:
    """Перцентили с compute=true (для агрегации)."""
    stats: dict[str, Any] = statistics_config(config)
    result: list[float] = []
    for profile in stats.get("percentiles", []):
        if profile.get("compute", True):
            result.append(float(profile["p"]))
    if not result:
        return [float(p) for p in config.get("percentiles", [20, 50, 80])]
    return result


def percentile_profile(config: dict[str, Any], p: float) -> dict[str, Any]:
    """Профиль экспорта одного перцентиля."""
    stats: dict[str, Any] = statistics_config(config)
    for profile in stats.get("percentiles", []):
        if abs(float(profile["p"]) - float(p)) < 1e-9:
            return dict(profile)
    default: dict[str, Any] = deepcopy(_DEFAULT_P80 if abs(float(p) - 80.0) < 1e-9 else _DEFAULT_P20_P50)
    default["p"] = float(p)
    return default


def _suffix_order(config: dict[str, Any]) -> tuple[str, ...]:
    return _SUFFIX_ORDER_LEFT if statistics_config(config).get("attach_counts_left", True) else _SUFFIX_ORDER_DEFAULT


def _export_suffix_map(profile: dict[str, Any]) -> dict[str, bool]:
    """Суффикс колонки → экспортировать ли."""
    return {
        "days": bool(profile.get("export_days", True)),
        "count": bool(profile.get("export_count", False)),
        "le_count": bool(profile.get("export_le_count", False)),
        "gt_count": bool(profile.get("export_gt_count", False)),
        "min": bool(profile.get("export_min", False)),
        "max": bool(profile.get("export_max", False)),
        "km_count": bool(profile.get("export_km_count", False)),
    }


def export_columns_for_metric(metric: str, config: dict[str, Any]) -> list[str]:
    """
    Внутренние имена колонок метрики для экспорта (Excel/JSON), в порядке отображения.
    Пример: days_on_stage_count, days_on_stage_p20_days, days_on_stage_p80_le_count, …
    """
    stats: dict[str, Any] = statistics_config(config)
    columns: list[str] = []
    suffix_order: tuple[str, ...] = _suffix_order(config)

    min_cfg: dict[str, Any] = stats.get("min", {})
    if min_cfg.get("export"):
        if min_cfg.get("export_le_count"):
            columns.append(f"{metric}_min_le_count")
        columns.append(f"{metric}_min")
        if min_cfg.get("export_gt_count"):
            columns.append(f"{metric}_min_gt_count")

    max_cfg: dict[str, Any] = stats.get("max", {})
    if max_cfg.get("export"):
        if max_cfg.get("export_le_count"):
            columns.append(f"{metric}_max_le_count")
        columns.append(f"{metric}_max")
        if max_cfg.get("export_gt_count"):
            columns.append(f"{metric}_max_gt_count")

    if stats.get("total_count", {}).get("export", True):
        columns.append(f"{metric}_count")

    for profile in stats.get("percentiles", []):
        p: float = float(profile["p"])
        label: str = percentile_label(p)
        export_map: dict[str, bool] = _export_suffix_map(profile)
        for suffix in suffix_order:
            if export_map.get(suffix, False):
                columns.append(f"{metric}_{label}_{suffix}")

    return columns


def build_percentile_column_mapping(config: dict[str, Any]) -> dict[str, str]:
    """Mapping внутренних имён колонок перцентилей → заголовки Excel."""
    templates: dict[str, dict[str, str]] = config.get("output", {}).get(
        "percentile_column_labels",
        {},
    )
    metrics: list[str] = list(config.get("aggregation", {}).get("metrics", ["days_on_stage", "days_since_deal"]))
    mapping: dict[str, str] = {}

    for metric in metrics:
        metric_templates: dict[str, str] = templates.get(metric, templates.get("days_on_stage", {}))
        for col_name in export_columns_for_metric(metric, config):
            if not col_name.startswith(f"{metric}_"):
                continue
            rest: str = col_name[len(metric) + 1 :]
            if rest in ("min", "max", "count"):
                continue
            if "_min_" in rest or "_max_" in rest:
                continue
            # percentile suffix: p20_days, p80_le_count, …
            parts: list[str] = rest.split("_", 1)
            if len(parts) != 2:
                continue
            p_label, suffix = parts[0], parts[1]
            if not p_label.startswith("p"):
                continue
            p_text: str = p_label[1:].replace("_", ".")
            template: str | None = metric_templates.get(suffix)
            if template:
                mapping[col_name] = template.format(p=p_text)

    return mapping


def build_min_max_count_column_mapping(config: dict[str, Any]) -> dict[str, str]:
    """Mapping min/max/count колонок по флагам statistics."""
    labels: dict[str, str] = config.get("output", {}).get("column_labels", {})
    stats: dict[str, Any] = statistics_config(config)
    metrics: list[str] = list(config.get("aggregation", {}).get("metrics", ["days_on_stage", "days_since_deal"]))
    mapping: dict[str, str] = {}

    for metric in metrics:
        min_cfg: dict[str, Any] = stats.get("min", {})
        if min_cfg.get("export"):
            if min_cfg.get("export_le_count"):
                mapping[f"{metric}_min_le_count"] = labels.get(f"{metric}_min_le_count", f"{metric} мин ≤")
            key_min: str = f"{metric}_min"
            mapping[key_min] = labels.get(key_min, key_min)
            if min_cfg.get("export_gt_count"):
                mapping[f"{metric}_min_gt_count"] = labels.get(f"{metric}_min_gt_count", f"{metric} мин >")

        max_cfg: dict[str, Any] = stats.get("max", {})
        if max_cfg.get("export"):
            if max_cfg.get("export_le_count"):
                mapping[f"{metric}_max_le_count"] = labels.get(f"{metric}_max_le_count", f"{metric} макс ≤")
            key_max: str = f"{metric}_max"
            mapping[key_max] = labels.get(key_max, key_max)
            if max_cfg.get("export_gt_count"):
                mapping[f"{metric}_max_gt_count"] = labels.get(f"{metric}_max_gt_count", f"{metric} макс >")

        if stats.get("total_count", {}).get("export", True):
            key_count: str = f"{metric}_count"
            mapping[key_count] = labels.get(key_count, key_count)

    return mapping


def build_statistics_export_mapping(config: dict[str, Any]) -> dict[str, str]:
    """Полный mapping статистических колонок для Excel."""
    from src.filter_funnel import build_filter_audit_mapping
    from src.outlier_clipping import build_outlier_audit_mapping

    result: dict[str, str] = {}
    result.update(build_min_max_count_column_mapping(config))
    result.update(build_percentile_column_mapping(config))
    result.update(build_filter_audit_mapping(config))
    result.update(build_outlier_audit_mapping(config))
    return result


def _is_statistics_column(name: str, metrics: list[str]) -> bool:
    """True — колонка относится к min/max/перцентилям метрики."""
    for metric in metrics:
        if name.startswith(f"{metric}_"):
            return True
    return False


def _is_outlier_audit_column(name: str) -> bool:
    """True — колонка аудита отсечения выбросов."""
    return name in {"outlier_before", "outlier_after", "outlier_clipped_total"} or name.startswith(
        "outlier_rule_"
    )


def _is_filter_audit_column(name: str) -> bool:
    """True — колонка аудита входных фильтров."""
    return name in {"filter_before", "filter_after"} or name.startswith("filter_dropped_")


def filter_and_order_statistics_frame(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Оставляет измерения + стат-колонки + аудит фильтров/выбросов в нужном порядке."""
    from src.filter_funnel import filter_audit_column_keys
    from src.outlier_clipping import audit_column_keys

    if frame.empty:
        return frame
    metrics: list[str] = list(config.get("aggregation", {}).get("metrics", ["days_on_stage", "days_since_deal"]))
    export_cols: list[str] = []
    for metric in metrics:
        for col_name in export_columns_for_metric(metric, config):
            if col_name in frame.columns and col_name not in export_cols:
                export_cols.append(col_name)

    filter_cols: list[str] = [c for c in filter_audit_column_keys(config) if c in frame.columns]
    for c in frame.columns:
        if _is_filter_audit_column(str(c)) and c not in filter_cols:
            filter_cols.append(str(c))

    audit_cols: list[str] = [c for c in audit_column_keys(config) if c in frame.columns]
    # На случай неизвестных outlier_* колонок
    for c in frame.columns:
        if _is_outlier_audit_column(str(c)) and c not in audit_cols:
            audit_cols.append(str(c))

    dim_cols: list[str] = [
        c
        for c in frame.columns
        if not _is_statistics_column(str(c), metrics)
        and not _is_outlier_audit_column(str(c))
        and not _is_filter_audit_column(str(c))
    ]
    # Сначала входные фильтры (до/после + по каждому), затем выбросы
    ordered: list[str] = dim_cols + export_cols + filter_cols + audit_cols
    return frame[ordered].copy()


def extract_percentile_json(
    row: dict[str, Any],
    metric: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Блок percentiles для JSON с учётом флагов export."""
    result: dict[str, Any] = {}
    stats: dict[str, Any] = statistics_config(config)

    for profile in stats.get("percentiles", []):
        p: float = float(profile["p"])
        label: str = percentile_label(p)
        export_map: dict[str, bool] = _export_suffix_map(profile)
        block: dict[str, Any] = {}
        for suffix, export_flag in export_map.items():
            if export_flag:
                block[suffix] = row.get(f"{metric}_{label}_{suffix}")
        if block:
            result[label] = block

    return result


def extract_metric_json(row: dict[str, Any], metric: str, config: dict[str, Any]) -> dict[str, Any]:
    """Блок metrics[metric] для JSON."""
    stats: dict[str, Any] = statistics_config(config)
    block: dict[str, Any] = {}

    min_cfg: dict[str, Any] = stats.get("min", {})
    if min_cfg.get("export"):
        block["min"] = row.get(f"{metric}_min")
        if min_cfg.get("export_le_count"):
            block["min_le_count"] = row.get(f"{metric}_min_le_count")
        if min_cfg.get("export_gt_count"):
            block["min_gt_count"] = row.get(f"{metric}_min_gt_count")

    max_cfg: dict[str, Any] = stats.get("max", {})
    if max_cfg.get("export"):
        block["max"] = row.get(f"{metric}_max")
        if max_cfg.get("export_le_count"):
            block["max_le_count"] = row.get(f"{metric}_max_le_count")
        if max_cfg.get("export_gt_count"):
            block["max_gt_count"] = row.get(f"{metric}_max_gt_count")

    if stats.get("total_count", {}).get("export", True):
        block["count"] = row.get(f"{metric}_count")

    percentiles_block: dict[str, Any] = extract_percentile_json(row, metric, config)
    if percentiles_block:
        block["percentiles"] = percentiles_block

    return block
