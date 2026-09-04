"""Тесты загрузки команд лида/сделки и сборки актуальной команды."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.team_loader import (
    build_leader_lookup,
    compose_lead_team,
    load_team_kind_frames,
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
            "Дата добавления в команду": pd.to_datetime(
                ["2026-01-01", "2026-06-01", "2026-07-01"]
            ),
            "ID ПрПр": ["L1", "L1", "L1"],
            "ID сделки": ["D1", "D1", "D1"],
            "Участник команды": ["Старый Лидер", "Средний Лидер", "Новый Лидер"],
            "Роль участника команды": ["ПС", "ПС", "КМ"],
            "Лидер": ["Да", "Да", "Да"],
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


def test_build_leader_lookup_same_added_keeps_both() -> None:
    df = pd.DataFrame(
        {
            "Дата отчета": pd.to_datetime(["2026-08-31", "2026-08-31"]),
            "Дата добавления в команду": pd.to_datetime(["2026-07-01", "2026-07-01"]),
            "ID ПрПр": ["L1", "L1"],
            "ID сделки": ["D1", "D1"],
            "Участник команды": ["Лидер А", "Лидер Б"],
            "Роль участника команды": ["ПС", "КМ"],
            "Лидер": ["Да", "Да"],
            "ТБ": ["ТБ1", "ТБ1"],
        }
    )
    lookup = build_leader_lookup(
        df, _team_config(), id_key="lead_id", source=SOURCE_LEAD_TEAM
    )
    assert {m["name"] for m in lookup["L1"]} == {"Лидер А", "Лидер Б"}


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


def test_load_team_kind_frames_concat_multiple(tmp_path: Path) -> None:
    """Несколько prod-файлов команды склеиваются в один DataFrame."""
    import pandas as pd

    input_dir: Path = tmp_path / "IN" / "PROD"
    input_dir.mkdir(parents=True)

    config: dict = _team_config()
    config["mode"] = "prod"
    config["paths"]["input_prod"] = str(input_dir)
    config["manager_analytics"]["team_files"]["lead_team"] = {
        "prod": ["team_ub.xlsx", "team_yuzb.xlsx"]
    }
    config["manager_analytics"]["team_files"]["deal_team"] = {"prod": []}

    for name, lead_id in [("team_ub.xlsx", "L1"), ("team_yuzb.xlsx", "L2")]:
        frame: pd.DataFrame = pd.DataFrame(
            {
                "Дата отчета": pd.to_datetime(["2026-09-01"]),
                "ID ПрПр": [lead_id],
                "ID сделки": ["D1"],
                "Участник команды": [f"Лидер {lead_id}"],
                "Роль участника команды": ["ПС"],
                "Лидер": ["Да"],
                "ТБ": ["ТБ"],
            }
        )
        frame.to_excel(input_dir / name, index=False)

    combined: pd.DataFrame = load_team_kind_frames(config, "lead_team")
    assert len(combined) == 2
    assert set(combined["source_file"]) == {"team_ub.xlsx", "team_yuzb.xlsx"}
    lookup = build_leader_lookup(
        combined, config, id_key="lead_id", source=SOURCE_LEAD_TEAM
    )
    assert set(lookup.keys()) == {"L1", "L2"}
