"""Тесты третьего Excel: source_export + ordered filters + report_parts source."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.filters import apply_ordered_filters, build_match_mask, normalize_filter
from src.v2.report_parts import (
    REPORT_PART_ANALYTICS,
    REPORT_PART_DETAIL,
    REPORT_PART_SOURCE,
    build_report_path,
    resolve_report_parts,
    sheet_belongs_to_part,
    want_source,
)
from src.v2.source_export import build_source_export_frame, source_export_cfg


def test_normalize_match_aliases() -> None:
    assert normalize_filter({"match": "startswith", "values": ["A"]})["match"] == "starts_with"
    assert normalize_filter({"match": ">", "values": [1], "value_type": "number"})["match"] == "gt"
    assert normalize_filter({"match": "max", "values": []})["match"] == "max"


def test_match_starts_with() -> None:
    s = pd.Series(["Активация продукта", "актив", "Другое"])
    mask = build_match_mask(
        s,
        {
            "match": "starts_with",
            "values": ["Активация"],
            "value_type": "string",
            "case_sensitive": False,
        },
    )
    assert mask.tolist() == [True, False, False]


def test_match_gt_number() -> None:
    s = pd.Series([1, 5, 10, None])
    mask = build_match_mask(
        s,
        {"match": "gt", "values": [5], "value_type": "number", "values_mode": "any"},
    )
    assert mask.tolist() == [False, False, True, False]


def test_match_max_date() -> None:
    config = {
        "dates": {
            "dayfirst": True,
            "formats": ["%d.%m.%Y"],
            "empty_values": ["", "-", "nan"],
        }
    }
    s = pd.Series(["01.09.2026", "10.09.2026", "05.09.2026", None])
    mask = build_match_mask(
        s,
        {
            "column_key": "report_date",
            "match": "max",
            "values": [],
            "value_type": "date",
        },
        config,
    )
    assert mask.tolist() == [False, True, False, False]


def test_apply_ordered_filters_sequential() -> None:
    config = {
        "columns": {
            "efs_flag": "ЕФС флаг",
            "report_date": "Дата отчета",
            "label": "Метка",
        },
        "dates": {
            "dayfirst": True,
            "formats": ["%d.%m.%Y"],
            "empty_values": ["", "-"],
        },
        "processing": {"audit_row_counts": False, "empty_stage_values": ["", "-"]},
    }
    df = pd.DataFrame(
        {
            "ЕФС флаг": [1, 1, 0, 1],
            "Дата отчета": ["01.09.2026", "10.09.2026", "10.09.2026", "10.09.2026"],
            "Метка": [
                "Стратегия 2 квартал",
                "Стратегия 2 квартал",
                "Стратегия 2 квартал",
                "Прочее",
            ],
        }
    )
    filters_cfg = {
        "efs_equals_1": {
            "enabled": True,
            "column_key": "efs_flag",
            "action": "include",
            "match": "equals",
            "values": [1],
            "value_type": "number",
        },
        "max_report_date": {
            "enabled": True,
            "column_key": "report_date",
            "action": "include",
            "match": "max",
            "values": [],
            "value_type": "date",
        },
        "label_strategy": {
            "enabled": True,
            "column_key": "label",
            "action": "include",
            "match": "contains",
            "values": ["Стратегия", "квартал"],
            "values_mode": "all",
            "value_type": "string",
        },
        "disabled_noise": {
            "enabled": False,
            "column_key": "efs_flag",
            "action": "include",
            "match": "equals",
            "values": [99],
            "value_type": "number",
        },
    }
    order = ["efs_equals_1", "max_report_date", "label_strategy", "disabled_noise"]
    result = apply_ordered_filters(df, config, filters_cfg, order)
    assert len(result) == 1
    assert result.iloc[0]["Метка"] == "Стратегия 2 квартал"
    assert str(result.iloc[0]["Дата отчета"]).startswith("10")


def test_resolve_report_parts_source_and_full() -> None:
    from src.v2.report_parts import REPORT_PART_PERCENTILES

    assert resolve_report_parts({"output": {"report_parts": "source"}}) == frozenset(
        {REPORT_PART_SOURCE}
    )
    assert resolve_report_parts({"output": {"report_parts": "full"}}) == frozenset(
        {
            REPORT_PART_ANALYTICS,
            REPORT_PART_DETAIL,
            REPORT_PART_SOURCE,
            REPORT_PART_PERCENTILES,
        }
    )
    assert resolve_report_parts({"output": {"report_parts": "all"}}) == frozenset(
        {
            REPORT_PART_ANALYTICS,
            REPORT_PART_DETAIL,
            REPORT_PART_SOURCE,
            REPORT_PART_PERCENTILES,
        }
    )
    assert resolve_report_parts({"output": {"report_parts": "both"}}) == frozenset(
        {REPORT_PART_ANALYTICS, REPORT_PART_DETAIL}
    )
    assert want_source(frozenset({REPORT_PART_SOURCE}))
    assert not want_source(frozenset({REPORT_PART_ANALYTICS, REPORT_PART_DETAIL}))


def test_build_report_path_source(tmp_path: Path) -> None:
    config = {
        "output": {
            "report_prefix": "kanban_excel_v2",
            "report_part_suffixes": {"source": "source"},
        }
    }
    path = build_report_path(tmp_path, config, REPORT_PART_SOURCE, "20260910_120000")
    assert path.name == "kanban_excel_v2_source_20260910_120000.xlsx"
    assert sheet_belongs_to_part("source", REPORT_PART_SOURCE)
    assert not sheet_belongs_to_part("source", REPORT_PART_DETAIL)


def test_root_and_source_filters_are_independent() -> None:
    """
    Корневой filters и output.source_export.filters — независимые ветки:
    каждая стартует от полного raw, не от остатка другой.
    """
    from src.filters import apply_filters

    config = {
        "columns": {
            "efs_flag": "ЕФС флаг",
            "label": "Метка",
            "lead_id": "ID ПрПр",
            "deal_id": "ID сделки",
        },
        "processing": {"audit_row_counts": False, "empty_stage_values": ["", "-"]},
        "team_files": {"enabled": False, "output_columns": {"lead": {}, "deal": {}}},
        "manager_emails": {"enabled": False},
        # analytics/detail: только ЕФС=1
        "filters": {
            "efs_flag": {
                "enabled": True,
                "column_key": "efs_flag",
                "action": "include",
                "match": "equals",
                "values": [1],
                "value_type": "number",
            }
        },
        # source: только метка со «Стратегия» (ЕФС не трогаем)
        "output": {
            "source_export": {
                "filters_order": ["label_strategy"],
                "filters": {
                    "label_strategy": {
                        "enabled": True,
                        "column_key": "label",
                        "action": "include",
                        "match": "contains",
                        "values": ["Стратегия"],
                        "value_type": "string",
                    }
                },
            }
        },
    }
    raw = pd.DataFrame(
        {
            "ЕФС флаг": [1, 1, 0, 0],
            "Метка": ["Стратегия A", "Прочее", "Стратегия B", "Прочее"],
            "ID ПрПр": ["a", "b", "c", "d"],
            "ID сделки": ["", "", "", ""],
        }
    )
    raw_for_source = raw.copy()

    analytics_rows = apply_filters(raw, config)
    source_rows = build_source_export_frame(raw_for_source, config)

    # analytics: ЕФС=1 → строки a,b (независимо от метки)
    assert sorted(analytics_rows["ID ПрПр"].tolist()) == ["a", "b"]
    # source: Стратегия → a,c (включая ЕФС=0 — корневой фильтр не режет)
    assert sorted(source_rows["ID ПрПр"].tolist()) == ["a", "c"]
    # полная копия raw не испорчена корневым фильтром
    assert len(raw_for_source) == 4


def test_build_source_export_frame_keeps_raw_columns() -> None:
    config = {
        "columns": {
            "efs_flag": "ЕФС флаг",
            "lead_id": "ID ПрПр",
            "deal_id": "ID сделки",
        },
        "processing": {"audit_row_counts": False, "empty_stage_values": ["", "-"]},
        "team_files": {"enabled": False, "output_columns": {"lead": {}, "deal": {}}},
        "manager_emails": {"enabled": False},
        "output": {
            "source_export": {
                "filters_order": ["efs_equals_1"],
                "filters": {
                    "efs_equals_1": {
                        "enabled": True,
                        "column_key": "efs_flag",
                        "action": "include",
                        "match": "equals",
                        "values": [1],
                        "value_type": "number",
                    }
                },
            }
        },
    }
    raw = pd.DataFrame(
        {
            "ЕФС флаг": [1, 0, 1],
            "ID ПрПр": ["a", "b", "c"],
            "ID сделки": ["", "", ""],
            "Произвольная колонка": ["x", "y", "z"],
        }
    )
    out = build_source_export_frame(raw, config)
    assert len(out) == 2
    assert "Произвольная колонка" in out.columns
    assert list(out["ЕФС флаг"]) == [1, 1]
    assert source_export_cfg(config)["filters_order"] == ["efs_equals_1"]
