"""Тесты справочника почт менеджеров по ТН."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.manager_emails import (
    attach_emails_by_tab_column,
    enrich_snapshot_with_manager_emails,
    load_manager_email_lookup,
    map_multiline_tn_to_email,
)


def _config(csv_path: Path) -> dict:
    return {
        "manager_emails": {
            "enabled": True,
            "directory": str(csv_path.parent),
            "filename": csv_path.name,
            "delimiter": ";",
            "encoding": "utf-8-sig",
            "columns": {
                "tab_number": "Табельный номер",
                "email_alpha": "Почта Альфа",
                "email_sigma": "Почта Сигма",
            },
            "output_columns": {
                "lead": {
                    "email_alpha": "Почта Альфа Лидера лида",
                    "email_sigma": "Почта Сигма Лидера лида",
                },
                "deal": {
                    "email_alpha": "Почта Альфа Лидера сделки",
                    "email_sigma": "Почта Сигма Лидера сделки",
                },
            },
        },
        "team_files": {
            "output_columns": {
                "lead": {"member_tab_number": "TN Лидера лида"},
                "deal": {"member_tab_number": "TN Лидера сделки"},
            }
        },
    }


def _write_csv(path: Path) -> None:
    path.write_text(
        "\ufeffТабельный номер;Почта Альфа;Почта Сигма\n"
        "1933957;a1@omega;a1@sigma\n"
        "01875872;a2@omega;a2@sigma\n",
        encoding="utf-8-sig",
    )


def test_load_and_normalize_tab(tmp_path: Path) -> None:
    csv_path = tmp_path / "mails.csv"
    _write_csv(csv_path)
    lookup = load_manager_email_lookup(_config(csv_path))
    assert "01933957" in lookup
    assert lookup["01933957"] == ("a1@omega", "a1@sigma")
    assert lookup["01875872"] == ("a2@omega", "a2@sigma")


def test_multiline_tn_preserves_order(tmp_path: Path) -> None:
    csv_path = tmp_path / "mails.csv"
    _write_csv(csv_path)
    lookup = load_manager_email_lookup(_config(csv_path))
    alpha = map_multiline_tn_to_email(
        "1875872\n1933957",
        lookup,
        which="alpha",
    )
    assert alpha == "a2@omega\na1@omega"
    # Один неизвестный — пустая позиция
    mixed = map_multiline_tn_to_email("999\n01875872", lookup, which="sigma")
    assert mixed == "\na2@sigma"


def test_enrich_snapshot_and_managers(tmp_path: Path) -> None:
    csv_path = tmp_path / "mails.csv"
    _write_csv(csv_path)
    cfg = _config(csv_path)
    snap = pd.DataFrame(
        {
            "TN Лидера лида": ["01933957", "1875872\n1933957"],
            "TN Лидера сделки": ["01875872", None],
        }
    )
    out = enrich_snapshot_with_manager_emails(snap, cfg)
    assert out.loc[0, "Почта Альфа Лидера лида"] == "a1@omega"
    assert out.loc[0, "Почта Сигма Лидера лида"] == "a1@sigma"
    assert out.loc[0, "Почта Альфа Лидера сделки"] == "a2@omega"
    assert out.loc[1, "Почта Альфа Лидера лида"] == "a2@omega\na1@omega"

    managers = pd.DataFrame({"Табельный номер": ["1933957"], "ФИО": ["X"]})
    with_mail = attach_emails_by_tab_column(managers, cfg)
    assert list(with_mail.columns[:3]) == ["Табельный номер", "Почта Альфа", "Почта Сигма"]
    assert with_mail.loc[0, "Почта Альфа"] == "a1@omega"
