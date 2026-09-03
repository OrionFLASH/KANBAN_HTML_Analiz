# -*- coding: utf-8 -*-
"""Воронка отсечения: фильтры (строки/лиды) и свод по выбросам для листа «Статистика»."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.outlier_clipping import (
    AUDIT_AFTER,
    AUDIT_BEFORE,
    AUDIT_CLIPPED,
    AUDIT_RULE_PREFIX,
    audit_column_keys,
    enabled_rules,
    outlier_clipping_config,
)
from src.settings import col

logger: logging.Logger = logging.getLogger("kanban.filter_funnel")

# Внутренние ключи аудита входных фильтров на строке нормативов
FILTER_BEFORE: str = "filter_before"
FILTER_AFTER: str = "filter_after"
FILTER_DROPPED_PREFIX: str = "filter_dropped_"


def _unique_leads(df: pd.DataFrame, config: dict[str, Any]) -> int:
    """Число уникальных ID ПрПр в кадре (0, если колонки нет)."""
    if df is None or df.empty:
        return 0
    lead_col: str = col(config, "lead_id")
    if lead_col not in df.columns:
        return 0
    series: pd.Series = df[lead_col].dropna().astype(str).str.strip()
    series = series[series != ""]
    return int(series.nunique())


def enabled_pipeline_filter_names(config: dict[str, Any]) -> list[str]:
    """
    Имена включённых фильтров в порядке применения pipeline v2:
    include (порядок config) → exclude (как enabled_terminal_exclusion_names, sorted).
    """
    from src.filters import enabled_terminal_exclusion_names, is_exclude_filter

    filters_cfg: dict[str, Any] = config.get("filters") or {}
    inclusion: list[str] = []
    for name, flt in filters_cfg.items():
        if not isinstance(flt, dict) or not bool(flt.get("enabled", False)):
            continue
        if is_exclude_filter(flt):
            continue
        inclusion.append(name)
    return inclusion + enabled_terminal_exclusion_names(config)


def filter_audit_column_keys(config: dict[str, Any]) -> list[str]:
    """Порядок колонок аудита входных фильтров для экспорта на «Нормативы»."""
    names: list[str] = enabled_pipeline_filter_names(config)
    if not names:
        return []
    keys: list[str] = [FILTER_BEFORE]
    for name in names:
        keys.append(f"{FILTER_DROPPED_PREFIX}{name}")
    keys.append(FILTER_AFTER)
    return keys


def build_filter_audit_mapping(config: dict[str, Any]) -> dict[str, str]:
    """Mapping внутренних колонок аудита фильтров → заголовки Excel."""
    labels: dict[str, str] = dict(config.get("output", {}).get("column_labels") or {})
    mapping: dict[str, str] = {}
    for key in filter_audit_column_keys(config):
        if key == FILTER_BEFORE:
            mapping[key] = labels.get(key, "До отсечения")
        elif key == FILTER_AFTER:
            mapping[key] = labels.get(key, "После фильтров")
        elif key.startswith(FILTER_DROPPED_PREFIX):
            fname: str = key[len(FILTER_DROPPED_PREFIX) :]
            mapping[key] = labels.get(key, f"Отсечено: {fname}")
        else:
            mapping[key] = labels.get(key, key)
    return mapping


def _is_filter_audit_column(name: str) -> bool:
    """True — колонка аудита входных фильтров."""
    return name in {FILTER_BEFORE, FILTER_AFTER} or name.startswith(FILTER_DROPPED_PREFIX)


def norms_group_columns(config: dict[str, Any], frame: pd.DataFrame) -> list[str]:
    """
    Ключи группы для стыковки с листом «Нормативы»:
    ТБ + группа продукта + продукт + current_status.
    """
    tb_col: str = col(config, "tb")
    pg_col: str = col(config, "product_group")
    pr_col: str = col(config, "product")
    status_raw: str = col(config, "current_status")
    candidates: list[str] = []
    for name in (tb_col, pg_col, pr_col):
        if name in frame.columns:
            candidates.append(name)
    if "current_status" in frame.columns:
        candidates.append("current_status")
    elif status_raw in frame.columns:
        candidates.append(status_raw)
    return candidates


def _prepare_group_frame(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Копия с полем current_status для merge с нормативами."""
    if df is None or df.empty:
        return pd.DataFrame()
    work: pd.DataFrame = df
    status_raw: str = col(config, "current_status")
    if "current_status" not in work.columns and status_raw in work.columns:
        work = work.copy()
        work["current_status"] = work[status_raw]
    return work


def count_leads_by_norm_group(
    df: pd.DataFrame,
    config: dict[str, Any],
    *,
    include_tb: bool = True,
) -> pd.DataFrame:
    """Уникальные лиды по группе нормативов (опционально без ТБ)."""
    work: pd.DataFrame = _prepare_group_frame(df, config)
    if work.empty:
        return pd.DataFrame()

    lead_col: str = col(config, "lead_id")
    if lead_col not in work.columns:
        return pd.DataFrame()

    tb_col: str = col(config, "tb")
    pg_col: str = col(config, "product_group")
    pr_col: str = col(config, "product")
    keys: list[str] = []
    if include_tb and tb_col in work.columns:
        keys.append(tb_col)
    for name in (pg_col, pr_col, "current_status"):
        if name in work.columns:
            keys.append(name)
    if not keys:
        return pd.DataFrame()

    cleaned: pd.Series = work[lead_col].dropna().astype(str).str.strip()
    mask: pd.Series = cleaned != ""
    subset: pd.DataFrame = work.loc[mask, keys].copy()
    subset["_lead"] = cleaned.loc[mask].values
    grouped: pd.DataFrame = (
        subset.groupby(keys, dropna=False, observed=True, sort=False)["_lead"]
        .nunique()
        .reset_index(name="_n_leads")
    )
    return grouped


class GroupFilterAuditor:
    """Накопитель отсечений входных фильтров по группам нормативов (уник. лиды)."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config: dict[str, Any] = config
        self.filter_order: list[str] = []
        self._before_by_tb: pd.DataFrame | None = None
        self._after_by_tb: pd.DataFrame | None = None
        self._dropped_by_tb: dict[str, pd.DataFrame] = {}
        self._before_overall: pd.DataFrame | None = None
        self._after_overall: pd.DataFrame | None = None
        self._dropped_overall: dict[str, pd.DataFrame] = {}

    def record_baseline(self, df: pd.DataFrame) -> None:
        """Фиксирует «до фильтров» (обычно сразу после загрузки)."""
        self._before_by_tb = count_leads_by_norm_group(df, self.config, include_tb=True)
        self._before_overall = count_leads_by_norm_group(df, self.config, include_tb=False)
        self._after_by_tb = self._before_by_tb
        self._after_overall = self._before_overall

    def record_filter_step(
        self,
        filter_name: str,
        before_df: pd.DataFrame,
        after_df: pd.DataFrame,
    ) -> None:
        """Учитывает отсечение одного фильтра по группам."""
        name: str = str(filter_name).strip()
        if not name:
            return
        if name not in self.filter_order:
            self.filter_order.append(name)

        before_tb: pd.DataFrame = count_leads_by_norm_group(before_df, self.config, include_tb=True)
        after_tb: pd.DataFrame = count_leads_by_norm_group(after_df, self.config, include_tb=True)
        before_all: pd.DataFrame = count_leads_by_norm_group(before_df, self.config, include_tb=False)
        after_all: pd.DataFrame = count_leads_by_norm_group(after_df, self.config, include_tb=False)

        self._dropped_by_tb[name] = self._dropped_counts(before_tb, after_tb)
        self._dropped_overall[name] = self._dropped_counts(before_all, after_all)
        self._after_by_tb = after_tb
        self._after_overall = after_all

    @staticmethod
    def _dropped_counts(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
        """before − after по ключам группы (отрицательные → 0)."""
        if before.empty and after.empty:
            return pd.DataFrame()
        if before.empty:
            keys: list[str] = [c for c in after.columns if c != "_n_leads"]
            out: pd.DataFrame = after[keys].copy()
            out["_n_leads"] = 0
            return out
        keys = [c for c in before.columns if c != "_n_leads"]
        merged: pd.DataFrame = before.merge(after, on=keys, how="outer", suffixes=("_b", "_a"))
        b: pd.Series = pd.to_numeric(merged.get("_n_leads_b"), errors="coerce").fillna(0)
        a: pd.Series = pd.to_numeric(merged.get("_n_leads_a"), errors="coerce").fillna(0)
        merged["_n_leads"] = (b - a).clip(lower=0).astype(int)
        return merged[keys + ["_n_leads"]]

    def to_norms_frames(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Кадры для merge в нормативы: (by_tb, overall).
        Колонки: ключи группы + filter_before/after + filter_dropped_*.
        """
        by_tb: pd.DataFrame = self._assemble_frame(
            before=self._before_by_tb,
            after=self._after_by_tb,
            dropped=self._dropped_by_tb,
        )
        overall: pd.DataFrame = self._assemble_frame(
            before=self._before_overall,
            after=self._after_overall,
            dropped=self._dropped_overall,
        )
        return by_tb, overall

    def _assemble_frame(
        self,
        *,
        before: pd.DataFrame | None,
        after: pd.DataFrame | None,
        dropped: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        if before is None or before.empty:
            seed: pd.DataFrame = after if after is not None and not after.empty else pd.DataFrame()
            if seed.empty:
                for part in dropped.values():
                    if part is not None and not part.empty:
                        seed = part
                        break
            if seed.empty:
                return pd.DataFrame()
            keys: list[str] = [c for c in seed.columns if c != "_n_leads"]
            result: pd.DataFrame = seed[keys].drop_duplicates().copy()
            result[FILTER_BEFORE] = 0
        else:
            keys = [c for c in before.columns if c != "_n_leads"]
            result = before.rename(columns={"_n_leads": FILTER_BEFORE})

        if after is not None and not after.empty:
            result = result.merge(
                after.rename(columns={"_n_leads": FILTER_AFTER}),
                on=keys,
                how="outer",
            )
        else:
            result[FILTER_AFTER] = result.get(FILTER_BEFORE, 0)

        for name in self.filter_order:
            col_name: str = f"{FILTER_DROPPED_PREFIX}{name}"
            part: pd.DataFrame = dropped.get(name, pd.DataFrame())
            if part is None or part.empty:
                result[col_name] = 0
                continue
            result = result.merge(
                part.rename(columns={"_n_leads": col_name}),
                on=keys,
                how="outer",
            )

        for col_name in [FILTER_BEFORE, FILTER_AFTER, *[f"{FILTER_DROPPED_PREFIX}{n}" for n in self.filter_order]]:
            if col_name in result.columns:
                result[col_name] = pd.to_numeric(result[col_name], errors="coerce").fillna(0).astype(int)
            else:
                result[col_name] = 0
        return result


def merge_filter_audit_into_norms(
    norms: pd.DataFrame,
    auditor: GroupFilterAuditor | None,
    config: dict[str, Any],
) -> pd.DataFrame:
    """
    Добавляет колонки filter_* к combined-нормативам (by_tb + «все тб»).
    """
    if norms is None or norms.empty or auditor is None:
        return norms
    if not filter_audit_column_keys(config):
        return norms

    by_tb_audit, overall_audit = auditor.to_norms_frames()
    if by_tb_audit.empty and overall_audit.empty:
        return norms

    tb_col: str = col(config, "tb")
    all_tb_label: str = str(config.get("output", {}).get("all_tb_label", "все тб"))
    pg_col: str = col(config, "product_group")
    pr_col: str = col(config, "product")
    audit_cols: list[str] = filter_audit_column_keys(config)

    work: pd.DataFrame = norms.copy()
    if tb_col in work.columns and not by_tb_audit.empty:
        is_all: pd.Series = work[tb_col].astype(str) == all_tb_label
        part_tb: pd.DataFrame = work.loc[~is_all].copy()
        part_all: pd.DataFrame = work.loc[is_all].copy()
        merge_keys_tb: list[str] = [c for c in (tb_col, pg_col, pr_col, "current_status") if c in part_tb.columns]
        if merge_keys_tb:
            part_tb = part_tb.merge(by_tb_audit, on=merge_keys_tb, how="left")
        if not part_all.empty and not overall_audit.empty:
            merge_keys_all: list[str] = [c for c in (pg_col, pr_col, "current_status") if c in part_all.columns]
            if merge_keys_all:
                part_all = part_all.merge(overall_audit, on=merge_keys_all, how="left")
        work = pd.concat([part_tb, part_all], ignore_index=True)
    elif not overall_audit.empty:
        merge_keys: list[str] = [c for c in (pg_col, pr_col, "current_status") if c in work.columns]
        if merge_keys:
            work = work.merge(overall_audit, on=merge_keys, how="left")

    for col_name in audit_cols:
        if col_name not in work.columns:
            work[col_name] = 0
        else:
            work[col_name] = pd.to_numeric(work[col_name], errors="coerce").fillna(0).astype(int)
    return work


def append_funnel_step(
    funnel: list[dict[str, Any]] | None,
    *,
    stage: str,
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    config: dict[str, Any],
    kind: str = "filter",
    filter_name: str | None = None,
    group_auditor: GroupFilterAuditor | None = None,
) -> None:
    """Добавляет шаг воронки (если funnel не None) и опционально group_auditor."""
    if funnel is not None:
        before_rows: int = len(before_df)
        after_rows: int = len(after_df)
        before_leads: int = _unique_leads(before_df, config)
        after_leads: int = _unique_leads(after_df, config)
        funnel.append(
            {
                "stage": stage,
                "kind": kind,
                "before_rows": before_rows,
                "after_rows": after_rows,
                "dropped_rows": max(0, before_rows - after_rows),
                "before_leads": before_leads,
                "after_leads": after_leads,
                "dropped_leads": max(0, before_leads - after_leads),
                "filter_name": filter_name,
            }
        )

    if group_auditor is None:
        return
    if kind == "load":
        group_auditor.record_baseline(after_df)
        return
    if filter_name:
        group_auditor.record_filter_step(filter_name, before_df, after_df)


def build_filter_funnel_frame(funnel: list[dict[str, Any]]) -> pd.DataFrame:
    """Таблица воронки фильтров для Excel."""
    if not funnel:
        return pd.DataFrame(
            columns=[
                "Этап",
                "До (строк)",
                "После (строк)",
                "Отсечено строк",
                "До (лидов)",
                "После (лидов)",
                "Отсечено лидов",
            ]
        )
    rows: list[dict[str, Any]] = []
    for step in funnel:
        rows.append(
            {
                "Этап": step["stage"],
                "До (строк)": step["before_rows"],
                "После (строк)": step["after_rows"],
                "Отсечено строк": step["dropped_rows"],
                "До (лидов)": step["before_leads"],
                "После (лидов)": step["after_leads"],
                "Отсечено лидов": step["dropped_leads"],
            }
        )
    return pd.DataFrame(rows)


def build_outlier_audit_summary(norms_internal: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """
    Свод по выбросам и входным фильтрам: сумма по группам нормативов.
    norms_internal — кадр до rename (внутренние имена outlier_* / filter_*).
    """
    labels: dict[str, str] = dict(config.get("output", {}).get("column_labels") or {})
    rows: list[dict[str, Any]] = []
    n_groups: int = 0 if norms_internal is None or norms_internal.empty else len(norms_internal)
    rows.append({"Показатель": "Групп в нормативах", "Значение": n_groups})

    filter_keys: list[str] = filter_audit_column_keys(config)
    filter_mapping: dict[str, str] = build_filter_audit_mapping(config)
    if filter_keys and norms_internal is not None and not norms_internal.empty:
        for key in filter_keys:
            if key not in norms_internal.columns:
                continue
            total: int = int(pd.to_numeric(norms_internal[key], errors="coerce").fillna(0).sum())
            rows.append({"Показатель": filter_mapping.get(key, key) + " (сумма по группам)", "Значение": total})
        rows.append(
            {
                "Показатель": "Входные фильтры (колонки на листе «Нормативы»)",
                "Значение": ", ".join(enabled_pipeline_filter_names(config)),
            }
        )

    cfg: dict[str, Any] = outlier_clipping_config(config)
    if not cfg["enabled"]:
        rows.append(
            {
                "Показатель": "Отсечение выбросов",
                "Значение": "выключено (outlier_clipping.enabled=false)",
            }
        )
        return pd.DataFrame(rows)

    keys: list[str] = audit_column_keys(config)
    if not keys or norms_internal is None or norms_internal.empty:
        rows.append(
            {
                "Показатель": "Отсечение выбросов",
                "Значение": "включено, но колонок аудита нет",
            }
        )
        return pd.DataFrame(rows)

    for key in keys:
        if key not in norms_internal.columns:
            continue
        total = int(pd.to_numeric(norms_internal[key], errors="coerce").fillna(0).sum())
        if key == AUDIT_BEFORE:
            title: str = labels.get(key, "До выбросов (сумма по группам)")
        elif key == AUDIT_AFTER:
            title = labels.get(key, "После отсечения (сумма по группам)")
        elif key == AUDIT_CLIPPED:
            title = labels.get(key, "Отсечено выбросами (всего, сумма)")
        elif key.startswith(AUDIT_RULE_PREFIX):
            rule_name: str = key[len(AUDIT_RULE_PREFIX) :]
            title = labels.get(key, f"Отсечено правилом: {rule_name}")
        else:
            title = key
        rows.append({"Показатель": title, "Значение": total})

    rule_names: list[str] = [r["name"] for r in enabled_rules(config)]
    if rule_names:
        rows.append(
            {
                "Показатель": "Правила выбросов (колонки на листе «Нормативы»)",
                "Значение": ", ".join(rule_names),
            }
        )
    return pd.DataFrame(rows)
