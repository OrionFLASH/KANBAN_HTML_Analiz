"""Аналитика по менеджерам (КМ): превышения порога P80 по продукту и стадии."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.lead_tracker import build_lead_stage_records
from src.percentile_stats import percentile_label, to_integer_days
from src.progress import ProgressReporter
from src.settings import DEFAULT_RANK_PRODUCTS, col, group_only_product_label, is_group_only_analysis

logger: logging.Logger = logging.getLogger("kanban.manager_analytics")

# Режимы фильтра метки для отбора TOP КМ (согласованы с filters.strategy_label*)
STRATEGY_FILTER_ALL: str = "all"
STRATEGY_FILTER_STRATEGY: str = "strategy"
STRATEGY_FILTER_STRATEGY_2026: str = "strategy_2026"
STRATEGY_FILTER_NON_STRATEGY: str = "non_strategy"
VALID_STRATEGY_FILTERS: frozenset[str] = frozenset(
    {STRATEGY_FILTER_ALL, STRATEGY_FILTER_STRATEGY, STRATEGY_FILTER_STRATEGY_2026, STRATEGY_FILTER_NON_STRATEGY}
)


def rank_selection_config(config: dict[str, Any]) -> dict[str, Any]:
    """Параметры отбора TOP КМ из manager_analytics.rank_selection."""
    mgr_defaults: dict[str, Any] = config.get("manager_analytics", {})
    raw: dict[str, Any] = dict(mgr_defaults.get("rank_selection") or {})
    strategy: str = str(raw.get("strategy_filter", STRATEGY_FILTER_STRATEGY_2026))
    if strategy not in VALID_STRATEGY_FILTERS:
        strategy = STRATEGY_FILTER_STRATEGY_2026
    groups: list[str] = [str(g) for g in raw.get("product_groups") or [] if str(g).strip()]
    products_raw: list[str] = raw.get("products") if "products" in raw else list(DEFAULT_RANK_PRODUCTS)
    products: list[str] = [str(p) for p in products_raw or [] if str(p).strip()]

    efs_flag: int | None = None
    if "efs_flag" in raw and raw["efs_flag"] is not None:
        efs_flag = int(raw["efs_flag"])

    change_conditions: int | None = None
    if "change_conditions" in raw and raw["change_conditions"] is not None:
        change_conditions = int(raw["change_conditions"])

    return {
        "product_groups": groups,
        "products": products,
        "strategy_filter": strategy,
        "efs_flag": efs_flag,
        "change_conditions": change_conditions,
    }


def _optional_column(config: dict[str, Any], key: str) -> str | None:
    """Имя колонки Excel по ключу или None."""
    if key not in config.get("columns", {}):
        return None
    return col(config, key)


def manager_tb_km_key(tb: str, km: str) -> str:
    """Уникальный ключ менеджера: ТБ + КМ (исключает однофамильцев)."""
    return f"{str(tb)}|{str(km)}"


def filter_latest_report_snapshot(
    df: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """Оставляет только строки с максимальной «Дата отчета» (актуальная выгрузка)."""
    report_col: str = col(config, "report_date")
    if report_col not in df.columns or df.empty:
        return df, None
    dates: pd.Series = pd.to_datetime(df[report_col], errors="coerce")
    max_date: pd.Timestamp | None = dates.max()
    if max_date is None or pd.isna(max_date):
        return df, None
    mask: pd.Series = dates == max_date
    sliced: pd.DataFrame = df.loc[mask].copy()
    logger.info(
        "Менеджеры: актуальная выгрузка %s — %s → %s строк",
        max_date.date(),
        f"{len(df):,}",
        f"{len(sliced):,}",
    )
    return sliced, max_date


def build_manager_records(
    filtered_df: pd.DataFrame,
    config: dict[str, Any],
    progress: ProgressReporter | None = None,
) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """
    Записи лид×стадия для аналитики менеджеров.
    По умолчанию — только срез с max(Дата отчета).
    """
    mgr_cfg: dict[str, Any] = config.get("manager_analytics", {})
    use_latest: bool = bool(mgr_cfg.get("use_latest_report_date", True))
    snapshot: pd.Timestamp | None = None
    work_df: pd.DataFrame = filtered_df
    if use_latest:
        work_df, snapshot = filter_latest_report_snapshot(filtered_df, config)
    if work_df.empty:
        logger.warning("Менеджеры: нет строк после среза актуальной даты отчета")
        return pd.DataFrame(), snapshot
    records: pd.DataFrame = build_lead_stage_records(work_df, config, progress)
    return records, snapshot


def _label_column(config: dict[str, Any]) -> str | None:
    """Имя колонки «Метка» или None."""
    if "label" not in config.get("columns", {}):
        return None
    return col(config, "label")


def strategy_filter_mask(series: pd.Series, mode: str, config: dict[str, Any]) -> pd.Series:
    """Маска строк по режиму strategy_filter (метка лида)."""
    if mode == STRATEGY_FILTER_ALL:
        return pd.Series(True, index=series.index)
    text: pd.Series = series.fillna("").astype(str)
    case: bool = False
    filters_cfg: dict[str, Any] = config.get("filters", {})
    if mode == STRATEGY_FILTER_STRATEGY:
        flt: dict[str, Any] = filters_cfg.get("strategy_label") or {}
        token: str = str(flt.get("contains", "Стратегия"))
        case = bool(flt.get("case_sensitive", False))
        return text.str.contains(token, case=case, na=False)
    if mode == STRATEGY_FILTER_STRATEGY_2026:
        flt = filters_cfg.get("strategy_label_2026") or {}
        tokens: list[str] = [str(t) for t in flt.get("contains_all", ["Стратегия", "2026"]) if str(t)]
        case = bool(flt.get("case_sensitive", False))
        mask: pd.Series = pd.Series(True, index=series.index)
        for token in tokens:
            mask &= text.str.contains(token, case=case, na=False)
        return mask
    if mode == STRATEGY_FILTER_NON_STRATEGY:
        flt = filters_cfg.get("strategy_label") or {}
        token = str(flt.get("contains", "Стратегия"))
        case = bool(flt.get("case_sensitive", False))
        return ~text.str.contains(token, case=case, na=False)
    return pd.Series(True, index=series.index)


def apply_rank_selection(
    detail: pd.DataFrame,
    config: dict[str, Any],
    rank_sel: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Оставляет строки detail, попадающие в пул отбора TOP КМ:
    группы/продукты из rank_selection (пустой список = все) и фильтр метки.
    """
    if detail.empty:
        return detail

    sel: dict[str, Any] = rank_sel or rank_selection_config(config)
    pg_col: str = col(config, "product_group")
    prod_col: str = col(config, "product")
    result: pd.DataFrame = detail.copy()

    groups: list[str] = list(sel.get("product_groups") or [])
    if groups and pg_col in result.columns:
        allowed: set[str] = {str(g) for g in groups}
        result = result[result[pg_col].astype(str).isin(allowed)]

    products: list[str] = list(sel.get("products") or [])
    if products and prod_col in result.columns and not is_group_only_analysis(config):
        allowed_prod: set[str] = {str(p) for p in products}
        result = result[result[prod_col].astype(str).isin(allowed_prod)]

    label_name: str | None = _label_column(config)
    strategy_mode: str = str(sel.get("strategy_filter", STRATEGY_FILTER_ALL))
    if label_name and label_name in result.columns and strategy_mode != STRATEGY_FILTER_ALL:
        mask: pd.Series = strategy_filter_mask(result[label_name], strategy_mode, config)
        result = result[mask]

    efs_val: int | None = sel.get("efs_flag")
    efs_col: str | None = _optional_column(config, "efs_flag")
    if efs_val is not None and efs_col and efs_col in result.columns:
        result = result[pd.to_numeric(result[efs_col], errors="coerce") == efs_val]

    cc_val: int | None = sel.get("change_conditions")
    cc_col: str | None = _optional_column(config, "change_conditions")
    if cc_val is not None and cc_col and cc_col in result.columns:
        result = result[pd.to_numeric(result[cc_col], errors="coerce") == cc_val]

    return result.reset_index(drop=True)


def km_column(config: dict[str, Any]) -> str | None:
    """Имя колонки КМ в данных или None, если не задана в config."""
    if "km" not in config.get("columns", {}):
        return None
    return col(config, "km")


def is_manager_analytics_enabled(config: dict[str, Any]) -> bool:
    """Проверяет, включена ли аналитика менеджеров."""
    cfg: dict[str, Any] = config.get("manager_analytics", {})
    return bool(cfg.get("enabled", True))


def build_p80_thresholds(
    overall_stats: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """
    Порог P80 (дней) для каждой группы × продукт × стадия из общей сводки (без ТБ).
    """
    mgr_cfg: dict[str, Any] = config.get("manager_analytics", {})
    metric: str = str(mgr_cfg.get("metric", "days_on_stage"))
    percentile: float = float(mgr_cfg.get("percentile", 80))
    p_label: str = percentile_label(percentile)
    thresh_col: str = f"{metric}_{p_label}_days"

    if overall_stats.empty or thresh_col not in overall_stats.columns:
        return pd.DataFrame()

    pg_col: str = col(config, "product_group")
    prod_col: str = col(config, "product")
    key_cols: list[str] = [pg_col, "stage_key", "analysis_level"]
    if not is_group_only_analysis(config):
        key_cols.insert(1, prod_col)

    missing: list[str] = [c for c in key_cols if c not in overall_stats.columns]
    if missing:
        logger.warning("Пороги P80: нет колонок %s в overall", missing)
        return pd.DataFrame()

    thresholds: pd.DataFrame = overall_stats[key_cols + [thresh_col]].copy()
    thresholds = thresholds.rename(columns={thresh_col: "threshold_days"})
    thresholds = thresholds.dropna(subset=["threshold_days"])
    return thresholds.reset_index(drop=True)


def build_manager_exceedance_detail(
    records: pd.DataFrame,
    thresholds: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Строки лид×стадия с флагом превышения P80 и порогом."""
    km_name: str | None = km_column(config)
    if not km_name or km_name not in records.columns:
        return pd.DataFrame()

    mgr_cfg: dict[str, Any] = config.get("manager_analytics", {})
    metric: str = str(mgr_cfg.get("metric", "days_on_stage"))
    if metric not in records.columns or thresholds.empty:
        return pd.DataFrame()

    pg_col: str = col(config, "product_group")
    prod_col: str = col(config, "product")
    tb_col: str = col(config, "tb")
    lead_col: str = col(config, "lead_id")

    merge_keys: list[str] = [pg_col, "stage_key", "analysis_level"]
    if not is_group_only_analysis(config):
        merge_keys.insert(1, prod_col)

    merged: pd.DataFrame = records.merge(thresholds, on=merge_keys, how="left")
    days: pd.Series = pd.to_numeric(merged[metric], errors="coerce")
    thresh: pd.Series = pd.to_numeric(merged["threshold_days"], errors="coerce")
    merged["days_int"] = days
    merged["exceeded"] = days.notna() & thresh.notna() & (days > thresh)

    merged = merged[merged[km_name].notna() & (merged[km_name].astype(str).str.strip() != "")]
    if merged.empty:
        return pd.DataFrame()

    keep: list[str] = [
        tb_col,
        km_name,
        pg_col,
        prod_col if prod_col in merged.columns else None,
        "stage_key",
        "analysis_level",
        lead_col,
        "days_int",
        "threshold_days",
        "exceeded",
    ]
    label_name: str | None = _label_column(config)
    if label_name and label_name in merged.columns:
        keep.append(label_name)
    for opt_key in ("deal_id", "inn", "change_conditions", "efs_flag"):
        opt_col: str | None = _optional_column(config, opt_key)
        if opt_col and opt_col in merged.columns:
            keep.append(opt_col)
    keep = [c for c in keep if c and c in merged.columns]
    return merged[keep].reset_index(drop=True)


def aggregate_manager_counts(detail: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Сводки: по менеджеру×продукт×стадия и итого по менеджеру×ТБ.
    """
    if detail.empty:
        return pd.DataFrame(), pd.DataFrame()

    km_name: str = km_column(config) or "km"
    pg_col: str = col(config, "product_group")
    prod_col: str = col(config, "product")
    tb_col: str = col(config, "tb")
    lead_col: str = col(config, "lead_id")

    product_cols: list[str] = [tb_col, km_name, pg_col, "stage_key", "analysis_level"]
    if prod_col in detail.columns and not is_group_only_analysis(config):
        product_cols.insert(3, prod_col)

    exceeded: pd.DataFrame = detail.loc[detail["exceeded"]].copy()
    if exceeded.empty:
        by_product = pd.DataFrame(
            columns=product_cols
            + [
                "exceedance_count",
                "threshold_days",
                "max_days",
                "max_overshoot",
                "avg_overshoot",
            ]
        )
    else:
        by_product = (
            exceeded.groupby(product_cols, dropna=False)
            .agg(
                exceedance_count=(lead_col, "count"),
                threshold_days=("threshold_days", "max"),
                max_days=("days_int", "max"),
                avg_days=("days_int", "mean"),
            )
            .reset_index()
        )
        by_product["max_overshoot"] = (
            pd.to_numeric(by_product["max_days"], errors="coerce")
            - pd.to_numeric(by_product["threshold_days"], errors="coerce")
        ).clip(lower=0)
        by_product["avg_overshoot"] = (
            pd.to_numeric(by_product["avg_days"], errors="coerce")
            - pd.to_numeric(by_product["threshold_days"], errors="coerce")
        ).clip(lower=0)
        by_product = by_product.drop(columns=["avg_days"])

    manager_totals: pd.DataFrame = (
        detail.groupby([tb_col, km_name], dropna=False)
        .agg(
            total_leads=(lead_col, "nunique"),
            exceedance_count=("exceeded", "sum"),
        )
        .reset_index()
    )
    manager_totals["exceedance_count"] = manager_totals["exceedance_count"].astype(int)
    return by_product, manager_totals


def _hotspot_records(by_product: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Список зон превышения (продукт×стадия) с метриками отклонения."""
    if by_product.empty:
        return []
    km_name: str | None = km_column(config)
    pg_col: str = col(config, "product_group")
    prod_col: str = col(config, "product")
    tb_col: str = col(config, "tb")
    rename: dict[str, str] = {
        tb_col: "tb",
        pg_col: "product_group",
        prod_col: "product",
    }
    if km_name:
        rename[km_name] = "km"
    frame: pd.DataFrame = by_product.rename(columns=rename)
    for col_name in ("max_days", "max_overshoot", "avg_overshoot", "threshold_days"):
        if col_name in frame.columns:
            frame[col_name] = pd.to_numeric(frame[col_name], errors="coerce").round(1)
    if "exceedance_count" in frame.columns:
        frame["exceedance_count"] = frame["exceedance_count"].astype(int)
    return frame.to_dict(orient="records")


def attach_hotspots_to_top(
    top_tb: pd.DataFrame,
    by_product: pd.DataFrame,
    exceeded_detail: pd.DataFrame,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Топ менеджеров (ключ ТБ+КМ) с hotspots и списком зависших лидов/сделок."""
    if top_tb.empty:
        return []

    top_n_hotspots: int = int(config.get("manager_analytics", {}).get("top_hotspots_per_manager", 5))
    stuck_limit: int = int(config.get("manager_analytics", {}).get("top_stuck_items_per_hotspot", 15))
    km_name: str = km_column(config) or "km"
    tb_col: str = col(config, "tb")
    hotspots: list[dict[str, Any]] = _hotspot_records(by_product, config)
    stuck_by_hotspot: dict[tuple[str, ...], list[dict[str, Any]]] = _stuck_items_by_hotspot(
        exceeded_detail, config, stuck_limit
    )
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}

    pg_col: str = col(config, "product_group")
    prod_col: str = col(config, "product")
    group_only: bool = is_group_only_analysis(config)

    for item in hotspots:
        tb_km: tuple[str, str] = (str(item.get("tb", "")), str(item.get("km", "")))
        by_key.setdefault(tb_km, []).append(item)
        hs_key: tuple[str, ...] = (
            str(item.get("tb", "")),
            str(item.get("km", "")),
            str(item.get("product_group", "")),
            str(item.get("product", "")) if not group_only else "—",
            str(item.get("stage_key", "")),
        )
        item["stuck_items"] = stuck_by_hotspot.get(hs_key, [])

    for items in by_key.values():
        items.sort(
            key=lambda row: (
                -int(row.get("exceedance_count") or 0),
                -float(row.get("max_overshoot") or 0),
                str(row.get("stage_key", "")),
            )
        )

    top_records: list[dict[str, Any]] = _frame_to_records(top_tb, config)
    for row in top_records:
        key = (str(row.get("tb", "")), str(row.get("km", "")))
        row["km_tb_key"] = manager_tb_km_key(row.get("tb", ""), row.get("km", ""))
        row["hotspots"] = by_key.get(key, [])[:top_n_hotspots]
    return top_records


def _stuck_items_by_hotspot(
    exceeded: pd.DataFrame,
    config: dict[str, Any],
    limit_per_hotspot: int,
) -> dict[tuple[str, ...], list[dict[str, Any]]]:
    """Группирует превышения по зоне (ТБ×КМ×продукт×стадия) с ID лидов/сделок и ИНН."""
    if exceeded.empty:
        return {}

    km_name: str = km_column(config) or "km"
    tb_col: str = col(config, "tb")
    pg_col: str = col(config, "product_group")
    prod_col: str = col(config, "product")
    lead_col: str = col(config, "lead_id")
    deal_col: str | None = _optional_column(config, "deal_id")
    inn_col: str | None = _optional_column(config, "inn")
    group_only: bool = is_group_only_analysis(config)

    result: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for _, row in exceeded.iterrows():
        product_val: str = str(row[prod_col]) if prod_col in exceeded.columns and not group_only else "—"
        hs_key: tuple[str, ...] = (
            str(row[tb_col]),
            str(row[km_name]),
            str(row[pg_col]),
            product_val,
            str(row["stage_key"]),
        )
        days: float = float(row.get("days_int") or 0)
        thresh: float = float(row.get("threshold_days") or 0)
        item: dict[str, Any] = {
            "lead_id": str(row[lead_col]),
            "deal_id": str(row[deal_col]) if deal_col and deal_col in exceeded.columns and pd.notna(row.get(deal_col)) else None,
            "inn": str(row[inn_col]) if inn_col and inn_col in exceeded.columns and pd.notna(row.get(inn_col)) else None,
            "stage_key": str(row["stage_key"]),
            "days_int": round(days, 1),
            "threshold_days": round(thresh, 1),
            "overshoot": round(max(0.0, days - thresh), 1),
        }
        bucket: list[dict[str, Any]] = result.setdefault(hs_key, [])
        if len(bucket) < limit_per_hotspot:
            bucket.append(item)

    for items in result.values():
        items.sort(key=lambda x: (-float(x.get("overshoot") or 0), str(x.get("lead_id", ""))))
    return result


def format_hotspots_excel_summary(hotspots: list[dict[str, Any]], config: dict[str, Any]) -> str:
    """Текстовое резюме топ-зон для колонки Excel."""
    if not hotspots:
        return "—"
    group_only: bool = is_group_only_analysis(config)
    parts: list[str] = []
    for idx, spot in enumerate(hotspots, start=1):
        if group_only:
            segment: str = str(spot.get("product_group", "—"))
        else:
            segment = f"{spot.get('product_group', '—')} · {spot.get('product', '—')}"
        stage: str = str(spot.get("stage_key", "—"))
        count: int = int(spot.get("exceedance_count") or 0)
        overshoot: float = float(spot.get("max_overshoot") or 0)
        threshold: float = float(spot.get("threshold_days") or 0)
        max_days: float = float(spot.get("max_days") or 0)
        parts.append(
            f"{idx}) {segment} / {stage}: {count} сд., "
            f"макс {max_days:.0f} дн. (P80={threshold:.0f}, +{overshoot:.0f})"
        )
    return " | ".join(parts)


def build_km_violation_charts(
    detail: pd.DataFrame,
    manager_totals: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Компактные агрегаты для bar-графиков «КМ с нарушениями P80» в HTML.
    by_tb — уникальные КМ с превышением по каждому ТБ;
    facts — факты (tb×km×группа×продукт×стадия) для детализации и фильтров UI.
    """
    tb_col: str = col(config, "tb")
    km_name: str = km_column(config) or "km"
    pg_col: str = col(config, "product_group")
    prod_col: str = col(config, "product")
    lead_col: str = col(config, "lead_id")
    group_only: bool = is_group_only_analysis(config)

    by_tb: list[dict[str, Any]] = []
    if not manager_totals.empty and tb_col in manager_totals.columns:
        for tb_value in sorted(manager_totals[tb_col].dropna().unique(), key=str):
            bucket: pd.DataFrame = manager_totals.loc[manager_totals[tb_col] == tb_value]
            with_viol: pd.DataFrame = bucket.loc[bucket["exceedance_count"] > 0]
            by_tb.append(
                {
                    "tb": str(tb_value),
                    "km_with_violations": int(len(with_viol)),
                    "km_total": int(len(bucket)),
                    "violation_deals": int(with_viol["exceedance_count"].sum()),
                }
            )

    facts: list[dict[str, Any]] = []
    if not detail.empty and "exceeded" in detail.columns:
        exceeded: pd.DataFrame = detail.loc[detail["exceeded"]].copy()
        if not exceeded.empty and km_name in exceeded.columns:
            group_cols: list[str] = [tb_col, km_name, pg_col, "stage_key"]
            if not group_only and prod_col in exceeded.columns:
                group_cols.insert(3, prod_col)

            grouped: pd.DataFrame = (
                exceeded.groupby(group_cols, dropna=False)
                .agg(deals=(lead_col, "count"))
                .reset_index()
            )
            for _, row in grouped.iterrows():
                fact: dict[str, Any] = {
                    "tb": str(row[tb_col]),
                    "km": str(row[km_name]),
                    "product_group": str(row[pg_col]),
                    "stage_key": str(row["stage_key"]),
                    "deals": int(row["deals"]),
                }
                if not group_only and prod_col in grouped.columns:
                    fact["product"] = str(row[prod_col])
                facts.append(fact)

    return {"by_tb": by_tb, "facts": facts}


def top_managers_per_tb(manager_totals: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Топ-N менеджеров по числу превышений P80 в каждом ТБ."""
    if manager_totals.empty:
        return pd.DataFrame()

    top_n: int = int(config.get("manager_analytics", {}).get("top_managers_per_tb", 3))
    tb_col: str = col(config, "tb")
    km_name: str = km_column(config) or "km"

    rows: list[pd.DataFrame] = []
    for tb_value in sorted(manager_totals[tb_col].dropna().unique(), key=str):
        bucket: pd.DataFrame = manager_totals.loc[manager_totals[tb_col] == tb_value].copy()
        bucket = bucket.loc[bucket["exceedance_count"] > 0]
        if bucket.empty:
            continue
        bucket = bucket.sort_values(
            ["exceedance_count", "total_leads", km_name],
            ascending=[False, False, True],
        ).head(top_n)
        bucket["rank"] = range(1, len(bucket) + 1)
        rows.append(bucket)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def _frame_to_records(df: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    """DataFrame → список dict для JSON (агрегаты без lead_id)."""
    if df.empty:
        return []
    km_name: str | None = km_column(config)
    pg_col: str = col(config, "product_group")
    prod_col: str = col(config, "product")
    tb_col: str = col(config, "tb")
    rename: dict[str, str] = {
        tb_col: "tb",
        pg_col: "product_group",
        prod_col: "product",
    }
    if km_name:
        rename[km_name] = "km"
    out: pd.DataFrame = df.rename(columns=rename)
    return out.to_dict(orient="records")


def lead_records_to_json(detail: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Все строки лид×стадия для UI-фильтрации (полный набор)."""
    if detail.empty:
        return []
    km_name: str | None = km_column(config)
    pg_col: str = col(config, "product_group")
    prod_col: str = col(config, "product")
    tb_col: str = col(config, "tb")
    lead_col: str = col(config, "lead_id")
    label_name: str | None = _label_column(config)
    rename: dict[str, str] = {
        tb_col: "tb",
        pg_col: "product_group",
        prod_col: "product",
        lead_col: "lead_id",
    }
    if km_name:
        rename[km_name] = "km"
    if label_name and label_name in detail.columns:
        rename[label_name] = "label"
    report_col: str | None = _optional_column(config, "report_date")
    if report_col and report_col in detail.columns:
        rename[report_col] = "report_date"
    for opt_key, json_key in (
        ("deal_id", "deal_id"),
        ("inn", "inn"),
        ("change_conditions", "change_conditions"),
        ("efs_flag", "efs_flag"),
    ):
        opt_col: str | None = _optional_column(config, opt_key)
        if opt_col and opt_col in detail.columns:
            rename[opt_col] = json_key
    out: pd.DataFrame = detail.rename(columns=rename)
    records: list[dict[str, Any]] = out.to_dict(orient="records")
    for row in records:
        row["exceeded"] = bool(row.get("exceeded"))
        row["km_tb_key"] = manager_tb_km_key(row.get("tb", ""), row.get("km", ""))
        if row.get("days_int") is not None:
            row["days_int"] = round(float(row["days_int"]), 1)
        if row.get("threshold_days") is not None:
            row["threshold_days"] = round(float(row["threshold_days"]), 1)
        for flag_key in ("change_conditions", "efs_flag"):
            if row.get(flag_key) is not None and row.get(flag_key) == row.get(flag_key):
                try:
                    row[flag_key] = int(float(row[flag_key]))
                except (TypeError, ValueError):
                    pass
        if row.get("report_date") is not None:
            row["report_date"] = str(row["report_date"])[:10]
    return records


def exceedances_to_json(detail: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Только строки с превышением P80 — для JSON и детализации зависших лидов/сделок."""
    if detail.empty or "exceeded" not in detail.columns:
        return []
    exceeded: pd.DataFrame = detail.loc[detail["exceeded"]].copy()
    if exceeded.empty:
        return []
    records: list[dict[str, Any]] = lead_records_to_json(exceeded, config)
    for row in records:
        thresh: float = float(row.get("threshold_days") or 0)
        days: float = float(row.get("days_int") or 0)
        row["overshoot"] = round(max(0.0, days - thresh), 1)
    return records


def build_manager_dimensions(detail: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """Справочник групп и продуктов в данных менеджеров."""
    if detail.empty:
        return {"product_groups": [], "products": []}
    pg_col: str = col(config, "product_group")
    prod_col: str = col(config, "product")
    groups: list[str] = sorted(detail[pg_col].dropna().astype(str).unique(), key=str)
    products: list[str] = []
    if prod_col in detail.columns and not is_group_only_analysis(config):
        products = sorted(detail[prod_col].dropna().astype(str).unique(), key=str)
    return {"product_groups": groups, "products": products}


def build_top_by_tb_grouped(top_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Топ-N нарушителей по каждому ТБ — для UI."""
    by_tb: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for row in top_records:
        tb: str = str(row.get("tb", ""))
        if tb not in by_tb:
            by_tb[tb] = []
            order.append(tb)
        by_tb[tb].append(row)
    return [{"tb": tb, "managers": by_tb[tb]} for tb in order]


def build_manager_analytics(
    records: pd.DataFrame,
    stats: dict[str, pd.DataFrame],
    config: dict[str, Any],
    snapshot_date: pd.Timestamp | None = None,
) -> dict[str, Any] | None:
    """Полный payload аналитики менеджеров или None, если КМ недоступна."""
    if not is_manager_analytics_enabled(config):
        logger.info("Аналитика менеджеров отключена в config")
        return None

    km_name: str | None = km_column(config)
    if not km_name or km_name not in records.columns:
        logger.warning("Колонка КМ (%s) не найдена в lead_stage_records — аналитика менеджеров пропущена", km_name)
        return None

    mgr_cfg: dict[str, Any] = config.get("manager_analytics", {})
    metric: str = str(mgr_cfg.get("metric", "days_on_stage"))
    percentile: float = float(mgr_cfg.get("percentile", 80))

    overall: pd.DataFrame = stats.get("overall", pd.DataFrame())
    thresholds: pd.DataFrame = build_p80_thresholds(overall, config)
    if thresholds.empty:
        logger.warning("Не удалось построить пороги P80 для аналитики менеджеров")
        return None

    detail: pd.DataFrame = build_manager_exceedance_detail(records, thresholds, config)
    by_product, manager_totals = aggregate_manager_counts(detail, config)

    rank_sel: dict[str, Any] = rank_selection_config(config)
    ranked_detail: pd.DataFrame = apply_rank_selection(detail, config, rank_sel)
    ranked_exceeded: pd.DataFrame = ranked_detail.loc[ranked_detail["exceeded"]].copy()
    ranked_by_product, ranked_totals = aggregate_manager_counts(ranked_detail, config)
    top_tb: pd.DataFrame = top_managers_per_tb(ranked_totals, config)
    top_records: list[dict[str, Any]] = attach_hotspots_to_top(
        top_tb, ranked_by_product, ranked_exceeded, config
    )
    charts: dict[str, Any] = build_km_violation_charts(detail, manager_totals, config)
    dimensions: dict[str, Any] = build_manager_dimensions(detail, config)
    lead_records: list[dict[str, Any]] = lead_records_to_json(detail, config)
    exceedances: list[dict[str, Any]] = exceedances_to_json(detail, config)

    logger.info(
        "Менеджеры: превышений %d, топ-записей %d (отбор: %s), порогов P80 %d, records %d, exceedances %d",
        int(detail["exceeded"].sum()) if not detail.empty else 0,
        len(top_tb),
        rank_sel.get("strategy_filter"),
        len(thresholds),
        len(lead_records),
        len(exceedances),
    )

    return {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "metric": metric,
            "percentile": percentile,
            "percentile_label": percentile_label(percentile),
            "threshold_scope": str(mgr_cfg.get("threshold_scope", "overall")),
            "top_managers_per_tb": int(mgr_cfg.get("top_managers_per_tb", 3)),
            "top_stuck_items_per_hotspot": int(mgr_cfg.get("top_stuck_items_per_hotspot", 15)),
            "km_column": km_name,
            "rank_selection": rank_sel,
            "manager_key": "km_tb_key",
            "use_latest_report_date": bool(mgr_cfg.get("use_latest_report_date", True)),
            "report_date_snapshot": (
                snapshot_date.date().isoformat() if snapshot_date is not None and not pd.isna(snapshot_date) else None
            ),
            "description": (
                "Превышение P80: срок лида на стадии строго больше порога P80 "
                "для той же группы, продукта и стадии (порог из общей сводки без ТБ). "
                "TOP КМ — по rank_selection (ТБ+КМ); records — все лиды; exceedances — только отклонения."
            ),
        },
        "dimensions": dimensions,
        "records": lead_records,
        "exceedances": exceedances,
        "top_by_tb": top_records,
        "top_by_tb_grouped": build_top_by_tb_grouped(top_records),
        "detail_by_product": _frame_to_records(by_product, config),
        "manager_totals": _frame_to_records(manager_totals, config),
        "charts": charts,
        "thresholds_count": int(len(thresholds)),
    }


def manager_analytics_to_excel_frame(payload: dict[str, Any], config: dict[str, Any]) -> pd.DataFrame:
    """Таблица для листа Excel: топ менеджеров по ТБ с резюме зон превышения."""
    rows: list[dict[str, Any]] = payload.get("top_by_tb") or []
    if not rows:
        return pd.DataFrame()

    km_label: str = config.get("output", {}).get("column_labels", {}).get("km", "КМ")
    tb_label: str = config.get("output", {}).get("column_labels", {}).get("tb", "ТБ")

    enriched: list[dict[str, Any]] = []
    for row in rows:
        copy_row: dict[str, Any] = dict(row)
        copy_row["hotspots_summary"] = format_hotspots_excel_summary(row.get("hotspots") or [], config)
        enriched.append(copy_row)

    frame: pd.DataFrame = pd.DataFrame(enriched)
    rename: dict[str, str] = {
        "tb": tb_label,
        "rank": "Место",
        "km": km_label,
        "exceedance_count": "Превышений P80",
        "total_leads": "Лидов (уник.)",
        "hotspots_summary": "Топ зон превышения (продукт · стадия)",
    }
    cols: list[str] = [
        "tb",
        "rank",
        "km",
        "exceedance_count",
        "total_leads",
        "hotspots_summary",
    ]
    cols = [c for c in cols if c in frame.columns]
    return frame[cols].rename(columns=rename)


def export_manager_json(payload: dict[str, Any], output_path: Path, config: dict[str, Any]) -> None:
    """Сохраняет JSON менеджеров только в output_path (с timestamp)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    compact: bool = bool(
        config.get("dashboard", {}).get("html_json", {}).get("compact", True)
    )
    dump_kw: dict[str, Any] = (
        {"ensure_ascii": False, "separators": (",", ":"), "default": str}
        if compact
        else {"ensure_ascii": False, "indent": 2, "default": str}
    )
    export_payload: dict[str, Any] = payload
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(export_payload, fh, **dump_kw)

    logger.info("JSON менеджеров: %s (%d KB)", output_path.name, output_path.stat().st_size // 1024)
