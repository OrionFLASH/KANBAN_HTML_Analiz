"""Отчёт о прогрессе в консоль и лог с принудительным flush и замером этапов."""

from __future__ import annotations

import logging
import sys
import time
from typing import Any


class ProgressReporter:
    """Периодический вывод статуса длительных операций и сводка по времени этапов."""

    def __init__(self, config: dict[str, Any], logger: logging.Logger) -> None:
        prog: dict[str, Any] = config.get("progress", {})
        self.enabled: bool = bool(prog.get("enabled", True))
        self.log_every_seconds: float = float(prog.get("log_every_seconds", 3))
        self.show_timing_summary: bool = bool(prog.get("show_timing_summary", True))
        self.logger: logging.Logger = logger
        self._last_emit: float = 0.0
        self._pipeline_start: float = time.monotonic()
        self._stage_name: str | None = None
        self._stage_start: float | None = None
        self._timings: list[tuple[str, float]] = []

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

    def _record_stage(self, name: str, elapsed: float, note: str = "") -> None:
        """Сохраняет длительность этапа и пишет строку с таймингом."""
        self._timings.append((name, elapsed))
        timing_line: str = f"⏱ Этап «{name}»: {elapsed:.1f} сек"
        if note:
            timing_line = f"{timing_line} — {note}"
        self._emit(timing_line)

    def _finalize_open_stage(self, note: str = "") -> None:
        """Закрывает текущий этап, если он ещё не зафиксирован через done()."""
        if self._stage_name is None or self._stage_start is None:
            return
        elapsed: float = time.monotonic() - self._stage_start
        self._record_stage(self._stage_name, elapsed, note)
        self._stage_name = None
        self._stage_start = None

    def stage(self, name: str, detail: str = "") -> None:
        """Начало крупного этапа pipeline."""
        self._finalize_open_stage()
        self._stage_name = name
        self._stage_start = time.monotonic()
        text: str = f"▶ Этап: {name}"
        if detail:
            text = f"{text} — {detail}"
        self._emit(text)

    def step(self, message: str) -> None:
        """Промежуточный шаг внутри этапа."""
        self._emit(f"  … {message}")

    def done(self, message: str) -> None:
        """Завершение этапа с фиксацией времени."""
        elapsed: float = 0.0
        if self._stage_start is not None:
            elapsed = time.monotonic() - self._stage_start

        text: str = f"✓ {message}"
        if elapsed > 0 and self._stage_name is not None:
            text = f"{text} ({elapsed:.1f} сек)"
        self._emit(text)

        if self._stage_name is not None and elapsed > 0:
            self._timings.append((self._stage_name, elapsed))
            self._stage_name = None
            self._stage_start = None

    def maybe_heartbeat(self, message: str) -> None:
        """Периодическое обновление (не чаще log_every_seconds)."""
        if not self.enabled:
            return
        now: float = time.monotonic()
        if now - self._last_emit >= self.log_every_seconds:
            self._emit(f"  … {message}")

    def timing_summary(self, total_wall: float | None = None) -> None:
        """Итоговая сводка времени по этапам и общее wall-clock время."""
        self._finalize_open_stage()
        if not self.enabled or not self.show_timing_summary:
            return

        wall: float = total_wall if total_wall is not None else time.monotonic() - self._pipeline_start
        if not self._timings:
            self._emit(f"⏱ Общее время pipeline: {wall:.1f} сек")
            return

        name_width: int = max(len(name) for name, _ in self._timings)
        name_width = max(name_width, len("ИТОГО"))

        lines: list[str] = [
            "",
            "═" * (name_width + 22),
            "Сводка времени обработки",
            "─" * (name_width + 22),
        ]
        for name, sec in self._timings:
            pct: float = (sec / wall * 100.0) if wall > 0 else 0.0
            lines.append(f"  {name:<{name_width}}  {sec:>6.1f} сек  ({pct:4.0f}%)")
        lines.append("─" * (name_width + 22))
        lines.append(f"  {'ИТОГО':<{name_width}}  {wall:>6.1f} сек")
        lines.append("═" * (name_width + 22))

        for line in lines:
            self._emit(line)

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
            self.reporter.step(f"{self.label}: {self.count} за {elapsed:.1f} сек{suffix}")
