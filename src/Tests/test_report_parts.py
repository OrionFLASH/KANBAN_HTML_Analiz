"""Тесты выбора частей отчёта Excel v2."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.v2.report_parts import (
    REPORT_PART_ANALYTICS,
    REPORT_PART_DETAIL,
    build_report_path,
    resolve_report_parts,
    sheet_belongs_to_part,
    want_analytics,
    want_detail,
)


def test_resolve_report_parts_both_default() -> None:
    assert resolve_report_parts({"output": {}}) == frozenset(
        {REPORT_PART_ANALYTICS, REPORT_PART_DETAIL}
    )
    assert resolve_report_parts({"output": {"report_parts": "both"}}) == frozenset(
        {REPORT_PART_ANALYTICS, REPORT_PART_DETAIL}
    )


def test_resolve_report_parts_single() -> None:
    assert resolve_report_parts({"output": {"report_parts": "analytics"}}) == frozenset(
        {REPORT_PART_ANALYTICS}
    )
    assert resolve_report_parts({"output": {"report_parts": "detail"}}) == frozenset(
        {REPORT_PART_DETAIL}
    )
    assert resolve_report_parts({"output": {"report_parts": "нормативы"}}) == frozenset(
        {REPORT_PART_ANALYTICS}
    )
    assert resolve_report_parts({"output": {"report_parts": "лиды"}}) == frozenset(
        {REPORT_PART_DETAIL}
    )


def test_resolve_report_parts_list() -> None:
    parts = resolve_report_parts(
        {"output": {"report_parts": ["analytics", "detail"]}}
    )
    assert parts == frozenset({REPORT_PART_ANALYTICS, REPORT_PART_DETAIL})
    only = resolve_report_parts({"output": {"report_parts": ["detail"]}})
    assert only == frozenset({REPORT_PART_DETAIL})


def test_resolve_report_parts_invalid() -> None:
    with pytest.raises(ValueError, match="report_parts"):
        resolve_report_parts({"output": {"report_parts": "unknown_mode"}})
    with pytest.raises(ValueError, match="пустой список"):
        resolve_report_parts({"output": {"report_parts": []}})


def test_want_helpers() -> None:
    both = frozenset({REPORT_PART_ANALYTICS, REPORT_PART_DETAIL})
    assert want_analytics(both) and want_detail(both)
    assert want_analytics({REPORT_PART_ANALYTICS}) and not want_detail(
        {REPORT_PART_ANALYTICS}
    )
    assert want_detail({REPORT_PART_DETAIL}) and not want_analytics(
        {REPORT_PART_DETAIL}
    )


def test_build_report_path_and_sheet_keys(tmp_path: Path) -> None:
    config = {
        "output": {
            "report_prefix": "kanban_excel_v2",
            "report_part_suffixes": {
                "analytics": "analytics",
                "detail": "detail",
            },
        }
    }
    a = build_report_path(tmp_path, config, REPORT_PART_ANALYTICS, "20260910_120000")
    d = build_report_path(tmp_path, config, REPORT_PART_DETAIL, "20260910_120000")
    assert a.name == "kanban_excel_v2_analytics_20260910_120000.xlsx"
    assert d.name == "kanban_excel_v2_detail_20260910_120000.xlsx"
    assert sheet_belongs_to_part("norms", REPORT_PART_ANALYTICS)
    assert sheet_belongs_to_part("duration_matrix_by_status", REPORT_PART_ANALYTICS)
    assert sheet_belongs_to_part("leads", REPORT_PART_DETAIL)
    assert not sheet_belongs_to_part("leads", REPORT_PART_ANALYTICS)
    assert not sheet_belongs_to_part("norms", REPORT_PART_DETAIL)
