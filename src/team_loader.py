"""Загрузка команд лида/сделки и сбор актуальной команды по ID."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.project_paths import resolve_path
from src.settings import col

logger: logging.Logger = logging.getLogger("kanban.team_loader")

ROLE_KM: str = "КМ"
ROLE_VKS: str = "ВКС"
SOURCE_LEAD_TEAM: str = "lead_team"
SOURCE_DEAL_TEAM: str = "deal_team"
SOURCE_KM: str = "km"
SOURCE_VKS: str = "vks"

EMPTY_NAME_TOKENS: frozenset[str] = frozenset({"", "-", "—", "nan", "none", "null"})


def team_files_config(config: dict[str, Any]) -> dict[str, Any]:
    """Блок manager_analytics.team_files или пустой dict."""
    raw: Any = config.get("manager_analytics", {}).get("team_files") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def is_team_files_enabled(config: dict[str, Any]) -> bool:
    """Включена ли подгрузка файлов команд."""
    cfg: dict[str, Any] = team_files_config(config)
    return bool(cfg.get("enabled", False))


def normalize_person_name(value: Any) -> str:
    """Нормализует ФИО для дедупликации."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text: str = " ".join(str(value).split()).strip()
    if text.casefold() in EMPTY_NAME_TOKENS:
        return ""
    return text


def _is_leader_value(value: Any, leader_values: set[str]) -> bool:
    """True, если значение колонки «Лидер» означает лидера."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    token: str = str(value).strip().casefold()
    return token in leader_values


def _team_column_map(config: dict[str, Any]) -> dict[str, str]:
    """Имена колонок файла команды (с defaults)."""
    defaults: dict[str, str] = {
        "report_date": "Дата отчета",
        "lead_id": "ID ПрПр",
        "deal_id": "ID сделки",
        "member": "Участник команды",
        "role": "Роль участника команды",
        "is_leader": "Лидер",
        "tb": "ТБ",
    }
    overrides: dict[str, Any] = team_files_config(config).get("columns") or {}
    result: dict[str, str] = dict(defaults)
    for key, value in overrides.items():
        if value:
            result[str(key)] = str(value)
    return result


def _leader_value_set(config: dict[str, Any]) -> set[str]:
    """Допустимые значения «Лидер = да» в нижнем регистре."""
    raw: list[Any] = list(
        team_files_config(config).get("leader_values")
        or ["Да", "да", "yes", "YES", "true", "True", "1"]
    )
    return {str(v).strip().casefold() for v in raw if str(v).strip()}


def _role_label(source: str, role: str) -> str:
    """Подпись роли с источником (команда лида / сделки / КМ / ВКС)."""
    role_clean: str = " ".join(str(role).split()).strip() if role else ""
    if source == SOURCE_KM:
        return ROLE_KM
    if source == SOURCE_VKS:
        return ROLE_VKS
    if source == SOURCE_LEAD_TEAM:
        return f"Команда лида · {role_clean}" if role_clean else "Команда лида · лидер"
    if source == SOURCE_DEAL_TEAM:
        return f"Команда сделки · {role_clean}" if role_clean else "Команда сделки · лидер"
    return role_clean or source


def _resolve_team_filenames(config: dict[str, Any], kind: str) -> list[str]:
    """Список имён файлов команды для текущего mode (test/prod)."""
    cfg: dict[str, Any] = team_files_config(config)
    block: Any = cfg.get(kind) or {}
    if isinstance(block, str):
        return [block] if block.strip() else []
    if isinstance(block, list):
        return [str(x) for x in block if str(x).strip()]
    if not isinstance(block, dict):
        return []
    mode: str = str(config.get("mode", "test"))
    names: Any = block.get(mode) or block.get("files") or []
    if isinstance(names, str):
        return [names] if names.strip() else []
    return [str(x) for x in names if str(x).strip()]


def _input_dir(config: dict[str, Any]) -> Path:
    """Каталог входных файлов по режиму."""
    mode: str = str(config.get("mode", "test"))
    key: str = "input_test" if mode == "test" else "input_prod"
    return resolve_path(config["paths"][key])


def _read_team_file(path: Path, config: dict[str, Any]) -> pd.DataFrame:
    """Читает один Excel файл команды."""
    engine: str = str(config.get("excel", {}).get("engine", "openpyxl"))
    na_values: list[str] = list(config.get("excel", {}).get("na_values", [""]))
    df: pd.DataFrame = pd.read_excel(path, engine=engine, na_values=na_values)
    # Убираем безымянные/пустые колонки
    drop_cols: list[str] = [
        c for c in df.columns if str(c).strip() == "" or str(c).startswith("Unnamed")
    ]
    if drop_cols:
        df = df.drop(columns=drop_cols)
    return df


def load_team_frames(config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Загружает и склеивает файлы команды лида и команды сделки."""
    if not is_team_files_enabled(config):
        return pd.DataFrame(), pd.DataFrame()

    input_dir: Path = _input_dir(config)
    lead_frames: list[pd.DataFrame] = []
    deal_frames: list[pd.DataFrame] = []

    for name in _resolve_team_filenames(config, "lead_team"):
        path: Path = input_dir / name
        if not path.exists():
            logger.warning("Файл команды лида не найден: %s", path)
            continue
        frame = _read_team_file(path, config)
        frame["source_file"] = name
        lead_frames.append(frame)
        logger.info("Команда лида: %s — %s строк", name, f"{len(frame):,}")

    for name in _resolve_team_filenames(config, "deal_team"):
        path = input_dir / name
        if not path.exists():
            logger.warning("Файл команды сделки не найден: %s", path)
            continue
        frame = _read_team_file(path, config)
        frame["source_file"] = name
        deal_frames.append(frame)
        logger.info("Команда сделки: %s — %s строк", name, f"{len(frame):,}")

    lead_df: pd.DataFrame = (
        pd.concat(lead_frames, ignore_index=True) if lead_frames else pd.DataFrame()
    )
    deal_df: pd.DataFrame = (
        pd.concat(deal_frames, ignore_index=True) if deal_frames else pd.DataFrame()
    )
    return lead_df, deal_df


def build_leader_lookup(
    df: pd.DataFrame,
    config: dict[str, Any],
    *,
    id_key: str,
    source: str,
) -> dict[str, list[dict[str, str]]]:
    """
    Словарь id → список лидеров на максимальной дате отчёта.
    id_key: lead_id | deal_id из карты колонок команды.
    """
    if df.empty:
        return {}

    cols: dict[str, str] = _team_column_map(config)
    id_col: str = cols[id_key]
    date_col: str = cols["report_date"]
    member_col: str = cols["member"]
    role_col: str = cols["role"]
    leader_col: str = cols["is_leader"]
    leader_values: set[str] = _leader_value_set(config)

    needed: list[str] = [id_col, date_col, member_col, leader_col]
    missing: list[str] = [c for c in needed if c not in df.columns]
    if missing:
        logger.warning("Команда (%s): нет колонок %s — lookup пуст", source, missing)
        return {}

    work: pd.DataFrame = df.copy()
    work["_is_leader"] = work[leader_col].map(lambda v: _is_leader_value(v, leader_values))
    work = work.loc[work["_is_leader"]].copy()
    if work.empty:
        return {}

    work["_id"] = work[id_col].map(lambda v: str(v).strip() if pd.notna(v) else "")
    work = work.loc[work["_id"] != ""].copy()
    work["_name"] = work[member_col].map(normalize_person_name)
    work = work.loc[work["_name"] != ""].copy()
    work["_role"] = (
        work[role_col].map(lambda v: " ".join(str(v).split()).strip() if pd.notna(v) else "")
        if role_col in work.columns
        else ""
    )
    work["_date"] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna(subset=["_date"])
    if work.empty:
        return {}

    max_dates: pd.Series = work.groupby("_id", sort=False)["_date"].transform("max")
    latest: pd.DataFrame = work.loc[work["_date"] == max_dates].copy()

    result: dict[str, list[dict[str, str]]] = {}
    for lead_id, group in latest.groupby("_id", sort=False):
        seen: set[str] = set()
        members: list[dict[str, str]] = []
        for _, row in group.iterrows():
            name: str = str(row["_name"])
            key: str = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            members.append(
                {
                    "name": name,
                    "role": str(row["_role"]),
                    "source": source,
                    "role_label": _role_label(source, str(row["_role"])),
                }
            )
        if members:
            result[str(lead_id)] = members
    logger.info(
        "Lookup лидеров (%s): %s ключей",
        source,
        f"{len(result):,}",
    )
    return result


def merge_person_roles(
    entries: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Уникальные ФИО с объединённым списком ролей (порядок появления)."""
    order: list[str] = []
    by_key: dict[str, dict[str, Any]] = {}
    for entry in entries:
        name: str = normalize_person_name(entry.get("name"))
        if not name:
            continue
        key: str = name.casefold()
        role_label: str = str(entry.get("role_label") or entry.get("role") or "").strip()
        if key not in by_key:
            by_key[key] = {"name": name, "roles": [], "_role_keys": set()}
            order.append(key)
        if role_label:
            role_key: str = role_label.casefold()
            if role_key not in by_key[key]["_role_keys"]:
                by_key[key]["_role_keys"].add(role_key)
                by_key[key]["roles"].append(role_label)
    result: list[dict[str, Any]] = []
    for key in order:
        item = by_key[key]
        result.append({"name": item["name"], "roles": list(item["roles"])})
    return result


def compose_lead_team(
    *,
    lead_id: str | None,
    deal_id: str | None,
    km: str | None,
    vks: str | None,
    lead_leaders: dict[str, list[dict[str, str]]],
    deal_leaders: dict[str, list[dict[str, str]]],
) -> list[dict[str, Any]]:
    """
    Актуальная команда сделки/лида: лидер лида + лидеры сделки + КМ + ВКС.
    Повторы ФИО схлопываются, роли объединяются.
    """
    entries: list[dict[str, str]] = []

    lid: str = str(lead_id or "").strip()
    if lid and lid in lead_leaders:
        entries.extend(lead_leaders[lid])

    did: str = str(deal_id or "").strip()
    if did and did not in EMPTY_NAME_TOKENS and did in deal_leaders:
        entries.extend(deal_leaders[did])

    km_name: str = normalize_person_name(km)
    if km_name:
        entries.append(
            {
                "name": km_name,
                "role": ROLE_KM,
                "source": SOURCE_KM,
                "role_label": ROLE_KM,
            }
        )

    vks_name: str = normalize_person_name(vks)
    if vks_name:
        entries.append(
            {
                "name": vks_name,
                "role": ROLE_VKS,
                "source": SOURCE_VKS,
                "role_label": ROLE_VKS,
            }
        )

    return merge_person_roles(entries)


def build_team_lookups(
    config: dict[str, Any],
) -> tuple[dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]]]:
    """Загружает файлы и строит lookup лидеров лида и сделки."""
    if not is_team_files_enabled(config):
        return {}, {}
    lead_df, deal_df = load_team_frames(config)
    lead_lookup = build_leader_lookup(
        lead_df, config, id_key="lead_id", source=SOURCE_LEAD_TEAM
    )
    deal_lookup = build_leader_lookup(
        deal_df, config, id_key="deal_id", source=SOURCE_DEAL_TEAM
    )
    return lead_lookup, deal_lookup


def vks_column(config: dict[str, Any]) -> str | None:
    """Имя колонки ВКС или None."""
    if "vks" not in config.get("columns", {}):
        return None
    return col(config, "vks")
