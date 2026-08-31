"""Тесты ранжирования TOP по участникам команды зависшего лида."""

from __future__ import annotations

import pandas as pd

from src.manager_analytics import (
    attach_teams_to_detail,
    explode_detail_by_team_member,
    aggregate_manager_counts,
    top_managers_per_tb,
)
from src.team_loader import SOURCE_DEAL_TEAM, SOURCE_LEAD_TEAM


def _config() -> dict:
    return {
        "columns": {
            "tb": "ТБ",
            "km": "КМ",
            "vks": "ВКС",
            "lead_id": "ID ПрПр",
            "deal_id": "ID сделки",
            "product_group": "Группа продукта",
            "product": "Продукт",
        },
        "product_analysis_mode": "group_product",
        "manager_analytics": {
            "enabled": True,
            "rank_by_team": True,
            "top_managers_per_tb": 3,
            "team_files": {"enabled": True},
        },
    }


def test_explode_and_top_by_team_member() -> None:
    detail = pd.DataFrame(
        {
            "ТБ": ["ТБ1", "ТБ1"],
            "КМ": ["КМ Альфа", "КМ Бета"],
            "ВКС": ["ВКС Гамма", "-"],
            "ID ПрПр": ["L1", "L2"],
            "ID сделки": ["D1", "D2"],
            "Группа продукта": ["G", "G"],
            "Продукт": ["P", "P"],
            "stage_key": ["S", "S"],
            "analysis_level": ["status", "status"],
            "days_int": [100.0, 90.0],
            "threshold_days": [50.0, 50.0],
            "exceeded": [True, True],
        }
    )
    lead_leaders = {
        "L1": [
            {
                "name": "Лидер Лида",
                "role": "ПС",
                "source": SOURCE_LEAD_TEAM,
                "role_label": "Команда лида · ПС",
            }
        ]
    }
    deal_leaders = {
        "D1": [
            {
                "name": "КМ Альфа",
                "role": "Владелец",
                "source": SOURCE_DEAL_TEAM,
                "role_label": "Команда сделки · Владелец",
            }
        ]
    }
    with_team = attach_teams_to_detail(detail, _config(), lead_leaders, deal_leaders)
    assert len(with_team.iloc[0]["team"]) >= 3  # лидер лида + КМ(+сделка) + ВКС

    exploded = explode_detail_by_team_member(with_team, _config())
    assert not exploded.empty
    assert "Лидер Лида" in set(exploded["КМ"].astype(str))

    _, totals = aggregate_manager_counts(exploded, _config())
    top = top_managers_per_tb(totals, _config())
    assert not top.empty
    assert "ТБ" in top.columns
    # КМ Альфа участвует в L1 (как КМ и лидер сделки) — exceedance считается по строкам
    alpha = top.loc[top["КМ"] == "КМ Альфа"]
    assert not alpha.empty
