"""Настройки порога превышения для Excel v2."""

from __future__ import annotations

from typing import Any

from src.percentile_stats import percentile_label
from src.settings import percentile_display_value


def exceedance_percentile(config: dict[str, Any]) -> float:
    """Перцентиль порога превышения (по умолчанию 80)."""
    block: dict[str, Any] = dict(config.get("exceedance") or {})
    raw: Any = block.get("percentile", 80)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 80.0


def exceedance_percentile_tag(config: dict[str, Any]) -> str:
    """Метка вида p80 / p50 для колонок статистики."""
    return percentile_label(exceedance_percentile(config))


def exceedance_percentile_display(config: dict[str, Any]) -> str:
    """Число перцентиля для подписей (80, 50)."""
    return percentile_display_value(exceedance_percentile(config))


def resolve_exceedance_columns(config: dict[str, Any]) -> dict[str, str]:
    """
    Имена колонок превышения в Excel с подстановкой {p}.
    Ключ p80_norm сохранён для совместимости конфига.
    """
    raw: dict[str, Any] = dict(config.get("output", {}).get("exceedance_columns") or {})
    p_disp: str = exceedance_percentile_display(config)
    defaults: dict[str, str] = {
        "p80_norm": "Норматив P{p}",
        "current_days": "Текущий срок",
        "exceedance_flag": "превышение",
        "exceedance_days": "дней отклонения",
    }
    resolved: dict[str, str] = {}
    for key, default in defaults.items():
        template: str = str(raw.get(key, default))
        resolved[key] = template.replace("{p}", p_disp)
    return resolved


def managers_exceedance_count_column(config: dict[str, Any]) -> str:
    """Заголовок колонки числа превышений в своде менеджеров."""
    return f"Превышений P{exceedance_percentile_display(config)}"
