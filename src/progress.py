"""Отчёт о прогрессе в консоль и лог с принудительным flush."""

from __future__ import annotations

import logging
import sys
import time
from typing import Any


class ProgressReporter:
    """Периодический вывод статуса длительных операций."""

    def __init__(self, config: dict[str, Any], logger: logging.Logger) -> None:
        prog: dict[str, Any] = config.get("progress", {})
        self.enabled: bool = bool(prog.get("enabled", True))
        self.log_every_seconds: float = float(prog.get("log_every_seconds", 3))
        self.logger: logging.Logger = logger
        self._last_emit: float = 0.0

    def _emit(self, message: str) -> None:
        """Пишет сообщение в лог и сразу выводит в консоль."""
        if not self.enabled:
            return
        self.logger.info(message)
        for handler in self.logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.flush()
        sys.stdout.flush()
        sys.stderr.flush()
        self._last_emit = time.monotonic()

    def stage(self, name: str, detail: str = "") -> None:
        """Начало крупного этапа pipeline."""
        text: str = f"▶ Этап: {name}"
        if detail:
            text = f"{text} — {detail}"
        self._emit(text)

    def step(self, message: str) -> None:
        """Промежуточный шаг внутри этапа."""
        self._emit(f"  … {message}")

    def done(self, message: str) -> None:
        """Завершение этапа."""
        self._emit(f"✓ {message}")

    def maybe_heartbeat(self, message: str) -> None:
        """Периодическое обновление (не чаще log_every_seconds)."""
        if not self.enabled:
            return
        now: float = time.monotonic()
        if now - self._last_emit >= self.log_every_seconds:
            self._emit(f"  … {message}")

    class Heartbeat:
        """Контекст для периодических сообщений в длительном цикле."""

        def __init__(self, reporter: "ProgressReporter", label: str) -> None:
            self.reporter: ProgressReporter = reporter
            self.label: str = label
            self.start: float = time.monotonic()
            self.count: int = 0

        def tick(self, count: int | None = None, extra: str = "") -> None:
            if count is not None:
                self.count = count
            elapsed: float = time.monotonic() - self.start
            msg: str = f"{self.label}: {self.count} обработано, {elapsed:.0f} сек"
            if extra:
                msg = f"{msg} ({extra})"
            self.reporter.maybe_heartbeat(msg)

        def finish(self, extra: str = "") -> None:
            elapsed: float = time.monotonic() - self.start
            suffix: str = f" ({extra})" if extra else ""
            self.reporter.done(f"{self.label}: {self.count} за {elapsed:.1f} сек{suffix}")
