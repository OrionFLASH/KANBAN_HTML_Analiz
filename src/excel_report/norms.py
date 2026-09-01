"""Нормативы перцентилей (по ТБ и по всем ТБ)."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.aggregator import build_all_statistics
from src.percentile_stats import percentile_label
from src.settings import build_percentile_column_mapping, col

logger: logging.Logger = logging.getLogger("kanban.excel_v2.norms")


def build_norms_tables(
    records: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Возвращает (combined_norms, by_tb, overall).
    combined_norms — единый лист: колонка ТБ + строки «все тб».
    """
    stats: dict[str, pd.DataFrame] = build_all_statistics(records, config)
    by_tb: pd.DataFrame = stats.get("by_tb", pd.DataFrame()).copy()
    overall: pd.DataFrame = stats.get("overall", pd.DataFrame()).copy()

    tb_col: str = col(config, "tb")
    all_tb_label: str = str(config.get("output", {}).get("all_tb_label", "все тб"))

    frames: list[pd.DataFrame] = []
    if not by_tb.empty and tb_col in by_tb.columns:
        frames.append(by_tb.copy())

    if not overall.empty:
        overall_part: pd.DataFrame = overall.copy()
        if tb_col not in overall_part.columns:
            overall_part.insert(0, tb_col, all_tb_label)
        else:
            overall_part[tb_col] = all_tb_label
        frames.append(overall_part)

    combined: pd.DataFrame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    logger.info(
        "Нормативы: by_tb=%s строк, overall=%s, combined=%s",
        len(by_tb),
        len(overall),
        len(combined),
    )
    return combined, by_tb, overall


def build_p80_lookup_frames(
    by_tb: pd.DataFrame,
    overall: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Два DataFrame для merge: норматив P80 по ТБ и fallback по всем ТБ.
    Колонки: tb, product_group, product, current_status, p80.
    """
    p80_key: str = f"days_on_stage_{percentile_label(80.0)}_days"
    pg_col: str = col(config, "product_group")
    pr_col: str = col(config, "product")
    status_col: str = "current_status"
    tb_col: str = col(config, "tb")
    merge_keys: list[str] = ["product_group", "product", "current_status"]

    empty: pd.DataFrame = pd.DataFrame(columns=["tb", *merge_keys, "p80"])

    if by_tb.empty or p80_key not in by_tb.columns:
        tb_frame: pd.DataFrame = empty.copy()
    else:
        tb_frame = by_tb[[tb_col, pg_col, pr_col, status_col, p80_key]].copy()
        tb_frame.columns = ["tb", *merge_keys, "p80"]

    if overall.empty or p80_key not in overall.columns:
        all_frame: pd.DataFrame = empty.copy()
    else:
        all_frame = overall[[pg_col, pr_col, status_col, p80_key]].copy()
        all_frame.columns = merge_keys + ["p80"]
        all_frame.insert(0, "tb", "__ALL__")

    return tb_frame, all_frame


def build_p80_lookup(
    by_tb: pd.DataFrame,
    overall: pd.DataFrame,
    config: dict[str, Any],
) -> dict[tuple[str, ...], int | None]:
    """
    Ключ (tb, product_group, product, current_status) → порог P80 (дни).
    Для overall ключ tb = __ALL__. Оставлен для совместимости; предпочтительнее merge через build_p80_lookup_frames.
    """
    lookup: dict[tuple[str, ...], int | None] = {}
    tb_frame, all_frame = build_p80_lookup_frames(by_tb, overall, config)
    for frame in (tb_frame, all_frame):
        for row in frame.itertuples(index=False):
            threshold: int | None = int(row.p80) if pd.notna(row.p80) else None
            lookup[(str(row.tb), str(row.product_group), str(row.product), str(row.current_status))] = threshold
    return lookup


def norms_to_export_frame(combined: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Переименовывает колонки нормативов — те же правила, что в export_excel."""
    if combined.empty:
        return combined

    labels: dict[str, str] = config.get("output", {}).get("column_labels", {})
    product_group_col: str = col(config, "product_group")
    product_col: str = col(config, "product")
    tb_col: str = col(config, "tb")

    rename: dict[str, str] = {
        product_group_col: labels.get("product_group", "Группа продукта"),
        product_col: labels.get("product", "Продукт"),
        "current_status": labels.get("current_status", "Стадия работы с лидом"),
        "days_on_stage_min": labels.get("days_on_stage_min", "Мин срок дней"),
        "days_on_stage_max": labels.get("days_on_stage_max", "Макс срок дней"),
        "days_on_stage_count": labels.get("days_on_stage_count", "Число лидов"),
    }
    rename.update(build_percentile_column_mapping(config))

    renamed: pd.DataFrame = combined.rename(columns=rename)
    preferred: list[str] = [
        tb_col,
        rename.get(product_group_col, "Группа продукта"),
        rename.get(product_col, "Продукт"),
        rename.get("current_status", "Стадия работы с лидом"),
        rename.get("days_on_stage_min", "Мин срок дней"),
        rename.get("days_on_stage_max", "Макс срок дней"),
        rename.get("days_on_stage_count", "Число лидов"),
    ]
    for p in config.get("percentiles", [20, 50, 80]):
        label: str = percentile_label(float(p))
        for suffix, header in (
            ("days", f"P{int(p)} дней"),
            ("le_count", f"P{int(p)} лидов ≤"),
            ("gt_count", f"P{int(p)} лидов >"),
        ):
            src: str = f"days_on_stage_{label}_{suffix}"
            if src in rename:
                preferred.append(rename[src])
            elif header in renamed.columns:
                preferred.append(header)

    present: list[str] = [c for c in preferred if c in renamed.columns]
    extra: list[str] = [c for c in renamed.columns if c not in present]
    return renamed[present + extra].copy()
