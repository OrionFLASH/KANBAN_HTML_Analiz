"""Обогащение снимка лидов данными лидеров команд."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.v2.config_loader import config_for_shared_modules
from src.settings import col
from src.team_loader import (
    _leader_value_set,
    _normalize_id_token,
    _resolve_column_name,
    load_team_frames,
    normalize_person_name,
    pick_leaders_on_latest_dates,
)
from src.tab_number import normalize_tab_number_multiline

logger: logging.Logger = logging.getLogger("kanban.excel_v2.team_enrich")


def _team_columns(config: dict[str, Any]) -> dict[str, str]:
    """Карта логических имён колонок команды."""
    defaults: dict[str, str] = {
        "report_date": "Дата отчета",
        "team_added_date": "Дата добавления в команду",
        "lead_id": "ID ПрПр",
        "deal_id": "ID сделки",
        "member_tab_number": "Табельный номер участника команды",
        "member": "Участник команды",
        "role": "Роль участника команды",
        "is_leader": "Лидер",
        "tb": "ТБ",
        "team_type": "Тип команды",
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
    DataFrame id → поля лидеров (TN, ФИО, роль, ТБ).
    Отбор: max(Дата отчета), затем max(Дата добавления в команду);
    если «Дата отчета» нет — весь файл считается одной датой отчёта
    (не ошибка), дальше обычный отбор по дате добавления;
    при равных датах — все лидеры через \\n.
    """
    if team_df.empty:
        return pd.DataFrame(columns=["member_tab_number", "member", "role", "tb"])

    cols: dict[str, str] = _team_columns(config)
    id_col: str | None = _resolve_column_name(team_df, cols[id_key])
    date_col: str | None = _resolve_column_name(team_df, cols["report_date"])
    added_expected: str = cols.get("team_added_date", "Дата добавления в команду")
    added_col: str | None = _resolve_column_name(team_df, added_expected)
    tn_col: str | None = _resolve_column_name(team_df, cols["member_tab_number"])
    member_col: str | None = _resolve_column_name(team_df, cols["member"])
    role_col: str | None = _resolve_column_name(team_df, cols["role"])
    leader_col: str | None = _resolve_column_name(team_df, cols["is_leader"])
    tb_col: str | None = _resolve_column_name(team_df, cols["tb"])
    shared: dict[str, Any] = config_for_shared_modules(config)
    leader_values: set[str] = _leader_value_set(shared)

    needed_map: dict[str, str | None] = {
        cols[id_key]: id_col,
        cols["member"]: member_col,
        cols["is_leader"]: leader_col,
    }
    missing: list[str] = [name for name, resolved in needed_map.items() if resolved is None]
    if missing:
        logger.warning(
            "Команда (%s): нет колонок %s среди %s",
            source,
            missing,
            list(team_df.columns)[:25],
        )
        return pd.DataFrame(columns=["member_tab_number", "member", "role", "tb"])

    assert id_col and member_col and leader_col

    use_cols: list[str] = [
        c
        for c in (id_col, date_col, added_col, tn_col, member_col, role_col, leader_col, tb_col)
        if c
    ]
    work: pd.DataFrame = team_df[use_cols].copy()

    leader_text: pd.Series = (
        work[leader_col].astype("string").fillna("").astype(str).str.strip().str.casefold()
    )
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
        logger.warning(
            "Команда (%s): нет строк с Лидер∈%s — lookup пуст",
            source,
            sorted(leader_values),
        )
        return pd.DataFrame(columns=["member_tab_number", "member", "role", "tb"])

    work["_id"] = work[id_col].map(_normalize_id_token)
    work = work.loc[work["_id"] != ""]

    if date_col is not None:
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
    else:
        # Нет колонки даты отчёта — весь файл считаем одной датой (не падаем)
        work["_date"] = pd.Timestamp("1970-01-01")
        logger.info(
            "Команда (%s): нет «%s» — весь файл считаем одной датой отчёта",
            source,
            cols["report_date"],
        )

    pick_mode: str = str(
        (config.get("team_files") or {}).get("pick_report_date", "latest")
    ).casefold()
    if pick_mode != "latest":
        logger.warning(
            "Команда (%s): pick_report_date=%s не поддерживается, используется latest",
            source,
            pick_mode,
        )

    team_added_key: str | None
    if added_col:
        work["_team_added"] = pd.to_datetime(work[added_col], errors="coerce")
        team_added_key = "_team_added"
    else:
        team_added_key = None
        logger.info(
            "Команда (%s): колонка «%s» отсутствует — отбор только по дате отчёта",
            source,
            added_expected,
        )

    latest: pd.DataFrame = pick_leaders_on_latest_dates(
        work,
        id_col="_id",
        report_date_col="_date",
        team_added_col=team_added_key,
        source=source,
    )
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
    if tn_col and tn_col in latest.columns:
        agg_spec["member_tab_number"] = (tn_col, _multiline_tab_agg)
    if role_col and role_col in latest.columns:
        agg_spec["role"] = (role_col, _multiline_agg)
    if tb_col and tb_col in latest.columns:
        agg_spec["tb"] = (tb_col, _multiline_agg)

    grouped: pd.DataFrame = latest.groupby("_id", sort=False).agg(**agg_spec)
    logger.info("Lookup лидеров (%s): %s ключей", source, f"{len(grouped):,}")
    return grouped


def _snapshot_id_column(snapshot: pd.DataFrame, config: dict[str, Any], key: str) -> str | None:
    """
    Имя колонки id в снимке для join с lookup лидеров.
    Снимок хранит поля под ключами config (lead_id, deal_id); Excel-имя — запасной вариант.
    """
    if key not in config.get("columns", {}):
        return None
    if key in snapshot.columns:
        return key
    excel_name: str = col(config, key)
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
        lead_key: pd.Series = result[lead_col].map(_normalize_id_token)
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
        matched_lead: int = int(lead_merge["member"].notna().sum()) if "member" in lead_merge.columns else 0
        logger.info(
            "Подливка лидера лида: совпало %s из %s строк снимка (lookup %s ключей)",
            f"{matched_lead:,}",
            f"{len(result):,}",
            f"{len(lead_lookup):,}",
        )
    else:
        if lead_lookup.empty:
            logger.warning("Lookup лидеров лида пуст — колонки лидера лида остаются пустыми")
        if not lead_col:
            logger.warning(
                "Снимок: нет колонки ID лида для подливки лидеров "
                "(ожидались «%s» или lead_id)",
                col(config, "lead_id") if "lead_id" in config.get("columns", {}) else "ID ПрПр",
            )
        for excel_label in lead_labels.values():
            result[excel_label] = None

    if deal_col and not deal_lookup.empty:
        deal_key: pd.Series = result[deal_col].map(_normalize_id_token)
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
        matched_deal: int = int(deal_merge["member"].notna().sum()) if "member" in deal_merge.columns else 0
        logger.info(
            "Подливка лидера сделки: совпало %s из %s строк снимка (lookup %s ключей)",
            f"{matched_deal:,}",
            f"{len(result):,}",
            f"{len(deal_lookup):,}",
        )
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
