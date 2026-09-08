"""Матрица числа лидов: группа/продукт × срок (дни)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.percentile_stats import empirical_percentile_stats, percentile_label
from src.settings import col
from src.v2.exceedance_config import exceedance_percentile

logger: logging.Logger = logging.getLogger("kanban.excel_v2.duration_matrix")

# Запас по ширине Excel (макс. 16384 колонки)
_EXCEL_MAX_COLUMNS: int = 16384
# Группа + продукт + процентили + Всего (число процентилей — из config)
_BASE_LABEL_COLUMNS: int = 3

# alpha_days — группы/продукты А→Я, дни по возрастанию
# by_volume — строки/колонки по убыванию числа лидов
# group_alpha_product_volume — дни ↑; группы А→Я; внутри группы продукты по убыванию лидов
SORT_MODE_ALPHA_DAYS: str = "alpha_days"
SORT_MODE_BY_VOLUME: str = "by_volume"
SORT_MODE_GROUP_ALPHA_PRODUCT_VOLUME: str = "group_alpha_product_volume"

KNOWN_SORT_MODES: frozenset[str] = frozenset(
    {
        SORT_MODE_ALPHA_DAYS,
        SORT_MODE_BY_VOLUME,
        SORT_MODE_GROUP_ALPHA_PRODUCT_VOLUME,
    }
)

# (группа, продукт, всего, counts_по_дням, percentiles)
RowTuple = tuple[str, str, int, dict[int, int], dict[float, int | None]]


@dataclass(frozen=True)
class DurationMatrixResult:
    """Готовая матрица для листа Excel."""

    rows: list[RowTuple]
    day_min: int
    day_max: int
    day_columns: list[int]
    day_totals: dict[int, int]
    grand_total: int
    percentile_list: list[float]
    exceedance_percentile: float
    sort_mode: str
    empty: bool
    sheet_key: str = "duration_matrix"

    def __len__(self) -> int:
        """Число строк (группа+продукт) в матрице."""
        return len(self.rows)


@dataclass(frozen=True)
class DurationMatrixSpec:
    """Описание одного листа матрицы из config."""

    sheet_key: str
    sort_mode: str


def _matrix_cfg(config: dict[str, Any]) -> dict[str, Any]:
    """Блок output.duration_matrix."""
    raw: Any = config.get("output", {}).get("duration_matrix")
    return dict(raw) if isinstance(raw, dict) else {}


def normalize_sort_mode(raw: Any, *, fallback: str = SORT_MODE_BY_VOLUME) -> str:
    """Проверяет sort_mode; неизвестный → fallback + warning."""
    text: str = str(raw or "").strip()
    if text in KNOWN_SORT_MODES:
        return text
    logger.warning(
        "Матрица сроков: неизвестный sort_mode=%r — используем %s",
        raw,
        fallback,
    )
    return fallback


def resolve_sort_mode(config: dict[str, Any]) -> str:
    """Режим порядка основного листа (для совместимости)."""
    return normalize_sort_mode(_matrix_cfg(config).get("sort_mode", SORT_MODE_BY_VOLUME))


def duration_matrix_enabled(config: dict[str, Any]) -> bool:
    """Лист матрицы включён (по умолчанию да, если задано имя листа)."""
    sheets: dict[str, Any] = config.get("output", {}).get("sheets") or {}
    if "duration_matrix" not in sheets and not _raw_variants(config):
        return False
    return bool(_matrix_cfg(config).get("enabled", True))


def _raw_variants(config: dict[str, Any]) -> list[Any]:
    raw: Any = _matrix_cfg(config).get("variants")
    return list(raw) if isinstance(raw, list) else []


def list_duration_matrix_specs(config: dict[str, Any]) -> list[DurationMatrixSpec]:
    """
    Список листов матрицы.

    variants[] в config — несколько листов; иначе один лист duration_matrix + sort_mode.
    """
    cfg: dict[str, Any] = _matrix_cfg(config)
    sheets: dict[str, Any] = config.get("output", {}).get("sheets") or {}
    raw_variants: list[Any] = _raw_variants(config)
    specs: list[DurationMatrixSpec] = []

    if raw_variants:
        for item in raw_variants:
            if not isinstance(item, dict):
                continue
            key: str = str(item.get("sheet_key") or "").strip()
            if not key:
                continue
            mode: str = normalize_sort_mode(
                item.get("sort_mode") or cfg.get("sort_mode") or SORT_MODE_BY_VOLUME
            )
            specs.append(DurationMatrixSpec(sheet_key=key, sort_mode=mode))
    elif "duration_matrix" in sheets or cfg.get("enabled", True):
        specs.append(
            DurationMatrixSpec(
                sheet_key="duration_matrix",
                sort_mode=resolve_sort_mode(config),
            )
        )

    filtered: list[DurationMatrixSpec] = []
    for spec in specs:
        if spec.sheet_key in sheets or spec.sheet_key == "duration_matrix":
            filtered.append(spec)
        else:
            logger.warning(
                "Матрица сроков: variants.sheet_key=%r нет в output.sheets — лист пропущен",
                spec.sheet_key,
            )
    return filtered


def _percentile_list(config: dict[str, Any]) -> list[float]:
    """Список процентилей из config (как на листе нормативов)."""
    raw: list[Any] = list(config.get("percentiles") or [20, 50, 80])
    result: list[float] = []
    for item in raw:
        try:
            result.append(float(item))
        except (TypeError, ValueError):
            continue
    return result


def _empty_result(
    config: dict[str, Any],
    sort_mode: str,
    *,
    sheet_key: str = "duration_matrix",
) -> DurationMatrixResult:
    """Пустая матрица с метаданными из config."""
    return DurationMatrixResult(
        rows=[],
        day_min=0,
        day_max=0,
        day_columns=[],
        day_totals={},
        grand_total=0,
        percentile_list=_percentile_list(config),
        exceedance_percentile=exceedance_percentile(config),
        sort_mode=sort_mode,
        empty=True,
        sheet_key=sheet_key,
    )


def _row_percentiles(
    day_values: np.ndarray,
    percentiles: list[float],
) -> dict[float, int | None]:
    """Эмпирические процентили по срокам лидов строки (все стадии вместе)."""
    out: dict[float, int | None] = {}
    for p in percentiles:
        stats: dict[str, int | None] = empirical_percentile_stats(day_values, p)
        days_val: int | None = stats.get("days")  # type: ignore[assignment]
        out[float(p)] = int(days_val) if days_val is not None else None
    return out


def _layout_rows(
    rows_map: dict[tuple[str, str], tuple[int, dict[int, int], dict[float, int | None]]],
    day_totals: dict[int, int],
    day_columns: list[int],
    sort_mode: str,
) -> tuple[list[int], list[RowTuple]]:
    """Упорядочивает дни и строки по sort_mode."""
    if sort_mode == SORT_MODE_BY_VOLUME:
        ordered_days: list[int] = sorted(
            day_columns,
            key=lambda d: (-day_totals[d], d),
        )
        rows_out: list[RowTuple] = [
            (pg, pr, total, counts, pcts)
            for (pg, pr), (total, counts, pcts) in sorted(
                rows_map.items(),
                key=lambda item: (
                    -item[1][0],
                    item[0][0].casefold(),
                    item[0][1].casefold(),
                ),
            )
        ]
        return ordered_days, rows_out

    if sort_mode == SORT_MODE_GROUP_ALPHA_PRODUCT_VOLUME:
        ordered_days = sorted(day_columns)
        rows_out = [
            (pg, pr, total, counts, pcts)
            for (pg, pr), (total, counts, pcts) in sorted(
                rows_map.items(),
                key=lambda item: (
                    item[0][0].casefold(),
                    -item[1][0],
                    item[0][1].casefold(),
                ),
            )
        ]
        return ordered_days, rows_out

    # alpha_days (и fallback)
    ordered_days = sorted(day_columns)
    rows_out = [
        (pg, pr, total, counts, pcts)
        for (pg, pr), (total, counts, pcts) in sorted(
            rows_map.items(),
            key=lambda item: (item[0][0].casefold(), item[0][1].casefold()),
        )
    ]
    return ordered_days, rows_out


def _aggregate_duration_counts(
    snapshot: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[
    dict[tuple[str, str], tuple[int, dict[int, int], dict[float, int | None]]],
    dict[int, int],
    list[int],
    int,
    int,
    int,
] | None:
    """
    Один проход по снимку → counts / процентили / итоги по дням.

    Возвращает None, если данных нет.
    """
    percentiles: list[float] = _percentile_list(config)
    pg_key: str = "product_group"
    pr_key: str = "product"
    days_internal: str = "_days_on_stage"

    pg_col: str = pg_key if pg_key in snapshot.columns else col(config, pg_key)
    pr_col: str = pr_key if pr_key in snapshot.columns else col(config, pr_key)
    if days_internal not in snapshot.columns:
        days_src: str = col(config, "days_on_stage")
        if days_src not in snapshot.columns:
            logger.warning("Матрица сроков: нет колонки дней в снимке")
            return None
        work: pd.DataFrame = snapshot[[pg_col, pr_col, days_src]].copy()
        work[days_internal] = pd.to_numeric(work[days_src], errors="coerce")
    else:
        work = snapshot[[pg_col, pr_col, days_internal]].copy()
        work[days_internal] = pd.to_numeric(work[days_internal], errors="coerce")

    work = work.dropna(subset=[days_internal])
    if work.empty:
        logger.info("Матрица сроков: нет лидов с известным сроком")
        return None

    work["_days_int"] = work[days_internal].round().astype("int64")
    work["_pg"] = work[pg_col].astype("string").fillna("").astype(str).str.strip()
    work["_pr"] = work[pr_col].astype("string").fillna("").astype(str).str.strip()
    work = work.loc[(work["_pg"] != "") | (work["_pr"] != "")]
    if work.empty:
        return None

    day_min: int = int(work["_days_int"].min())
    day_max: int = int(work["_days_int"].max())
    cfg: dict[str, Any] = _matrix_cfg(config)
    max_span: int = int(cfg.get("max_day_span", 3000))

    day_set: set[int] = {int(v) for v in work["_days_int"].tolist()}
    if len(day_set) > max_span:
        # Общая обрезка по объёму (сохраняет самые населённые дни для всех variants)
        day_counts_all: pd.Series = work.groupby("_days_int").size()
        keep_days: list[int] = [
            int(d)
            for d in day_counts_all.sort_values(ascending=False).head(max_span).index.tolist()
        ]
        logger.warning(
            "Матрица сроков: %s уникальных дней > max_day_span=%s — обрезка до %s",
            len(day_set),
            max_span,
            len(keep_days),
        )
        keep_set: set[int] = set(keep_days)
        work = work.loc[work["_days_int"].isin(keep_set)]
        if work.empty:
            return None
        day_min = int(work["_days_int"].min())
        day_max = int(work["_days_int"].max())
        day_set = {int(v) for v in work["_days_int"].tolist()}

    label_cols: int = _BASE_LABEL_COLUMNS + len(percentiles)
    if label_cols + len(day_set) > _EXCEL_MAX_COLUMNS:
        logger.error(
            "Матрица сроков: слишком много колонок (%s) — лист пропущен",
            label_cols + len(day_set),
        )
        return None

    grouped = (
        work.groupby(["_pg", "_pr", "_days_int"], sort=False)
        .size()
        .reset_index(name="_cnt")
    )

    pairs: list[tuple[str, str]] = list(
        {
            (str(pg), str(pr))
            for pg, pr in zip(grouped["_pg"].tolist(), grouped["_pr"].tolist(), strict=True)
        }
    )

    day_totals: dict[int, int] = {d: 0 for d in day_set}
    rows_map: dict[tuple[str, str], tuple[int, dict[int, int], dict[float, int | None]]] = {}
    for pg, pr in pairs:
        sub: pd.DataFrame = grouped.loc[(grouped["_pg"] == pg) & (grouped["_pr"] == pr)]
        counts: dict[int, int] = {}
        for day_val, cnt_val in zip(
            sub["_days_int"].tolist(), sub["_cnt"].tolist(), strict=True
        ):
            cnt_i: int = int(cnt_val)
            day_i: int = int(day_val)
            if cnt_i > 0 and day_i in day_totals:
                counts[day_i] = cnt_i
                day_totals[day_i] += cnt_i
        total: int = int(sum(counts.values()))
        day_values: np.ndarray = np.repeat(
            np.array(list(counts.keys()), dtype=np.int64),
            np.array(list(counts.values()), dtype=np.int64),
        )
        pct_map: dict[float, int | None] = _row_percentiles(day_values, percentiles)
        rows_map[(pg, pr)] = (total, counts, pct_map)

    day_columns: list[int] = [d for d in day_set if day_totals.get(d, 0) > 0]
    day_totals = {d: day_totals[d] for d in day_columns}
    grand_total: int = int(sum(day_totals.values()))
    return rows_map, day_totals, day_columns, day_min, day_max, grand_total


def build_duration_matrix(
    snapshot: pd.DataFrame,
    config: dict[str, Any],
    *,
    sort_mode: str | None = None,
    sheet_key: str = "duration_matrix",
) -> DurationMatrixResult:
    """
    Считает число уникальных лидов по (группа, продукт, целые дни на стадии).

    sort_mode=None → из config (основной лист).
    """
    mode: str = (
        normalize_sort_mode(sort_mode)
        if sort_mode is not None
        else resolve_sort_mode(config)
    )
    empty: DurationMatrixResult = _empty_result(config, mode, sheet_key=sheet_key)
    if snapshot is None or snapshot.empty:
        return empty

    aggregated = _aggregate_duration_counts(snapshot, config)
    if aggregated is None:
        return empty

    rows_map, day_totals, day_columns, day_min, day_max, grand_total = aggregated
    ordered_days, rows_out = _layout_rows(rows_map, day_totals, day_columns, mode)
    percentiles: list[float] = _percentile_list(config)
    exc_p: float = exceedance_percentile(config)
    logger.info(
        "Матрица сроков [%s]: mode=%s, %s продуктов, дни %s…%s (%s колонок), "
        "процентили=%s, порог P%s, всего лидов %s",
        sheet_key,
        mode,
        len(rows_out),
        day_min,
        day_max,
        len(ordered_days),
        [percentile_label(p) for p in percentiles],
        percentile_label(exc_p).lstrip("p"),
        grand_total,
    )
    return DurationMatrixResult(
        rows=rows_out,
        day_min=day_min,
        day_max=day_max,
        day_columns=ordered_days,
        day_totals=day_totals,
        grand_total=grand_total,
        percentile_list=percentiles,
        exceedance_percentile=exc_p,
        sort_mode=mode,
        empty=False,
        sheet_key=sheet_key,
    )


def build_all_duration_matrices(
    snapshot: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, DurationMatrixResult]:
    """
    Строит все листы матрицы из variants (один проход агрегации).

    Ключ словаря = sheet_key.
    """
    specs: list[DurationMatrixSpec] = list_duration_matrix_specs(config)
    if not specs:
        return {}

    if snapshot is None or snapshot.empty:
        return {
            spec.sheet_key: _empty_result(config, spec.sort_mode, sheet_key=spec.sheet_key)
            for spec in specs
        }

    aggregated = _aggregate_duration_counts(snapshot, config)
    if aggregated is None:
        return {
            spec.sheet_key: _empty_result(config, spec.sort_mode, sheet_key=spec.sheet_key)
            for spec in specs
        }

    rows_map, day_totals, day_columns, day_min, day_max, grand_total = aggregated
    percentiles: list[float] = _percentile_list(config)
    exc_p: float = exceedance_percentile(config)
    result: dict[str, DurationMatrixResult] = {}

    for spec in specs:
        ordered_days, rows_out = _layout_rows(
            rows_map, day_totals, day_columns, spec.sort_mode
        )
        logger.info(
            "Матрица сроков [%s]: mode=%s, %s продуктов, дни %s…%s (%s колонок), "
            "процентили=%s, порог P%s, всего лидов %s",
            spec.sheet_key,
            spec.sort_mode,
            len(rows_out),
            day_min,
            day_max,
            len(ordered_days),
            [percentile_label(p) for p in percentiles],
            percentile_label(exc_p).lstrip("p"),
            grand_total,
        )
        result[spec.sheet_key] = DurationMatrixResult(
            rows=rows_out,
            day_min=day_min,
            day_max=day_max,
            day_columns=ordered_days,
            day_totals=day_totals,
            grand_total=grand_total,
            percentile_list=percentiles,
            exceedance_percentile=exc_p,
            sort_mode=spec.sort_mode,
            empty=False,
            sheet_key=spec.sheet_key,
        )
    return result
