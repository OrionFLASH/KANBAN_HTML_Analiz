"""Схема config.json, значения по умолчанию и доступ к настройкам."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Значения по умолчанию — подставляются, если ключ отсутствует в config.json
DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "input_test": "Docs/FileIN",
        "input_prod": "IN",
        "output": "OUT",
        "log": "log",
    },
    "columns": {
        "report_date": "Дата отчета",
        "lead_id": "ID ПрПр",
        "product_group": "Группа продукта",
        "product": "Продукт",
        "work_start_date": "Дата начала работы",
        "current_status": "Текущий статус",
        "days_on_stage": "Количество дней на текущей стадии",
        "deal_created_date": "Дата создания сделки",
        "deal_stage": "Стадия сделки",
        "days_since_deal": "Количество дней с создания сделки",
        "tb": "ТБ",
        "label": "Метка",
        "change_conditions": "_Изменение условий",
        "data_entry": "_Ввод данных",
        "efs_flag": "ЕФС флаг",
    },
    "required_column_keys": [
        "report_date",
        "lead_id",
        "product_group",
        "product",
        "work_start_date",
        "current_status",
        "days_on_stage",
        "deal_created_date",
        "deal_stage",
        "days_since_deal",
        "tb",
        "change_conditions",
        "data_entry",
        "efs_flag",
        "label",
    ],
    "excel": {
        "sheet_name": "Sheet1",
        "table_name": "Base",
        "table_auto": True,
        "engine": "openpyxl",
        "na_values": [""],
        "category_markers": {
            "for_sale": "К ПРОДАЖЕ",
            "in_work": "В РАБОТЕ",
            "unknown": "UNKNOWN",
        },
    },
    "processing": {
        "empty_stage_values": ["", "-", "nan", "None"],
        "dedup_same_date_agg": "max",
        "pick_across_dates": "max_days_then_latest_report_date",
    },
    "aggregation": {
        "group_keys": [
            "product_group",
            "product",
            "analysis_level",
            "current_status",
            "deal_stage",
            "stage_key",
        ],
        "metrics": ["days_on_stage", "days_since_deal"],
    },
    "output": {
        "report_prefix": "kanban_report",
        "timestamp_format": "%Y%m%d_%H%M%S",
        "excel_sheets": {
            "summary": "Сводная",
            "overall": "Общий",
        },
        "excel_max_sheet_name_length": 31,
        "column_labels": {
            "product_group": "ГРУППА",
            "product": "ПРОДУКТ",
            "tb": "ТБ",
            "current_status": "Текущий статус",
            "deal_stage": "Стадия сделки",
            "stage_key": "Ключ стадии",
            "analysis_level": "Уровень анализа",
            "days_on_stage_min": "Мин дней на стадии",
            "days_on_stage_max": "Макс дней на стадии",
            "days_on_stage_count": "Число лидов",
            "days_since_deal_min": "Мин дней с создания сделки",
            "days_since_deal_max": "Макс дней с создания сделки",
            "days_since_deal_count": "Число лидов (сделка)",
            "min_header_marker": "Мин",
            "max_header_marker": "Макс",
        },
        "excel_format": {
            "freeze_panes": "A2",
            "float_format": "0.00",
            "int_format": "0",
            "max_column_width": 45,
            "min_column_width": 12,
            "sample_rows_for_width": 200,
            "colors": {
                "min": "C6EFCE",
                "max": "FFC7CE",
            },
        },
    },
    "logging": {
        "logger_name": "kanban",
        "info_file_prefix": "INFO_kanban",
        "debug_file_prefix": "DEBUG_kanban",
        "hour_format": "%Y%m%d_%H",
    },
    "duration_source": "columns",
    "stage_analysis_mode": "status",
    "percentiles": [20, 50, 80],
    "parallel_workers": 0,
    "excel_theme": "green_red",
    "filters": {
        "change_conditions": {
            "enabled": False,
            "column_key": "change_conditions",
            "value": 1,
        },
        "data_entry": {
            "enabled": False,
            "column_key": "data_entry",
            "value": 1,
        },
        "efs_flag": {
            "enabled": False,
            "column_key": "efs_flag",
            "value": 1,
        },
        "strategy_label": {
            "enabled": False,
            "column_key": "label",
            "contains": "Стратегия",
            "case_sensitive": False,
        },
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Рекурсивно дополняет base значениями из override."""
    result: dict[str, Any] = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    """Сливает пользовательский config с DEFAULT_CONFIG и переносит legacy-ключи."""
    merged: dict[str, Any] = _deep_merge(DEFAULT_CONFIG, raw)

    # Обратная совместимость: плоские ключи корневого уровня
    legacy_excel: dict[str, tuple[str, str]] = {
        "sheet_name": ("excel", "sheet_name"),
        "excel_table_name": ("excel", "table_name"),
        "excel_table_auto": ("excel", "table_auto"),
    }
    for legacy_key, (section, target) in legacy_excel.items():
        if legacy_key in raw:
            merged[section][target] = raw[legacy_key]

    # Фильтры: column → column_key
    for flt in merged.get("filters", {}).values():
        if isinstance(flt, dict) and "column" in flt and "column_key" not in flt:
            col_name: str = flt["column"]
            for key, name in merged["columns"].items():
                if name == col_name:
                    flt["column_key"] = key
                    break

    return merged


def col(config: dict[str, Any], key: str) -> str:
    """Имя колонки Excel по ключу config.columns."""
    columns: dict[str, str] = config["columns"]
    if key not in columns:
        raise KeyError(f"Неизвестный ключ колонки: {key}")
    return columns[key]


def required_column_names(config: dict[str, Any]) -> list[str]:
    """Список обязательных имён колонок Excel."""
    keys: list[str] = config.get("required_column_keys", list(config["columns"].keys()))
    return [col(config, k) for k in keys]


def filter_column_name(config: dict[str, Any], flt: dict[str, Any]) -> str | None:
    """Имя колонки для фильтра: column_key или явный column."""
    if "column_key" in flt:
        return col(config, flt["column_key"])
    if "column" in flt:
        return str(flt["column"])
    return None


def aggregation_group_columns(config: dict[str, Any], records_columns: set[str]) -> list[str]:
    """Колонки группировки агрегации с учётом фактических колонок records."""
    group: list[str] = []
    mapping: dict[str, str] = {
        "product_group": col(config, "product_group"),
        "product": col(config, "product"),
        "tb": col(config, "tb"),
    }
    for key in config["aggregation"]["group_keys"]:
        if key in mapping:
            name = mapping[key]
        else:
            name = key
        if name in records_columns or key in records_columns:
            group.append(name if name in records_columns else key)
    return group


def empty_stage_values(config: dict[str, Any]) -> set[str]:
    """Значения, считающиеся пустой подстадией."""
    return {str(v) for v in config["processing"]["empty_stage_values"]}
