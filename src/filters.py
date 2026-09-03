"""Применение фильтров из config (универсальная схема + legacy-адаптер)."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

import pandas as pd

from src.data_audit import audit_rows
from src.date_utils import parse_date_column
from src.settings import filter_column_name, filter_column_names

logger: logging.Logger = logging.getLogger("kanban.filters")

_UNIVERSAL_KEYS: frozenset[str] = frozenset(
    {"action", "match", "values", "values_mode", "value_type"}
)


def _has_legacy_match_keys(flt: dict[str, Any]) -> bool:
    """True — в фильтре есть старые ключи совпадения."""
    return any(
        key in flt
        for key in (
            "value",
            "contains",
            "contains_all",
            "contains_any",
            "exclude_contains",
            "exclude_equals",
            "filter_mode",
        )
    )


def _infer_value_type(values: list[Any]) -> str:
    """Эвристика value_type по первому непустому эталону."""
    for raw in values:
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            continue
        if isinstance(raw, bool):
            return "number"
        if isinstance(raw, (int, float)):
            return "number"
        text: str = str(raw).strip()
        if not text:
            continue
        # Дата: несколько числовых групп с разделителями
        normalized: str = text.replace("/", ".").replace("-", ".")
        digit_groups: int = sum(1 for part in normalized.split(".") if part.isdigit())
        if digit_groups >= 2 and any(sep in text for sep in ("/", "-", ".")):
            return "date"
        try:
            float(text.replace(",", "."))
            return "number"
        except ValueError:
            return "string"
    return "string"


def normalize_filter(flt: dict[str, Any]) -> dict[str, Any]:
    """
    Приводит описание фильтра к универсальной схеме.
    Legacy-ключи (value / contains* / exclude_*) конвертируются.
    """
    if not isinstance(flt, dict):
        raise TypeError("Фильтр должен быть dict")

    # Уже универсальный (есть values + не только legacy) — дополняем умолчаниями
    if "values" in flt and not _has_legacy_match_keys(flt):
        out: dict[str, Any] = deepcopy(flt)
        out.setdefault("action", "include")
        out.setdefault("match", "equals")
        out.setdefault("values_mode", "any")
        out.setdefault("value_type", "auto")
        out.setdefault("case_sensitive", False)
        if "column_keys" not in out and out.get("also_column_keys"):
            out["column_keys"] = list(out["also_column_keys"])
        return out

    # Смешанный или legacy → собираем universal поверх копии
    out = deepcopy(flt)
    case_sensitive: bool = bool(flt.get("case_sensitive", False))
    out["case_sensitive"] = case_sensitive

    # column_keys из also_column_keys
    if "column_keys" not in out and flt.get("also_column_keys"):
        out["column_keys"] = list(flt["also_column_keys"])

    # action
    if flt.get("action") in {"include", "exclude"}:
        action: str = str(flt["action"])
    elif (
        flt.get("filter_mode") == "exclude"
        or "exclude_contains" in flt
        or "exclude_equals" in flt
    ):
        action = "exclude"
    else:
        action = "include"
    out["action"] = action

    values: list[Any] = []
    match: str = "equals"
    values_mode: str = "any"
    value_type: str = "auto"

    if "values" in flt and isinstance(flt["values"], list) and not _has_legacy_match_keys(flt):
        values = list(flt["values"])
        match = str(flt.get("match", "equals"))
        values_mode = str(flt.get("values_mode", "any"))
        value_type = str(flt.get("value_type", "auto"))
    elif "exclude_equals" in flt:
        values = [flt["exclude_equals"]]
        match = "equals"
        value_type = "string"
    elif "exclude_contains" in flt:
        values = [flt["exclude_contains"]]
        match = "contains"
        value_type = "string"
    elif "contains_any" in flt:
        values = list(flt["contains_any"] or [])
        match = "contains"
        values_mode = "any"
        value_type = "string"
    elif "contains_all" in flt:
        values = list(flt["contains_all"] or [])
        match = "contains"
        values_mode = "all"
        value_type = "string"
    elif "contains" in flt:
        values = [flt["contains"]]
        match = "contains"
        values_mode = "any"
        value_type = "string"
    elif "value" in flt:
        values = [flt["value"]]
        match = "equals"
        values_mode = "any"
        value_type = "number"
    elif "values" in flt:
        values = list(flt.get("values") or [])
        match = str(flt.get("match", "equals"))
        values_mode = str(flt.get("values_mode", "any"))
        value_type = str(flt.get("value_type", "auto"))
    else:
        # Пустой фильтр без критериев — не отсекает
        values = []
        match = str(flt.get("match", "equals"))
        values_mode = str(flt.get("values_mode", "any"))
        value_type = str(flt.get("value_type", "auto"))

    # Явные поля нового формата поверх legacy, если заданы вместе
    if "match" in flt and "values" in flt:
        match = str(flt["match"])
    if "values_mode" in flt and "values" in flt:
        values_mode = str(flt["values_mode"])
    if "value_type" in flt and ("values" in flt or "value" in flt):
        value_type = str(flt["value_type"])

    out["values"] = values
    out["match"] = match if match in {"equals", "contains"} else "equals"
    out["values_mode"] = values_mode if values_mode in {"any", "all"} else "any"
    out["value_type"] = value_type if value_type in {"string", "number", "date", "auto"} else "auto"
    return out


def is_exclude_filter(flt: dict[str, Any]) -> bool:
    """True — фильтр исключает совпавшие строки (action=exclude или legacy)."""
    if not isinstance(flt, dict):
        return False
    if flt.get("action") == "exclude":
        return True
    return (
        flt.get("filter_mode") == "exclude"
        or "exclude_contains" in flt
        or "exclude_equals" in flt
    )


def _resolve_value_type(flt: dict[str, Any]) -> str:
    """Итоговый value_type после auto."""
    declared: str = str(flt.get("value_type", "auto"))
    values: list[Any] = list(flt.get("values") or [])
    if declared == "auto":
        return _infer_value_type(values)
    if declared in {"string", "number", "date"}:
        return declared
    return _infer_value_type(values)


def _string_series(series: pd.Series) -> pd.Series:
    """Строковое представление ячеек без изменения индекса."""
    return series.fillna("").astype(str)


def _coerce_tokens(values: list[Any]) -> list[str]:
    """Строковые эталоны без пустых (числа/bool сохраняются как str)."""
    tokens: list[str] = []
    for v in values:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        if isinstance(v, (int, float, bool)):
            tokens.append(str(v))
            continue
        token: str = str(v).strip()
        if token == "":
            continue
        tokens.append(token)
    return tokens


def _match_string(
    series: pd.Series,
    values: list[Any],
    *,
    match: str,
    values_mode: str,
    case_sensitive: bool,
) -> pd.Series:
    """Маска совпадения для строкового типа."""
    tokens: list[str] = _coerce_tokens(values)
    if not tokens:
        return pd.Series(True, index=series.index)

    text: pd.Series = _string_series(series)
    parts: list[pd.Series]
    if match == "equals":
        if case_sensitive:
            parts = [text.str.strip() == t for t in tokens]
        else:
            folded: pd.Series = text.str.strip().str.casefold()
            parts = [folded == t.casefold() for t in tokens]
    else:
        parts = [
            text.str.contains(t, case=case_sensitive, na=False, regex=False) for t in tokens
        ]

    result: pd.Series = parts[0].copy()
    for part in parts[1:]:
        if values_mode == "all":
            result &= part
        else:
            result |= part
    return result


def _match_number(
    series: pd.Series,
    values: list[Any],
    *,
    match: str,
    values_mode: str,
) -> pd.Series:
    """Маска совпадения для числового типа (equals; contains → как string)."""
    if match == "contains":
        logger.warning("value_type=number с match=contains: сравнение как string")
        return _match_string(
            series,
            values,
            match="contains",
            values_mode=values_mode,
            case_sensitive=False,
        )

    nums: list[float] = []
    for v in values:
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            continue
    if not nums:
        return pd.Series(True, index=series.index)

    col_num: pd.Series = pd.to_numeric(series, errors="coerce")
    parts: list[pd.Series] = [col_num == n for n in nums]
    result: pd.Series = parts[0].fillna(False)
    for part in parts[1:]:
        if values_mode == "all":
            result &= part.fillna(False)
        else:
            result |= part.fillna(False)
    return result


def _match_date(
    series: pd.Series,
    values: list[Any],
    config: dict[str, Any] | None,
    *,
    match: str,
    values_mode: str,
) -> pd.Series:
    """Маска совпадения для дат (equals по календарному дню; contains → string)."""
    if match == "contains":
        logger.warning("value_type=date с match=contains: сравнение как string")
        return _match_string(
            series,
            values,
            match="contains",
            values_mode=values_mode,
            case_sensitive=False,
        )

    cfg: dict[str, Any] = config or {}
    parsed_col: pd.Series = parse_date_column(series, cfg, "filter_date")
    day_col: pd.Series = parsed_col.dt.normalize()

    ref_days: list[pd.Timestamp] = []
    for v in values:
        ref_series: pd.Series = parse_date_column(pd.Series([v]), cfg, "filter_date_value")
        if ref_series.notna().any():
            ref_days.append(pd.Timestamp(ref_series.iloc[0]).normalize())

    if not ref_days:
        return pd.Series(True, index=series.index)

    parts: list[pd.Series] = [(day_col == d) for d in ref_days]
    result: pd.Series = parts[0].fillna(False)
    for part in parts[1:]:
        if values_mode == "all":
            result &= part.fillna(False)
        else:
            result |= part.fillna(False)
    return result


def build_match_mask(
    series: pd.Series,
    flt: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> pd.Series:
    """
    Маска строк, совпавших с критериями универсального фильтра
    (после normalize_filter). Пустой values → всё True (не отсекает).
    """
    uni: dict[str, Any] = normalize_filter(flt)
    values: list[Any] = list(uni.get("values") or [])
    if not values:
        logger.warning("Фильтр без values — строки не отсекаются")
        return pd.Series(True, index=series.index)

    match: str = str(uni.get("match", "equals"))
    values_mode: str = str(uni.get("values_mode", "any"))
    case_sensitive: bool = bool(uni.get("case_sensitive", False))
    value_type: str = _resolve_value_type(uni)

    if value_type == "number":
        return _match_number(series, values, match=match, values_mode=values_mode)
    if value_type == "date":
        return _match_date(
            series,
            values,
            config,
            match=match,
            values_mode=values_mode,
        )
    return _match_string(
        series,
        values,
        match=match,
        values_mode=values_mode,
        case_sensitive=case_sensitive,
    )


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
    Маска строк, которые нужно исключить.
    Пустая стадия (—, nan) никогда не считается терминальной.
    """
    uni: dict[str, Any] = normalize_filter(flt)
    match = build_match_mask(series, uni, config)
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
        uni: dict[str, Any] = normalize_filter(flt)
        column_key: str = str(uni.get("column_key", ""))
        if column_key not in {"current_status", "deal_stage"}:
            continue
        # Только точное равенство — убираем колонку стадии из UI/порядка
        if str(uni.get("match", "")) != "equals":
            continue
        for raw in uni.get("values") or []:
            token: str = str(raw).strip()
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
    Маска строк к удалению: совпадение в основной колонке
    или в любой из column_keys / also_column_keys (OR).
    """
    uni: dict[str, Any] = normalize_filter(flt)
    drop: pd.Series = pd.Series(False, index=df.index)
    for column in filter_column_names(config, uni):
        if column not in df.columns:
            continue
        drop |= exclude_match_mask(df[column], uni, config)
    return drop


def row_keep_mask(
    df: pd.DataFrame,
    column: str,
    flt: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> pd.Series:
    """Маска строк, которые остаются после применения одного фильтра."""
    uni: dict[str, Any] = normalize_filter(flt)
    if is_exclude_filter(uni):
        if config is not None:
            return ~exclude_row_drop_mask(df, uni, config)
        return ~exclude_match_mask(df[column], uni, config)

    # include: совпадение в основной или любой доп. колонке (OR)
    if config is not None:
        columns: list[str] = filter_column_names(config, uni)
        if columns:
            keep: pd.Series = pd.Series(False, index=df.index)
            any_col: bool = False
            for col_name in columns:
                if col_name not in df.columns:
                    continue
                any_col = True
                keep |= build_match_mask(df[col_name], uni, config)
            if any_col:
                return keep
    return build_match_mask(df[column], uni, config)


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
    *,
    audit_each_filter: bool = False,
    funnel: list[dict[str, Any]] | None = None,
    group_auditor: Any = None,
) -> pd.DataFrame:
    """
    Убирает строки с терминальной стадией (конкретная дата отчёта).
    Для exclude_deal_otkaz — также «Текущий статус» с «отказ» (column_keys).
    Остальные строки того же лида (другие даты / стадии) сохраняются.
    """
    from src.filter_funnel import append_funnel_step

    names: list[str]
    if exclusion_filter_names is not None:
        names = sorted(exclusion_filter_names)
    else:
        names = enabled_terminal_exclusion_names(config)
    if not names or df.empty:
        return df

    result: pd.DataFrame = df
    filters_cfg: dict[str, Any] = config.get("filters", {})
    for name in names:
        flt: dict[str, Any] | None = filters_cfg.get(name)
        if not isinstance(flt, dict) or not is_exclude_filter(flt):
            continue
        before_df: pd.DataFrame = result
        before: int = len(result)
        mask: pd.Series = ~exclude_row_drop_mask(result, flt, config)
        result = result.loc[mask]
        after: int = len(result)
        logger.info("Фильтр '%s' (искл.): %d -> %d строк", name, before, after)
        append_funnel_step(
            funnel,
            stage=f"Исключение: {name}",
            before_df=before_df,
            after_df=result,
            config=config,
            kind="exclude",
            filter_name=name,
            group_auditor=group_auditor,
        )
        if audit_each_filter:
            audit_rows(
                f"exclude:{name}",
                before,
                after,
                config,
                reason=f"фильтр '{name}' (exclude)",
            )

    return result.reset_index(drop=True)


def _apply_filter_subset(
    df: pd.DataFrame,
    config: dict[str, Any],
    filters_cfg: dict[str, Any],
    *,
    include_filter: Any,
    audit_each_filter: bool = False,
    funnel: list[dict[str, Any]] | None = None,
    group_auditor: Any = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Общая логика AND-фильтрации с предикатом include_filter(name, flt)."""
    from src.filter_funnel import append_funnel_step

    result: pd.DataFrame = df
    active: list[str] = []

    for name, flt in filters_cfg.items():
        if not isinstance(flt, dict) or not include_filter(name, flt):
            continue

        uni: dict[str, Any] = normalize_filter(flt)
        if is_exclude_filter(uni):
            mask = ~exclude_row_drop_mask(result, uni, config)
        else:
            column = filter_column_name(config, uni)
            if not column:
                logger.warning("Фильтр '%s': не задан column_key/column, пропуск", name)
                continue
            if column not in result.columns:
                logger.warning("Колонка фильтра '%s' (%s) не найдена, пропуск", name, column)
                continue
            mask = row_keep_mask(result, column, uni, config)

        before_df: pd.DataFrame = result
        before: int = len(result)
        result = result.loc[mask]
        after: int = len(result)
        active.append(name)
        mode_label: str = "искл." if is_exclude_filter(uni) else "вкл."
        logger.info("Фильтр '%s' (%s): %d -> %d строк", name, mode_label, before, after)
        append_funnel_step(
            funnel,
            stage=f"Фильтр: {name} ({mode_label})",
            before_df=before_df,
            after_df=result,
            config=config,
            kind="filter",
            filter_name=name,
            group_auditor=group_auditor,
        )
        if audit_each_filter:
            audit_rows(
                f"filter:{name}",
                before,
                after,
                config,
                reason=f"фильтр '{name}' ({mode_label})",
            )

    return result.reset_index(drop=True), active


def apply_filters(
    df: pd.DataFrame,
    config: dict[str, Any],
    *,
    audit_each_filter: bool = False,
    funnel: list[dict[str, Any]] | None = None,
    group_auditor: Any = None,
) -> pd.DataFrame:
    """Оставляет строки после включённых фильтров Excel (без exclude — см. lead_tracker)."""
    filters_cfg: dict[str, Any] = config.get("filters", {})
    result, active = _apply_filter_subset(
        df,
        config,
        filters_cfg,
        include_filter=lambda _name, flt: bool(flt.get("enabled", False))
        and not is_exclude_filter(flt),
        audit_each_filter=audit_each_filter,
        funnel=funnel,
        group_auditor=group_auditor,
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
