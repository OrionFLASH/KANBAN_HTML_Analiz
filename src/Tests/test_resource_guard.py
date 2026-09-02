"""Тесты адаптивного управления памятью."""

from __future__ import annotations

from pathlib import Path

from src.resource_guard import (
    AdaptivePlan,
    SystemMemory,
    apply_adaptive_resources,
    build_adaptive_plan,
    get_system_memory,
    memory_pressure,
    sum_input_bytes,
)


def _base_config() -> dict:
    return {
        "parallel_workers": 0,
        "_parallel_workers_explicit": 0,
        "performance": {
            "max_parallel_workers": 8,
            "reserve_cpu_cores": 1,
            "parallel_pipeline_stages": True,
            "parallel_team_files": True,
            "adaptive_resources": {
                "enabled": True,
                "min_available_ram_gb": 3.0,
                "critical_available_ram_gb": 1.5,
                "warn_used_ram_percent": 80.0,
                "critical_used_ram_percent": 92.0,
                "sequential_load_below_total_ram_gb": 20.0,
                "input_size_per_worker_gb": 1.2,
            },
        },
        "dashboard": {"precompute_html_filter_slices": True},
    }


def test_memory_pressure_levels() -> None:
    config: dict = _base_config()
    ok_mem = SystemMemory(total_bytes=16 * 1024**3, available_bytes=8 * 1024**3)
    warn_mem = SystemMemory(total_bytes=16 * 1024**3, available_bytes=2 * 1024**3)
    crit_mem = SystemMemory(total_bytes=16 * 1024**3, available_bytes=1 * 1024**3)

    assert memory_pressure(config, ok_mem) == "ok"
    assert memory_pressure(config, warn_mem) == "warn"
    assert memory_pressure(config, crit_mem) == "critical"


def test_build_plan_16gb_prod_input() -> None:
    """16 ГБ RAM + большой вход → последовательная загрузка."""
    config: dict = _base_config()
    mem = SystemMemory(total_bytes=16 * 1024**3, available_bytes=5 * 1024**3)
    input_bytes: int = 3 * 1024**3

    plan: AdaptivePlan = build_adaptive_plan(config, input_bytes, mem)

    assert plan.parallel_workers == 1
    assert plan.parallel_pipeline_stages is False


def test_build_plan_critical_disables_html_slices() -> None:
    config: dict = _base_config()
    mem = SystemMemory(total_bytes=32 * 1024**3, available_bytes=1 * 1024**3)

    plan: AdaptivePlan = build_adaptive_plan(config, 0, mem)

    assert plan.pressure == "critical"
    assert plan.parallel_workers == 1
    assert plan.precompute_html_filter_slices is False


def test_apply_adaptive_mutates_config(tmp_path: Path) -> None:
    config: dict = _base_config()
    data_file: Path = tmp_path / "sample.xlsx"
    data_file.write_bytes(b"x" * 1024)

    plan = apply_adaptive_resources(config, tmp_path, [data_file.name], log=None)

    assert plan is not None
    assert config["parallel_workers"] >= 1
    assert "performance" in config


def test_sum_input_bytes(tmp_path: Path) -> None:
    f1 = tmp_path / "a.xlsx"
    f2 = tmp_path / "b.xlsx"
    f1.write_bytes(b"12345")  # 5 байт
    f2.write_bytes(b"67")  # 2 байта

    assert sum_input_bytes(tmp_path, ["a.xlsx", "b.xlsx", "missing.xlsx"]) == 7


def test_get_system_memory_smoke() -> None:
    mem = get_system_memory()
    assert mem.total_bytes >= 0
    assert mem.available_bytes >= 0
    # На реальной ОС (не CI без /proc и без darwin API) ожидаем ненулевой total
    import sys

    if sys.platform in {"darwin", "win32", "linux"}:
        assert mem.total_bytes > 0, f"RAM не определена на {sys.platform}"
        assert mem.available_bytes > 0
