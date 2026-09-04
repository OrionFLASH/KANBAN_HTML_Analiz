"""Тесты подливки лидеров лида/сделки в снимок v2."""

from __future__ import annotations

import pandas as pd

from src.v2.config_loader import load_excel_v2_config
from src.v2.snapshot import build_lead_snapshot
from src.v2.team_enrich import (
    build_leaders_lookup_df,
    enrich_snapshot_with_team_dfs,
)
from src.settings import col


def _team_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Минимальные файлы команды лида и сделки."""
    lead_team: pd.DataFrame = pd.DataFrame(
        {
            "Дата отчета": pd.to_datetime(["2026-08-01", "2026-09-01", "2026-09-01"]),
            "ID ПрПр": ["L1", "L1", "L1"],
            "ID сделки": ["D1", "D1", "D1"],
            "Табельный номер участника команды": ["111", "222", "333"],
            "Участник команды": ["Старый Лидер", "Лидер Лида А", "Лидер Лида Б"],
            "Роль участника команды": ["ПС", "ПС", "КМ"],
            "Лидер": ["Да", "Да", "Да"],
            "ТБ": ["ТБ1", "ТБ1", "ТБ2"],
        }
    )
    deal_team: pd.DataFrame = pd.DataFrame(
        {
            "Дата отчета": pd.to_datetime(["2026-08-01", "2026-09-01", "2026-09-01"]),
            "ID ПрПр": ["L1", "L1", "L1"],
            "ID сделки": ["D1", "D1", "D1"],
            "Табельный номер участника команды": ["444", "555", "666"],
            "Участник команды": ["Старый Сделка", "Лидер Сделки А", "Лидер Сделки Б"],
            "Роль участника команды": ["ВКС", "ВКС", "ПС"],
            "Лидер": ["Да", "Да", "Да"],
            "ТБ": ["ТБ1", "ТБ1", "ТБ2"],
        }
    )
    return lead_team, deal_team


def test_build_leaders_lookup_keeps_all_on_max_date() -> None:
    """На max дате все лидеры склеиваются через перевод строки."""
    config: dict = load_excel_v2_config("config_excel_v2.json")
    lead_team, _ = _team_frames()
    lookup: pd.DataFrame = build_leaders_lookup_df(
        lead_team, config, id_key="lead_id", source="lead"
    )
    assert list(lookup.index) == ["L1"]
    names: str = str(lookup.loc["L1", "member"])
    assert "Лидер Лида А" in names
    assert "Лидер Лида Б" in names
    assert "Старый Лидер" not in names
    assert "\n" in names


def test_enrich_uses_snapshot_deal_id_key() -> None:
    """
    Снимок хранит deal_id под ключом config, не под «ID сделки».
    Раньше merge искал колонку «ID сделки» и лидер сделки всегда был пустым.
    """
    config: dict = load_excel_v2_config("config_excel_v2.json")
    lead_col: str = col(config, "lead_id")
    report_col: str = col(config, "report_date")
    deal_src: str = col(config, "deal_id")
    days_col: str = col(config, "days_on_stage")
    status_col: str = col(config, "current_status")

    kanban: pd.DataFrame = pd.DataFrame(
        {
            lead_col: ["L1", "L2"],
            report_col: pd.to_datetime(["2026-09-01", "2026-09-01"]),
            deal_src: ["D1", "D2"],
            days_col: [10, 20],
            status_col: ["С1", "С2"],
        }
    )
    snapshot: pd.DataFrame = build_lead_snapshot(kanban, config)
    assert "deal_id" in snapshot.columns
    assert "ID сделки" not in snapshot.columns

    lead_team, deal_team = _team_frames()
    # Вторая сделка — один лидер
    deal_team = pd.concat(
        [
            deal_team,
            pd.DataFrame(
                {
                    "Дата отчета": pd.to_datetime(["2026-09-01"]),
                    "ID ПрПр": ["L2"],
                    "ID сделки": ["D2"],
                    "Табельный номер участника команды": ["777"],
                    "Участник команды": ["Лидер Сделки L2"],
                    "Роль участника команды": ["ВКС"],
                    "Лидер": ["Да"],
                    "ТБ": ["ТБ3"],
                }
            ),
        ],
        ignore_index=True,
    )

    enriched: pd.DataFrame = enrich_snapshot_with_team_dfs(
        snapshot, lead_team, deal_team, config
    )

    row_l1: pd.Series = enriched.loc[enriched[lead_col] == "L1"].iloc[0]
    row_l2: pd.Series = enriched.loc[enriched[lead_col] == "L2"].iloc[0]

    assert "Лидер Лида А" in str(row_l1["ФИО Лидера лида"])
    assert "Лидер Сделки А" in str(row_l1["ФИО Лидера сделки"])
    assert "Лидер Сделки Б" in str(row_l1["ФИО Лидера сделки"])
    assert row_l2["ФИО Лидера сделки"] == "Лидер Сделки L2"
    assert pd.isna(row_l2["ФИО Лидера лида"]) or row_l2["ФИО Лидера лида"] in (None, "")
