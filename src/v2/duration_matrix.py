"""Матрица числа лидов: группа/продукт × срок (дни)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.settings import col

logger: logging.Logger = logging.getLogger("kanban.excel_v2.duration_matrix")

# Запас по ширине Excel (макс. 16384 колонки)
_EXCEL_MAX_COLUMNS: int = 16384
_LABEL_COLUMNS: int = 3

# alpha_days — группы/продукты А→Я, дни по возрастанию
# by_volume — строки/колонки по убыванию числа лидов
SORT_MODE_ALPHA_DAYS: str = "alpha_days"
SORT_MODE_BY_VOLUME: str = "by_volume"


@dataclass(frozen=True)
class DurationMatrixResult:
    """Готовая матрица для листа Excel."""

    # Строки: (группа, продукт, всего); колонки дней — int → count
    rows: list[tuple[str, str, int, dict[int, int]]]
    day_min: int
    day_max: int
    # Дни с ≥1 лидом (порядок зависит от sort_mode)
    day_columns: list[int]
    # Суммы по столбцам дней (горизонталь «Всего»)
    day_totals: dict[int, int]
    # Сумма всех лидов в матрице
    grand_total: int
    sort_mode: str
    empty: bool


def _matrix_cfg(config: dict[str, Any]) -> dict[str, Any]:
    """Блок output.duration_matrix."""
    raw: Any = config.get("output", {}).get("duration_matrix")
    return dict(raw) if isinstance(raw, dict) else {}


def resolve_sort_mode(config: dict[str, Any]) -> str:
    """Режим порядка строк/столбцов матрицы."""
    raw: str = str(_matrix_cfg(config).get("sort_mode", SORT_MODE_BY_VOLUME)).strip()
    if raw in {SORT_MODE_ALPHA_DAYS, SORT_MODE_BY_VOLUME}:
        return raw
    logger.warning(
        "Матрица сроков: неизвестный sort_mode=%r — используем %s",
        raw,
        SORT_MODE_BY_VOLUME,
    )
    return SORT_MODE_BY_VOLUME


def duration_matrix_enabled(config: dict[str, Any]) -> bool:
    """Лист матрицы включён (по умолчанию да, если задано имя листа)."""
    sheets: dict[str, Any] = config.get("output", {}).get("sheets") or {}
    if "duration_matrix" not in sheets:
        return False
    return bool(_matrix_cfg(config).get("enabled", True))


def build_duration_matrix(
    snapshot: pd.DataFrame,
    config: dict[str, Any],
) -> DurationMatrixResult:
    """
    Считает число уникальных лидов по (группа, продукт, целые дни на стадии).

    Столбцы дней — только значения, где есть ≥1 лид.
    Порядок строк/столбцов — `output.duration_matrix.sort_mode`.
    """
    sort_mode: str = resolve_sort_mode(config)
    empty: DurationMatrixResult = DurationMatrixResult(
        rows=[],
        day_min=0,
        day_max=0,
        day_columns=[],
        day_totals={},
        grand_total=0,
        sort_mode=sort_mode,
        empty=True,
    )
    if snapshot is None or snapshot.empty:
        return empty

    pg_key: str = "product_group"
    pr_key: str = "product"
    days_internal: str = "_days_on_stage"

    # В снимке могут быть ключи config или уже сырые имена колонок
    pg_col: str = pg_key if pg_key in snapshot.columns else col(config, pg_key)
    pr_col: str = pr_key if pr_key in snapshot.columns else col(config, pr_key)
    if days_internal not in snapshot.columns:
        days_src: str = col(config, "days_on_stage")
        if days_src not in snapshot.columns:
            logger.warning("Матрица сроков: нет колонки дней в снимке")
            return empty
        work: pd.DataFrame = snapshot[[pg_col, pr_col, days_src]].copy()
        work[days_internal] = pd.to_numeric(work[days_src], errors="coerce")
    else:
        work = snapshot[[pg_col, pr_col, days_internal]].copy()
        work[days_internal] = pd.to_numeric(work[days_internal], errors="coerce")

    work = work.dropna(subset=[days_internal])
    if work.empty:
        logger.info("Матрица сроков: нет лидов с известным сроком")
        return empty

    # Целые дни (как на листе уникальных ID после round в exceedance)
    work["_days_int"] = work[days_internal].round().astype("int64")
    work["_pg"] = work[pg_col].fillna("").astype(str).str.strip()
    work["_pr"] = work[pr_col].fillna("").astype(str).str.strip()
    work = work.loc[(work["_pg"] != "") | (work["_pr"] != "")]
    if work.empty:
        return empty

    day_min: int = int(work["_days_int"].min())
    day_max: int = int(work["_days_int"].max())
    cfg: dict[str, Any] = _matrix_cfg(config)
    max_span: int = int(cfg.get("max_day_span", 3000))

    # Предварительный набор дней (уникальные)
    day_set: set[int] = {int(v) for v in work["_days_int"].tolist()}
    if len(day_set) > max_span:
        # Обрезка: оставляем дни с наибольшим числом лидов, иначе — наименьшие дни
        day_counts_all: pd.Series = work.groupby("_days_int").size()
        if sort_mode == SORT_MODE_BY_VOLUME:
            keep_days: list[int] = [
                int(d)
                for d in day_counts_all.sort_values(ascending=False).head(max_span).index.tolist()
            ]
        else:
            keep_days = sorted(day_set)[:max_span]
        logger.warning(
            "Матрица сроков: %s уникальных дней > max_day_span=%s — обрезка до %s",
            len(day_set),
            max_span,
            len(keep_days),
        )
        keep_set: set[int] = set(keep_days)
        work = work.loc[work["_days_int"].isin(keep_set)]
        if work.empty:
            return empty
        day_min = int(work["_days_int"].min())
        day_max = int(work["_days_int"].max())
        day_set = {int(v) for v in work["_days_int"].tolist()}

    if _LABEL_COLUMNS + len(day_set) > _EXCEL_MAX_COLUMNS:
        logger.error(
            "Матрица сроков: слишком много колонок (%s) — лист пропущен",
            _LABEL_COLUMNS + len(day_set),
        )
        return empty

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
    rows_map: dict[tuple[str, str], tuple[int, dict[int, int]]] = {}
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
        rows_map[(pg, pr)] = (total, counts)

    # Убрать дни с нулевой суммой
    day_columns: list[int] = [d for d in day_set if day_totals.get(d, 0) > 0]
    day_totals = {d: day_totals[d] for d in day_columns}
    grand_total: int = int(sum(day_totals.values()))

    if sort_mode == SORT_MODE_BY_VOLUME:
        # Столбцы: слева дни с максимумом лидов; при равенстве — меньший день
        day_columns = sorted(
            day_columns,
            key=lambda d: (-day_totals[d], d),
        )
        # Строки: сверху максимум лидов; при равенстве — алфавит группа/продукт
        rows_out: list[tuple[str, str, int, dict[int, int]]] = [
            (pg, pr, total, counts)
            for (pg, pr), (total, counts) in sorted(
                rows_map.items(),
                key=lambda item: (
                    -item[1][0],
                    item[0][0].casefold(),
                    item[0][1].casefold(),
                ),
            )
        ]
    else:
        day_columns = sorted(day_columns)
        rows_out = [
            (pg, pr, total, counts)
            for (pg, pr), (total, counts) in sorted(
                rows_map.items(),
                key=lambda item: (item[0][0].casefold(), item[0][1].casefold()),
            )
        ]

    logger.info(
        "Матрица сроков: mode=%s, %s продуктов, дни %s…%s (%s колонок), всего лидов %s",
        sort_mode,
        len(rows_out),
        day_min,
        day_max,
        len(day_columns),
        grand_total,
    )
    return DurationMatrixResult(
        rows=rows_out,
        day_min=day_min,
        day_max=day_max,
        day_columns=day_columns,
        day_totals=day_totals,
        grand_total=grand_total,
        sort_mode=sort_mode,
        empty=False,
    )
