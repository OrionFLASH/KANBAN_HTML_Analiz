"""Тесты аналитики менеджеров (превышения P80)."""

from __future__ import annotations

import pandas as pd

from src.aggregator import build_all_statistics
from src.lead_tracker import build_lead_stage_records
from src.v1.manager_analytics import (
    apply_rank_selection,
    build_manager_analytics,
    build_manager_records,
    build_p80_thresholds,
    filter_latest_report_snapshot,
)


def _config() -> dict:
    return {
        "columns": {
            "report_date": "Дата отчета",
            "lead_id": "ID ПрПр",
            "product_group": "Группа продукта",
            "product": "Продукт",
            "work_start_date": "Дата начала работы",
            "current_status": "Текущий статус",
            "days_on_stage": "Количество дней на текущей стадии",
            "deal_created_date": "Дата создания сделки",
            "deal_stage": "Стадия сделки",
            "days_since_deal": "Количество дней с создания сделки",
            "tb": "ТБ",
            "km": "КМ",
            "label": "Метка",
        },
        "required_column_keys": [
            "report_date",
            "lead_id",
            "product_group",
            "product",
            "work_start_date",
            "current_status",
            "days_on_stage",
            "deal_created_date",
            "deal_stage",
            "days_since_deal",
            "tb",
            "label",
        ],
        "processing": {
            "empty_stage_values": ["", "-"],
            "dedup_same_date_agg": "max",
            "duration_fallback_to_columns": True,
        },
        "aggregation": {
            "group_keys": [
                "product_group",
                "product",
                "analysis_level",
                "current_status",
                "deal_stage",
                "stage_key",
            ],
            "metrics": ["days_on_stage", "days_since_deal"],
        },
        "duration_source": "columns",
        "stage_analysis_mode": "status",
        "product_analysis_mode": "group_product",
        "percentiles": [80],
        "manager_analytics": {
            "enabled": True,
            "metric": "days_on_stage",
            "percentile": 80,
            "top_managers_per_tb": 3,
            "rank_selection": {
                "product_groups": [],
                "products": [],
                "strategy_filter": "all",
            },
        },
    }


def _raw_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Дата отчета": pd.to_datetime(["2026-01-01"] * 8),
            "ID ПрПр": ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"],
            "Группа продукта": ["G1"] * 8,
            "Продукт": ["P1"] * 8,
            "Дата начала работы": pd.to_datetime(["2026-01-01"] * 8),
            "Текущий статус": ["В РАБОТЕ"] * 8,
            "Количество дней на текущей стадии": [5, 7, 8, 9, 10, 15, 3, 12],
            "Дата создания сделки": pd.to_datetime(["2026-01-01"] * 8),
            "Стадия сделки": [""] * 8,
            "Количество дней с создания сделки": [5, 7, 8, 9, 10, 15, 3, 12],
            "ТБ": ["ТБ1", "ТБ1", "ТБ1", "ТБ1", "ТБ1", "ТБ2", "ТБ2", "ТБ2"],
            "КМ": ["Иванов", "Иванов", "Петров", "Петров", "Сидоров", "Иванов", "Петров", "Петров"],
            "Метка": ["Стратегия 2026"] * 4 + ["Обычная"] * 4,
        }
    )


def test_build_manager_analytics_top3() -> None:
    """Топ менеджеров по превышениям P80 в каждом ТБ."""
    config = _config()
    records = build_lead_stage_records(_raw_df(), config)
    stats = build_all_statistics(records, config)
    payload = build_manager_analytics(records, stats, config)

    assert payload is not None
    top = payload["top_by_tb"]
    assert len(top) >= 1
    tb2 = [row for row in top if row["tb"] == "ТБ2" and row["exceedance_count"] > 0]
    assert tb2
    assert tb2[0]["km"] == "Иванов"
    assert "hotspots" in tb2[0]
    assert isinstance(tb2[0]["hotspots"], list)
    charts = payload.get("charts") or {}
    assert "by_tb" in charts
    assert isinstance(charts.get("facts"), list)
    with_viol = [row for row in charts["by_tb"] if row["km_with_violations"] > 0]
    assert with_viol


def test_manager_payload_includes_records_and_rank_selection() -> None:
    """JSON содержит полные records и rank_selection из config."""
    config = _config()
    records = build_lead_stage_records(_raw_df(), config)
    stats = build_all_statistics(records, config)
    payload = build_manager_analytics(records, stats, config)

    assert payload is not None
    assert isinstance(payload.get("records"), list)
    assert len(payload["records"]) >= 1
    assert "label" in payload["records"][0]
    assert payload["meta"]["rank_selection"]["strategy_filter"] == "all"
    assert "exceedances" in payload
    assert "top_by_tb_grouped" in payload
    assert "dimensions" in payload


def test_rank_selection_strategy_2026() -> None:
    """apply_rank_selection оставляет только лиды с меткой «Стратегия» и «2026»."""
    from src.v1.manager_analytics import build_manager_exceedance_detail

    config = _config()
    config["filters"] = {
        "strategy_label": {"contains": "Стратегия", "case_sensitive": False},
        "strategy_label_2026": {"contains_all": ["Стратегия", "2026"], "case_sensitive": False},
    }
    records = build_lead_stage_records(_raw_df(), config)
    stats = build_all_statistics(records, config)
    thresholds = build_p80_thresholds(stats["overall"], config)
    detail = build_manager_exceedance_detail(records, thresholds, config)

    filtered = apply_rank_selection(
        detail,
        config,
        {"product_groups": [], "products": [], "strategy_filter": "strategy_2026"},
    )
    label_col = config["columns"]["label"]
    assert not filtered.empty
    assert all("2026" in str(v) and "Стратегия" in str(v) for v in filtered[label_col])
    assert len(filtered) < len(detail)


def test_rank_selection_efs_and_change_conditions() -> None:
    """rank_selection фильтрует по ЕФС и изменению условий."""
    from src.v1.manager_analytics import build_manager_exceedance_detail

    config = _config()
    config["columns"]["deal_id"] = "ID сделки"
    config["columns"]["inn"] = "ИНН"
    config["columns"]["efs_flag"] = "ЕФС флаг"
    config["columns"]["change_conditions"] = "_Изменение условий"
    df = _raw_df()
    df["ID сделки"] = [f"D{i}" for i in range(8)]
    df["ИНН"] = [f"770{i}" for i in range(8)]
    df["ЕФС флаг"] = [1, 1, 1, 0, 1, 1, 1, 1]
    df["_Изменение условий"] = [0, 0, 1, 0, 0, 0, 0, 0]
    records = build_lead_stage_records(df, config)
    stats = build_all_statistics(records, config)
    thresholds = build_p80_thresholds(stats["overall"], config)
    detail = build_manager_exceedance_detail(records, thresholds, config)

    filtered = apply_rank_selection(
        detail,
        config,
        {
            "product_groups": [],
            "products": [],
            "strategy_filter": "all",
            "efs_flag": 1,
            "change_conditions": 0,
        },
    )
    assert len(filtered) < len(detail)
    if not filtered.empty:
        assert all(int(v) == 1 for v in filtered["ЕФС флаг"])
        assert all(int(v) == 0 for v in filtered["_Изменение условий"])


def test_exceedances_include_lead_deal_inn() -> None:
    """exceedances содержит ID ПрПр, ID сделки, ИНН и Клиент только для превышений."""
    from src.v1.manager_analytics import exceedances_to_json, build_manager_exceedance_detail, lead_records_to_json

    config = _config()
    config["columns"]["deal_id"] = "ID сделки"
    config["columns"]["inn"] = "ИНН"
    config["columns"]["client"] = "Клиент"
    df = _raw_df()
    df["ID сделки"] = ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]
    df["ИНН"] = ["7701", "7702", "7703", "7704", "7705", "7706", "7707", "7708"]
    df["Клиент"] = [f"Клиент {i}" for i in range(1, 9)]
    records = build_lead_stage_records(df, config)
    stats = build_all_statistics(records, config)
    thresholds = build_p80_thresholds(stats["overall"], config)
    detail = build_manager_exceedance_detail(records, thresholds, config)
    exc = exceedances_to_json(detail, config)
    if exc:
        assert "lead_id" in exc[0]
        assert "deal_id" in exc[0]
        assert "inn" in exc[0]
        assert "client" in exc[0]
        assert exc[0]["exceeded"] is True

    all_recs = lead_records_to_json(detail, config)
    ok_rows = [r for r in all_recs if not r.get("exceeded")]
    bad_rows = [r for r in all_recs if r.get("exceeded")]
    if ok_rows:
        assert "client" not in ok_rows[0]
        assert "inn" not in ok_rows[0]
        assert "deal_id" not in ok_rows[0]
    if bad_rows:
        assert bad_rows[0].get("client")
        assert bad_rows[0].get("inn")


def test_latest_report_snapshot() -> None:
    """Для менеджеров берётся только max(Дата отчета)."""
    config = _config()
    df = _raw_df()
    df["Дата отчета"] = pd.to_datetime(["2026-01-01"] * 4 + ["2026-02-01"] * 4)
    sliced, snap = filter_latest_report_snapshot(df, config)
    assert snap is not None
    assert snap.date().isoformat() == "2026-02-01"
    assert len(sliced) == 4


def test_build_manager_records_uses_latest_date() -> None:
    """build_manager_records строит записи только по актуальной выгрузке."""
    config = _config()
    config["manager_analytics"]["use_latest_report_date"] = True
    config["manager_analytics"]["rank_selection"] = {
        "product_groups": [],
        "products": [],
        "strategy_filter": "all",
    }
    df = _raw_df()
    df["Дата отчета"] = pd.to_datetime(["2026-01-01"] * 4 + ["2026-02-01"] * 4)
    records, snap = build_manager_records(df, config)
    assert snap is not None
    if not records.empty:
        report_col = config["columns"]["report_date"]
        assert all(str(d)[:10] == "2026-02-01" for d in records[report_col].astype(str))


def test_p80_thresholds_built() -> None:
    """Пороги P80 строятся из overall."""
    config = _config()
    records = build_lead_stage_records(_raw_df(), config)
    stats = build_all_statistics(records, config)
    thresholds = build_p80_thresholds(stats["overall"], config)
    assert not thresholds.empty
    assert "threshold_days" in thresholds.columns
