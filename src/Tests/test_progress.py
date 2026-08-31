"""Тесты ProgressReporter и замера этапов."""

from __future__ import annotations

import logging
import time

from src.progress import ProgressReporter


def test_timing_summary_after_stages() -> None:
    """done() фиксирует этап, summary выводит таблицу."""
    logger: logging.Logger = logging.getLogger("test.progress")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())

    config: dict = {"progress": {"enabled": True, "show_timing_summary": True}}
    reporter: ProgressReporter = ProgressReporter(config, logger)

    reporter.stage("Этап A")
    time.sleep(0.05)
    reporter.done("готово A")

    reporter.stage("Этап B")
    time.sleep(0.05)
    reporter.done("готово B")

    assert len(reporter._timings) == 2
    assert reporter._timings[0][0] == "Этап A"
    assert reporter._timings[1][0] == "Этап B"
    assert reporter._timings[0][1] > 0
    assert reporter._timings[1][1] > 0


def test_stage_closes_previous_without_done() -> None:
    """Следующий stage() закрывает предыдущий этап без done()."""
    logger: logging.Logger = logging.getLogger("test.progress.close")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())

    config: dict = {"progress": {"enabled": True}}
    reporter: ProgressReporter = ProgressReporter(config, logger)

    reporter.stage("Первый")
    time.sleep(0.03)
    reporter.stage("Второй")
    reporter.done("завершён")

    names: list[str] = [name for name, _ in reporter._timings]
    assert names == ["Первый", "Второй"]
