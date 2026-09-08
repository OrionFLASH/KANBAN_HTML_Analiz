"""Лёгкий DEBUG-трейс процедур: старт/финиш + время (без содержимого файлов)."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator


def _format_meta(meta: dict[str, Any]) -> str:
    """Склеивает обезличенные метрики (счётчики, флаги, имена этапов)."""
    parts: list[str] = []
    for key, value in meta.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    return ", ".join(parts)


@contextmanager
def procedure(
    logger: logging.Logger,
    name: str,
    **meta: Any,
) -> Iterator[None]:
    """
    DEBUG: вход/выход процедуры с elapsed.
    В meta — только обезличенное: counts, enabled, имена этапов/ключей фильтров.
    Не передавать ФИО, ID, содержимое ячеек.
    """
    extras: str = _format_meta(meta)
    suffix: str = f" [{extras}]" if extras else ""
    logger.debug("→ %s%s", name, suffix)
    started: float = time.monotonic()
    error: BaseException | None = None
    try:
        yield
    except BaseException as exc:
        error = exc
        raise
    finally:
        elapsed: float = time.monotonic() - started
        if error is None:
            logger.debug("← %s — %.2f сек%s", name, elapsed, suffix)
        else:
            logger.debug(
                "✗ %s — %.2f сек, ошибка %s%s",
                name,
                elapsed,
                type(error).__name__,
                suffix,
            )


def debug_event(logger: logging.Logger, message: str, **meta: Any) -> None:
    """Одноразовое DEBUG-событие внутри процедуры."""
    extras: str = _format_meta(meta)
    if extras:
        logger.debug("  · %s (%s)", message, extras)
    else:
        logger.debug("  · %s", message)
