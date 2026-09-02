# -*- coding: utf-8 -*-
"""Тесты воронки фильтров и свода выбросов (лист «Статистика»)."""

from __future__ import annotations

import pandas as pd

from src.filter_funnel import (
    append_funnel_step,
    build_filter_funnel_frame,
    build_outlier_audit_summary,
)
from src.outlier_clipping import AUDIT_BEFORE, AUDIT_AFTER, AUDIT_CLIPPED


def _cfg() -> dict:
    return {
        "columns": {"lead_id": "ID ПрПр"},
        "outlier_clipping": {
            "enabled": True,
            "export_audit": True,
            "min_group_size": 1,
            "min_remaining": 1,
            "rules": [{"name": "max100", "enabled": True, "mode": "range", "max_days": 100}],
        },
        "output": {"column_labels": {}},
    }


def test_funnel_tracks_dropped_rows_and_leads() -> None:
    cfg = _cfg()
    funnel: list = []
    before = pd.DataFrame({"ID ПрПр": ["a", "a", "b", "c"], "x": [1, 2, 3, 4]})
    after = pd.DataFrame({"ID ПрПр": ["a", "b"], "x": [1, 3]})
    append_funnel_step(
        funnel,
        stage="Фильтр: demo",
        before_df=before,
        after_df=after,
        config=cfg,
    )
    frame = build_filter_funnel_frame(funnel)
    assert len(frame) == 1
    assert int(frame.loc[0, "Отсечено строк"]) == 2
    assert int(frame.loc[0, "До (лидов)"]) == 3
    assert int(frame.loc[0, "После (лидов)"]) == 2
    assert int(frame.loc[0, "Отсечено лидов"]) == 1


def test_outlier_summary_sums_groups() -> None:
    cfg = _cfg()
    norms = pd.DataFrame(
        {
            AUDIT_BEFORE: [10, 20],
            AUDIT_AFTER: [8, 15],
            AUDIT_CLIPPED: [2, 5],
            "outlier_rule_max100": [2, 5],
        }
    )
    summary = build_outlier_audit_summary(norms, cfg)
    assert not summary.empty
    clipped_row = summary.loc[summary["Показатель"].astype(str).str.contains("всего", case=False)]
    assert int(clipped_row.iloc[0]["Значение"]) == 7


def test_outlier_summary_when_disabled() -> None:
    cfg = _cfg()
    cfg["outlier_clipping"]["enabled"] = False
    summary = build_outlier_audit_summary(pd.DataFrame(), cfg)
    assert "выключено" in str(summary.iloc[0]["Значение"]).lower()
