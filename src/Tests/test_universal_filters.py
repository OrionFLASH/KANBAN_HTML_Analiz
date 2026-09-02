"""Тесты универсальных фильтров (normalize + match)."""

from __future__ import annotations

import pandas as pd

from src.filters import (
    build_match_mask,
    excluded_analysis_stages,
    filter_terminal_deal_stage_rows,
    is_exclude_filter,
    normalize_filter,
    row_keep_mask,
)


def test_normalize_legacy_value() -> None:
    uni = normalize_filter({"column_key": "efs_flag", "value": 1})
    assert uni["action"] == "include"
    assert uni["match"] == "equals"
    assert uni["values"] == [1]
    assert uni["value_type"] == "number"
    assert uni["values_mode"] == "any"


def test_normalize_legacy_contains_any() -> None:
    uni = normalize_filter(
        {
            "column_key": "label",
            "contains_any": ["A", "B"],
            "case_sensitive": False,
        }
    )
    assert uni["match"] == "contains"
    assert uni["values_mode"] == "any"
    assert uni["values"] == ["A", "B"]
    assert uni["value_type"] == "string"


def test_normalize_legacy_contains_all() -> None:
    uni = normalize_filter({"contains_all": ["Стратегия", "2026"]})
    assert uni["values_mode"] == "all"
    assert uni["match"] == "contains"


def test_normalize_legacy_exclude_equals() -> None:
    uni = normalize_filter(
        {
            "filter_mode": "exclude",
            "exclude_equals": "К ПРОДАЖЕ",
            "column_key": "current_status",
        }
    )
    assert is_exclude_filter(uni)
    assert uni["action"] == "exclude"
    assert uni["match"] == "equals"
    assert uni["values"] == ["К ПРОДАЖЕ"]


def test_normalize_universal_passthrough() -> None:
    src = {
        "enabled": True,
        "column_key": "efs_flag",
        "action": "include",
        "match": "equals",
        "values": [1],
        "values_mode": "any",
        "value_type": "number",
    }
    uni = normalize_filter(src)
    assert uni["values"] == [1]
    assert uni["action"] == "include"


def test_match_equals_number_any() -> None:
    s = pd.Series([0, 1, 1, None])
    mask = build_match_mask(
        s,
        {
            "match": "equals",
            "values": [1],
            "values_mode": "any",
            "value_type": "number",
        },
    )
    assert mask.tolist() == [False, True, True, False]


def test_match_contains_any_string() -> None:
    s = pd.Series(
        [
            "Стратегия 2 квартал 2026",
            "стратегия 2 кватал 2026",
            "Стратегия 2026",
            "",
        ]
    )
    mask = build_match_mask(
        s,
        {
            "match": "contains",
            "values": ["Стратегия 2 квартал 2026", "Стратегия 2 кватал 2026"],
            "values_mode": "any",
            "value_type": "string",
            "case_sensitive": False,
        },
    )
    assert mask.tolist() == [True, True, False, False]


def test_match_contains_all_string() -> None:
    s = pd.Series(["Стратегия 2026", "Стратегия", "2026"])
    mask = build_match_mask(
        s,
        {
            "match": "contains",
            "values": ["Стратегия", "2026"],
            "values_mode": "all",
            "value_type": "string",
            "case_sensitive": False,
        },
    )
    assert mask.tolist() == [True, False, False]


def test_match_equals_casefold() -> None:
    s = pd.Series(["К ПРОДАЖЕ", "к продаже", "В РАБОТЕ"])
    mask = build_match_mask(
        s,
        {
            "action": "exclude",
            "match": "equals",
            "values": ["К ПРОДАЖЕ"],
            "value_type": "string",
            "case_sensitive": False,
        },
    )
    assert mask.tolist() == [True, True, False]


def test_exclude_skips_empty_cells() -> None:
    config = {
        "columns": {"current_status": "Текущий статус"},
        "processing": {"empty_stage_values": ["", "-", "nan", "None"]},
        "filters": {},
    }
    df = pd.DataFrame({"Текущий статус": ["К ПРОДАЖЕ", "-", ""]})
    flt = {
        "column_key": "current_status",
        "action": "exclude",
        "match": "equals",
        "values": ["К ПРОДАЖЕ"],
        "value_type": "string",
        "case_sensitive": False,
    }
    keep = row_keep_mask(df, "Текущий статус", flt, config)
    assert keep.tolist() == [False, True, True]


def test_excluded_analysis_stages_from_values() -> None:
    config = {
        "filters": {
            "exclude_current_for_sale": {
                "enabled": True,
                "column_key": "current_status",
                "action": "exclude",
                "match": "equals",
                "values": ["К ПРОДАЖЕ"],
                "html_slice": False,
            }
        }
    }
    assert excluded_analysis_stages(config) == ["К ПРОДАЖЕ"]


def test_value_type_auto_number() -> None:
    uni = normalize_filter({"values": [0], "match": "equals", "action": "include"})
    # auto → number по int
    s = pd.Series([0, 1])
    mask = build_match_mask(s, {**uni, "value_type": "auto"})
    assert mask.tolist() == [True, False]


def test_match_date_equals() -> None:
    config = {
        "dates": {
            "dayfirst": True,
            "formats": ["%d.%m.%Y"],
            "empty_values": ["", "-", "nan"],
        }
    }
    s = pd.Series(["01.09.2026", "02.09.2026", None])
    mask = build_match_mask(
        s,
        {
            "match": "equals",
            "values": ["01.09.2026"],
            "values_mode": "any",
            "value_type": "date",
        },
        config,
    )
    assert mask.tolist() == [True, False, False]


def test_terminal_exclude_universal_config() -> None:
    config = {
        "columns": {
            "deal_stage": "Стадия сделки",
            "current_status": "Текущий статус",
        },
        "processing": {"empty_stage_values": ["", "-"]},
        "filters": {
            "exclude_deal_otkaz": {
                "enabled": True,
                "column_key": "deal_stage",
                "action": "exclude",
                "match": "contains",
                "values": ["отказ"],
                "value_type": "string",
                "case_sensitive": False,
            }
        },
    }
    df = pd.DataFrame(
        {
            "Стадия сделки": ["В работе", "Отказ клиента", "—"],
            "Текущий статус": ["ok", "ok", "ok"],
        }
    )
    # «—» не в empty_stage_values как символ тире длинное — используем "-"
    df.loc[2, "Стадия сделки"] = "-"
    result = filter_terminal_deal_stage_rows(df, config)
    assert len(result) == 2
    assert "Отказ клиента" not in result["Стадия сделки"].tolist()
