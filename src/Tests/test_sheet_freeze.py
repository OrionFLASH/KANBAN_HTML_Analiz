"""Тесты закрепления областей Excel из config."""

from __future__ import annotations

from src.excel_format import freeze_panes_from_last, resolve_freeze_panes


def test_freeze_panes_from_last() -> None:
    assert freeze_panes_from_last(last_row=1, last_col=0) == "A2"
    assert freeze_panes_from_last(last_row=3, last_col=3) == "D4"
    assert freeze_panes_from_last(last_row=1, last_col=2) == "C2"
    assert freeze_panes_from_last(last_row=0, last_col=1) == "B1"
    assert freeze_panes_from_last(last_row=0, last_col=0) is None


def test_resolve_freeze_panes_per_sheet() -> None:
    config = {
        "output": {
            "sheet_freeze": {
                "default": {"last_row": 1, "last_col": 0},
                "duration_matrix": {"last_row": 3, "last_col": "C"},
                "leads": {"last_row": 1, "last_col": 2},
            },
            "excel_format": {"freeze_panes": "A2"},
        }
    }
    assert resolve_freeze_panes(config, "duration_matrix") == "D4"
    assert resolve_freeze_panes(config, "leads") == "C2"
    assert resolve_freeze_panes(config, "norms") == "A2"  # default
    assert resolve_freeze_panes(config, "unknown") == "A2"
