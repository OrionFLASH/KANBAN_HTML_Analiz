"""Тесты загрузки команд лида/сделки и сборки актуальной команды."""

from __future__ import annotations

import pandas as pd

from src.team_loader import (
    build_leader_lookup,
    compose_lead_team,
    merge_person_roles,
    normalize_person_name,
    SOURCE_DEAL_TEAM,
    SOURCE_LEAD_TEAM,
)


def _team_config() -> dict:
    return {
        "mode": "test",
        "paths": {"input_test": "Docs/FileIN", "input_prod": "IN", "output": "OUT", "log": "log"},
        "excel": {"engine": "openpyxl", "na_values": [""]},
        "manager_analytics": {
            "team_files": {
                "enabled": True,
                "leader_values": ["Да", "да", "1"],
                "columns": {
                    "report_date": "Дата отчета",
                    "lead_id": "ID ПрПр",
                    "deal_id": "ID сделки",
                    "member": "Участник команды",
                    "role": "Роль участника команды",
                    "is_leader": "Лидер",
                    "tb": "ТБ",
                },
            }
        },
    }


def test_normalize_person_name() -> None:
    assert normalize_person_name("  Иванов   И.  ") == "Иванов И."
    assert normalize_person_name("-") == ""
    assert normalize_person_name(None) == ""


def test_build_leader_lookup_max_date() -> None:
    df = pd.DataFrame(
        {
            "Дата отчета": pd.to_datetime(["2026-01-01", "2026-08-31", "2026-08-31"]),
            "ID ПрПр": ["L1", "L1", "L1"],
            "ID сделки": ["D1", "D1", "D1"],
            "Участник команды": ["Старый Лидер", "Новый Лидер", "Не лидер"],
            "Роль участника команды": ["ПС", "ПС", "КМ"],
            "Лидер": ["Да", "Да", "Нет"],
            "ТБ": ["ТБ1"] * 3,
        }
    )
    lookup = build_leader_lookup(
        df, _team_config(), id_key="lead_id", source=SOURCE_LEAD_TEAM
    )
    assert list(lookup.keys()) == ["L1"]
    assert len(lookup["L1"]) == 1
    assert lookup["L1"][0]["name"] == "Новый Лидер"
    assert "Команда лида" in lookup["L1"][0]["role_label"]


def test_compose_lead_team_unique_roles() -> None:
    lead_leaders = {
        "L1": [
            {
                "name": "Иванов Иван",
                "role": "Продуктовый специалист",
                "source": SOURCE_LEAD_TEAM,
                "role_label": "Команда лида · Продуктовый специалист",
            }
        ]
    }
    deal_leaders = {
        "D1": [
            {
                "name": "Иванов Иван",
                "role": "Владелец карточки сделки",
                "source": SOURCE_DEAL_TEAM,
                "role_label": "Команда сделки · Владелец карточки сделки",
            }
        ]
    }
    team = compose_lead_team(
        lead_id="L1",
        deal_id="D1",
        km="Иванов Иван",
        vks="Петров Пётр",
        lead_leaders=lead_leaders,
        deal_leaders=deal_leaders,
    )
    assert len(team) == 2
    ivanov = next(m for m in team if m["name"] == "Иванов Иван")
    assert "КМ" in ivanov["roles"]
    assert any("Команда лида" in r for r in ivanov["roles"])
    assert any("Команда сделки" in r for r in ivanov["roles"])
    petrov = next(m for m in team if m["name"] == "Петров Пётр")
    assert petrov["roles"] == ["ВКС"]


def test_merge_person_roles_order() -> None:
    merged = merge_person_roles(
        [
            {"name": "A", "role_label": "КМ"},
            {"name": "B", "role_label": "ВКС"},
            {"name": "A", "role_label": "КМ"},
            {"name": "A", "role_label": "Команда лида · ПС"},
        ]
    )
    assert [m["name"] for m in merged] == ["A", "B"]
    assert merged[0]["roles"] == ["КМ", "Команда лида · ПС"]
