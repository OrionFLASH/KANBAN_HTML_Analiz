"""Аналитика по менеджерам (КМ): превышения порога P80 по продукту и стадии."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.percentile_stats import percentile_label, to_integer_days
from src.settings import col, group_only_product_label, is_group_only_analysis

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
    raw: dict[str, Any] = dict(config.get("manager_analytics", {}).get("rank_selection") or {})
    strategy: str = str(raw.get("strategy_filter", STRATEGY_FILTER_ALL))
    if strategy not in VALID_STRATEGY_FILTERS:
        strategy = STRATEGY_FILTER_ALL
    groups: list[str] = [str(g) for g in raw.get("product_groups") or [] if str(g).strip()]
    products: list[str] = [str(p) for p in raw.get("products") or [] if str(p).strip()]
    return {
        "product_groups": groups,
        "products": products,
        "strategy_filter": strategy,
    }


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
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Топ менеджеров с вложенным списком ключевых зон превышения."""
    if top_tb.empty:
        return []

    top_n_hotspots: int = int(config.get("manager_analytics", {}).get("top_hotspots_per_manager", 5))
    km_name: str = km_column(config) or "km"
    tb_col: str = col(config, "tb")
    hotspots: list[dict[str, Any]] = _hotspot_records(by_product, config)
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for item in hotspots:
        key: tuple[str, str] = (str(item.get("tb", "")), str(item.get("km", "")))
        by_key.setdefault(key, []).append(item)

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
        row["hotspots"] = by_key.get(key, [])[:top_n_hotspots]
    return top_records


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
    out: pd.DataFrame = detail.rename(columns=rename)
    records: list[dict[str, Any]] = out.to_dict(orient="records")
    for row in records:
        row["exceeded"] = bool(row.get("exceeded"))
        if row.get("days_int") is not None:
            row["days_int"] = round(float(row["days_int"]), 1)
        if row.get("threshold_days") is not None:
            row["threshold_days"] = round(float(row["threshold_days"]), 1)
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


def build_manager_analytics(
    records: pd.DataFrame,
    stats: dict[str, pd.DataFrame],
    config: dict[str, Any],
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
    ranked_by_product, ranked_totals = aggregate_manager_counts(ranked_detail, config)
    top_tb: pd.DataFrame = top_managers_per_tb(ranked_totals, config)
    top_records: list[dict[str, Any]] = attach_hotspots_to_top(top_tb, ranked_by_product, config)
    charts: dict[str, Any] = build_km_violation_charts(detail, manager_totals, config)
    dimensions: dict[str, Any] = build_manager_dimensions(detail, config)
    lead_records: list[dict[str, Any]] = lead_records_to_json(detail, config)

    logger.info(
        "Менеджеры: превышений %d, топ-записей %d (отбор: %s), порогов P80 %d, lead records %d",
        int(detail["exceeded"].sum()) if not detail.empty else 0,
        len(top_tb),
        rank_sel.get("strategy_filter"),
        len(thresholds),
        len(lead_records),
    )

    return {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "metric": metric,
            "percentile": percentile,
            "percentile_label": percentile_label(percentile),
            "threshold_scope": str(mgr_cfg.get("threshold_scope", "overall")),
            "top_managers_per_tb": int(mgr_cfg.get("top_managers_per_tb", 3)),
            "km_column": km_name,
            "rank_selection": rank_sel,
            "description": (
                "Превышение P80: срок лида на стадии строго больше порога P80 "
                "для той же группы, продукта и стадии (порог из общей сводки без ТБ). "
                "TOP КМ — по rank_selection; полные данные в records для UI-фильтров."
            ),
        },
        "dimensions": dimensions,
        "records": lead_records,
        "top_by_tb": top_records,
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
