"""Бенчмарк этапов Excel v2 pipeline (запуск: python -m src.Tests.bench_v2_pipeline)."""

from __future__ import annotations

import time
import tracemalloc
from typing import Any, Callable

from src.excel_loader import load_all_files
from src.excel_report.config_loader import (
    config_for_shared_modules,
    get_excel_v2_file_list,
    get_excel_v2_input_dir,
    load_excel_v2_config,
)
from src.excel_report.exceedance import attach_p80_exceedance
from src.excel_report.manager_summary import build_manager_reports
from src.excel_report.norms import build_norms_tables, build_p80_lookup_frames, norms_to_export_frame
from src.excel_report.parallel_utils import run_snapshot_records_teams_parallel
from src.excel_report.snapshot import build_lead_snapshot, snapshot_to_export_frame
from src.excel_report.team_enrich import enrich_snapshot_with_team_dfs
from src.filters import apply_filters, filter_terminal_deal_stage_rows
from src.lead_tracker import build_lead_stage_records


def _bench(name: str, fn: Callable[[], Any], stages: dict[str, tuple[float, float]]) -> Any:
    tracemalloc.start()
    t0: float = time.monotonic()
    result: Any = fn()
    elapsed: float = time.monotonic() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    stages[name] = (elapsed, peak / 1024 / 1024)
    return result


def main() -> None:
    config: dict = load_excel_v2_config("config_excel_v2.json")
    shared: dict = config_for_shared_modules(config)
    input_dir = get_excel_v2_input_dir(config)
    files = get_excel_v2_file_list(config)
    stages: dict[str, tuple[float, float]] = {}

    raw = _bench("1_load", lambda: load_all_files(config, input_dir, files, None), stages)
    rows_loaded = len(raw)
    filtered = _bench(
        "2_filters",
        lambda: filter_terminal_deal_stage_rows(apply_filters(raw, config), config),
        stages,
    )
    rows_filtered = len(filtered)
    del raw

    snapshot, records, lt, dt = _bench(
        "3_parallel_bundle",
        lambda: run_snapshot_records_teams_parallel(filtered, config, shared),
        stages,
    )
    snapshot = _bench(
        "4_team_enrich",
        lambda: enrich_snapshot_with_team_dfs(snapshot, lt, dt, config),
        stages,
    )

    _bench(
        "5_snapshot_sequential",
        lambda: build_lead_snapshot(filtered, config),
        stages,
    )
    _bench(
        "6_records_sequential",
        lambda: build_lead_stage_records(filtered, config, None),
        stages,
    )

    combined_norms, by_tb, overall = _bench(
        "7_norms",
        lambda: build_norms_tables(records, config),
        stages,
    )
    tb_p80, all_p80 = build_p80_lookup_frames(by_tb, overall, config)
    snapshot = _bench(
        "8_p80_exceedance",
        lambda: attach_p80_exceedance(snapshot, tb_p80, all_p80, config),
        stages,
    )
    _bench("9_managers", lambda: build_manager_reports(snapshot, config), stages)
    _bench(
        "10_export_frames",
        lambda: (
            snapshot_to_export_frame(snapshot, config),
            norms_to_export_frame(combined_norms, config),
        ),
        stages,
    )

    total: float = sum(v[0] for v in stages.values())
    print(f"\n=== Benchmark v2 (loaded {rows_loaded:,}, filtered {rows_filtered:,}, files {len(files)}) ===")
    for name, (sec, mb) in stages.items():
        print(f"  {name:28s} {sec:7.2f}s  peak ~{mb:6.0f} MB")
    print(f"  {'TOTAL (with duplicate seq tests)':28s} {total:7.2f}s")

    core = sum(stages[k][0] for k in stages if k not in {"5_snapshot_sequential", "6_records_sequential"})
    print(f"\n  Core pipeline (без дублирующих seq-тестов): {core:.2f}s")
    ratio = 16_000_000 / max(rows_loaded, 1)
    print(f"\n  Наивная экстраполяция на 16M строк (x{ratio:.0f}): ~{core * ratio / 60:.0f} мин")


if __name__ == "__main__":
    main()
