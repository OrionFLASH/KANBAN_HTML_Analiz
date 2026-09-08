"""Тесты DEBUG-трейса процедур."""

from __future__ import annotations

import logging
import time

from src.debug_trace import debug_event, procedure


def test_procedure_logs_start_and_end(caplog) -> None:
    """procedure пишет → и ← с временем."""
    logger = logging.getLogger("test.debug_trace.proc")
    with caplog.at_level(logging.DEBUG, logger="test.debug_trace.proc"):
        with procedure(logger, "demo_proc", rows_in=5):
            time.sleep(0.01)
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("→ demo_proc") for m in messages)
    assert any(m.startswith("← demo_proc") and "сек" in m for m in messages)


def test_debug_event_with_meta(caplog) -> None:
    """debug_event добавляет обезличенные meta."""
    logger = logging.getLogger("test.debug_trace.event")
    with caplog.at_level(logging.DEBUG, logger="test.debug_trace.event"):
        debug_event(logger, "checkpoint", sheets=3, rows=100)
    assert any("checkpoint" in r.getMessage() and "sheets=3" in r.getMessage() for r in caplog.records)
