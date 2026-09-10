"""Тесты колонок сроков по «Текущий статус» на листе уникальных ID."""

from __future__ import annotations

import pandas as pd

from src.v2.snapshot import snapshot_to_export_frame
from src.v2.status_durations import (
    attach_status_duration_columns,
    build_status_duration_pivot,
    resolve_status_column_order,
)


def _config() -> dict:
    return {
        "columns": {
            "lead_id": "ID ПрПр",
            "current_status": "Текущий статус",
            "days_on_stage": "Дней на стадии",
        },
        "output": {
            "snapshot_columns": {
                "product": "Продукт",
                "current_status": "Стадия работы с лидом",
                "tb": "ТБ",
            },
            "status_duration_columns": {
                "enabled": True,
                "include_others": True,
                "others_sort": "alpha",
                "order": [
                    "К продаже",
                    "Выявление потребности",
                    "Обсуждение условий",
                    "Реализация сделки",
                    "Активация продукта",
                    "Продажа завершена",
                ],
            },
            "exceedance_columns": {
                "p80_norm": "Норматив P80",
                "current_days": "Текущий срок",
                "exceedance_flag": "превышение",
                "exceedance_days": "дней отклонения",
            },
            "team_files": {"output_columns": {}},
        },
        "team_files": {"output_columns": {}},
        "manager_emails": {"output_columns": {}},
    }


def test_resolve_order_preferred_then_others() -> None:
    order = resolve_status_column_order(
        ["Отказ", "К ПРОДАЖЕ", "Выявление потребности", "Зов"],
        _config(),
    )
    assert order[:6] == [
        "К продаже",
        "Выявление потребности",
        "Обсуждение условий",
        "Реализация сделки",
        "Активация продукта",
        "Продажа завершена",
    ]
    assert order[6:] == ["Зов", "Отказ"]


def test_build_status_duration_pivot_max_days() -> None:
    records = pd.DataFrame(
        {
            "lead_id": ["L1", "L1", "L1", "L2"],
            "analysis_level": ["status", "status", "status", "status"],
            "current_status": [
                "К ПРОДАЖЕ",
                "Выявление потребности",
                "К продаже",
                "Отказ",
            ],
            "days_on_stage": [3, 10, 5, 7],
        }
    )
    pivot, cols = build_status_duration_pivot(records, _config())
    assert cols[0] == "К продаже"
    assert cols[1] == "Выявление потребности"
    assert "Отказ" in cols
    row_l1 = pivot.loc[pivot["lead_id"] == "L1"].iloc[0]
    # max(3, 5) для «К продаже»
    assert int(row_l1["К продаже"]) == 5
    assert int(row_l1["Выявление потребности"]) == 10
    assert pd.isna(row_l1["Обсуждение условий"])
    row_l2 = pivot.loc[pivot["lead_id"] == "L2"].iloc[0]
    assert int(row_l2["Отказ"]) == 7
    assert pd.isna(row_l2["К продаже"])


def test_attach_and_export_column_order() -> None:
    config = _config()
    snapshot = pd.DataFrame(
        {
            "lead_id": ["L1", "L2"],
            "product": ["P1", "P2"],
            "current_status": ["Выявление потребности", "Отказ"],
            "tb": ["ТБ1", "ТБ2"],
            "Норматив P80": [8, 8],
            "Текущий срок": [10, 7],
            "превышение": ["ДА", ""],
            "дней отклонения": [2, None],
        }
    )
    records = pd.DataFrame(
        {
            "lead_id": ["L1", "L1", "L2"],
            "analysis_level": ["status", "status", "status"],
            "current_status": [
                "К продаже",
                "Выявление потребности",
                "Отказ",
            ],
            "days_on_stage": [2, 10, 7],
        }
    )
    enriched, status_cols = attach_status_duration_columns(snapshot, records, config)
    assert status_cols[0] == "К продаже"
    assert "Отказ" in status_cols
    exported = snapshot_to_export_frame(
        enriched, config, status_duration_columns=status_cols
    )
    cols = list(exported.columns)
    status_idx = cols.index("Стадия работы с лидом")
    assert cols[status_idx + 1] == "К продаже"
    assert cols[status_idx + 2] == "Выявление потребности"
    assert cols[status_idx + 6] == "Продажа завершена"
    # прочий статус после канонических
    assert "Отказ" in cols
    assert cols.index("Отказ") == status_idx + 7
    # значения
    assert int(exported.loc[exported["ID ПрПр"] == "L1", "К продаже"].iloc[0]) == 2
    assert int(
        exported.loc[exported["ID ПрПр"] == "L1", "Выявление потребности"].iloc[0]
    ) == 10
    assert pd.isna(
        exported.loc[exported["ID ПрПр"] == "L1", "Реализация сделки"].iloc[0]
    )
    assert int(exported.loc[exported["ID ПрПр"] == "L2", "Отказ"].iloc[0]) == 7
