"""Свод по менеджерам и детализация нарушений по ПрПр."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import pandas as pd

from src.settings import col
from src.tab_number import normalize_tab_number, normalize_tab_number_multiline
from src.team_loader import normalize_person_name

logger: logging.Logger = logging.getLogger("kanban.excel_v2.manager_summary")

ROLE_KM: str = "ВКО"
ROLE_VKS: str = "ВКС"


def _manager_key(tab_number: str | None, name: str) -> str:
    """Уникальный ключ менеджера: табельный или ФИО."""
    tn: str = normalize_tab_number(tab_number)
    if tn:
        return f"TN:{tn}"
    return f"FIO:{name.casefold()}"


def _has_leader(snapshot_row: pd.Series, config: dict[str, Any]) -> bool:
    """True, если у лида есть лидер лида или лидер сделки."""
    out_cfg: dict[str, Any] = config.get("team_files", {}).get("output_columns") or {}
    for block in ("lead", "deal"):
        labels: dict[str, str] = dict(out_cfg.get(block) or {})
        fio_col: str = labels.get("member", "")
        if fio_col and pd.notna(snapshot_row.get(fio_col)) and str(snapshot_row.get(fio_col)).strip():
            return True
    return False


def _collect_manager_entries(snapshot: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Собирает записи менеджер ↔ лид для подсчёта превышений.
    Без лидеров — КМ и ВКС как псевдо-менеджеры.
    """
    entries: list[dict[str, Any]] = []
    out_cfg: dict[str, Any] = config.get("team_files", {}).get("output_columns") or {}
    lead_labels: dict[str, str] = dict(out_cfg.get("lead") or {})
    deal_labels: dict[str, str] = dict(out_cfg.get("deal") or {})
    exc_flag: str = config["output"]["exceedance_columns"]["exceedance_flag"]

    km_col: str = "km"
    vks_col: str | None = "vks" if config.get("columns", {}).get("vks") else None
    tb_col: str = "tb"
    pg_col: str = "product_group"
    product_col: str = "product"
    lead_col: str = col(config, "lead_id")

    for _, row in snapshot.iterrows():
        is_exceeded: bool = str(row.get(exc_flag) or "").upper() == "ДА"
        pg: str = str(row.get(pg_col, ""))
        pr: str = str(row.get(product_col, ""))
        gp_key: str = f"{pg}: {pr}" if pg or pr else ""

        if _has_leader(row, config):
            for labels, default_role in ((lead_labels, "Лидер лида"), (deal_labels, "Лидер сделки")):
                fio_col: str = labels.get("member", "")
                tn_col: str = labels.get("member_tab_number", "")
                role_col: str = labels.get("role", "")
                mgr_tb_col: str = labels.get("tb", "")

                fio_raw: Any = row.get(fio_col)
                if not fio_raw or not str(fio_raw).strip():
                    continue

                fio_lines: list[str] = str(fio_raw).splitlines()
                tn_lines: list[str] = str(row.get(tn_col) or "").splitlines()
                role_lines: list[str] = str(row.get(role_col) or "").splitlines()
                tb_lines: list[str] = str(row.get(mgr_tb_col) or "").splitlines()

                for idx, fio in enumerate(fio_lines):
                    name: str = normalize_person_name(fio)
                    if not name:
                        continue
                    tn: str = normalize_tab_number(tn_lines[idx]) if idx < len(tn_lines) else ""
                    role: str = role_lines[idx].strip() if idx < len(role_lines) else default_role
                    mgr_tb: str = tb_lines[idx].strip() if idx < len(tb_lines) else str(row.get(tb_col, ""))
                    entries.append(
                        {
                            "manager_key": _manager_key(tn, name),
                            "tab_number": tn or None,
                            "name": name,
                            "role": role,
                            "tb": mgr_tb,
                            "lead_id": row.get(lead_col),
                            "group_product": gp_key,
                            "exceeded": is_exceeded,
                            "row": row,
                        }
                    )
        else:
            km_name: str = normalize_person_name(row.get(km_col))
            if km_name:
                entries.append(
                    {
                        "manager_key": _manager_key(None, km_name),
                        "tab_number": None,
                        "name": km_name,
                        "role": ROLE_KM,
                        "tb": str(row.get(tb_col, "")),
                        "lead_id": row.get(lead_col),
                        "group_product": gp_key,
                        "exceeded": is_exceeded,
                        "row": row,
                    }
                )
            if vks_col:
                vks_name: str = normalize_person_name(row.get(vks_col))
                if vks_name:
                    entries.append(
                        {
                            "manager_key": _manager_key(None, vks_name),
                            "tab_number": None,
                            "name": vks_name,
                            "role": ROLE_VKS,
                            "tb": str(row.get(tb_col, "")),
                            "lead_id": row.get(lead_col),
                            "group_product": gp_key,
                            "exceeded": is_exceeded,
                            "row": row,
                        }
                    )

    return entries


def build_manager_reports(
    snapshot: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Свод по менеджеру и детализация нарушений за один проход по данным."""
    entries: list[dict[str, Any]] = _collect_manager_entries(snapshot, config)
    summary: pd.DataFrame = _manager_summary_from_entries(entries, config)
    violations: pd.DataFrame = _violations_detail_from_entries(entries, snapshot, config)
    return summary, violations


def build_manager_summary(snapshot: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Лист «Свод по менеджеру»: уникальные ФИО/ТН, число превышений, разрез Группа+Продукт."""
    entries: list[dict[str, Any]] = _collect_manager_entries(snapshot, config)
    return _manager_summary_from_entries(entries, config)


def _manager_summary_from_entries(
    entries: list[dict[str, Any]],
    config: dict[str, Any],
) -> pd.DataFrame:
    if not entries:
        return pd.DataFrame()

    by_manager: dict[str, dict[str, Any]] = {}
    violations_by_gp: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    exceeded_leads_by_manager: dict[str, set[str]] = defaultdict(set)

    lead_col: str = col(config, "lead_id")

    for entry in entries:
        key: str = entry["manager_key"]
        if key not in by_manager:
            by_manager[key] = {
                "Табельный номер": entry["tab_number"],
                "ФИО": entry["name"],
                "Роль": entry["role"],
                "ТБ": entry["tb"],
                "Превышений P80": 0,
                "Группа + Продукт": "",
            }

        if entry["exceeded"]:
            lead_id: str = str(entry["lead_id"])
            if lead_id not in exceeded_leads_by_manager[key]:
                exceeded_leads_by_manager[key].add(lead_id)
                by_manager[key]["Превышений P80"] += 1
                gp: str = str(entry.get("group_product") or "")
                if gp:
                    violations_by_gp[key][gp] += 1

    rows: list[dict[str, Any]] = []
    for key, row in by_manager.items():
        gp_counts: dict[str, int] = violations_by_gp.get(key, {})
        sorted_gp: list[tuple[str, int]] = sorted(gp_counts.items(), key=lambda x: (-x[1], x[0]))
        lines: list[str] = [f"{gp} - {count} нарушений" for gp, count in sorted_gp]
        row["Группа + Продукт"] = "\n".join(lines) if lines else ""
        rows.append(row)

    result: pd.DataFrame = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("Превышений P80", ascending=False, kind="mergesort")
    logger.info("Свод по менеджеру: %s уникальных записей", f"{len(result):,}")
    return result.reset_index(drop=True)


def build_violations_detail(snapshot: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Лист «Свод ПрПр с отклонениями»: по одной строке на лид с превышением для каждого менеджера."""
    entries: list[dict[str, Any]] = _collect_manager_entries(snapshot, config)
    return _violations_detail_from_entries(entries, snapshot, config)


def _violations_detail_from_entries(
    entries: list[dict[str, Any]],
    snapshot: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    if not entries:
        return pd.DataFrame()

    snap_cols: dict[str, str] = config.get("output", {}).get("snapshot_columns") or {}
    exc_cfg: dict[str, str] = config["output"]["exceedance_columns"]
    lead_col: str = col(config, "lead_id")

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for entry in entries:
        if not entry["exceeded"]:
            continue
        lead_id: str = str(entry["lead_id"])
        dedup: tuple[str, str] = (entry["manager_key"], lead_id)
        if dedup in seen:
            continue
        seen.add(dedup)

        snap_row: pd.Series = entry["row"]
        row: dict[str, Any] = {
            "Табельный номер": entry["tab_number"],
            "ФИО менеджера": entry["name"],
            "Роль": entry["role"],
            "ТБ менеджера": entry["tb"],
            lead_col: lead_id,
        }
        for key, label in snap_cols.items():
            if key in snap_row.index:
                row[label] = snap_row.get(key)
        row[exc_cfg["p80_norm"]] = snap_row.get(exc_cfg["p80_norm"])
        row[exc_cfg["current_days"]] = snap_row.get(exc_cfg["current_days"])
        row[exc_cfg["exceedance_days"]] = snap_row.get(exc_cfg["exceedance_days"])
        rows.append(row)

    result: pd.DataFrame = pd.DataFrame(rows)
    logger.info("Свод ПрПр с отклонениями: %s строк", f"{len(result):,}")
    return result.reset_index(drop=True)
