"""Аналитика по менеджерам (КМ): превышения порога P80 по продукту и стадии."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.percentile_stats import percentile_label, to_integer_days
from src.settings import col, group_only_product_label, is_group_only_analysis

logger: logging.Logger = logging.getLogger("kanban.manager_analytics")


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
        by_product = pd.DataFrame(columns=product_cols + ["exceedance_count", "threshold_days"])
    else:
        by_product = (
            exceeded.groupby(product_cols, dropna=False)
            .agg(
                exceedance_count=(lead_col, "count"),
                threshold_days=("threshold_days", "max"),
            )
            .reset_index()
        )

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
    """DataFrame → список dict для JSON."""
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
    top_tb: pd.DataFrame = top_managers_per_tb(manager_totals, config)

    logger.info(
        "Менеджеры: превышений %d, топ-записей %d, порогов P80 %d",
        int(detail["exceeded"].sum()) if not detail.empty else 0,
        len(top_tb),
        len(thresholds),
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
            "description": (
                "Превышение P80: срок лида на стадии строго больше порога P80 "
                "для той же группы, продукта и стадии (порог из общей сводки без ТБ)."
            ),
        },
        "top_by_tb": _frame_to_records(top_tb, config),
        "detail_by_product": _frame_to_records(by_product, config),
        "manager_totals": _frame_to_records(manager_totals, config),
        "thresholds_count": int(len(thresholds)),
    }


def manager_analytics_to_excel_frame(payload: dict[str, Any], config: dict[str, Any]) -> pd.DataFrame:
    """Таблица для листа Excel: топ менеджеров по ТБ."""
    rows: list[dict[str, Any]] = payload.get("top_by_tb") or []
    if not rows:
        return pd.DataFrame()

    km_label: str = config.get("output", {}).get("column_labels", {}).get("km", "КМ")
    tb_label: str = config.get("output", {}).get("column_labels", {}).get("tb", "ТБ")

    frame: pd.DataFrame = pd.DataFrame(rows)
    rename: dict[str, str] = {
        "tb": tb_label,
        "rank": "Место",
        "km": km_label,
        "exceedance_count": "Превышений P80",
        "total_leads": "Лидов (уник.)",
    }
    cols: list[str] = ["tb", "rank", "km", "exceedance_count", "total_leads"]
    cols = [c for c in cols if c in frame.columns]
    return frame[cols].rename(columns=rename)


def export_manager_json(payload: dict[str, Any], output_path: Path, config: dict[str, Any]) -> None:
    """Сохраняет отдельный JSON менеджеров и копию для HTML."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)

    prefix: str = config.get("output", {}).get("report_prefix", "kanban_report")
    latest_path: Path = output_path.parent / f"{prefix}_managers_latest.json"
    shutil.copy2(output_path, latest_path)

    html_data_dir: Path = output_path.parent.parent / "HTML" / "data"
    html_data_dir.mkdir(parents=True, exist_ok=True)
    html_latest: Path = html_data_dir / "kanban_managers_latest.json"
    shutil.copy2(output_path, html_latest)

    logger.info("JSON менеджеров: %s → %s", output_path.name, html_latest)
