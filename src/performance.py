"""Вычисление числа workers с ограничением нагрузки на систему."""

from __future__ import annotations

import os
from typing import Any


def resolve_parallel_workers(config: dict[str, Any]) -> int:
    """
    Число параллельных процессов:
    - parallel_workers > 0 — явное значение
    - иначе CPU − reserve_cpu_cores, но не больше max_parallel_workers
    """
    perf: dict[str, Any] = config.get("performance", {})
    explicit: int = int(config.get("parallel_workers", 0))
    max_workers: int = int(perf.get("max_parallel_workers", 4))
    reserve: int = int(perf.get("reserve_cpu_cores", 1))
    cpu: int = os.cpu_count() or 4

    if explicit > 0:
        workers: int = explicit
    else:
        workers = max(1, cpu - reserve)

    return min(workers, max_workers)
