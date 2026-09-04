"""Тесты Excel v2 pipeline."""

from __future__ import annotations

import pandas as pd

from src.v2.config_loader import load_excel_v2_config
from src.v2.snapshot import build_lead_snapshot, snapshot_to_export_frame
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
    row_l1: pd.Series = snapshot.loc[snapshot["lead_id"] == "L1"].iloc[0]

    assert row_l1["current_status"] == "СТАТУС 1"
    assert row_l1["product"] == "Продукт А"


def test_export_leader_emails_after_fio() -> None:
    """На «Уникальные ID» почты лидера идут сразу после ФИО."""
    config: dict = load_excel_v2_config("config_excel_v2.json")
    snap: pd.DataFrame = pd.DataFrame(
        {
            "lead_id": ["L1"],
            "product": ["P"],
            "TN Лидера лида": ["00000001"],
            "ФИО Лидера лида": ["Иванов"],
            "Роль Лидера лида": ["ПС"],
            "ТБ Лидера лида": ["ТБ1"],
            "Почта Альфа Лидера лида": ["a@x"],
            "Почта Сигма Лидера лида": ["a@s"],
            "TN Лидера сделки": ["00000002"],
            "ФИО Лидера сделки": ["Петров"],
            "Роль Лидера сделки": ["ВКС"],
            "ТБ Лидера сделки": ["ТБ2"],
            "Почта Альфа Лидера сделки": ["b@x"],
            "Почта Сигма Лидера сделки": ["b@s"],
        }
    )
    exported: pd.DataFrame = snapshot_to_export_frame(snap, config)
    cols: list[str] = list(exported.columns)

    fio_lead: int = cols.index("ФИО Лидера лида")
    assert cols[fio_lead + 1] == "Почта Альфа Лидера лида"
    assert cols[fio_lead + 2] == "Почта Сигма Лидера лида"
    assert cols[fio_lead + 3] == "Роль Лидера лида"

    fio_deal: int = cols.index("ФИО Лидера сделки")
    assert cols[fio_deal + 1] == "Почта Альфа Лидера сделки"
    assert cols[fio_deal + 2] == "Почта Сигма Лидера сделки"
    assert cols[fio_deal + 3] == "Роль Лидера сделки"
