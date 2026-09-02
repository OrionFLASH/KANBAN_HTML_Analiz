"""Схема config.json, значения по умолчанию и доступ к настройкам."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Продукты по умолчанию для отбора TOP КМ (Excel / rank_selection)
DEFAULT_RANK_PRODUCTS: list[str] = [
    "Зарплатные проекты (объем ФОТ)",
    "Краткосрочное финансирование",
    "Расчетные операции",
    "Срочное привлечение",
    "Бизнес карта",
    "Готовые образовательные решения",
    "Комплексная поддержка по повышению эффективности бизнеса",
    "Факторинг",
    "Process Mining от Сбера",
    "Непокрытые аккредитивы",
    "Корпоративное обучение",
    "Лизинг СБЛ",
    "Cash-management",
    "Sbergile-консалтинг",
]

# Значения по умолчанию — подставляются, если ключ отсутствует в config.json
DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "input_test": "IN/TEST",
        "input_prod": "IN/PROD",
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
        "km": "КМ",
        "vks": "ВКС",
        "change_conditions": "_Изменение условий",
        "data_entry": "_Ввод данных",
        "efs_flag": "ЕФС флаг",
        "deal_id": "ID сделки",
        "inn": "ИНН",
        "client": "Клиент",
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
        "km",
        "deal_id",
        "inn",
        "client",
    ],
    "optional_column_keys": [
        "vks",
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
        "group_only_product_label": "—",
        "audit_row_counts": True,
        "duration_fallback_to_columns": True,
    },
    "performance": {
        "max_parallel_workers": 4,
        "reserve_cpu_cores": 1,
        "read_only_required_columns": True,
        "downcast_numeric": True,
        "free_memory_between_stages": True,
        "compact_distribution_series": True,
        "precompute_pivot_matrices": False,
        "adaptive_resources": {
            "enabled": True,
            "min_available_ram_gb": 3.0,
            "critical_available_ram_gb": 1.5,
            "warn_used_ram_percent": 80.0,
            "critical_used_ram_percent": 92.0,
            "sequential_load_below_total_ram_gb": 20.0,
            "input_size_per_worker_gb": 1.2,
            "gc_on_pressure": True,
            "override_explicit_workers_on_critical": True,
            "disable_html_slices_on_critical": True,
        },
    },
    "progress": {
        "enabled": True,
        "log_every_seconds": 3,
        "show_timing_summary": True,
    },
    "dates": {
        "dayfirst": True,
        "excel_origin": "1899-12-30",
        "formats": ["%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"],
        "empty_values": ["", "-", "nan", "none", "nat", "null", "N/A", "n/a"]
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
            "matrix": "Матрица",
            "managers": "Менеджеры",
        },
        "excel_max_sheet_name_length": 31,
        "excel_max_rows_per_sheet": 900_000,
        "csv_overflow": {
            "enabled": True,
            "delimiter": ";",
            "encoding": "utf-8-sig",
        },
        "column_labels": {
            "product_group": "ГРУППА",
            "product": "ПРОДУКТ",
            "tb": "ТБ",
            "km": "КМ",
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
        "percentile_column_labels": {
            "days_on_stage": {
                "days": "П{p} дней",
                "count": "П{p} лидов",
                "min": "П{p} мин",
                "max": "П{p} макс",
                "km_count": "П{p} КМ ≥",
                "le_count": "П{p} лидов ≤",
                "gt_count": "П{p} лидов >",
            },
            "days_since_deal": {
                "days": "П{p} дн.сделки",
                "count": "П{p} лид.сделки",
                "min": "П{p} мин сд.",
                "max": "П{p} макс сд.",
                "km_count": "П{p} КМ ≥ сд.",
                "le_count": "П{p} лид. ≤ сд.",
                "gt_count": "П{p} лид. > сд.",
            },
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
        "statistics": {
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
                {
                    "p": 20,
                    "compute": True,
                    "export_days": True,
                    "export_count": False,
                    "export_le_count": False,
                    "export_gt_count": False,
                    "export_min": False,
                    "export_max": False,
                    "export_km_count": False,
                },
                {
                    "p": 50,
                    "compute": True,
                    "export_days": True,
                    "export_count": False,
                    "export_le_count": False,
                    "export_gt_count": False,
                    "export_min": False,
                    "export_max": False,
                    "export_km_count": False,
                },
                {
                    "p": 80,
                    "compute": True,
                    "export_days": True,
                    "export_count": False,
                    "export_le_count": True,
                    "export_gt_count": True,
                    "export_min": True,
                    "export_max": True,
                    "export_km_count": True,
                },
            ],
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
    "product_analysis_mode": "group_product",
    "percentiles": [20, 50, 80],
    "stages_order": [
        "К ПРОДАЖЕ",
        "ВЫЯВЛЕНИЕ ПОТРЕБНОСТИ",
        "ОБСУЖДЕНИЕ УСЛОВИЙ",
        "РЕАЛИЗАЦИЯ СДЕЛКИ",
        "АКТИВАЦИЯ ПРОДУКТА",
        "ПРОДАЖА ЗАВЕРШЕНА",
    ],
    "dashboard": {
        "all_tb_label": "__ALL__",
        "all_tb_display": "ВСЕ ТБ",
        "default_tb": "__ALL__",
        "default_metric": "days_on_stage",
        "default_indicator": "p80",
        "excel_max_chart_series": 8,
        "max_chart_series": 12,
        "precompute_html_filter_slices": True,
        "show_managers_tab": False,
        "html_json": {
            "bundle_mode": "monolith",
            "compact": True,
            "include_statistics": False,
            "include_dimensions": True,
            "max_distribution_points": 800,
            "slices_subdir": "slices",
            "write_monolith_archive": False,
            "embed_managers": True,
            "write_separate_managers_json": False,
        },
    },
    "client_display": {
        "enabled": True,
        "abbreviations": [
            {"match": "публичное акционерное общество", "replace": "ПАО"},
            {"match": "непубличное акционерное общество", "replace": "НАО"},
            {"match": "закрытое акционерное общество", "replace": "ЗАО"},
            {"match": "открытое акционерное общество", "replace": "ОАО"},
            {"match": "общество с ограниченной ответственностью", "replace": "ООО"},
            {"match": "акционерное общество", "replace": "АО"},
            {"match": "индивидуальный предприниматель", "replace": "ИП"},
            {"match": "федеральное государственное бюджетное учреждение", "replace": "ФГБУ"},
            {"match": "федеральное государственное унитарное предприятие", "replace": "ФГУП"},
            {"match": "государственное унитарное предприятие", "replace": "ГУП"},
            {"match": "муниципальное унитарное предприятие", "replace": "МУП"},
            {"match": "автономная некоммерческая организация", "replace": "АНО"},
            {"match": "некоммерческая организация", "replace": "НКО"},
            {"match": "товарищество собственников жилья", "replace": "ТСЖ"},
            {"match": "товарищество собственников недвижимости", "replace": "ТСН"},
            {"match": "крестьянское (фермерское) хозяйство", "replace": "КФХ"},
            {"match": "крестьянское фермерское хозяйство", "replace": "КФХ"},
            {"match": "производственный кооператив", "replace": "ПК"},
            {"match": "сельскохозяйственный производственный кооператив", "replace": "СПК"},
            {"match": "полное товарищество", "replace": "ПТ"},
            {"match": "товарищество на вере", "replace": "ТНВ"},
            {"match": "коммандитное товарищество", "replace": "КТ"},
        ],
    },
    "manager_analytics": {
        "enabled": True,
        "metric": "days_on_stage",
        "percentile": 80,
        "threshold_scope": "overall",
        "top_managers_per_tb": 3,
        "top_hotspots_per_manager": 5,
        "html_include_detail": False,
        "rank_by_team": True,
        "team_files": {
            "enabled": False,
            "lead_team": {"test": [], "prod": []},
            "deal_team": {"test": [], "prod": []},
            "leader_values": ["Да", "да", "yes", "YES", "true", "True", "1"],
            "columns": {
                "report_date": "Дата отчета",
                "lead_id": "ID ПрПр",
                "deal_id": "ID сделки",
                "member": "Участник команды",
                "role": "Роль участника команды",
                "is_leader": "Лидер",
                "tb": "ТБ",
            },
        },
        "rank_selection": {
            "product_groups": [],
            "products": list(DEFAULT_RANK_PRODUCTS),
            "strategy_filter": "strategy_2026",
            "efs_flag": 1,
            "change_conditions": 0,
        },
        "top_stuck_items_per_hotspot": 15,
        "use_latest_report_date": True,
    },
    "parallel_workers": 0,
    "excel_theme": "green_red",
    "filters": {
        "change_conditions": {
            "enabled": True,
            "column_key": "change_conditions",
            "value": 0,
            "html_slice": False,
        },
        "data_entry": {
            "enabled": True,
            "column_key": "data_entry",
            "value": 0,
            "html_slice": False,
        },
        "efs_flag": {
            "enabled": True,
            "column_key": "efs_flag",
            "value": 1,
            "html_slice": False,
        },
        "strategy_label": {
            "enabled": False,
            "column_key": "label",
            "contains": "Стратегия",
            "case_sensitive": False,
            "exclusive_group": "strategy_label",
        },
        "strategy_label_2026": {
            "enabled": False,
            "column_key": "label",
            "contains_all": ["Стратегия", "2026"],
            "case_sensitive": False,
            "exclusive_group": "strategy_label",
        },
        "exclude_deal_otkaz": {
            "enabled": True,
            "column_key": "deal_stage",
            "also_column_keys": ["current_status"],
            "filter_mode": "exclude",
            "exclude_contains": "отказ",
            "case_sensitive": False,
            "html_slice": False,
        },
        "exclude_deal_zakryta": {
            "enabled": True,
            "column_key": "deal_stage",
            "filter_mode": "exclude",
            "exclude_contains": "закрыта",
            "case_sensitive": False,
            "html_slice": False,
        },
        "exclude_deal_zaklyuchen": {
            "enabled": True,
            "column_key": "deal_stage",
            "filter_mode": "exclude",
            "exclude_contains": "заключен",
            "case_sensitive": False,
            "html_slice": False,
        },
        "exclude_current_for_sale": {
            "enabled": False,
            "column_key": "current_status",
            "filter_mode": "exclude",
            "exclude_equals": "К ПРОДАЖЕ",
            "case_sensitive": False,
            "html_slice": False,
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


def optional_column_names(config: dict[str, Any]) -> list[str]:
    """Доп. колонки (ВКС и т.п.): читаем если есть, не валидируем как обязательные."""
    keys: list[str] = list(config.get("optional_column_keys") or [])
    names: list[str] = []
    for key in keys:
        if key not in config.get("columns", {}):
            continue
        name: str = col(config, key)
        if name and name not in names:
            names.append(name)
    return names


def load_column_names(config: dict[str, Any]) -> list[str]:
    """Колонки для usecols: обязательные + опциональные (без дублей)."""
    names: list[str] = required_column_names(config)
    for name in optional_column_names(config):
        if name not in names:
            names.append(name)
    return names


def filter_column_name(config: dict[str, Any], flt: dict[str, Any]) -> str | None:
    """Имя колонки для фильтра: column_key или явный column."""
    if "column_key" in flt:
        return col(config, flt["column_key"])
    if "column" in flt:
        return str(flt["column"])
    return None


def filter_column_names(config: dict[str, Any], flt: dict[str, Any]) -> list[str]:
    """
    Все колонки фильтра: основная + column_keys (или legacy also_column_keys).
    Дубликаты и пустые имена отбрасываются. Совпадение по колонкам — OR.
    """
    names: list[str] = []
    primary: str | None = filter_column_name(config, flt)
    if primary:
        names.append(primary)
    extra_keys: list[Any] = list(flt.get("column_keys") or flt.get("also_column_keys") or [])
    for key in extra_keys:
        # column_keys может дублировать column_key — пропускаем дубли имён
        key_str: str = str(key)
        if key_str == str(flt.get("column_key", "")):
            continue
        resolved: str = col(config, key_str)
        if resolved and resolved not in names:
            names.append(resolved)
    return names


def with_product_analysis_mode(config: dict[str, Any], mode: str) -> dict[str, Any]:
    """Копия config с подменённым product_analysis_mode (для JSON/HTML-срезов)."""
    from copy import deepcopy

    merged: dict[str, Any] = deepcopy(config)
    merged["product_analysis_mode"] = mode
    return merged


def product_analysis_mode(config: dict[str, Any]) -> str:
    """Режим анализа продуктов: group_product | group_only."""
    return str(config.get("product_analysis_mode", "group_product"))


def is_group_only_analysis(config: dict[str, Any]) -> bool:
    """True — расчёт только в разрезе группы продукта, без детализации по продукту."""
    return product_analysis_mode(config) == "group_only"


def group_only_product_label(config: dict[str, Any]) -> str:
    """Подпись в колонке «Продукт» при режиме group_only."""
    return str(config.get("processing", {}).get("group_only_product_label", "—"))


def analysis_row_key(config: dict[str, Any]) -> str:
    """Ключ строки сводных таблиц: product_group или product."""
    return "product_group" if is_group_only_analysis(config) else "product"


def analysis_row_column(config: dict[str, Any]) -> str:
    """Имя колонки Excel для строк сводных таблиц."""
    return col(config, analysis_row_key(config))


def aggregation_group_columns(config: dict[str, Any], records_columns: set[str]) -> list[str]:
    """Колонки группировки агрегации с учётом фактических колонок records."""
    group: list[str] = []
    mapping: dict[str, str] = {
        "product_group": col(config, "product_group"),
        "product": col(config, "product"),
        "tb": col(config, "tb"),
    }
    for key in config["aggregation"]["group_keys"]:
        if is_group_only_analysis(config) and key == "product":
            continue
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


def percentile_display_value(p: float) -> str:
    """Число перцентиля для подстановки в заголовок (20, 50)."""
    return str(int(p)) if float(p).is_integer() else str(p)


def build_percentile_column_mapping(config: dict[str, Any]) -> dict[str, str]:
    """Генерирует mapping колонок перцентилей → русские заголовки Excel."""
    from src.statistics_config import build_percentile_column_mapping as _build

    return _build(config)
