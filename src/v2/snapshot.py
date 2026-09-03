"""Снимок уникальных лидов с заполнением из самых свежих дат отчёта."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.client_names import abbreviate_client_name
from src.settings import col
from src.v2.exceedance_config import resolve_exceedance_columns

logger: logging.Logger = logging.getLogger("kanban.excel_v2.snapshot")


def _empty_tokens(config: dict[str, Any]) -> set[str]:
    """Множество пустых текстовых значений."""
    raw: list[Any] = config.get("processing", {}).get("empty_stage_values", ["", "-", "nan", "None"])
    tokens: set[str] = {str(v).strip().casefold() for v in raw}
    tokens.update({"", "nan", "none", "null", "nat"})
    return tokens


def _nonempty_mask(series: pd.Series, empty: set[str]) -> pd.Series:
    """Векторная маска непустых значений."""
    as_str: pd.Series = series.fillna("").astype(str).str.strip().str.casefold()
    return ~as_str.isin(empty)


def _first_nonempty_per_group(series: pd.Series, empty: set[str]) -> Any:
    """Первое непустое значение в серии (порядок строк уже по убыванию даты)."""
    mask: pd.Series = _nonempty_mask(series, empty)
    if not mask.any():
        return pd.NA
    return series.loc[mask.index[mask]].iloc[0]


def snapshot_column_map(config: dict[str, Any]) -> dict[str, str]:
    """Ключ колонки config → заголовок Excel на листе уникальных ID."""
    raw: dict[str, Any] = config.get("output", {}).get("snapshot_columns") or {}
    return {str(k): str(v) for k, v in raw.items()}


def build_lead_snapshot(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """
    Уникальные ID ПрПр с подтягиванием полей из самых свежих непустых строк.
    Один проход сортировки и groupby, без цепочки merge.
    """
    if df.empty:
        return pd.DataFrame()

    lead_col: str = col(config, "lead_id")
    report_col: str = col(config, "report_date")
    days_col: str = col(config, "days_on_stage")
    field_keys: list[str] = list(snapshot_column_map(config).keys())

    src_cols: set[str] = {lead_col, report_col, days_col}
    for key in field_keys:
        if key in config.get("columns", {}):
            src_cols.add(col(config, key))
    use_cols: list[str] = [c for c in src_cols if c in df.columns]

    work: pd.DataFrame = df[use_cols].copy()
    work[report_col] = pd.to_datetime(work[report_col], errors="coerce")
    work = work.dropna(subset=[lead_col])
    work[lead_col] = work[lead_col].astype(str).str.strip()
    work = work.loc[work[lead_col] != ""]
    work = work.sort_values([lead_col, report_col], ascending=[True, False], kind="mergesort")

    empty: set[str] = _empty_tokens(config)
    grouped = work.groupby(lead_col, sort=False)

    latest: pd.DataFrame = work.drop_duplicates(subset=[lead_col], keep="first")
    indexed: pd.DataFrame = latest[[lead_col]].set_index(lead_col)
    indexed["_report_date"] = latest[report_col].values
    if days_col in latest.columns:
        indexed["_days_on_stage"] = pd.to_numeric(latest[days_col], errors="coerce").values
    else:
        indexed["_days_on_stage"] = pd.NA

    for key in field_keys:
        if key not in config.get("columns", {}):
            continue
        src_col: str = col(config, key)
        if src_col not in work.columns:
            indexed[key] = pd.NA
            continue
        indexed[key] = grouped[src_col].apply(lambda s: _first_nonempty_per_group(s, empty))

    result: pd.DataFrame = indexed.reset_index()

    if "client" in result.columns:
        result["client"] = result["client"].map(
            lambda v: abbreviate_client_name(v, config) if pd.notna(v) else v
        )

    logger.info("Снимок лидов: %s уникальных ID", f"{len(result):,}")
    return result.reset_index(drop=True)


def snapshot_to_export_frame(snapshot: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Переименовывает колонки снимка для Excel."""
    if snapshot.empty:
        return snapshot

    lead_col: str = col(config, "lead_id")
    mapping: dict[str, str] = snapshot_column_map(config)
    rename: dict[str, str] = {lead_col: lead_col}
    for key, label in mapping.items():
        if key in snapshot.columns:
            rename[key] = label

    export_cols: list[str] = [lead_col] + [mapping[k] for k in mapping if k in snapshot.columns]
    renamed: pd.DataFrame = snapshot.rename(columns=rename)
    exc_cfg: dict[str, str] = resolve_exceedance_columns(config)
    extra_cols: list[str] = [
        exc_cfg["p80_norm"],
        exc_cfg["current_days"],
        exc_cfg["exceedance_flag"],
        exc_cfg["exceedance_days"],
    ]
    for col_name in extra_cols:
        if col_name in renamed.columns:
            export_cols.append(col_name)

    team_out: dict[str, Any] = config.get("team_files", {}).get("output_columns") or {}
    email_out: dict[str, Any] = (
        (config.get("manager_emails") or {}).get("output_columns") or {}
    )
    for block_name in ("lead", "deal"):
        block = team_out.get(block_name)
        if not isinstance(block, dict):
            continue
        # Стабильный порядок полей лидера
        for field_key in ("member_tab_number", "member", "role", "tb"):
            label = block.get(field_key)
            if label and label in renamed.columns and label not in export_cols:
                export_cols.append(str(label))
            if field_key == "member_tab_number":
                email_block = email_out.get(block_name)
                if isinstance(email_block, dict):
                    for ek in ("email_alpha", "email_sigma"):
                        elabel = email_block.get(ek)
                        if elabel and elabel in renamed.columns and elabel not in export_cols:
                            export_cols.append(str(elabel))
        for label in block.values():
            if label in renamed.columns and label not in export_cols:
                export_cols.append(str(label))

    present: list[str] = [c for c in export_cols if c in renamed.columns]
    return renamed[present].copy()
