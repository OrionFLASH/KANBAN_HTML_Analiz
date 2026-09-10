"""Выбор частей Excel-отчёта v2: analytics / detail / source / both / full."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger: logging.Logger = logging.getLogger("kanban.excel_v2.report_parts")

REPORT_PART_ANALYTICS: str = "analytics"
REPORT_PART_DETAIL: str = "detail"
REPORT_PART_SOURCE: str = "source"

KNOWN_REPORT_PARTS: frozenset[str] = frozenset(
    {REPORT_PART_ANALYTICS, REPORT_PART_DETAIL, REPORT_PART_SOURCE}
)

# Синонимы значения output.report_parts
_BOTH_ALIASES: frozenset[str] = frozenset(
    {"both", "оба", "analytics+detail", "detail+analytics"}
)
_FULL_ALIASES: frozenset[str] = frozenset(
    {
        "full",
        "all",
        "все",
        "все_файлы",
        "analytics+detail+source",
        "source+detail+analytics",
    }
)
_ANALYTICS_ALIASES: frozenset[str] = frozenset(
    {
        "analytics",
        "norms",
        "summary",
        "matrix",
        "аналитика",
        "нормативы",
        "сроки",
        "1",
        "first",
        "file1",
    }
)
_DETAIL_ALIASES: frozenset[str] = frozenset(
    {
        "detail",
        "leads",
        "managers",
        "violations",
        "детализация",
        "лиды",
        "менеджеры",
        "2",
        "second",
        "file2",
    }
)
_SOURCE_ALIASES: frozenset[str] = frozenset(
    {
        "source",
        "raw",
        "kanban",
        "исходные",
        "исходник",
        "source_export",
        "3",
        "third",
        "file3",
    }
)

DEFAULT_PART_SUFFIXES: dict[str, str] = {
    REPORT_PART_ANALYTICS: "analytics",
    REPORT_PART_DETAIL: "detail",
    REPORT_PART_SOURCE: "source",
}

ANALYTICS_SHEET_KEYS: frozenset[str] = frozenset({"norms", "statistics"})
DETAIL_SHEET_KEYS: frozenset[str] = frozenset({"leads", "managers", "violations"})
SOURCE_SHEET_KEYS: frozenset[str] = frozenset({"source"})


def _normalize_part_token(raw: Any) -> str:
    """Один токен → analytics | detail | source | both | full | ''."""
    text: str = str(raw or "").strip().casefold()
    if not text:
        return ""
    if text in _FULL_ALIASES:
        return "full"
    if text in _BOTH_ALIASES:
        return "both"
    if text in _ANALYTICS_ALIASES:
        return REPORT_PART_ANALYTICS
    if text in _DETAIL_ALIASES:
        return REPORT_PART_DETAIL
    if text in _SOURCE_ALIASES:
        return REPORT_PART_SOURCE
    if text in KNOWN_REPORT_PARTS:
        return text
    return text


def resolve_report_parts(config: dict[str, Any]) -> frozenset[str]:
    """
    Какие части отчёта строить.

    output.report_parts:
      - строка: both | full | analytics | detail | source (+ синонимы)
      - список частей
    По умолчанию: both (analytics + detail), без source.
    """
    out_cfg: dict[str, Any] = config.get("output") or {}
    raw: Any = out_cfg.get("report_parts", "both")
    selected: set[str] = set()

    if isinstance(raw, list):
        if not raw:
            raise ValueError("output.report_parts: пустой список")
        for item in raw:
            token: str = _normalize_part_token(item)
            if token == "both":
                selected.update({REPORT_PART_ANALYTICS, REPORT_PART_DETAIL})
            elif token == "full":
                selected.update(KNOWN_REPORT_PARTS)
            elif token in KNOWN_REPORT_PARTS:
                selected.add(token)
            else:
                raise ValueError(
                    f"output.report_parts: неизвестное значение {item!r}; "
                    f"ожидается analytics / detail / source / both / full"
                )
    else:
        token = _normalize_part_token(raw)
        if token == "both" or token == "":
            selected.update({REPORT_PART_ANALYTICS, REPORT_PART_DETAIL})
        elif token == "full":
            selected.update(KNOWN_REPORT_PARTS)
        elif token in KNOWN_REPORT_PARTS:
            selected.add(token)
        else:
            raise ValueError(
                f"output.report_parts={raw!r}: ожидается analytics / detail / source / "
                f"both / full (или список)"
            )

    if not selected:
        raise ValueError("output.report_parts: не выбрана ни одна часть отчёта")
    return frozenset(selected)


def want_analytics(parts: frozenset[str]) -> bool:
    return REPORT_PART_ANALYTICS in parts


def want_detail(parts: frozenset[str]) -> bool:
    return REPORT_PART_DETAIL in parts


def want_source(parts: frozenset[str]) -> bool:
    return REPORT_PART_SOURCE in parts


def report_part_suffix(config: dict[str, Any], part: str) -> str:
    """Суффикс имени файла для части отчёта."""
    suffixes: dict[str, Any] = (config.get("output") or {}).get("report_part_suffixes") or {}
    default: str = DEFAULT_PART_SUFFIXES.get(part, part)
    return str(suffixes.get(part, default))


def build_report_path(
    output_dir: Path,
    config: dict[str, Any],
    part: str,
    timestamp: str,
) -> Path:
    """Путь `{prefix}_{suffix}_{timestamp}.xlsx`."""
    out_cfg: dict[str, Any] = config.get("output") or {}
    prefix: str = str(out_cfg.get("report_prefix", "kanban_excel_v2"))
    suffix: str = report_part_suffix(config, part)
    return output_dir / f"{prefix}_{suffix}_{timestamp}.xlsx"


def sheet_belongs_to_part(sheet_key: str, part: str) -> bool:
    """Принадлежит ли ключ листа указанной части отчёта."""
    if part == REPORT_PART_ANALYTICS:
        return sheet_key in ANALYTICS_SHEET_KEYS or sheet_key.startswith("duration_matrix")
    if part == REPORT_PART_DETAIL:
        return sheet_key in DETAIL_SHEET_KEYS
    if part == REPORT_PART_SOURCE:
        return sheet_key in SOURCE_SHEET_KEYS
    return False
