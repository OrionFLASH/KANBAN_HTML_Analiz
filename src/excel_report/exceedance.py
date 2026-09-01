"""Превышение норматива P80 на уровне уникальных лидов."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger: logging.Logger = logging.getLogger("kanban.excel_v2.exceedance")


def attach_p80_exceedance(
    snapshot: pd.DataFrame,
    tb_p80: pd.DataFrame,
    all_p80: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """
    Добавляет норматив P80, текущий срок, флаг превышения и дней отклонения.
    Векторизованный merge вместо iterrows.
    """
    if snapshot.empty:
        return snapshot

    exc_cfg: dict[str, str] = config["output"]["exceedance_columns"]
    p80_col: str = exc_cfg["p80_norm"]
    current_col: str = exc_cfg["current_days"]
    flag_col: str = exc_cfg["exceedance_flag"]
    days_col: str = exc_cfg["exceedance_days"]

    merge_keys: list[str] = ["tb", "product_group", "product", "current_status"]
    work: pd.DataFrame = snapshot.copy()

    for key in merge_keys:
        if key not in work.columns:
            work[key] = ""

    if not tb_p80.empty:
        work = work.merge(
            tb_p80.rename(columns={"p80": "_p80_tb"}),
            on=merge_keys,
            how="left",
        )
    else:
        work["_p80_tb"] = np.nan

    fallback_keys: list[str] = ["product_group", "product", "current_status"]
    if not all_p80.empty:
        all_part: pd.DataFrame = all_p80[fallback_keys + ["p80"]].rename(columns={"p80": "_p80_all"})
        work = work.merge(all_part, on=fallback_keys, how="left")
    else:
        work["_p80_all"] = np.nan

    threshold: pd.Series = work["_p80_tb"].combine_first(work["_p80_all"])
    current: pd.Series = pd.to_numeric(work["_days_on_stage"], errors="coerce").round()

    work[p80_col] = threshold.where(threshold.notna(), None)
    work[current_col] = current.where(current.notna(), None)

    exceeded: pd.Series = threshold.notna() & current.notna() & (current > threshold)
    work[flag_col] = np.where(exceeded, "ДА", None)
    deviation: pd.Series = (current - threshold).where(exceeded, other=pd.NA)
    work[days_col] = deviation.where(deviation.notna(), None)

    work = work.drop(columns=["_p80_tb", "_p80_all"], errors="ignore")

    exceeded_count: int = int(exceeded.sum())
    logger.info("Превышения P80: %s из %s лидов", f"{exceeded_count:,}", f"{len(work):,}")
    return work
