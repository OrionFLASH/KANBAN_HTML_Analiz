"""Обогащение снимка лидов данными лидеров команд."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.v2.config_loader import config_for_shared_modules
from src.settings import col
from src.team_loader import (
    _leader_value_set,
    load_team_frames,
    normalize_person_name,
)
from src.tab_number import normalize_tab_number_multiline

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


def _multiline_tab_agg(values: pd.Series) -> str | None:
    """Склеивает нормализованные табельные номера через перевод строки."""
    cleaned: list[str] = []
    for value in values:
        normalized: str | None = normalize_tab_number_multiline(value)
        if normalized:
            cleaned.append(normalized)
    if not cleaned:
        return None
    return "\n".join(cleaned)


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
    before_leader: int = len(work)
    work = work.loc[leader_text.isin(leader_values)]
    if len(work) < before_leader:
        logger.info(
            "Команда (%s): оставлены только лидеры (%d → %d строк, Лидер из config)",
            source,
            before_leader,
            len(work),
        )
    if work.empty:
        return pd.DataFrame(columns=["member_tab_number", "member", "role", "tb"])

    work["_id"] = work[id_col].astype(str).str.strip()
    work = work.loc[work["_id"] != ""]
    work["_date"] = pd.to_datetime(work[date_col], errors="coerce")
    bad_date: int = int(work["_date"].isna().sum())
    if bad_date:
        logger.warning(
            "Команда (%s): %s строк лидеров без разобранной «%s» — не участвуют в lookup",
            source,
            f"{bad_date:,}",
            date_col,
        )
    work = work.dropna(subset=["_date"])
    if work.empty:
        return pd.DataFrame(columns=["member_tab_number", "member", "role", "tb"])

    pick_mode: str = str(
        (config.get("team_files") or {}).get("pick_report_date", "latest")
    ).casefold()
    if pick_mode != "latest":
        logger.warning(
            "Команда (%s): pick_report_date=%s не поддерживается, используется latest",
            source,
            pick_mode,
        )

    # Все строки с max(Дата отчета) по id — несколько лидеров на одной дате сохраняем
    max_dates: pd.Series = work.groupby("_id", sort=False)["_date"].transform("max")
    latest: pd.DataFrame = work.loc[work["_date"] == max_dates].copy()
    latest["_name"] = latest[member_col].map(normalize_person_name)
    before_names: int = len(latest)
    latest = latest.loc[latest["_name"] != ""]
    if len(latest) < before_names:
        logger.warning(
            "Команда (%s): %s строк лидеров без ФИО пропущены",
            source,
            before_names - len(latest),
        )
    before_dedup: int = len(latest)
    latest = latest.drop_duplicates(subset=["_id", "_name"], keep="first")
    if len(latest) < before_dedup:
        logger.info(
            "Команда (%s): дедупликация (_id, ФИО): %d → %d строк",
            source,
            before_dedup,
            len(latest),
        )

    agg_spec: dict[str, Any] = {"member": ("_name", _multiline_agg)}
    if tn_col in latest.columns:
        agg_spec["member_tab_number"] = (tn_col, _multiline_tab_agg)
    if role_col in latest.columns:
        agg_spec["role"] = (role_col, _multiline_agg)
    if tb_col in latest.columns:
        agg_spec["tb"] = (tb_col, _multiline_agg)

    grouped: pd.DataFrame = latest.groupby("_id", sort=False).agg(**agg_spec)
    logger.info("Lookup лидеров (%s): %s ключей", source, f"{len(grouped):,}")
    return grouped


def _snapshot_id_column(snapshot: pd.DataFrame, config: dict[str, Any], key: str) -> str | None:
    """
    Имя колонки id в снимке для join с lookup лидеров.

    В build_lead_snapshot:
    - lead_id остаётся под Excel-именем (например «ID ПрПр»);
    - прочие поля snapshot_columns — под ключами config («deal_id», не «ID сделки»).
    """
    if key not in config.get("columns", {}):
        return None
    excel_name: str = col(config, key)
    if key == "lead_id":
        if excel_name in snapshot.columns:
            return excel_name
        if key in snapshot.columns:
            return key
        return None
    # deal_id и аналоги: сначала ключ снимка, затем Excel-имя (если уже переименовано)
    if key in snapshot.columns:
        return key
    if excel_name in snapshot.columns:
        return excel_name
    return None


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
    lead_col: str | None = _snapshot_id_column(snapshot, config, "lead_id")
    deal_col: str | None = _snapshot_id_column(snapshot, config, "deal_id")

    result: pd.DataFrame = snapshot.copy()

    if lead_col and not lead_lookup.empty:
        lead_key: pd.Series = result[lead_col].astype(str).str.strip()
        lead_merge: pd.DataFrame = lead_key.to_frame("_lead_id").merge(
            lead_lookup,
            left_on="_lead_id",
            right_index=True,
            how="left",
        )
        for field_key, excel_label in lead_labels.items():
            if field_key in lead_lookup.columns:
                result[excel_label] = lead_merge[field_key].values
            else:
                result[excel_label] = None
    else:
        if not lead_col:
            logger.warning(
                "Снимок: нет колонки ID лида для подливки лидеров "
                "(ожидались «%s» или lead_id)",
                col(config, "lead_id") if "lead_id" in config.get("columns", {}) else "ID ПрПр",
            )
        for excel_label in lead_labels.values():
            result[excel_label] = None

    if deal_col and not deal_lookup.empty:
        deal_key: pd.Series = result[deal_col].astype(str).str.strip()
        # Пустые / NaN → не матчим на ключ «nan»
        empty_deal: pd.Series = deal_key.isin({"", "nan", "none", "null", "nat", "-", "—"})
        deal_key = deal_key.mask(empty_deal, other=pd.NA)
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
        if deal_lookup.empty:
            logger.info("Lookup лидеров сделки пуст — колонки лидера сделки остаются пустыми")
        elif not deal_col:
            logger.warning(
                "Снимок: нет колонки ID сделки для подливки лидеров "
                "(ожидались deal_id или «%s») — лидер сделки не подливается",
                col(config, "deal_id") if "deal_id" in config.get("columns", {}) else "ID сделки",
            )
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
