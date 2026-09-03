"""Справочник почт менеджеров по табельному номеру (CSV в IN/)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.project_paths import resolve_path
from src.tab_number import normalize_tab_number, normalize_tab_number_multiline

logger: logging.Logger = logging.getLogger("kanban.manager_emails")

# TN → (почта_альфа, почта_сигма)
EmailLookup = dict[str, tuple[str, str]]


def _emails_cfg(config: dict[str, Any]) -> dict[str, Any]:
    raw: Any = config.get("manager_emails")
    return dict(raw) if isinstance(raw, dict) else {}


def manager_emails_enabled(config: dict[str, Any]) -> bool:
    """Блок manager_emails включён."""
    return bool(_emails_cfg(config).get("enabled", False))


def resolve_manager_emails_path(config: dict[str, Any]) -> Path:
    """Полный путь к CSV: directory + filename из config."""
    cfg: dict[str, Any] = _emails_cfg(config)
    directory: str = str(cfg.get("directory", "IN")).strip() or "IN"
    filename: str = str(cfg.get("filename", "")).strip()
    if not filename:
        raise ValueError("manager_emails.filename не задан в config")
    base: Path = resolve_path(directory)
    return base / filename


def load_manager_email_lookup(config: dict[str, Any]) -> EmailLookup:
    """
    Читает CSV и строит словарь нормализованный_TN → (Почта Альфа, Почта Сигма).
    При дубликатах TN оставляется первая непустая почта.
    """
    if not manager_emails_enabled(config):
        return {}

    cfg: dict[str, Any] = _emails_cfg(config)
    path: Path = resolve_manager_emails_path(config)
    if not path.is_file():
        logger.warning("Справочник почт не найден: %s — колонки почт будут пустыми", path)
        return {}

    delimiter: str = str(cfg.get("delimiter", ";"))
    encoding: str = str(cfg.get("encoding", "utf-8-sig"))
    cols_cfg: dict[str, Any] = dict(cfg.get("columns") or {})
    tn_col: str = str(cols_cfg.get("tab_number", "Табельный номер"))
    alpha_col: str = str(cols_cfg.get("email_alpha", "Почта Альфа"))
    sigma_col: str = str(cols_cfg.get("email_sigma", "Почта Сигма"))

    try:
        frame: pd.DataFrame = pd.read_csv(
            path,
            sep=delimiter,
            encoding=encoding,
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:  # noqa: BLE001 — лог и пустой lookup
        logger.error("Не удалось прочитать справочник почт %s: %s", path, exc)
        return {}

    missing: list[str] = [c for c in (tn_col, alpha_col, sigma_col) if c not in frame.columns]
    if missing:
        logger.error(
            "Справочник почт %s: нет колонок %s (есть: %s)",
            path.name,
            missing,
            list(frame.columns[:12]),
        )
        return {}

    lookup: EmailLookup = {}
    for tn_raw, alpha_raw, sigma_raw in zip(
        frame[tn_col].tolist(),
        frame[alpha_col].tolist(),
        frame[sigma_col].tolist(),
        strict=True,
    ):
        tn: str = normalize_tab_number(tn_raw)
        if not tn:
            continue
        alpha: str = str(alpha_raw or "").strip()
        sigma: str = str(sigma_raw or "").strip()
        if tn in lookup:
            prev_a, prev_s = lookup[tn]
            lookup[tn] = (prev_a or alpha, prev_s or sigma)
        else:
            lookup[tn] = (alpha, sigma)

    logger.info(
        "Справочник почт: %s записей TN из %s",
        f"{len(lookup):,}",
        path.name,
    )
    return lookup


def map_multiline_tn_to_email(
    tn_value: Any,
    lookup: EmailLookup,
    *,
    which: str,
) -> str | None:
    """
    Для одного или нескольких TN (через \\n) возвращает почты в том же порядке.
    which: 'alpha' | 'sigma'. Нет в справочнике — пустая строка на этой позиции.
    """
    if not lookup:
        return None
    normalized: str | None = normalize_tab_number_multiline(tn_value)
    if not normalized:
        return None
    idx: int = 0 if which == "alpha" else 1
    lines: list[str] = []
    for part in normalized.splitlines():
        emails: tuple[str, str] | None = lookup.get(part)
        lines.append(emails[idx] if emails else "")
    # Если все пустые — None, чтобы ячейка была пустой
    if not any(lines):
        return None
    return "\n".join(lines)


def _output_email_labels(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    """lead/deal → {email_alpha, email_sigma} с Excel-заголовками."""
    cfg: dict[str, Any] = _emails_cfg(config)
    raw: dict[str, Any] = dict(cfg.get("output_columns") or {})
    defaults: dict[str, dict[str, str]] = {
        "lead": {
            "email_alpha": "Почта Альфа Лидера лида",
            "email_sigma": "Почта Сигма Лидера лида",
        },
        "deal": {
            "email_alpha": "Почта Альфа Лидера сделки",
            "email_sigma": "Почта Сигма Лидера сделки",
        },
    }
    result: dict[str, dict[str, str]] = {}
    for block in ("lead", "deal"):
        block_cfg: dict[str, Any] = dict(raw.get(block) or {})
        result[block] = {
            "email_alpha": str(
                block_cfg.get("email_alpha") or defaults[block]["email_alpha"]
            ),
            "email_sigma": str(
                block_cfg.get("email_sigma") or defaults[block]["email_sigma"]
            ),
        }
    return result


def enrich_snapshot_with_manager_emails(
    snapshot: pd.DataFrame,
    config: dict[str, Any],
    lookup: EmailLookup | None = None,
) -> pd.DataFrame:
    """
    Добавляет колонки почт к снимку по TN Лидера лида / TN Лидера сделки.
    Порядок строк почт совпадает с порядком TN в многострочной ячейке.
    """
    if snapshot.empty or not manager_emails_enabled(config):
        return snapshot

    email_lookup: EmailLookup = lookup if lookup is not None else load_manager_email_lookup(config)
    team_out: dict[str, Any] = config.get("team_files", {}).get("output_columns") or {}
    lead_tn_label: str = str((team_out.get("lead") or {}).get("member_tab_number") or "")
    deal_tn_label: str = str((team_out.get("deal") or {}).get("member_tab_number") or "")
    labels: dict[str, dict[str, str]] = _output_email_labels(config)

    result: pd.DataFrame = snapshot.copy()
    for block, tn_label in (("lead", lead_tn_label), ("deal", deal_tn_label)):
        alpha_label: str = labels[block]["email_alpha"]
        sigma_label: str = labels[block]["email_sigma"]
        if not tn_label or tn_label not in result.columns:
            result[alpha_label] = None
            result[sigma_label] = None
            continue
        result[alpha_label] = result[tn_label].map(
            lambda v: map_multiline_tn_to_email(v, email_lookup, which="alpha")
        )
        result[sigma_label] = result[tn_label].map(
            lambda v: map_multiline_tn_to_email(v, email_lookup, which="sigma")
        )

    matched: int = 0
    for block in ("lead", "deal"):
        alpha_label = labels[block]["email_alpha"]
        if alpha_label in result.columns:
            matched += int(result[alpha_label].notna().sum())
    logger.info("Почты лидеров: заполнено ячеек Альфа (лид+сделка) ≈ %s", f"{matched:,}")
    return result


def attach_emails_by_tab_column(
    frame: pd.DataFrame,
    config: dict[str, Any],
    *,
    tn_column: str = "Табельный номер",
    after_column: str | None = "ФИО",
    alpha_label: str = "Почта Альфа",
    sigma_label: str = "Почта Сигма",
    lookup: EmailLookup | None = None,
) -> pd.DataFrame:
    """Добавляет почты к таблице со столбцом табельных (свод менеджеров / нарушений)."""
    if frame.empty or not manager_emails_enabled(config):
        return frame
    if tn_column not in frame.columns:
        return frame
    email_lookup: EmailLookup = lookup if lookup is not None else load_manager_email_lookup(config)
    if not email_lookup:
        out: pd.DataFrame = frame.copy()
        out[alpha_label] = None
        out[sigma_label] = None
        return out

    out = frame.copy()
    out[alpha_label] = out[tn_column].map(
        lambda v: map_multiline_tn_to_email(v, email_lookup, which="alpha")
    )
    out[sigma_label] = out[tn_column].map(
        lambda v: map_multiline_tn_to_email(v, email_lookup, which="sigma")
    )
    # По умолчанию сразу после ФИО; иначе после ТН
    cols: list[str] = list(out.columns)
    cols.remove(alpha_label)
    cols.remove(sigma_label)
    anchor: str = after_column if after_column and after_column in cols else tn_column
    insert_at: int = cols.index(anchor) + 1
    cols[insert_at:insert_at] = [alpha_label, sigma_label]
    return out[cols]
