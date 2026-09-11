"""Загрузка команд лида/сделки и сбор актуальной команды по ID."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd

from src.performance import resolve_parallel_workers
from src.project_paths import resolve_path
from src.settings import col
from src.tab_number import normalize_team_tab_column

logger: logging.Logger = logging.getLogger("kanban.team_loader")

ROLE_KM: str = "КМ"
ROLE_VKS: str = "ВКС"
SOURCE_LEAD_TEAM: str = "lead_team"
SOURCE_DEAL_TEAM: str = "deal_team"
SOURCE_KM: str = "km"
SOURCE_VKS: str = "vks"

# Единый список файлов (лид + сделка в одном комплекте)
TEAM_FILES_KIND_UNIFIED: str = "files"
# Устаревшие раздельные списки (fallback, если files пуст)
TEAM_FILES_KIND_LEAD: str = "lead_team"
TEAM_FILES_KIND_DEAL: str = "deal_team"

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


def is_empty_token(value: Any) -> bool:
    """True для пустых / прочерков / NaN (тип команды, табельный и т.п.)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    token: str = str(value).strip().casefold()
    return token in EMPTY_NAME_TOKENS


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
    overrides: dict[str, Any] = team_files_config(config).get("columns") or {}
    result: dict[str, str] = dict(defaults)
    for key, value in overrides.items():
        if value:
            result[str(key)] = str(value)
    return result


def _team_type_value_sets(config: dict[str, Any]) -> dict[str, set[str]]:
    """
    Допустимые значения «Тип команды» в нормализованном виде (strip + casefold).
    lead=1, deal=2, unassigned=прочерк.
    """
    defaults: dict[str, list[Any]] = {
        "lead": [1, "1"],
        "deal": [2, "2"],
        "unassigned": ["-", "—", ""],
    }
    raw: Any = team_files_config(config).get("team_type_values") or {}
    overrides: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
    result: dict[str, set[str]] = {}
    for key, default_list in defaults.items():
        values: list[Any] = list(overrides.get(key) or default_list)
        result[key] = {str(v).strip().casefold() for v in values if str(v).strip() or key == "unassigned"}
        # пустая строка всегда в unassigned
        if key == "unassigned":
            result[key].add("")
    return result


def _normalize_team_type_token(value: Any) -> str:
    """Нормализует значение «Тип команды» к строке для сравнения."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    # Excel может отдать 1.0 / 2.0
    if isinstance(value, (int, float)) and float(value) == int(value):
        return str(int(value))
    text: str = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text.casefold() if text else ""


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


def team_filenames_for_mode(config: dict[str, Any], kind: str) -> list[str]:
    """Публичная обёртка: имена файлов команды для текущего mode."""
    return _resolve_team_filenames(config, kind)


def unified_team_filenames_for_mode(config: dict[str, Any]) -> list[str]:
    """Имена объединённых файлов команды (team_files.files) для текущего mode."""
    return _resolve_team_filenames(config, TEAM_FILES_KIND_UNIFIED)


def uses_unified_team_files(config: dict[str, Any]) -> bool:
    """True, если для текущего mode задан единый комплект files."""
    return bool(unified_team_filenames_for_mode(config))


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


def _normalize_id_token(value: Any) -> str:
    """
    Нормализует ID ПрПр / ID сделки для join.
    Убирает хвост «.0» у числовых значений из Excel (12345.0 → 12345).
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            as_float: float = float(value)
            if as_float == int(as_float):
                return str(int(as_float))
        except (ValueError, OverflowError):
            pass
    text: str = str(value).strip()
    if text.casefold() in EMPTY_NAME_TOKENS:
        return ""
    if text.endswith(".0"):
        head: str = text[:-2]
        if head.isdigit() or (head.startswith("-") and head[1:].isdigit()):
            return head
    return text


def _resolve_column_name(df: pd.DataFrame, expected: str) -> str | None:
    """
    Ищет колонку: точное имя → strip → casefold.
    Нужно из‑за пробелов/регистра в заголовках Excel.
    """
    if not expected:
        return None
    columns: list[str] = [str(c) for c in df.columns]
    if expected in df.columns:
        return expected
    expected_strip: str = expected.strip()
    for col_name in columns:
        if col_name.strip() == expected_strip:
            return col_name
    expected_fold: str = expected_strip.casefold()
    for col_name in columns:
        if col_name.strip().casefold() == expected_fold:
            return col_name
    return None


def _read_team_file(path: Path, config: dict[str, Any]) -> pd.DataFrame:
    """Читает один Excel файл команды (лист с заголовком, read_only)."""
    engine: str = str(config.get("excel", {}).get("engine", "openpyxl"))
    na_values: list[str] = list(config.get("excel", {}).get("na_values", [""]))
    read_kwargs: dict[str, Any] = {
        "engine": engine,
        "na_values": na_values,
    }
    if engine == "openpyxl":
        excel_cfg: dict[str, Any] = config.get("excel") or {}
        read_kwargs["engine_kwargs"] = {
            "read_only": bool(excel_cfg.get("read_only", True)),
            "data_only": bool(excel_cfg.get("data_only", True)),
            "keep_links": bool(excel_cfg.get("keep_links", False)),
        }
    df: pd.DataFrame = pd.read_excel(path, **read_kwargs)
    # Убираем пробелы в заголовках (частая причина «нет колонки Тип команды»)
    rename_map: dict[str, str] = {}
    for col_name in df.columns:
        stripped: str = str(col_name).strip()
        if stripped != str(col_name):
            rename_map[col_name] = stripped
    if rename_map:
        df = df.rename(columns=rename_map)
        logger.info(
            "Команда: обрезаны пробелы в заголовках (%d шт.) в %s",
            len(rename_map),
            path.name,
        )
    # Убираем безымянные/пустые колонки
    drop_cols: list[str] = [
        c for c in df.columns if str(c).strip() == "" or str(c).startswith("Unnamed")
    ]
    if drop_cols:
        df = df.drop(columns=drop_cols)
    return df


def _filter_team_frame_leaders_only(
    frame: pd.DataFrame,
    config: dict[str, Any],
    *,
    source_label: str,
) -> pd.DataFrame:
    """
    Оставляет только строки «Лидер∈leader_values».

    Дальше pipeline использует команду исключительно для lookup лидеров
    (ФИО/ТН/роль/ТБ). Участники без флага «Лидер» в расчёты не входят —
    отсев здесь безопасен и экономит RAM до concat.
    """
    tf_cfg: dict[str, Any] = team_files_config(config)
    if not bool(tf_cfg.get("keep_leaders_only", True)):
        return frame
    if frame.empty:
        return frame

    cols: dict[str, str] = _team_column_map(config)
    leader_expected: str = cols.get("is_leader", "Лидер")
    leader_col: str | None = _resolve_column_name(frame, leader_expected)
    if leader_col is None:
        logger.warning(
            "Команда (%s): keep_leaders_only — нет колонки «%s», фильтр пропущен",
            source_label,
            leader_expected,
        )
        return frame

    leader_values: set[str] = _leader_value_set(config)
    before: int = len(frame)
    leader_text: pd.Series = (
        frame[leader_col].astype("string").fillna("").astype(str).str.strip().str.casefold()
    )
    filtered: pd.DataFrame = frame.loc[leader_text.isin(leader_values)].copy()
    removed: int = before - len(filtered)
    if removed > 0:
        logger.info(
            "Команда (%s): keep_leaders_only %s → %s строк (−%s не-лидеров)",
            source_label,
            f"{before:,}",
            f"{len(filtered):,}",
            f"{removed:,}",
        )
    return filtered


def _load_one_team_file(path: Path, name: str, config: dict[str, Any]) -> pd.DataFrame:
    """Читает один файл команды, сразу оставляет лидеров, помечает source_file."""
    frame: pd.DataFrame = _read_team_file(path, config)
    frame = _filter_team_frame_leaders_only(frame, config, source_label=name)
    frame["source_file"] = name
    return frame


def _load_team_file_list(
    config: dict[str, Any],
    filenames: list[str],
    *,
    label: str,
) -> pd.DataFrame:
    """Загружает и склеивает список файлов команды."""
    if not filenames:
        return pd.DataFrame()

    input_dir: Path = _input_dir(config)
    mode: str = str(config.get("mode", "test"))
    paths: list[tuple[Path, str]] = []
    for name in filenames:
        path: Path = input_dir / name
        if not path.is_file():
            raise FileNotFoundError(
                f"Файл команды {label} не найден: {path} "
                f"(режим: {mode}, каталог: {input_dir})"
            )
        paths.append((path, name))

    perf: dict[str, Any] = config.get("performance", {})
    parallel: bool = bool(perf.get("parallel_team_files", True))
    workers: int = resolve_parallel_workers(config)
    frames: list[pd.DataFrame] = []

    if parallel and workers > 1 and len(paths) > 1:
        logger.info(
            "Команда %s: загрузка %s файлов (workers=%s)…",
            label,
            len(paths),
            min(workers, len(paths)),
        )
        with ThreadPoolExecutor(max_workers=min(workers, len(paths))) as pool:
            futures = {
                pool.submit(_load_one_team_file, path, name, config): name
                for path, name in paths
            }
            done_n: int = 0
            for future in as_completed(futures):
                name = futures[future]
                frame = future.result()
                frames.append(frame)
                done_n += 1
                logger.info(
                    "Команда %s: [%s/%s] %s — %s строк",
                    label,
                    done_n,
                    len(paths),
                    name,
                    f"{len(frame):,}",
                )
    else:
        for i, (path, name) in enumerate(paths, start=1):
            logger.info(
                "Команда %s: [%s/%s] читаю %s…",
                label,
                i,
                len(paths),
                name,
            )
            frame = _load_one_team_file(path, name, config)
            frames.append(frame)
            logger.info("Команда %s: %s — %s строк", label, name, f"{len(frame):,}")

    combined: pd.DataFrame = pd.concat(frames, ignore_index=True)
    cols: dict[str, str] = _team_column_map(config)
    tn_expected: str = cols.get("member_tab_number", "")
    tn_col: str | None = _resolve_column_name(combined, tn_expected) if tn_expected else None
    if tn_col:
        combined = normalize_team_tab_column(combined, tn_col)
    elif tn_expected:
        logger.warning(
            "Команда %s: колонка ТН «%s» не найдена среди %s",
            label,
            tn_expected,
            list(combined.columns)[:20],
        )
    logger.info(
        "Команда %s: загружено %d файлов, всего %s строк",
        label,
        len(frames),
        f"{len(combined):,}",
    )
    return combined


def split_team_frames_by_type(
    combined: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Делит объединённый файл по колонке «Тип команды»:
    1 → команда лида, 2 → команда сделки.
    Тип и ТН = «-» → лид не взят в работу (не попадает в lookup лидеров;
    КМ/ВКС берутся из канбана, если лидеров нет).
    """
    if combined.empty:
        return pd.DataFrame(), pd.DataFrame()

    cols: dict[str, str] = _team_column_map(config)
    type_expected: str = cols.get("team_type", "Тип команды")
    tn_expected: str = cols.get("member_tab_number", "Табельный номер участника команды")
    type_sets: dict[str, set[str]] = _team_type_value_sets(config)

    type_col: str | None = _resolve_column_name(combined, type_expected)
    tn_col: str | None = _resolve_column_name(combined, tn_expected)

    if type_col is None:
        sample_cols: list[str] = [str(c) for c in combined.columns][:30]
        logger.error(
            "Команда (объединённая): нет колонки «%s» — split невозможен, "
            "лидеры лида/сделки будут пустыми. Доступные колонки: %s",
            type_expected,
            sample_cols,
        )
        return pd.DataFrame(), pd.DataFrame()

    if type_col != type_expected:
        logger.info(
            "Команда (объединённая): колонка типа найдена как «%s» (ожидали «%s»)",
            type_col,
            type_expected,
        )

    work: pd.DataFrame = combined.copy()
    type_norm: pd.Series = work[type_col].map(_normalize_team_type_token)
    work["_team_type_norm"] = type_norm

    # Диагностика распределения типов (топ значений)
    value_counts: dict[str, int] = {
        str(k): int(v) for k, v in type_norm.value_counts(dropna=False).head(15).items()
    }
    logger.info(
        "Команда (объединённая): распределение «%s» (норм.): %s",
        type_col,
        value_counts,
    )

    if tn_col:
        tn_empty: pd.Series = work[tn_col].map(is_empty_token)
    else:
        logger.warning(
            "Команда (объединённая): нет колонки ТН «%s» — "
            "признак «не взят в работу» только по пустому типу",
            tn_expected,
        )
        tn_empty = pd.Series(True, index=work.index)

    type_empty: pd.Series = type_norm.map(lambda t: t in type_sets["unassigned"] or t == "")
    unassigned_mask: pd.Series = type_empty & tn_empty
    unassigned_count: int = int(unassigned_mask.sum())
    if unassigned_count:
        logger.info(
            "Команда (объединённая): %s строк без команды (Тип=«-» и ТН=«-») — "
            "лид не взят в работу, лидеры не подливаются; КМ/ВКС из канбана",
            f"{unassigned_count:,}",
        )

    lead_mask: pd.Series = type_norm.isin(type_sets["lead"])
    deal_mask: pd.Series = type_norm.isin(type_sets["deal"])
    other_mask: pd.Series = ~(lead_mask | deal_mask | unassigned_mask)
    other_count: int = int(other_mask.sum())
    if other_count:
        sample: list[str] = sorted({str(v) for v in type_norm.loc[other_mask].unique()})[:10]
        logger.warning(
            "Команда (объединённая): %s строк с неизвестным «%s»=%s — пропущены "
            "(ожидали lead=%s, deal=%s)",
            f"{other_count:,}",
            type_col,
            sample,
            sorted(type_sets["lead"]),
            sorted(type_sets["deal"]),
        )

    lead_df: pd.DataFrame = work.loc[lead_mask].drop(columns=["_team_type_norm"], errors="ignore")
    deal_df: pd.DataFrame = work.loc[deal_mask].drop(columns=["_team_type_norm"], errors="ignore")
    logger.info(
        "Команда (объединённая): тип=1 (лид) %s строк, тип=2 (сделка) %s строк",
        f"{len(lead_df):,}",
        f"{len(deal_df):,}",
    )
    if lead_df.empty and deal_df.empty:
        logger.error(
            "Команда (объединённая): после split оба кадра пусты — "
            "проверьте значения «%s» (сейчас %s) и team_type_values в config",
            type_col,
            value_counts,
        )
    return lead_df.reset_index(drop=True), deal_df.reset_index(drop=True)


def load_team_frames(config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Загружает файлы команд и возвращает (lead_df, deal_df).
    Приоритет: единый комплект team_files.files + split по «Тип команды»;
    иначе устаревшие lead_team / deal_team.
    """
    from src.debug_trace import procedure

    if not is_team_files_enabled(config):
        logger.debug("load_team_frames: team_files выключены")
        return pd.DataFrame(), pd.DataFrame()

    unified_names: list[str] = unified_team_filenames_for_mode(config)
    if unified_names:
        with procedure(
            logger,
            "load_team_frames.unified",
            files=len(unified_names),
            mode=str(config.get("mode", "")),
        ):
            combined: pd.DataFrame = _load_team_file_list(
                config, unified_names, label="лида и сделки"
            )
            lead_df, deal_df = split_team_frames_by_type(combined, config)
        return lead_df, deal_df

    with procedure(logger, "load_team_frames.legacy"):
        lead_df = load_team_kind_frames(config, TEAM_FILES_KIND_LEAD)
        deal_df = load_team_kind_frames(config, TEAM_FILES_KIND_DEAL)
    return lead_df, deal_df


def load_team_kind_frames(config: dict[str, Any], kind: str) -> pd.DataFrame:
    """
    Загружает кадр одного типа команды (lead_team | deal_team).
    При едином комплекте files — читает его и фильтрует по «Тип команды».
    """
    if not is_team_files_enabled(config):
        return pd.DataFrame()
    if kind not in {TEAM_FILES_KIND_LEAD, TEAM_FILES_KIND_DEAL}:
        raise ValueError("kind должен быть 'lead_team' или 'deal_team'")

    if uses_unified_team_files(config):
        lead_df, deal_df = load_team_frames(config)
        return lead_df if kind == TEAM_FILES_KIND_LEAD else deal_df

    label: str = "лида" if kind == TEAM_FILES_KIND_LEAD else "сделки"
    filenames: list[str] = _resolve_team_filenames(config, kind)
    return _load_team_file_list(config, filenames, label=label)


def pick_leaders_on_latest_dates(
    work: pd.DataFrame,
    *,
    id_col: str = "_id",
    report_date_col: str = "_date",
    team_added_col: str | None = "_team_added",
    source: str = "lead",
) -> pd.DataFrame:
    """
    Среди лидеров: max(Дата отчета), затем max(Дата добавления в команду).
    Несколько строк с одинаковой парой дат — все остаются (склейка снаружи).
    Нет колонки / все даты добавления пустые — остаются все на max дате отчёта.
    """
    if work.empty:
        return work

    max_report: pd.Series = work.groupby(id_col, sort=False)[report_date_col].transform("max")
    latest: pd.DataFrame = work.loc[work[report_date_col] == max_report].copy()
    if latest.empty:
        return latest

    if not team_added_col or team_added_col not in latest.columns:
        return latest

    added: pd.Series = latest[team_added_col]
    has_any_added: pd.Series = added.notna().groupby(latest[id_col], sort=False).transform("any")
    if not bool(has_any_added.any()):
        return latest

    max_added: pd.Series = added.groupby(latest[id_col], sort=False).transform("max")
    # Есть хотя бы одна дата добавления → только строки с max; иначе все на max отчёта
    keep: pd.Series = (~has_any_added) | (added == max_added)
    before: int = len(latest)
    latest = latest.loc[keep].copy()
    if len(latest) < before:
        logger.info(
            "Команда (%s): отбор по дате добавления в команду: %d → %d строк",
            source,
            before,
            len(latest),
        )
    return latest


def build_leader_lookup(
    df: pd.DataFrame,
    config: dict[str, Any],
    *,
    id_key: str,
    source: str,
) -> dict[str, list[dict[str, str]]]:
    """
    Словарь id → список лидеров на max(дата отчёта), затем max(дата добавления).
    Нет колонки даты отчёта — весь файл считаем одной датой (не ошибка).
    id_key: lead_id | deal_id из карты колонок команды.
    """
    if df.empty:
        return {}

    cols: dict[str, str] = _team_column_map(config)
    id_col: str | None = _resolve_column_name(df, cols[id_key])
    date_col: str | None = _resolve_column_name(df, cols["report_date"])
    added_expected: str = cols.get("team_added_date", "Дата добавления в команду")
    added_col: str | None = _resolve_column_name(df, added_expected)
    member_col: str | None = _resolve_column_name(df, cols["member"])
    role_col: str | None = _resolve_column_name(df, cols["role"])
    leader_col: str | None = _resolve_column_name(df, cols["is_leader"])
    leader_values: set[str] = _leader_value_set(config)

    needed_map: dict[str, str | None] = {
        cols[id_key]: id_col,
        cols["member"]: member_col,
        cols["is_leader"]: leader_col,
    }
    missing: list[str] = [name for name, resolved in needed_map.items() if resolved is None]
    if missing:
        logger.warning(
            "Команда (%s): нет колонок %s среди %s — lookup пуст",
            source,
            missing,
            list(df.columns)[:25],
        )
        return {}

    assert id_col and member_col and leader_col

    work: pd.DataFrame = df.copy()
    work["_is_leader"] = work[leader_col].map(lambda v: _is_leader_value(v, leader_values))
    before_leader: int = len(work)
    work = work.loc[work["_is_leader"]].copy()
    if work.empty:
        logger.warning(
            "Команда (%s): нет строк с Лидер∈%s (%d → 0) — lookup пуст",
            source,
            sorted(leader_values),
            before_leader,
        )
        return {}

    work["_id"] = work[id_col].map(_normalize_id_token)
    work = work.loc[work["_id"] != ""].copy()
    work["_name"] = work[member_col].map(normalize_person_name)
    work = work.loc[work["_name"] != ""].copy()
    work["_role"] = (
        work[role_col].map(lambda v: " ".join(str(v).split()).strip() if pd.notna(v) else "")
        if role_col and role_col in work.columns
        else ""
    )

    if date_col is not None:
        work["_date"] = pd.to_datetime(work[date_col], errors="coerce")
        work = work.dropna(subset=["_date"])
        if work.empty:
            logger.warning(
                "Команда (%s): после отбора лидеров/дат кадр пуст — lookup пуст",
                source,
            )
            return {}
    else:
        work["_date"] = pd.Timestamp("1970-01-01")
        logger.info(
            "Команда (%s): нет «%s» — весь файл считаем одной датой отчёта",
            source,
            cols["report_date"],
        )

    team_added_key: str | None
    if added_col:
        work["_team_added"] = pd.to_datetime(work[added_col], errors="coerce")
        team_added_key = "_team_added"
    else:
        team_added_key = None

    latest: pd.DataFrame = pick_leaders_on_latest_dates(
        work,
        id_col="_id",
        report_date_col="_date",
        team_added_col=team_added_key,
        source=source,
    )

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
    Если лид не взят в работу (в файле команды Тип/ТН = «-»), lookup лидеров
    пуст — остаются КМ и ВКС из канбана.
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
