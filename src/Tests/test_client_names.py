"""Тесты сокращения названий клиентов."""

from __future__ import annotations

from src.client_names import abbreviate_client_name


def test_abbreviate_ooo() -> None:
    name = abbreviate_client_name(
        'Общество с ограниченной ответственностью "Ромашка"',
        {"client_display": {"enabled": True}},
    )
    assert name is not None
    assert name.startswith("ООО ")
    assert "Ромашка" in name
    assert "общество" not in name.lower()


def test_abbreviate_space_when_glued() -> None:
    """После замены всегда пробел перед названием."""
    name = abbreviate_client_name(
        'Общество с ограниченной ответственностью"Альфа"',
        {"client_display": {"enabled": True}},
    )
    assert name == 'ООО "Альфа"'


def test_abbreviate_already_glued_short() -> None:
    name = abbreviate_client_name(
        "ОООРомашка",
        {
            "client_display": {
                "enabled": True,
                "abbreviations": [{"match": "общество с ограниченной ответственностью", "replace": "ООО"}],
            }
        },
    )
    assert name == "ООО Ромашка"


def test_abbreviate_pao_before_ao() -> None:
    name = abbreviate_client_name(
        "Публичное акционерное общество Сбербанк",
        {"client_display": {"enabled": True}},
    )
    assert name is not None
    assert name.startswith("ПАО")
    assert not name.startswith("АО")


def test_abbreviate_ip() -> None:
    name = abbreviate_client_name(
        "Индивидуальный предприниматель Иванов Иван Иванович",
        {"client_display": {"enabled": True}},
    )
    assert name is not None
    assert name.startswith("ИП")


def test_abbreviate_disabled() -> None:
    raw = "Общество с ограниченной ответственностью Тест"
    name = abbreviate_client_name(raw, {"client_display": {"enabled": False}})
    assert name == raw


def test_custom_abbreviation() -> None:
    cfg = {
        "client_display": {
            "enabled": True,
            "abbreviations": [{"match": "общество с ограниченной ответственностью", "replace": "ООО"}],
        }
    }
    assert abbreviate_client_name("ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ Альфа", cfg) == "ООО Альфа"
