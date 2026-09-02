"""Тесты отсечения выбросов срока дней."""

from __future__ import annotations

import pandas as pd

from src.aggregator import aggregate_statistics
from src.outlier_clipping import (
    AUDIT_AFTER,
    AUDIT_BEFORE,
    AUDIT_CLIPPED,
    clip_group_frame,
    rule_applies_to_group,
)


def _base_config(**outlier_kwargs: object) -> dict:
    outlier: dict = {
        "enabled": True,
        "metric": "days_on_stage",
        "export_audit": True,
        "min_group_size": 3,
        "min_remaining": 1,
        "rules": [],
    }
    outlier.update(outlier_kwargs)
    return {
        "columns": {
            "product_group": "Группа продукта",
            "product": "Продукт",
            "tb": "ТБ",
            "current_status": "Текущий статус",
        },
        "aggregation": {
            "group_keys": ["product_group", "product", "analysis_level", "current_status", "stage_key"],
            "metrics": ["days_on_stage"],
        },
        "percentiles": [50, 80],
        "output": {"statistics": {"min": {"export": True}, "max": {"export": True}}},
        "outlier_clipping": outlier,
        "product_analysis_mode": "group_product",
        "processing": {"group_only_product_label": "—"},
    }


def _records(days: list[int]) -> pd.DataFrame:
    n: int = len(days)
    return pd.DataFrame(
        {
            "Группа продукта": ["G"] * n,
            "Продукт": ["P"] * n,
            "analysis_level": ["status"] * n,
            "current_status": ["В работе"] * n,
            "stage_key": ["В работе"] * n,
            "ТБ": ["ТБ1"] * n,
            "days_on_stage": days,
        }
    )


def test_scope_empty_applies_everywhere() -> None:
    assert rule_applies_to_group({"scope": {}}, {"Группа продукта": "G"}, _base_config())


def test_scope_product_group_match() -> None:
    cfg = _base_config()
    rule = {"scope": {"product_group": "G"}}
    assert rule_applies_to_group(rule, {"Группа продукта": "G"}, cfg)
    assert not rule_applies_to_group(rule, {"Группа продукта": "Other"}, cfg)


def test_range_max_days_clips() -> None:
    cfg = _base_config(
        rules=[
            {
                "name": "max500",
                "enabled": True,
                "scope": {},
                "mode": "range",
                "max_days": 500,
            }
        ]
    )
    group = _records([10, 100, 600, 700])
    keys = {
        "Группа продукта": "G",
        "Продукт": "P",
        "current_status": "В работе",
        "ТБ": "ТБ1",
    }
    clipped, audit = clip_group_frame(group, keys, cfg)
    assert len(clipped) == 2
    assert audit[AUDIT_BEFORE] == 4
    assert audit[AUDIT_AFTER] == 2
    assert audit[AUDIT_CLIPPED] == 2
    assert audit["outlier_rule_max500"] == 2


def test_range_min_and_max() -> None:
    cfg = _base_config(
        rules=[
            {
                "name": "band",
                "mode": "range",
                "min_days": 2,
                "max_days": 500,
            }
        ]
    )
    group = _records([1, 2, 100, 501])
    clipped, audit = clip_group_frame(group, {"Группа продукта": "G"}, cfg)
    assert sorted(clipped["days_on_stage"].tolist()) == [2, 100]
    assert audit[AUDIT_CLIPPED] == 2


def test_percentile_trim_upper() -> None:
    cfg = _base_config(
        min_group_size=5,
        rules=[
            {
                "name": "trim_top",
                "mode": "percentile_trim",
                "trim_lower_pct": 0,
                "trim_upper_pct": 20,
            }
        ],
    )
    # 10 значений 1..10 → верхние ~20% отсекаются
    group = _records(list(range(1, 11)))
    clipped, audit = clip_group_frame(group, {"Группа продукта": "G"}, cfg)
    assert audit[AUDIT_CLIPPED] >= 1
    assert clipped["days_on_stage"].max() < 10 or audit[AUDIT_CLIPPED] > 0


def test_iqr_clips_extreme() -> None:
    cfg = _base_config(
        min_group_size=5,
        rules=[{"name": "iqr", "mode": "iqr", "iqr_k": 1.5}],
    )
    days: list[int] = [10, 11, 12, 10, 11, 12, 10, 11, 1000]
    group = _records(days)
    clipped, audit = clip_group_frame(group, {"Группа продукта": "G"}, cfg)
    assert 1000 not in clipped["days_on_stage"].tolist()
    assert audit["outlier_rule_iqr"] >= 1


def test_aggregate_includes_audit_and_recalculates() -> None:
    cfg = _base_config(
        rules=[
            {
                "name": "max100",
                "mode": "range",
                "max_days": 100,
            }
        ]
    )
    records = _records([10, 20, 30, 500])
    result = aggregate_statistics(records, cfg, [50.0], include_tb=True)
    assert len(result) == 1
    row = result.iloc[0]
    assert int(row[AUDIT_BEFORE]) == 4
    assert int(row[AUDIT_AFTER]) == 3
    assert int(row[AUDIT_CLIPPED]) == 1
    assert int(row["outlier_rule_max100"]) == 1
    assert int(row["days_on_stage_count"]) == 3
    assert int(row["days_on_stage_max"]) == 30


def test_min_remaining_skips_rule() -> None:
    """Если после отсечения останется меньше min_remaining — правило не применяется."""
    cfg = _base_config(
        min_remaining=3,
        rules=[
            {
                "name": "max50",
                "mode": "range",
                "max_days": 50,
            }
        ],
    )
    # 4 лида, 2 выше 50 → осталось бы 2 < 3 → отсечение отменяется
    group = _records([10, 20, 100, 200])
    clipped, audit = clip_group_frame(group, {"Группа продукта": "G"}, cfg)
    assert len(clipped) == 4
    assert audit[AUDIT_CLIPPED] == 0
    assert audit["outlier_rule_max50"] == 0


def test_min_remaining_allows_when_enough_left() -> None:
    cfg = _base_config(
        min_remaining=2,
        rules=[{"name": "max50", "mode": "range", "max_days": 50}],
    )
    group = _records([10, 20, 100, 200])
    clipped, audit = clip_group_frame(group, {"Группа продукта": "G"}, cfg)
    assert len(clipped) == 2
    assert audit[AUDIT_CLIPPED] == 2
    assert audit["outlier_rule_max50"] == 2


def test_rule_min_remaining_overrides_global() -> None:
    cfg = _base_config(
        min_remaining=2,
        rules=[
            {
                "name": "max50",
                "mode": "range",
                "max_days": 50,
                "min_remaining": 3,
            }
        ],
    )
    group = _records([10, 20, 100, 200])
    clipped, audit = clip_group_frame(group, {"Группа продукта": "G"}, cfg)
    assert len(clipped) == 4
    assert audit["outlier_rule_max50"] == 0


def test_disabled_clipping_no_audit_columns() -> None:
    cfg = _base_config(enabled=False, rules=[{"name": "max100", "mode": "range", "max_days": 100}])
    records = _records([10, 500])
    result = aggregate_statistics(records, cfg, [50.0], include_tb=False)
    assert AUDIT_CLIPPED not in result.columns
    assert int(result.iloc[0]["days_on_stage_count"]) == 2
