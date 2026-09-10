"""Колонки сроков по «Текущий статус» для листа «Уникальные ID»."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.settings import col

logger: logging.Logger = logging.getLogger("kanban.excel_v2.status_durations")


def _status_cfg(config: dict[str, Any]) -> dict[str, Any]:
    """Блок output.status_duration_columns."""
    raw: Any = (config.get("output") or {}).get("status_duration_columns")
    return dict(raw) if isinstance(raw, dict) else {}


def status_duration_columns_enabled(config: dict[str, Any]) -> bool:
    """Включены ли колонки сроков по статусам на снимке лидов."""
    cfg: dict[str, Any] = _status_cfg(config)
    if not cfg and "status_duration_columns" not in (config.get("output") or {}):
        # По умолчанию включено, если блок не задан — для v2 detail
        return True
    return bool(cfg.get("enabled", True))


def preferred_status_order(config: dict[str, Any]) -> list[str]:
    """Заданный порядок статусов (заголовки колонок)."""
    raw: Any = _status_cfg(config).get("order")
    if not isinstance(raw, list):
        return [
            "К продаже",
            "Выявление потребности",
            "Обсуждение условий",
            "Реализация сделки",
            "Активация продукта",
            "Продажа завершена",
        ]
    return [str(item).strip() for item in raw if str(item).strip()]


def _normalize_status(value: Any) -> str:
    """Нормализация подписи статуса для сопоставления."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def resolve_status_column_order(
    observed_statuses: list[str],
    config: dict[str, Any],
) -> list[str]:
    """
    Порядок колонок: весь order из config (всегда),
    затем прочие статусы из данных (А→Я), если include_others.
    """
    cfg: dict[str, Any] = _status_cfg(config)
    include_others: bool = bool(cfg.get("include_others", True))
    preferred: list[str] = preferred_status_order(config)

    observed_clean: list[str] = []
    seen_fold: set[str] = set()
    for name in observed_statuses:
        text: str = _normalize_status(name)
        if not text:
            continue
        fold: str = text.casefold()
        if fold in seen_fold:
            continue
        seen_fold.add(fold)
        observed_clean.append(text)

    used_folds: set[str] = {p.casefold() for p in preferred}
    ordered: list[str] = list(preferred)

    if include_others:
        others: list[str] = [
            s for s in observed_clean if s.casefold() not in used_folds
        ]
        others_sort: str = str(cfg.get("others_sort", "alpha")).strip().casefold()
        if others_sort in {"alpha", "az", "a-z", "ая", "а→я"}:
            others = sorted(others, key=lambda s: s.casefold())
        ordered.extend(others)

    return ordered


def build_status_duration_pivot(
    records: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, list[str]]:
    """
    Сводка: lead_id × статус → max(days_on_stage) по записям analysis_level=status.

    Возвращает (кадр с lead_id и колонками статусов, список имён колонок-статусов).
    """
    empty: pd.DataFrame = pd.DataFrame(columns=["lead_id"])
    if records is None or records.empty:
        return empty, []

    work: pd.DataFrame = records
    if "analysis_level" in work.columns:
        work = work.loc[work["analysis_level"].astype(str) == "status"]
    if work.empty:
        return empty, []

    lead_src: str = col(config, "lead_id")
    lead_col: str = "lead_id" if "lead_id" in work.columns else lead_src
    if lead_col not in work.columns:
        logger.warning("Сроки по статусам: нет колонки lead_id в records")
        return empty, []

    status_col: str = "current_status"
    if status_col not in work.columns:
        status_src: str = col(config, "current_status")
        if status_src in work.columns:
            status_col = status_src
        else:
            logger.warning("Сроки по статусам: нет колонки статуса в records")
            return empty, []

    days_col: str = "days_on_stage"
    if days_col not in work.columns:
        logger.warning("Сроки по статусам: нет days_on_stage в records")
        return empty, []

    slim: pd.DataFrame = work[[lead_col, status_col, days_col]].copy()
    slim["_lead"] = slim[lead_col].astype(str).str.strip()
    slim["_status"] = slim[status_col].map(_normalize_status)
    slim["_days"] = pd.to_numeric(slim[days_col], errors="coerce")
    slim = slim.loc[(slim["_lead"] != "") & (slim["_status"] != "")]
    slim = slim.dropna(subset=["_days"])
    if slim.empty:
        return empty, []

    # Канонические имена из preferred order (casefold → label)
    preferred: list[str] = preferred_status_order(config)
    fold_to_label: dict[str, str] = {p.casefold(): p for p in preferred}

    def _label_for(status: str) -> str:
        return fold_to_label.get(status.casefold(), status)

    slim["_col"] = slim["_status"].map(_label_for)

    # Несколько продуктов/ТБ у одного лида на одной стадии → max дней
    grouped: pd.DataFrame = (
        slim.groupby(["_lead", "_col"], sort=False)["_days"].max().reset_index()
    )
    observed: list[str] = list(dict.fromkeys(grouped["_col"].tolist()))
    col_order: list[str] = resolve_status_column_order(observed, config)
    if not col_order:
        return empty, []

    pivot: pd.DataFrame = grouped.pivot(index="_lead", columns="_col", values="_days")
    # Только колонки из порядка; отсутствующие — не создаём пустые заранее
    for name in col_order:
        if name not in pivot.columns:
            pivot[name] = pd.NA
    pivot = pivot.reindex(columns=col_order)
    pivot = pivot.reset_index().rename(columns={"_lead": "lead_id"})

    # Целые дни, где есть значение
    for name in col_order:
        pivot[name] = pd.to_numeric(pivot[name], errors="coerce")
        # Округление до целых дней для Excel
        as_num = pivot[name]
        pivot[name] = as_num.round().astype("Int64")

    logger.info(
        "Сроки по статусам: %s лидов, колонок статусов=%s",
        f"{len(pivot):,}",
        len(col_order),
    )
    return pivot, col_order


def attach_status_duration_columns(
    snapshot: pd.DataFrame,
    records: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, list[str]]:
    """
    Добавляет к снимку колонки дней по статусам.

    Возвращает (snapshot с колонками, список имён добавленных колонок).
    """
    if not status_duration_columns_enabled(config):
        return snapshot, []
    if snapshot is None or snapshot.empty:
        return snapshot, []

    pivot, status_cols = build_status_duration_pivot(records, config)
    if not status_cols:
        # Даже без данных в records — колонки из order (пустые), чтобы шапка была стабильной
        preferred = preferred_status_order(config)
        if not preferred:
            return snapshot, []
        out: pd.DataFrame = snapshot.copy()
        for name in preferred:
            if name not in out.columns:
                out[name] = pd.NA
        return out, preferred

    out = snapshot.copy()
    # Убрать одноимённые колонки, если уже были
    drop_existing: list[str] = [c for c in status_cols if c in out.columns]
    if drop_existing:
        out = out.drop(columns=drop_existing)

    lead_key: str = "lead_id" if "lead_id" in out.columns else col(config, "lead_id")
    merge_right: pd.DataFrame = pivot.rename(columns={"lead_id": lead_key})
    out["_merge_lead"] = out[lead_key].astype(str).str.strip()
    merge_right["_merge_lead"] = merge_right[lead_key].astype(str).str.strip()
    merge_right = merge_right.drop(columns=[lead_key])
    out = out.merge(merge_right, on="_merge_lead", how="left")
    out = out.drop(columns=["_merge_lead"])
    return out, status_cols
