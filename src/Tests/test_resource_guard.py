"""Тесты адаптивного управления памятью."""

from __future__ import annotations

from pathlib import Path

from src.resource_guard import (
    AdaptivePlan,
    SystemMemory,
    adaptive_config,
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
                "sequential_load_below_total_ram_gb": 16.0,
                "low_ram_max_workers": 2,
                "low_ram_disable_parallel_stages": True,
                "low_ram_disable_parallel_teams": True,
                "warn_max_workers": 2,
                "warn_disable_parallel_stages": True,
                "critical_max_workers": 1,
                "critical_disable_parallel_stages": True,
                "critical_disable_parallel_teams": True,
                "input_size_per_worker_gb": 1.2,
            },
        },
        "dashboard": {"precompute_html_filter_slices": True},
    }


def test_memory_pressure_levels() -> None:
    config: dict = _base_config()
    ok_mem = SystemMemory(total_bytes=32 * 1024**3, available_bytes=8 * 1024**3)
    # свободно 2.8 ГБ → warn по min_available; занято ~91% < critical 92%
    warn_mem = SystemMemory(total_bytes=32 * 1024**3, available_bytes=int(2.8 * 1024**3))
    crit_mem = SystemMemory(total_bytes=32 * 1024**3, available_bytes=1 * 1024**3)

    assert memory_pressure(config, ok_mem) == "ok"
    assert memory_pressure(config, warn_mem) == "warn"
    assert memory_pressure(config, crit_mem) == "critical"


def test_build_plan_low_ram_uses_config_workers() -> None:
    """RAM < 16 ГБ → осторожный режим с low_ram_max_workers=2."""
    config: dict = _base_config()
    config["parallel_workers"] = 8
    mem = SystemMemory(total_bytes=12 * 1024**3, available_bytes=5 * 1024**3)
    input_bytes: int = 1 * 1024**3

    plan: AdaptivePlan = build_adaptive_plan(config, input_bytes, mem)

    assert plan.parallel_workers == 2
    assert plan.max_parallel_workers == 2
    assert plan.parallel_pipeline_stages is False
    assert plan.parallel_team_files is False
    assert any("осторожный режим" in r for r in plan.reasons)


def test_build_plan_low_ram_workers_from_config() -> None:
    """low_ram_max_workers=4 поднимает потолок осторожного режима."""
    config: dict = _base_config()
    config["parallel_workers"] = 8
    config["performance"]["adaptive_resources"]["low_ram_max_workers"] = 4
    mem = SystemMemory(total_bytes=12 * 1024**3, available_bytes=8 * 1024**3)

    plan: AdaptivePlan = build_adaptive_plan(config, 0, mem)
    assert plan.parallel_workers == 4


def test_build_plan_critical_disables_html_slices() -> None:
    config: dict = _base_config()
    mem = SystemMemory(total_bytes=32 * 1024**3, available_bytes=1 * 1024**3)

    plan: AdaptivePlan = build_adaptive_plan(config, 0, mem)

    assert plan.pressure == "critical"
    assert plan.parallel_workers == 1
    assert plan.precompute_html_filter_slices is False


def test_build_plan_warn_uses_warn_max_workers() -> None:
    config: dict = _base_config()
    config["parallel_workers"] = 8
    config["performance"]["adaptive_resources"]["warn_max_workers"] = 3
    # 32 ГБ total, 2.8 ГБ free → warn (min_available=3), занято < 92%
    mem = SystemMemory(total_bytes=32 * 1024**3, available_bytes=int(2.8 * 1024**3))

    plan: AdaptivePlan = build_adaptive_plan(config, 0, mem)
    assert plan.pressure == "warn"
    assert plan.parallel_workers == 3
    assert plan.parallel_pipeline_stages is False


def test_adaptive_config_defaults() -> None:
    cfg = adaptive_config({"performance": {}})
    assert cfg["sequential_load_below_total_ram_gb"] == 16.0
    assert cfg["low_ram_max_workers"] == 2
    assert cfg["warn_max_workers"] == 2
    assert cfg["critical_max_workers"] == 1


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
