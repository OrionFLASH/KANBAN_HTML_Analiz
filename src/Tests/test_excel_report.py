"""Тесты Excel v2 pipeline."""

from __future__ import annotations

import pandas as pd

from src.excel_report.config_loader import load_excel_v2_config
from src.excel_report.snapshot import build_lead_snapshot
from src.settings import col


def test_build_lead_snapshot_fill_forward() -> None:
    """Снимок берёт непустые значения из более свежей даты отчёта."""
    config: dict = load_excel_v2_config("config_excel_v2.json")
    lead_col: str = col(config, "lead_id")
    report_col: str = col(config, "report_date")
    status_col: str = col(config, "current_status")
    product_col: str = col(config, "product")

    df: pd.DataFrame = pd.DataFrame(
        [
            {lead_col: "L1", report_col: "2026-08-30", status_col: "", product_col: "Продукт А"},
            {lead_col: "L1", report_col: "2026-08-31", status_col: "СТАТУС 1", product_col: ""},
            {lead_col: "L2", report_col: "2026-08-31", status_col: "СТАТУС 2", product_col: "Продукт Б"},
        ]
    )
    df[report_col] = pd.to_datetime(df[report_col])

    snapshot: pd.DataFrame = build_lead_snapshot(df, config)
    row_l1: pd.Series = snapshot.loc[snapshot[lead_col] == "L1"].iloc[0]

    assert row_l1["current_status"] == "СТАТУС 1"
    assert row_l1["product"] == "Продукт А"
