# -*- coding: utf-8 -*-
"""Тесты построчного аудита входных фильтров на нормативах."""

from __future__ import annotations

import pandas as pd

from src.filter_funnel import (
    FILTER_AFTER,
    FILTER_BEFORE,
    FILTER_DROPPED_PREFIX,
    GroupFilterAuditor,
    merge_filter_audit_into_norms,
)
from src.filters import apply_filters, filter_terminal_deal_stage_rows
from src.v2.exceedance_config import exceedance_percentile, resolve_exceedance_columns


def _config() -> dict:
    return {
        "columns": {
            "lead_id": "ID ПрПр",
            "product_group": "Группа продукта",
            "product": "Продукт",
            "tb": "ТБ",
            "current_status": "Текущий статус",
            "efs_flag": "ЕФС",
            "label": "Метка",
            "deal_stage": "Стадия сделки",
        },
        "processing": {"empty_stage_values": ["", "-", "nan", "None"]},
        "filters": {
            "efs_flag": {
                "enabled": True,
                "column_key": "efs_flag",
                "action": "include",
                "match": "equals",
                "values": [1],
                "values_mode": "any",
                "value_type": "number",
            },
            "strategy_label": {
                "enabled": True,
                "column_key": "label",
                "action": "include",
                "match": "contains",
                "values": ["Стратегия"],
                "values_mode": "any",
                "value_type": "string",
                "case_sensitive": False,
            },
            "exclude_deal_otkaz": {
                "enabled": True,
                "column_key": "deal_stage",
                "action": "exclude",
                "match": "contains",
                "values": ["отказ"],
                "values_mode": "any",
                "value_type": "string",
                "case_sensitive": False,
            },
        },
        "output": {"all_tb_label": "все тб", "column_labels": {}},
        "exceedance": {"percentile": 50},
        "percentiles": [20, 50, 80],
    }


def test_group_auditor_counts_per_filter() -> None:
    cfg = _config()
    raw = pd.DataFrame(
        {
            "ID ПрПр": ["L1", "L2", "L3", "L4"],
            "ТБ": ["TB1", "TB1", "TB1", "TB2"],
            "Группа продукта": ["G", "G", "G", "G"],
            "Продукт": ["P", "P", "P", "P"],
            "Текущий статус": ["S", "S", "S", "S"],
            "ЕФС": [1, 1, 0, 1],
            "Метка": ["Стратегия X", "другое", "Стратегия Y", "Стратегия Z"],
            "Стадия сделки": ["в работе", "в работе", "в работе", "отказ клиента"],
        }
    )
    auditor = GroupFilterAuditor(cfg)
    auditor.record_baseline(raw)
    after_efs = apply_filters(raw, {**cfg, "filters": {"efs_flag": cfg["filters"]["efs_flag"]}})
    # Пошагово как в pipeline: сначала efs, затем strategy, затем exclude
    step1 = raw.loc[raw["ЕФС"] == 1].copy()
    auditor.record_filter_step("efs_flag", raw, step1)
    step2 = step1.loc[step1["Метка"].astype(str).str.contains("Стратегия", case=False)].copy()
    auditor.record_filter_step("strategy_label", step1, step2)
    step3 = filter_terminal_deal_stage_rows(step2, cfg)
    auditor.record_filter_step("exclude_deal_otkaz", step2, step3)

    by_tb, overall = auditor.to_norms_frames()
    assert FILTER_BEFORE in by_tb.columns
    assert f"{FILTER_DROPPED_PREFIX}efs_flag" in by_tb.columns
    row_tb1 = by_tb.loc[by_tb["ТБ"] == "TB1"].iloc[0]
    assert int(row_tb1[FILTER_BEFORE]) == 3  # L1 L2 L3
    assert int(row_tb1[f"{FILTER_DROPPED_PREFIX}efs_flag"]) == 1  # L3
    assert int(row_tb1[f"{FILTER_DROPPED_PREFIX}strategy_label"]) == 1  # L2
    assert int(row_tb1[FILTER_AFTER]) == 1  # L1 after include filters; exclude is TB2

    row_tb2 = by_tb.loc[by_tb["ТБ"] == "TB2"].iloc[0]
    assert int(row_tb2[f"{FILTER_DROPPED_PREFIX}exclude_deal_otkaz"]) == 1

    assert not overall.empty
    assert after_efs is not None


def test_merge_filter_audit_into_norms() -> None:
    cfg = _config()
    auditor = GroupFilterAuditor(cfg)
    raw = pd.DataFrame(
        {
            "ID ПрПр": ["L1", "L2"],
            "ТБ": ["TB1", "TB1"],
            "Группа продукта": ["G", "G"],
            "Продукт": ["P", "P"],
            "Текущий статус": ["S", "S"],
            "ЕФС": [1, 0],
            "Метка": ["Стратегия", "Стратегия"],
            "Стадия сделки": ["ok", "ok"],
        }
    )
    auditor.record_baseline(raw)
    after = raw.loc[raw["ЕФС"] == 1]
    auditor.record_filter_step("efs_flag", raw, after)
    auditor.record_filter_step("strategy_label", after, after)
    auditor.record_filter_step("exclude_deal_otkaz", after, after)

    norms = pd.DataFrame(
        {
            "ТБ": ["TB1", "все тб"],
            "Группа продукта": ["G", "G"],
            "Продукт": ["P", "P"],
            "current_status": ["S", "S"],
            "days_on_stage_count": [1, 1],
        }
    )
    merged = merge_filter_audit_into_norms(norms, auditor, cfg)
    assert FILTER_BEFORE in merged.columns
    assert f"{FILTER_DROPPED_PREFIX}efs_flag" in merged.columns
    tb_row = merged.loc[merged["ТБ"] == "TB1"].iloc[0]
    assert int(tb_row[FILTER_BEFORE]) == 2
    assert int(tb_row[f"{FILTER_DROPPED_PREFIX}efs_flag"]) == 1
    assert int(tb_row[FILTER_AFTER]) == 1


def test_exceedance_percentile_from_config() -> None:
    cfg = _config()
    assert exceedance_percentile(cfg) == 50.0
    cols = resolve_exceedance_columns(cfg)
    assert cols["p80_norm"] == "Норматив P50"
