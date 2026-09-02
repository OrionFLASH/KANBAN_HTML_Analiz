"""Адаптивное управление памятью и параллелизмом без внешних зависимостей."""

from __future__ import annotations

import gc
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from src.performance import resolve_parallel_workers

PressureLevel = Literal["ok", "warn", "critical"]

logger: logging.Logger = logging.getLogger("kanban.resource_guard")


@dataclass(frozen=True)
class SystemMemory:
    """Снимок оперативной памяти системы."""

    total_bytes: int
    available_bytes: int

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024**3)

    @property
    def available_gb(self) -> float:
        return self.available_bytes / (1024**3)

    @property
    def used_percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        used: int = self.total_bytes - self.available_bytes
        return max(0.0, min(100.0, 100.0 * used / self.total_bytes))


@dataclass(frozen=True)
class AdaptivePlan:
    """Итог автоподстройки параметров pipeline."""

    pressure: PressureLevel
    parallel_workers: int
    max_parallel_workers: int
    parallel_pipeline_stages: bool
    parallel_team_files: bool
    precompute_html_filter_slices: bool
    reasons: tuple[str, ...]


def adaptive_config(config: dict[str, Any]) -> dict[str, Any]:
    """Блок performance.adaptive_resources с дефолтами."""
    perf: dict[str, Any] = config.get("performance", {})
    raw: dict[str, Any] = dict(perf.get("adaptive_resources") or {})
    return {
        "enabled": bool(raw.get("enabled", True)),
        "min_available_ram_gb": float(raw.get("min_available_ram_gb", 3.0)),
        "critical_available_ram_gb": float(raw.get("critical_available_ram_gb", 1.5)),
        "warn_used_ram_percent": float(raw.get("warn_used_ram_percent", 80.0)),
        "critical_used_ram_percent": float(raw.get("critical_used_ram_percent", 92.0)),
        "sequential_load_below_total_ram_gb": float(
            raw.get("sequential_load_below_total_ram_gb", 20.0)
        ),
        "input_size_per_worker_gb": float(raw.get("input_size_per_worker_gb", 1.2)),
        "gc_on_pressure": bool(raw.get("gc_on_pressure", True)),
        "override_explicit_workers_on_critical": bool(
            raw.get("override_explicit_workers_on_critical", True)
        ),
        "disable_html_slices_on_critical": bool(
            raw.get("disable_html_slices_on_critical", True)
        ),
    }


def get_system_memory() -> SystemMemory:
    """Возвращает объём RAM через stdlib (Windows ctypes / Linux /proc)."""
    if sys.platform == "win32":
        return _memory_windows()
    return _memory_linux()


def _memory_linux() -> SystemMemory:
    """Читает MemTotal/MemAvailable из /proc/meminfo."""
    total_kb: int = 0
    avail_kb: int = 0
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    total_kb = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail_kb = int(line.split()[1])
    except OSError:
        pass
    if total_kb <= 0:
        return SystemMemory(total_bytes=0, available_bytes=0)
    if avail_kb <= 0:
        avail_kb = total_kb // 4
    return SystemMemory(
        total_bytes=total_kb * 1024,
        available_bytes=avail_kb * 1024,
    )


def _memory_windows() -> SystemMemory:
    """GlobalMemoryStatusEx через kernel32 (без pip)."""
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat: MEMORYSTATUSEX = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ok: int = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    if not ok:
        return SystemMemory(total_bytes=0, available_bytes=0)
    return SystemMemory(
        total_bytes=int(stat.ullTotalPhys),
        available_bytes=int(stat.ullAvailPhys),
    )


def get_process_rss_bytes() -> int:
    """RSS текущего процесса (байты)."""
    if sys.platform == "win32":
        return _process_rss_windows()
    return _process_rss_linux()


def _process_rss_linux() -> int:
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        return 0
    return 0


def _process_rss_windows() -> int:
    import ctypes

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters: PROCESS_MEMORY_COUNTERS = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    ok: int = ctypes.windll.psapi.GetProcessMemoryInfo(
        handle,
        ctypes.byref(counters),
        counters.cb,
    )
    if not ok:
        return 0
    return int(counters.WorkingSetSize)


def sum_input_bytes(input_dir: Path, filenames: list[str]) -> int:
    """Суммарный размер входных файлов на диске."""
    total: int = 0
    for name in filenames:
        path: Path = input_dir / name
        if path.is_file():
            total += path.stat().st_size
    return total


def memory_pressure(config: dict[str, Any], mem: SystemMemory | None = None) -> PressureLevel:
    """Уровень давления на RAM: ok / warn / critical."""
    if mem is None:
        mem = get_system_memory()
    if mem.total_bytes <= 0:
        return "ok"

    cfg: dict[str, Any] = adaptive_config(config)
    if mem.available_gb <= cfg["critical_available_ram_gb"]:
        return "critical"
    if mem.used_percent >= cfg["critical_used_ram_percent"]:
        return "critical"
    if mem.available_gb <= cfg["min_available_ram_gb"]:
        return "warn"
    if mem.used_percent >= cfg["warn_used_ram_percent"]:
        return "warn"
    return "ok"


def build_adaptive_plan(
    config: dict[str, Any],
    input_bytes: int,
    mem: SystemMemory | None = None,
) -> AdaptivePlan:
    """Строит план снижения нагрузки по RAM и объёму входных данных."""
    cfg: dict[str, Any] = adaptive_config(config)
    if mem is None:
        mem = get_system_memory()

    perf: dict[str, Any] = config.setdefault("performance", {})
    dashboard: dict[str, Any] = config.setdefault("dashboard", {})
    explicit_raw: int = int(config.get("_parallel_workers_explicit", 0))
    base_workers: int = resolve_parallel_workers(config)
    max_workers: int = int(perf.get("max_parallel_workers", 4))
    parallel_stages: bool = bool(perf.get("parallel_pipeline_stages", True))
    parallel_teams: bool = bool(perf.get("parallel_team_files", True))
    precompute_slices: bool = bool(dashboard.get("precompute_html_filter_slices", True))

    reasons: list[str] = []
    pressure: PressureLevel = memory_pressure(config, mem)
    workers: int = base_workers

    input_gb: float = input_bytes / (1024**3)
    if mem.total_gb > 0 and mem.total_gb < cfg["sequential_load_below_total_ram_gb"]:
        workers = 1
        parallel_stages = False
        parallel_teams = False
        reasons.append(
            f"RAM {mem.total_gb:.1f} ГБ < порога {cfg['sequential_load_below_total_ram_gb']:.0f} ГБ"
        )

    if input_gb > 0 and workers > 1:
        by_input: int = max(
            1,
            int(mem.available_gb // max(cfg["input_size_per_worker_gb"], 0.1)),
        )
        if by_input < workers:
            workers = by_input
            reasons.append(
                f"вход {input_gb:.1f} ГБ при доступно {mem.available_gb:.1f} ГБ RAM"
            )

    if pressure == "warn":
        workers = min(workers, 2)
        max_workers = min(max_workers, 2)
        parallel_stages = False
        reasons.append(
            f"RAM warn: занято {mem.used_percent:.0f}%, свободно {mem.available_gb:.1f} ГБ"
        )

    if pressure == "critical":
        workers = 1
        max_workers = 1
        parallel_stages = False
        parallel_teams = False
        if cfg["disable_html_slices_on_critical"]:
            precompute_slices = False
        reasons.append(
            f"RAM critical: занято {mem.used_percent:.0f}%, свободно {mem.available_gb:.1f} ГБ"
        )

    if explicit_raw > 0:
        if pressure == "critical" and cfg["override_explicit_workers_on_critical"]:
            if explicit_raw > 1:
                reasons.append(
                    f"critical: parallel_workers {explicit_raw} → 1 (защита системы)"
                )
            workers = 1
        elif pressure == "ok":
            workers = min(explicit_raw, max_workers)
            if explicit_raw != workers:
                reasons.append(
                    f"явный parallel_workers={explicit_raw} ограничен max={max_workers}"
                )
        elif workers < explicit_raw:
            reasons.append(
                f"parallel_workers снижен с {explicit_raw} до {workers} (RAM {pressure})"
            )

    workers = max(1, min(workers, max_workers))

    if not reasons:
        reasons.append("адаптация не требуется")

    return AdaptivePlan(
        pressure=pressure,
        parallel_workers=workers,
        max_parallel_workers=max_workers,
        parallel_pipeline_stages=parallel_stages,
        parallel_team_files=parallel_teams,
        precompute_html_filter_slices=precompute_slices,
        reasons=tuple(reasons),
    )


def apply_adaptive_resources(
    config: dict[str, Any],
    input_dir: Path,
    filenames: list[str],
    log: logging.Logger | None = None,
) -> AdaptivePlan | None:
    """
    Подстраивает config под доступную RAM и объём входных файлов.
    Возвращает план или None, если adaptive отключён.
    """
    cfg: dict[str, Any] = adaptive_config(config)
    if not cfg["enabled"]:
        return None

    mem: SystemMemory = get_system_memory()
    input_bytes: int = sum_input_bytes(input_dir, filenames)
    plan: AdaptivePlan = build_adaptive_plan(config, input_bytes, mem)

    perf: dict[str, Any] = config.setdefault("performance", {})
    config["parallel_workers"] = plan.parallel_workers
    perf["max_parallel_workers"] = plan.max_parallel_workers
    perf["parallel_pipeline_stages"] = plan.parallel_pipeline_stages
    perf["parallel_team_files"] = plan.parallel_team_files
    config.setdefault("dashboard", {})["precompute_html_filter_slices"] = (
        plan.precompute_html_filter_slices
    )

    sink: logging.Logger = log or logger
    rss_mb: float = get_process_rss_bytes() / (1024**2)
    sink.info(
        "Адаптивные ресурсы: RAM %.1f/%.1f ГБ (%.0f%%), вход %.1f ГБ, "
        "давление=%s, workers=%d, parallel_stages=%s, html_slices=%s",
        mem.available_gb,
        mem.total_gb,
        mem.used_percent,
        input_bytes / (1024**3),
        plan.pressure,
        plan.parallel_workers,
        plan.parallel_pipeline_stages,
        plan.precompute_html_filter_slices,
    )
    for reason in plan.reasons:
        sink.info("  → %s", reason)
    sink.debug(
        "RSS процесса %.0f МБ [class: resource_guard | def: apply_adaptive_resources]",
        rss_mb,
    )
    return plan


def release_memory_if_needed(
    config: dict[str, Any],
    log: logging.Logger | None = None,
    checkpoint: str = "",
) -> PressureLevel:
    """
    При warn/critical вызывает gc.collect() и пишет в лог.
    Вызывать между файлами/этапами загрузки.
    """
    cfg: dict[str, Any] = adaptive_config(config)
    if not cfg["enabled"]:
        return "ok"

    pressure: PressureLevel = memory_pressure(config)
    if pressure == "ok" or not cfg["gc_on_pressure"]:
        return pressure

    collected: int = gc.collect()
    mem: SystemMemory = get_system_memory()
    sink: logging.Logger = log or logger
    label: str = f" ({checkpoint})" if checkpoint else ""
    sink.info(
        "Освобождение памяти%s: gc=%d объектов, RAM свободно %.1f ГБ (%.0f%% занято, %s)",
        label,
        collected,
        mem.available_gb,
        mem.used_percent,
        pressure,
    )
    return pressure


def maybe_free_memory_between_stages(config: dict[str, Any]) -> None:
    """gc.collect() между этапами pipeline (как раньше + при давлении)."""
    perf: dict[str, Any] = config.get("performance", {})
    if not perf.get("free_memory_between_stages", True):
        return
    gc.collect()
    adaptive: dict[str, Any] = adaptive_config(config)
    if adaptive["enabled"]:
        release_memory_if_needed(config, checkpoint="между этапами")
