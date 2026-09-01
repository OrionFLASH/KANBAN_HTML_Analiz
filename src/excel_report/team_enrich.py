"""Обогащение снимка лидов данными лидеров команд."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.excel_report.config_loader import config_for_shared_modules
from src.settings import col
from src.team_loader import (
    _leader_value_set,
    load_team_frames,
    normalize_person_name,
)

logger: logging.Logger = logging.getLogger("kanban.excel_v2.team_enrich")


def _team_columns(config: dict[str, Any]) -> dict[str, str]:
    """Карта логических имён колонок команды."""
    defaults: dict[str, str] = {
        "report_date": "Дата отчета",
        "lead_id": "ID ПрПр",
        "deal_id": "ID сделки",
        "member_tab_number": "Табельный номер участника команды",
        "member": "Участник команды",
        "role": "Роль участника команды",
        "is_leader": "Лидер",
        "tb": "ТБ",
    }
    overrides: dict[str, Any] = config.get("team_files", {}).get("columns") or {}
    result: dict[str, str] = dict(defaults)
    for key, value in overrides.items():
        if value:
            result[str(key)] = str(value)
    return result


def _multiline_agg(values: pd.Series) -> str | None:
    """Склеивает значения серии через перевод строки."""
    cleaned: list[str] = [str(v).strip() for v in values if pd.notna(v) and str(v).strip()]
    if not cleaned:
        return None
    return "\n".join(cleaned)


def build_leaders_lookup_df(
    team_df: pd.DataFrame,
    config: dict[str, Any],
    *,
    id_key: str = "lead_id",
    source: str = "lead",
) -> pd.DataFrame:
    """
    DataFrame id → поля лидеров (TN, ФИО, роль, ТБ) на max(дата отчёта).
    Векторизованная группировка вместо iterrows.
    """
    if team_df.empty:
        return pd.DataFrame(columns=["member_tab_number", "member", "role", "tb"])

    cols: dict[str, str] = _team_columns(config)
    id_col: str = cols[id_key]
    date_col: str = cols["report_date"]
    tn_col: str = cols["member_tab_number"]
    member_col: str = cols["member"]
    role_col: str = cols["role"]
    leader_col: str = cols["is_leader"]
    tb_col: str = cols["tb"]
    shared: dict[str, Any] = config_for_shared_modules(config)
    leader_values: set[str] = _leader_value_set(shared)

    needed: list[str] = [id_col, date_col, member_col, leader_col]
    missing: list[str] = [c for c in needed if c not in team_df.columns]
    if missing:
        logger.warning("Команда (%s): нет колонок %s", source, missing)
        return pd.DataFrame(columns=["member_tab_number", "member", "role", "tb"])

    work: pd.DataFrame = team_df[
        [c for c in (id_col, date_col, tn_col, member_col, role_col, leader_col, tb_col) if c in team_df.columns]
    ].copy()

    leader_text: pd.Series = work[leader_col].fillna("").astype(str).str.strip().str.casefold()
    work = work.loc[leader_text.isin(leader_values)]
    if work.empty:
        return pd.DataFrame(columns=["member_tab_number", "member", "role", "tb"])

    work["_id"] = work[id_col].astype(str).str.strip()
    work = work.loc[work["_id"] != ""]
    work["_date"] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna(subset=["_date"])
    if work.empty:
        return pd.DataFrame(columns=["member_tab_number", "member", "role", "tb"])

    idx_latest: pd.Series = work.groupby("_id", sort=False)["_date"].idxmax()
    latest: pd.DataFrame = work.loc[idx_latest].copy()
    latest["_name"] = latest[member_col].map(normalize_person_name)
    latest = latest.loc[latest["_name"] != ""]
    latest = latest.drop_duplicates(subset=["_id", "_name"], keep="first")

    agg_spec: dict[str, Any] = {"member": ("_name", _multiline_agg)}
    if tn_col in latest.columns:
        agg_spec["member_tab_number"] = (tn_col, _multiline_agg)
    if role_col in latest.columns:
        agg_spec["role"] = (role_col, _multiline_agg)
    if tb_col in latest.columns:
        agg_spec["tb"] = (tb_col, _multiline_agg)

    grouped: pd.DataFrame = latest.groupby("_id", sort=False).agg(**agg_spec)
    logger.info("Lookup лидеров (%s): %s ключей", source, f"{len(grouped):,}")
    return grouped


def enrich_snapshot_with_team_dfs(
    snapshot: pd.DataFrame,
    lead_team_df: pd.DataFrame,
    deal_team_df: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Добавляет колонки лидеров через merge (без повторной загрузки файлов)."""
    if snapshot.empty:
        return snapshot

    lead_lookup: pd.DataFrame = build_leaders_lookup_df(
        lead_team_df, config, id_key="lead_id", source="lead"
    )
    deal_lookup: pd.DataFrame = build_leaders_lookup_df(
        deal_team_df, config, id_key="deal_id", source="deal"
    )

    out_cfg: dict[str, Any] = config.get("team_files", {}).get("output_columns") or {}
    lead_labels: dict[str, str] = dict(out_cfg.get("lead") or {})
    deal_labels: dict[str, str] = dict(out_cfg.get("deal") or {})
    lead_col: str = col(config, "lead_id")
    deal_col: str | None = col(config, "deal_id") if "deal_id" in config.get("columns", {}) else None

    result: pd.DataFrame = snapshot.copy()

    if not lead_lookup.empty:
        lead_merge: pd.DataFrame = result[[lead_col]].astype(str).merge(
            lead_lookup,
            left_on=lead_col,
            right_index=True,
            how="left",
        )
        for field_key, excel_label in lead_labels.items():
            if field_key in lead_lookup.columns:
                result[excel_label] = lead_merge[field_key].values
            else:
                result[excel_label] = None
    else:
        for excel_label in lead_labels.values():
            result[excel_label] = None

    if deal_col and deal_col in result.columns and not deal_lookup.empty:
        deal_key: pd.Series = result[deal_col].astype(str).str.strip()
        deal_merge: pd.DataFrame = deal_key.to_frame("_deal_id").merge(
            deal_lookup,
            left_on="_deal_id",
            right_index=True,
            how="left",
        )
        for field_key, excel_label in deal_labels.items():
            if field_key in deal_lookup.columns:
                result[excel_label] = deal_merge[field_key].values
            else:
                result[excel_label] = None
    else:
        for excel_label in deal_labels.values():
            result[excel_label] = None

    return result


def enrich_snapshot_with_teams(snapshot: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Добавляет колонки лидеров лида и сделки к снимку (с загрузкой файлов)."""
    if snapshot.empty:
        return snapshot

    shared_config: dict[str, Any] = config_for_shared_modules(config)
    lead_team_df, deal_team_df = load_team_frames(shared_config)
    return enrich_snapshot_with_team_dfs(snapshot, lead_team_df, deal_team_df, config)
