"""Выбор частей Excel-отчёта v2: analytics / detail / both."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger: logging.Logger = logging.getLogger("kanban.excel_v2.report_parts")

REPORT_PART_ANALYTICS: str = "analytics"
REPORT_PART_DETAIL: str = "detail"

KNOWN_REPORT_PARTS: frozenset[str] = frozenset(
    {REPORT_PART_ANALYTICS, REPORT_PART_DETAIL}
)

# Синонимы значения output.report_parts
_BOTH_ALIASES: frozenset[str] = frozenset(
    {"both", "all", "оба", "все", "analytics+detail", "detail+analytics"}
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

DEFAULT_PART_SUFFIXES: dict[str, str] = {
    REPORT_PART_ANALYTICS: "analytics",
    REPORT_PART_DETAIL: "detail",
}

# Листы, входящие в каждую часть (duration_matrix* — по префиксу)
ANALYTICS_SHEET_KEYS: frozenset[str] = frozenset(
    {"norms", "statistics"}
)
DETAIL_SHEET_KEYS: frozenset[str] = frozenset(
    {"leads", "managers", "violations"}
)


def _normalize_part_token(raw: Any) -> str:
    """Один токен → analytics | detail | both | ''."""
    text: str = str(raw or "").strip().casefold()
    if not text:
        return ""
    if text in _BOTH_ALIASES:
        return "both"
    if text in _ANALYTICS_ALIASES:
        return REPORT_PART_ANALYTICS
    if text in _DETAIL_ALIASES:
        return REPORT_PART_DETAIL
    if text in KNOWN_REPORT_PARTS:
        return text
    return text


def resolve_report_parts(config: dict[str, Any]) -> frozenset[str]:
    """
    Какие части отчёта строить.

    output.report_parts:
      - \"both\" | \"analytics\" | \"detail\"
      - или список: [\"analytics\", \"detail\"]
    По умолчанию — both.
    """
    out_cfg: dict[str, Any] = dict(config.get("output") or {})
    raw: Any = out_cfg.get("report_parts", "both")

    selected: set[str] = set()
    if isinstance(raw, list):
        if not raw:
            raise ValueError("output.report_parts: пустой список")
        for item in raw:
            token: str = _normalize_part_token(item)
            if token == "both":
                selected |= set(KNOWN_REPORT_PARTS)
            elif token in KNOWN_REPORT_PARTS:
                selected.add(token)
            else:
                raise ValueError(
                    f"output.report_parts: неизвестное значение {item!r}; "
                    f"ожидается analytics / detail / both"
                )
    else:
        token = _normalize_part_token(raw)
        if token == "both" or token == "":
            selected = set(KNOWN_REPORT_PARTS)
        elif token in KNOWN_REPORT_PARTS:
            selected = {token}
        else:
            raise ValueError(
                f"output.report_parts={raw!r}: ожидается analytics / detail / both "
                f"(или список)"
            )

    if not selected:
        raise ValueError("output.report_parts: не выбрана ни одна часть отчёта")
    return frozenset(selected)


def want_analytics(parts: frozenset[str] | set[str]) -> bool:
    """Нужен файл с нормативами / статистикой / матрицами сроков."""
    return REPORT_PART_ANALYTICS in parts


def want_detail(parts: frozenset[str] | set[str]) -> bool:
    """Нужен файл с уникальными ID / менеджерами / нарушениями."""
    return REPORT_PART_DETAIL in parts


def report_part_suffix(config: dict[str, Any], part: str) -> str:
    """Суффикс имени файла для части (без точки/расширения)."""
    out_cfg: dict[str, Any] = dict(config.get("output") or {})
    suffixes: dict[str, Any] = dict(out_cfg.get("report_part_suffixes") or {})
    raw: Any = suffixes.get(part, DEFAULT_PART_SUFFIXES.get(part, part))
    text: str = str(raw or "").strip()
    return text or str(DEFAULT_PART_SUFFIXES.get(part, part))


def build_report_path(
    output_dir: Path,
    config: dict[str, Any],
    part: str,
    timestamp: str,
) -> Path:
    """Путь xlsx для части: {prefix}_{suffix}_{timestamp}.xlsx."""
    out_cfg: dict[str, Any] = dict(config.get("output") or {})
    prefix: str = str(out_cfg.get("report_prefix", "kanban_excel_v2")).strip() or "kanban_excel_v2"
    suffix: str = report_part_suffix(config, part)
    name: str = f"{prefix}_{suffix}_{timestamp}.xlsx"
    return Path(output_dir) / name


def sheet_belongs_to_part(sheet_key: str, part: str) -> bool:
    """Принадлежит ли ключ листа указанной части отчёта."""
    key: str = str(sheet_key)
    if part == REPORT_PART_ANALYTICS:
        if key in ANALYTICS_SHEET_KEYS:
            return True
        return key == "duration_matrix" or key.startswith("duration_matrix_")
    if part == REPORT_PART_DETAIL:
        return key in DETAIL_SHEET_KEYS
    return False
