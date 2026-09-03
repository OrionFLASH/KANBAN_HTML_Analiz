"""Отсечение выбросов срока (дней) перед расчётом нормативов/статистики."""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from src.settings import col

logger: logging.Logger = logging.getLogger("kanban.outlier_clipping")

# Внутренние ключи аудита в строке агрегации
AUDIT_BEFORE: str = "outlier_before"
AUDIT_AFTER: str = "outlier_after"
AUDIT_CLIPPED: str = "outlier_clipped_total"
AUDIT_RULE_PREFIX: str = "outlier_rule_"


def _metric_days_aligned(series: pd.Series) -> pd.Series:
    """
    Целые дни с тем же индексом, что у исходной серии (NaN сохраняются).

    Нельзя использовать to_integer_days() здесь: он возвращает ndarray без NaN
    и ломает выравнивание маски с DataFrame группы (groupby → не-RangeIndex).
    """
    numeric: pd.Series = pd.to_numeric(series, errors="coerce")
    rounded: pd.Series = pd.Series(np.round(numeric), index=series.index, dtype="float64")
    return rounded


def outlier_clipping_config(config: dict[str, Any]) -> dict[str, Any]:
    """Блок outlier_clipping с умолчаниями."""
    raw: dict[str, Any] = dict(config.get("outlier_clipping") or {})
    return {
        "enabled": bool(raw.get("enabled", False)),
        "metric": str(raw.get("metric", "days_on_stage")),
        "export_audit": bool(raw.get("export_audit", True)),
        "min_group_size": int(raw.get("min_group_size", 5)),
        # Минимум лидов, которые должны остаться после правила; иначе правило не применяется
        "min_remaining": int(raw.get("min_remaining", 3)),
        "rules": list(raw.get("rules") or []),
    }


def enabled_rules(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Включённые правила в порядке config."""
    cfg: dict[str, Any] = outlier_clipping_config(config)
    if not cfg["enabled"]:
        return []
    result: list[dict[str, Any]] = []
    for idx, rule in enumerate(cfg["rules"]):
        if not isinstance(rule, dict) or not bool(rule.get("enabled", True)):
            continue
        name: str = str(rule.get("name") or f"rule_{idx + 1}").strip()
        if not name:
            name = f"rule_{idx + 1}"
        normalized: dict[str, Any] = dict(rule)
        normalized["name"] = name
        normalized["mode"] = str(rule.get("mode", "range")).strip().lower()
        result.append(normalized)
    return result


def audit_column_keys(config: dict[str, Any]) -> list[str]:
    """Порядок колонок аудита для экспорта."""
    cfg: dict[str, Any] = outlier_clipping_config(config)
    if not cfg["enabled"] or not cfg["export_audit"]:
        return []
    keys: list[str] = [AUDIT_BEFORE, AUDIT_AFTER, AUDIT_CLIPPED]
    for rule in enabled_rules(config):
        keys.append(f"{AUDIT_RULE_PREFIX}{rule['name']}")
    return keys


def build_outlier_audit_mapping(config: dict[str, Any]) -> dict[str, str]:
    """Mapping внутренних колонок аудита → заголовки Excel."""
    from src.filter_funnel import filter_audit_column_keys

    labels: dict[str, str] = config.get("output", {}).get("column_labels", {})
    has_input_filters: bool = bool(filter_audit_column_keys(config))
    mapping: dict[str, str] = {}
    for key in audit_column_keys(config):
        if key == AUDIT_BEFORE:
            default: str = "До выбросов" if has_input_filters else "До отсечения"
            mapping[key] = labels.get(key, default)
        elif key == AUDIT_AFTER:
            mapping[key] = labels.get(key, "После отсечения")
        elif key == AUDIT_CLIPPED:
            mapping[key] = labels.get(key, "Отсечено выбросами (всего)")
        elif key.startswith(AUDIT_RULE_PREFIX):
            rule_name: str = key[len(AUDIT_RULE_PREFIX) :]
            mapping[key] = labels.get(key, f"Отсечено: {rule_name}")
        else:
            mapping[key] = labels.get(key, key)
    return mapping


def _scope_values(raw: Any) -> list[str] | None:
    """None = любое значение; иначе список допустимых (str)."""
    if raw is None:
        return None
    if isinstance(raw, list):
        vals: list[str] = [str(v).strip() for v in raw if str(v).strip() != ""]
        return vals or None
    text: str = str(raw).strip()
    return [text] if text else None


def rule_applies_to_group(
    rule: dict[str, Any],
    group_keys: dict[str, Any],
    config: dict[str, Any],
) -> bool:
    """
    True, если scope правила покрывает ключи группы агрегации.
    Пустой scope {} — для всех групп.
    Ключи scope: product_group, product, current_status, deal_stage, stage_key, tb
    (имена — ключи columns / служебные поля records).
    """
    scope: dict[str, Any] = dict(rule.get("scope") or {})
    if not scope:
        return True

    # Соответствие ключ scope → значение в group_keys (имя колонки DataFrame)
    field_map: dict[str, str] = {}
    for key in ("product_group", "product", "tb", "deal_stage"):
        if key in config.get("columns", {}):
            field_map[key] = col(config, key)
    field_map["current_status"] = "current_status"
    field_map["stage_key"] = "stage_key"
    field_map["analysis_level"] = "analysis_level"

    for scope_key, expected_raw in scope.items():
        expected: list[str] | None = _scope_values(expected_raw)
        if expected is None:
            continue
        col_name: str = field_map.get(scope_key, scope_key)
        actual_raw: Any = group_keys.get(col_name, group_keys.get(scope_key))
        if actual_raw is None or (isinstance(actual_raw, float) and pd.isna(actual_raw)):
            return False
        actual: str = str(actual_raw).strip()
        # Сравнение без учёта регистра для удобства конфига
        expected_cf: set[str] = {e.casefold() for e in expected}
        if actual.casefold() not in expected_cf:
            return False
    return True


def _drop_mask_range(
    days: pd.Series,
    rule: dict[str, Any],
) -> pd.Series:
    """True — строку отсечь (вне [min_days, max_days])."""
    drop: pd.Series = pd.Series(False, index=days.index)
    if rule.get("min_days") is not None:
        try:
            min_days: float = float(rule["min_days"])
            drop |= days < min_days
        except (TypeError, ValueError):
            logger.warning("Правило '%s': некорректный min_days", rule.get("name"))
    if rule.get("max_days") is not None:
        try:
            max_days: float = float(rule["max_days"])
            drop |= days > max_days
        except (TypeError, ValueError):
            logger.warning("Правило '%s': некорректный max_days", rule.get("name"))
    # NaN срока не считаем выбросом range — оставляем (агрегатор всё равно отфильтрует)
    drop &= days.notna()
    return drop


def _drop_mask_percentile_trim(
    days: pd.Series,
    rule: dict[str, Any],
    *,
    min_group_size: int,
) -> pd.Series:
    """Отсечь нижние/верхние проценты по эмпирическим квантилям группы."""
    valid: pd.Series = days.dropna()
    if len(valid) < max(min_group_size, 3):
        return pd.Series(False, index=days.index)

    lower_pct: float = float(rule.get("trim_lower_pct") or 0.0)
    upper_pct: float = float(rule.get("trim_upper_pct") or 0.0)
    if lower_pct <= 0 and upper_pct <= 0:
        return pd.Series(False, index=days.index)

    low_thr: float | None = None
    high_thr: float | None = None
    arr: np.ndarray = valid.to_numpy(dtype=float)
    if lower_pct > 0:
        low_thr = float(np.nanpercentile(arr, lower_pct))
    if upper_pct > 0:
        high_thr = float(np.nanpercentile(arr, 100.0 - upper_pct))

    drop: pd.Series = pd.Series(False, index=days.index)
    if low_thr is not None:
        drop |= days < low_thr
    if high_thr is not None:
        drop |= days > high_thr
    drop &= days.notna()
    return drop


def _drop_mask_unique_days_trim(
    days: pd.Series,
    rule: dict[str, Any],
    *,
    min_group_size: int,
) -> pd.Series:
    """
    Отсечь крайние уникальные значения срока (дни, где есть лиды).

    Пример: 20 разных сроков в группе, trim_lower_pct=trim_upper_pct=10
    → убираем 2 самых маленьких и 2 самых больших уникальных дня
    (10% от числа уникальных значений), вместе со всеми лидами этих дней.
    """
    valid: pd.Series = days.dropna()
    if len(valid) < max(min_group_size, 3):
        return pd.Series(False, index=days.index)

    lower_pct: float = float(rule.get("trim_lower_pct") or 0.0)
    upper_pct: float = float(rule.get("trim_upper_pct") or 0.0)
    if lower_pct <= 0 and upper_pct <= 0:
        return pd.Series(False, index=days.index)

    # Уникальные сроки, по которым есть лиды (отсортированы)
    unique_days: np.ndarray = np.sort(np.unique(valid.to_numpy(dtype=float)))
    n_unique: int = int(unique_days.size)
    if n_unique < 2:
        return pd.Series(False, index=days.index)

    # Доля от числа уникальных значений (вниз до целого)
    lower_n: int = int(n_unique * lower_pct / 100.0) if lower_pct > 0 else 0
    upper_n: int = int(n_unique * upper_pct / 100.0) if upper_pct > 0 else 0
    if lower_n <= 0 and upper_n <= 0:
        return pd.Series(False, index=days.index)

    # Нельзя снять все уникальные значения
    if lower_n + upper_n >= n_unique:
        logger.debug(
            "unique_days_trim: lower_n+upper_n=%d >= n_unique=%d — пропуск",
            lower_n + upper_n,
            n_unique,
        )
        return pd.Series(False, index=days.index)

    drop_values: set[float] = set()
    if lower_n > 0:
        drop_values.update(float(v) for v in unique_days[:lower_n])
    if upper_n > 0:
        drop_values.update(float(v) for v in unique_days[-upper_n:])

    drop: pd.Series = days.isin(list(drop_values))
    drop &= days.notna()
    return drop


def _drop_mask_iqr(
    days: pd.Series,
    rule: dict[str, Any],
    *,
    min_group_size: int,
) -> pd.Series:
    """Классический IQR: вне [Q1 − k·IQR, Q3 + k·IQR]."""
    valid: pd.Series = days.dropna()
    if len(valid) < max(min_group_size, 4):
        return pd.Series(False, index=days.index)

    k: float = float(rule.get("iqr_k", 1.5))
    q1: float = float(np.nanpercentile(valid.to_numpy(dtype=float), 25))
    q3: float = float(np.nanpercentile(valid.to_numpy(dtype=float), 75))
    iqr: float = q3 - q1
    if iqr <= 0 or math.isnan(iqr):
        return pd.Series(False, index=days.index)

    low: float = q1 - k * iqr
    high: float = q3 + k * iqr
    drop: pd.Series = (days < low) | (days > high)
    drop &= days.notna()
    return drop


def clip_group_frame(
    group: pd.DataFrame,
    group_keys: dict[str, Any],
    config: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, int]]:
    """
    Применяет включённые правила к группе (последовательно).
    Возвращает (отфильтрованный DataFrame, audit dict).
    """
    cfg: dict[str, Any] = outlier_clipping_config(config)
    rules: list[dict[str, Any]] = enabled_rules(config)
    before: int = len(group)
    audit: dict[str, int] = {
        AUDIT_BEFORE: before,
        AUDIT_AFTER: before,
        AUDIT_CLIPPED: 0,
    }
    for rule in rules:
        audit[f"{AUDIT_RULE_PREFIX}{rule['name']}"] = 0

    if not rules or group.empty:
        return group, audit

    metric: str = cfg["metric"]
    if metric not in group.columns:
        logger.warning("outlier_clipping: метрика '%s' отсутствует в группе", metric)
        return group, audit

    work: pd.DataFrame = group
    min_group_size: int = int(cfg["min_group_size"])
    default_min_remaining: int = max(0, int(cfg["min_remaining"]))

    for rule in rules:
        if not rule_applies_to_group(rule, group_keys, config):
            continue
        days: pd.Series = _metric_days_aligned(work[metric])
        mode: str = str(rule.get("mode", "range"))
        if mode == "range":
            drop = _drop_mask_range(days, rule)
        elif mode in {"percentile_trim", "trim", "percentile"}:
            drop = _drop_mask_percentile_trim(days, rule, min_group_size=min_group_size)
        elif mode in {"unique_days_trim", "distinct_days_trim", "unique_value_trim"}:
            drop = _drop_mask_unique_days_trim(days, rule, min_group_size=min_group_size)
        elif mode == "iqr":
            drop = _drop_mask_iqr(days, rule, min_group_size=min_group_size)
        else:
            logger.warning("Правило '%s': неизвестный mode='%s'", rule.get("name"), mode)
            continue

        # Гарантируем выравнивание с текущим work (после предыдущих правил индекс мог ужаться)
        drop = drop.reindex(work.index, fill_value=False).astype(bool)

        clipped_n: int = int(drop.sum())
        if not clipped_n:
            continue

        remaining: int = len(work) - clipped_n
        min_remaining: int = default_min_remaining
        if rule.get("min_remaining") is not None:
            try:
                min_remaining = max(0, int(rule["min_remaining"]))
            except (TypeError, ValueError):
                logger.warning(
                    "Правило '%s': некорректный min_remaining, используем %s",
                    rule.get("name"),
                    default_min_remaining,
                )
                min_remaining = default_min_remaining

        if remaining < min_remaining:
            logger.debug(
                "Правило '%s' пропущено: после отсечения осталось бы %d < min_remaining=%d",
                rule.get("name"),
                remaining,
                min_remaining,
            )
            # В аудите 0 — правило не применено
            audit[f"{AUDIT_RULE_PREFIX}{rule['name']}"] = 0
            continue

        audit[f"{AUDIT_RULE_PREFIX}{rule['name']}"] = clipped_n
        work = work.loc[~drop].copy()

    after: int = len(work)
    audit[AUDIT_AFTER] = after
    audit[AUDIT_CLIPPED] = before - after
    return work, audit
