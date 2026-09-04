"""Тесты аудита полноты данных и пропуска повторной фильтрации."""

from __future__ import annotations

import pandas as pd

from src.data_audit import audit_snapshot_coverage
from src.v2.config_loader import load_excel_v2_config
from src.v2.snapshot import build_lead_snapshot
from src.filters import filter_terminal_deal_stage_rows
from src.lead_tracker import build_lead_stage_records
from src.settings import col


def _filter_config() -> dict:
    return {
        "columns": {
            "lead_id": "ID ПрПр",
            "current_status": "Текущий статус",
            "deal_stage": "Стадия сделки",
            "product_group": "Группа продукта",
            "product": "Продукт",
            "tb": "ТБ",
            "report_date": "Дата отчета",
            "work_start_date": "Дата начала работы",
            "deal_created_date": "Дата создания сделки",
            "days_on_stage": "Кол-во дней",
            "days_since_deal": "Дней сделки",
        },
        "processing": {"empty_stage_values": ["", "-", "nan", "None"], "audit_row_counts": True},
        "filters": {
            "exclude_deal_otkaz": {
                "enabled": True,
                "column_key": "deal_stage",
                "filter_mode": "exclude",
                "exclude_contains": "отказ",
                "case_sensitive": False,
            },
        },
    }


def test_filter_terminal_sequential_matches_batch() -> None:
    """Пошаговое исключение даёт тот же результат, что и единая маска."""
    df = pd.DataFrame(
        {
            "ID ПрПр": ["L1", "L1", "L2"],
            "Стадия сделки": ["В работе", "отказ", "закрыта"],
            "Текущий статус": ["A", "A", "B"],
        }
    )
    config = _filter_config()
    sequential = filter_terminal_deal_stage_rows(df, config, audit_each_filter=False)
    assert len(sequential) == 2
    assert set(sequential["Стадия сделки"]) == {"В работе", "закрыта"}


def test_terminal_filters_skip_second_pass() -> None:
    """Повторный filter_terminal в lead_tracker можно пропустить."""
    config = load_excel_v2_config("config_excel_v2.json")
    lead_col = col(config, "lead_id")
    report_col = col(config, "report_date")
    status_col = col(config, "current_status")
    days_col = col(config, "days_on_stage")
    days_since_col = col(config, "days_since_deal")
    work_start_col = col(config, "work_start_date")
    deal_created_col = col(config, "deal_created_date")

    df = pd.DataFrame(
        {
            lead_col: ["L1", "L1"],
            report_col: pd.to_datetime(["2026-08-30", "2026-08-31"]),
            status_col: ["СТАТУС", "СТАТУС"],
            "Группа продукта": ["G", "G"],
            "Продукт": ["P", "P"],
            "ТБ": ["TB", "TB"],
            days_col: [10, 20],
            days_since_col: [10, 20],
            work_start_col: pd.to_datetime(["2026-08-01", "2026-08-01"]),
            deal_created_col: pd.to_datetime(["2026-08-01", "2026-08-01"]),
            "Стадия сделки": ["", ""],
        }
    )
    filtered = filter_terminal_deal_stage_rows(df, config)
    with_skip = build_lead_stage_records(
        filtered,
        config,
        None,
        terminal_filters_already_applied=True,
    )
    without_skip = build_lead_stage_records(filtered, config, None)
    assert len(with_skip) == len(without_skip)


def test_audit_snapshot_coverage_passes() -> None:
    """Все ID после фильтров присутствуют в снимке."""
    config = load_excel_v2_config("config_excel_v2.json")
    lead_col = col(config, "lead_id")
    report_col = col(config, "report_date")
    status_col = col(config, "current_status")
    product_col = col(config, "product")

    filtered = pd.DataFrame(
        {
            lead_col: ["L1", "L2"],
            report_col: pd.to_datetime(["2026-08-31", "2026-08-31"]),
            status_col: ["A", "B"],
            product_col: ["P1", "P2"],
            "Группа продукта": ["G", "G"],
            "ТБ": ["TB", "TB"],
            col(config, "days_on_stage"): [5, 10],
        }
    )
    snapshot = build_lead_snapshot(filtered, config)
    audit_snapshot_coverage(filtered, snapshot, config)
    assert set(snapshot["lead_id"]) == {"L1", "L2"}
