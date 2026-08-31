"""Применение фильтров из config.json."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.settings import filter_column_name, filter_column_names

logger: logging.Logger = logging.getLogger("kanban.filters")


def is_exclude_filter(flt: dict[str, Any]) -> bool:
    """True — фильтр исключает строки по equals/contains в колонке (терминальные стадии)."""
    return (
        flt.get("filter_mode") == "exclude"
        or "exclude_contains" in flt
        or "exclude_equals" in flt
    )


def _text_match_mask(series: pd.Series, flt: dict[str, Any]) -> pd.Series:
    """Маска для contains / contains_all."""
    case: bool = bool(flt.get("case_sensitive", False))
    text: pd.Series = series.astype(str)
    if "contains_all" in flt:
        tokens: list[str] = [str(t) for t in flt["contains_all"] if str(t)]
        if not tokens:
            return pd.Series(True, index=series.index)
        mask: pd.Series = pd.Series(True, index=series.index)
        for token in tokens:
            mask &= text.str.contains(token, case=case, na=False)
        return mask
    if "contains" in flt:
        return text.str.contains(str(flt["contains"]), case=case, na=False)
    raise ValueError("Фильтр не содержит contains или contains_all")


def _mask_empty_column_values(series: pd.Series, config: dict[str, Any]) -> pd.Series:
    """Пустые значения колонки (—, nan, пусто) — не отсекаются фильтрами exclude."""
    raw_empty: list[Any] = config.get("processing", {}).get(
        "empty_stage_values", ["", "-", "nan", "None"]
    )
    empty: set[str] = {str(v) for v in raw_empty}
    lowered: set[str] = {v.lower() for v in empty}
    as_str: pd.Series = series.fillna("").astype(str).str.strip()
    return as_str.isin(empty) | as_str.str.lower().isin(lowered) | (as_str == "")


def exclude_match_mask(
    series: pd.Series,
    flt: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> pd.Series:
    """
    Маска строк, которые нужно исключить (equals / contains в колонке стадии).
    Пустая стадия (—, nan) никогда не считается терминальной.
    """
    case: bool = bool(flt.get("case_sensitive", False))
    text: pd.Series = series.fillna("").astype(str).str.strip()
    equals_token: str = str(flt.get("exclude_equals", "")).strip()
    contains_token: str = str(flt.get("exclude_contains", "")).strip()

    if equals_token:
        if case:
            match = text == equals_token
        else:
            match = text.str.casefold() == equals_token.casefold()
    elif contains_token:
        match = text.str.contains(contains_token, case=case, na=False)
    else:
        return pd.Series(False, index=series.index)

    if config is not None:
        match = match & ~_mask_empty_column_values(series, config)
    return match


def excluded_analysis_stages(config: dict[str, Any]) -> list[str]:
    """
    Стадии/статусы, выкинутые из анализа config-only exclude-фильтрами
    (например «К ПРОДАЖЕ» при exclude_current_for_sale).
    """
    stages: list[str] = []
    seen: set[str] = set()
    for _name, flt in config.get("filters", {}).items():
        if not isinstance(flt, dict):
            continue
        if not bool(flt.get("enabled", False)):
            continue
        if is_html_slice_filter(flt) or not is_exclude_filter(flt):
            continue
        column_key: str = str(flt.get("column_key", ""))
        if column_key not in {"current_status", "deal_stage"}:
            continue
        # Только точное равенство — убираем колонку стадии из UI/порядка
        token: str = str(flt.get("exclude_equals", "")).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        stages.append(token)
    return stages


def exclude_row_drop_mask(
    df: pd.DataFrame,
    flt: dict[str, Any],
    config: dict[str, Any],
) -> pd.Series:
    """
    Маска строк к удалению: подстрока найдена в основной колонке
    или в любой из also_column_keys (OR).
    """
    drop: pd.Series = pd.Series(False, index=df.index)
    for column in filter_column_names(config, flt):
        if column not in df.columns:
            continue
        drop |= exclude_match_mask(df[column], flt, config)
    return drop


def row_keep_mask(df: pd.DataFrame, column: str, flt: dict[str, Any], config: dict[str, Any] | None = None) -> pd.Series:
    """Маска строк, которые остаются после применения одного фильтра."""
    if is_exclude_filter(flt):
        if config is not None:
            return ~exclude_row_drop_mask(df, flt, config)
        return ~exclude_match_mask(df[column], flt, config)
    if "contains" in flt or "contains_all" in flt:
        return _text_match_mask(df[column], flt)
    value = flt.get("value", 1)
    return pd.to_numeric(df[column], errors="coerce") == value


def is_html_slice_filter(flt: dict[str, Any]) -> bool:
    """True — фильтр участвует в комбинациях JSON/HTML (переключатель в UI)."""
    return bool(flt.get("html_slice", True))


def default_html_active_filters(config: dict[str, Any]) -> list[str]:
    """Имена HTML-фильтров, включённых по умолчанию в UI (default_active)."""
    names: list[str] = []
    for name, flt in config.get("filters", {}).items():
        if (
            isinstance(flt, dict)
            and is_html_slice_filter(flt)
            and bool(flt.get("default_active", False))
        ):
            names.append(name)
    return sorted(names)


def enabled_terminal_exclusion_names(config: dict[str, Any]) -> list[str]:
    """Имена exclude-фильтров с enabled=true (Excel / менеджеры по умолчанию)."""
    names: list[str] = []
    for name, flt in config.get("filters", {}).items():
        if isinstance(flt, dict) and is_exclude_filter(flt) and bool(flt.get("enabled", False)):
            names.append(name)
    return sorted(names)


def split_active_filter_names(
    config: dict[str, Any],
    active_names: list[str],
) -> tuple[list[str], list[str]]:
    """Делит активные HTML-фильтры на включение и исключение терминальных стадий."""
    filters_cfg: dict[str, Any] = config.get("filters", {})
    inclusion: list[str] = []
    exclusion: list[str] = []
    for name in active_names:
        flt: dict[str, Any] | None = filters_cfg.get(name)
        if isinstance(flt, dict) and is_exclude_filter(flt):
            exclusion.append(name)
        else:
            inclusion.append(name)
    return inclusion, exclusion


def filter_terminal_deal_stage_rows(
    df: pd.DataFrame,
    config: dict[str, Any],
    exclusion_filter_names: list[str] | None = None,
) -> pd.DataFrame:
    """
    Убирает строки с терминальной стадией (конкретная дата отчёта).
    Для exclude_deal_otkaz — также «Текущий статус» с «отказ» (also_column_keys).
    Остальные строки того же лида (другие даты / стадии) сохраняются.
    """
    names: list[str]
    if exclusion_filter_names is not None:
        names = sorted(exclusion_filter_names)
    else:
        names = enabled_terminal_exclusion_names(config)
    if not names or df.empty:
        return df

    keep: pd.Series = pd.Series(True, index=df.index)
    filters_cfg: dict[str, Any] = config.get("filters", {})
    for name in names:
        flt: dict[str, Any] | None = filters_cfg.get(name)
        if not isinstance(flt, dict) or not is_exclude_filter(flt):
            continue
        keep &= ~exclude_row_drop_mask(df, flt, config)

    before: int = len(df)
    result: pd.DataFrame = df.loc[keep].reset_index(drop=True)
    if len(result) < before:
        logger.info(
            "Терминальные стадии: %d → %d строк (%s)",
            before,
            len(result),
            ", ".join(names),
        )
    return result


def _apply_filter_subset(
    df: pd.DataFrame,
    config: dict[str, Any],
    filters_cfg: dict[str, Any],
    *,
    include_filter: Any,
) -> tuple[pd.DataFrame, list[str]]:
    """Общая логика AND-фильтрации с предикатом include_filter(name, flt)."""
    result: pd.DataFrame = df.copy()
    active: list[str] = []

    for name, flt in filters_cfg.items():
        if not isinstance(flt, dict) or not include_filter(name, flt):
            continue

        if is_exclude_filter(flt):
            mask = ~exclude_row_drop_mask(result, flt, config)
        else:
            column = filter_column_name(config, flt)
            if not column:
                logger.warning("Фильтр '%s': не задан column_key/column, пропуск", name)
                continue
            if column not in result.columns:
                logger.warning("Колонка фильтра '%s' (%s) не найдена, пропуск", name, column)
                continue
            mask = row_keep_mask(result, column, flt, config)

        before: int = len(result)
        result = result[mask]
        active.append(name)
        mode_label: str = "искл." if is_exclude_filter(flt) else "вкл."
        logger.info("Фильтр '%s' (%s): %d -> %d строк", name, mode_label, before, len(result))

    return result.reset_index(drop=True), active


def apply_filters(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Оставляет строки после включённых фильтров Excel (без exclude — см. lead_tracker)."""
    filters_cfg: dict[str, Any] = config.get("filters", {})
    result, active = _apply_filter_subset(
        df,
        config,
        filters_cfg,
        include_filter=lambda _name, flt: bool(flt.get("enabled", False))
        and not is_exclude_filter(flt),
    )

    if active:
        logger.info("Применены фильтры (AND): %s", ", ".join(active))
    else:
        logger.info("Фильтры не активны, анализируются все строки")

    return result


def apply_config_only_filters(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """
    Фильтры только из config (html_slice: false), без комбинаций в JSON/UI.
    Exclude терминальных стадий сюда не входит — их применяет lead_tracker
    через enabled_terminal_exclusion_names.
    """
    filters_cfg: dict[str, Any] = config.get("filters", {})
    result, active = _apply_filter_subset(
        df,
        config,
        filters_cfg,
        include_filter=lambda _name, flt: bool(flt.get("enabled", False))
        and not is_html_slice_filter(flt)
        and not is_exclude_filter(flt),
    )

    if active:
        logger.info("Config-only фильтры (AND): %s", ", ".join(active))

    return result
