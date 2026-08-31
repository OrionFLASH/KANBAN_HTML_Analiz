"""Сокращение полных юридических форм в названиях клиентов."""

from __future__ import annotations

import re
from typing import Any


# Длинные формы первыми — чтобы «Публичное АО» не сжалось до «АО» раньше ПАО
DEFAULT_ABBREVIATIONS: list[dict[str, str]] = [
    {"match": "публичное акционерное общество", "replace": "ПАО"},
    {"match": "непубличное акционерное общество", "replace": "НАО"},
    {"match": "закрытое акционерное общество", "replace": "ЗАО"},
    {"match": "открытое акционерное общество", "replace": "ОАО"},
    {"match": "общество с ограниченной ответственностью", "replace": "ООО"},
    {"match": "акционерное общество", "replace": "АО"},
    {"match": "индивидуальный предприниматель", "replace": "ИП"},
    {"match": "федеральное государственное бюджетное учреждение", "replace": "ФГБУ"},
    {"match": "федеральное государственное унитарное предприятие", "replace": "ФГУП"},
    {"match": "государственное унитарное предприятие", "replace": "ГУП"},
    {"match": "муниципальное унитарное предприятие", "replace": "МУП"},
    {"match": "автономная некоммерческая организация", "replace": "АНО"},
    {"match": "некоммерческая организация", "replace": "НКО"},
    {"match": "товарищество собственников жилья", "replace": "ТСЖ"},
    {"match": "товарищество собственников недвижимости", "replace": "ТСН"},
    {"match": "крестьянское (фермерское) хозяйство", "replace": "КФХ"},
    {"match": "крестьянское фермерское хозяйство", "replace": "КФХ"},
    {"match": "производственный кооператив", "replace": "ПК"},
    {"match": "сельскохозяйственный производственный кооператив", "replace": "СПК"},
    {"match": "полное товарищество", "replace": "ПТ"},
    {"match": "товарищество на вере", "replace": "ТНВ"},
    {"match": "коммандитное товарищество", "replace": "КТ"},
]


def client_display_config(config: dict[str, Any]) -> dict[str, Any]:
    """Блок config.client_display с дефолтами."""
    raw: dict[str, Any] = config.get("client_display") or {}
    if not isinstance(raw, dict):
        return {"enabled": True, "abbreviations": list(DEFAULT_ABBREVIATIONS)}
    return raw


def abbreviation_pairs(config: dict[str, Any]) -> list[tuple[str, str]]:
    """Пары (полная форма → сокращение), длинные первыми."""
    cfg: dict[str, Any] = client_display_config(config)
    items: list[Any] = list(cfg.get("abbreviations") or DEFAULT_ABBREVIATIONS)
    pairs: list[tuple[str, str]] = []
    for item in items:
        if isinstance(item, dict) and item.get("match") and item.get("replace") is not None:
            pairs.append((str(item["match"]).strip(), str(item["replace"]).strip()))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            pairs.append((str(item[0]).strip(), str(item[1]).strip()))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def abbreviate_client_name(name: str | None, config: dict[str, Any] | None = None) -> str | None:
    """
    Заменяет полные юрформы на аббревиатуры (регистр не важен).
    После сокращения всегда пробел перед названием / кавычкой.
    """
    if name is None:
        return None
    text: str = str(name).strip()
    if not text:
        return None

    cfg: dict[str, Any] = client_display_config(config or {})
    if not bool(cfg.get("enabled", True)):
        return text

    pairs: list[tuple[str, str]] = abbreviation_pairs(config or {})
    result: str = text
    for full, short in pairs:
        if not full:
            continue
        # 1) Юрформа целиком в кавычках/скобках — снимаем обёртку
        wrapped: str = (
            r"(?i)[«\"'(\[]\s*"
            + re.escape(full)
            + r"\.?\s*[»\"')\]]"
        )
        result = re.sub(wrapped, short + " ", result)
        # 2) Голая юрформа — кавычки названия («Альфа») не трогаем
        bare: str = r"(?i)" + re.escape(full) + r"\.?"
        result = re.sub(bare, short + " ", result)

    result = re.sub(r"\s{2,}", " ", result).strip(" ,;")
    # Уже слипшиеся «ОООРомашка» / «ООО«Ромашка»» → пробел
    shorts: list[str] = sorted({s for _, s in pairs if s}, key=len, reverse=True)
    if shorts:
        alt: str = "|".join(re.escape(s) for s in shorts)
        result = re.sub(
            rf"({alt})(?=[A-Za-zА-Яа-яЁё0-9«\"'(\[])",
            r"\1 ",
            result,
        )
        result = re.sub(r"\s{2,}", " ", result).strip(" ,;")
    return result or None


def abbreviations_for_meta(config: dict[str, Any]) -> dict[str, Any]:
    """Фрагмент meta/JSON для UI (те же правила, что в pipeline)."""
    cfg: dict[str, Any] = client_display_config(config)
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "abbreviations": [
            {"match": m, "replace": r} for m, r in abbreviation_pairs(config)
        ],
    }
