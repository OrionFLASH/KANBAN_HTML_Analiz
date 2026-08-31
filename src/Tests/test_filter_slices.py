"""Тесты срезов pipeline-фильтров."""

from __future__ import annotations

import pandas as pd

from src.filter_slices import (
    apply_filter_subset,
    build_filter_catalog,
    filter_slice_key,
    iter_filter_combinations,
)


def _config() -> dict:
    return {
        "columns": {
            "change_conditions": "_Изменение условий",
            "data_entry": "_Ввод данных",
            "label": "Метка",
        },
        "filters": {
            "change_conditions": {"column_key": "change_conditions", "value": 1},
            "data_entry": {"column_key": "data_entry", "value": 1},
            "strategy_label": {
                "column_key": "label",
                "contains": "Стратегия",
                "case_sensitive": False,
                "exclusive_group": "strategy_label",
            },
            "strategy_label_2026": {
                "column_key": "label",
                "contains_all": ["Стратегия", "2026"],
                "case_sensitive": False,
                "exclusive_group": "strategy_label",
            },
        },
    }


def test_filter_combinations_count() -> None:
    """HTML-фильтры с exclusive_group: недопустимые пары меток не считаются."""
    combos = list(iter_filter_combinations(_config()))
    assert len(combos) == 12
    assert filter_slice_key([]) == "none"
    # Оба варианта метки вместе не комбинируются
    assert not any(
        "strategy_label" in c and "strategy_label_2026" in c for c in combos
    )


def test_config_only_excludes_not_in_html_catalog() -> None:
    """Терминальные exclude с html_slice:false не в каталоге и комбинациях."""
    config = {
        "columns": {"deal_stage": "Стадия сделки", "label": "Метка"},
        "filters": {
            "strategy_label": {
                "column_key": "label",
                "contains": "Стратегия",
                "html_slice": True,
            },
            "exclude_deal_otkaz": {
                "enabled": True,
                "column_key": "deal_stage",
                "filter_mode": "exclude",
                "exclude_contains": "отказ",
                "html_slice": False,
            },
        },
    }
    names = [c["name"] for c in build_filter_catalog(config)]
    assert names == ["strategy_label"]
    combos = list(iter_filter_combinations(config))
    assert len(combos) == 2
    assert all("exclude_deal_otkaz" not in c for c in combos)


def test_efs_excluded_from_html_filters() -> None:
    """efs_flag с html_slice:false не участвует в комбинациях и каталоге."""
    config = {
        "columns": {"efs_flag": "ЕФС флаг", "change_conditions": "_Изменение условий"},
        "filters": {
            "change_conditions": {"column_key": "change_conditions", "value": 1},
            "efs_flag": {
                "enabled": False,
                "column_key": "efs_flag",
                "value": 1,
                "html_slice": False,
            },
        },
    }
    from src.filter_slices import html_filter_names

    assert "efs_flag" not in html_filter_names(config)
    assert len(list(iter_filter_combinations(config))) == 2
    assert len(build_filter_catalog(config)) == 1


def test_apply_filter_strategy_2026() -> None:
    """Метка: одновременно «Стратегия» и «2026»."""
    df = pd.DataFrame(
        {
            "Метка": [
                "Стратегия 2026",
                "стратегия план 2026",
                "Стратегия",
                "2026 без слова",
            ],
        }
    )
    config = _config()
    result = apply_filter_subset(df, config, ["strategy_label_2026"])
    assert len(result) == 2


def test_strategy_filters_mutually_valid_in_subset() -> None:
    """Оба варианта метки можно комбинировать в JSON (AND сужает выборку)."""
    df = pd.DataFrame({"Метка": ["Стратегия 2026", "Стратегия"]})
    config = _config()
    both = apply_filter_subset(df, config, ["strategy_label", "strategy_label_2026"])
    assert len(both) == 1


def test_apply_filter_subset_eq() -> None:
    """Фильтр value=1 отбирает нужные строки."""
    df = pd.DataFrame(
        {
            "_Изменение условий": [1, 0, 1],
            "_Ввод данных": [1, 1, 0],
            "Метка": ["Стратегия", "X", "Стратегия"],
        }
    )
    config = _config()
    result = apply_filter_subset(df, config, ["change_conditions"])
    assert len(result) == 2


def test_filter_catalog_labels() -> None:
    """Каталог содержит подписи для HTML и варианты метки."""
    catalog = build_filter_catalog(_config())
    assert len(catalog) == 4
    strategy = next(item for item in catalog if item["name"] == "strategy_label")
    strategy2026 = next(item for item in catalog if item["name"] == "strategy_label_2026")
    assert strategy["type"] == "contains"
    assert strategy2026["type"] == "contains_all"
    assert strategy["exclusive_group"] == "strategy_label"
