"""Тесты split-bundle экспорта JSON для HTML."""

from __future__ import annotations

from pathlib import Path

from src.v1.html_json_export import (
    downsample_days_sorted,
    export_split_html_bundle,
    optimize_aggregation_for_html,
    public_slice_payload,
)


def test_downsample_days_sorted() -> None:
    days: list[int] = list(range(1, 1001))
    sampled: list[int] = downsample_days_sorted(days, 100)
    assert len(sampled) <= 101
    assert sampled[-1] == 1000


def test_optimize_aggregation_adds_full_count() -> None:
    agg: dict = {
        "distribution_series": [{"days_sorted": list(range(2000)), "total_leads": 2000}],
        "pivot_flat": [],
    }
    out = optimize_aggregation_for_html(agg, 500)
    series = out["distribution_series"][0]
    assert len(series["days_sorted"]) <= 501
    assert series["days_sorted_full_count"] == 2000


def test_export_split_html_bundle(tmp_path: Path) -> None:
    config: dict = {
        "dashboard": {
            "html_json": {
                "bundle_mode": "split",
                "compact": True,
                "max_distribution_points": 0,
            }
        }
    }
    filter_slices: dict = {
        "none": {
            "active_filters": [],
            "label": "Без фильтров",
            "aggregations": {
                "group_product": {"distribution_series": [], "pivot_flat": []},
            },
        }
    }
    visualizations: dict = {
        "default_view": {"filter_slice": "none"},
        "filter_catalog": [],
    }
    manifest_path, sizes = export_split_html_bundle(
        meta={"mode": "test"},
        dimensions={"tb": ["A"]},
        visualizations=visualizations,
        filter_slices=filter_slices,
        config=config,
        output_dir=tmp_path,
        prefix="kanban_report",
        timestamp="20260831_120000",
    )
    assert manifest_path.exists()
    assert (tmp_path / "kanban_report_20260831_120000_html" / "slices" / "none.json").exists()
    assert not (tmp_path / "kanban_report_latest.manifest.json").exists()
    assert sizes["manifest"] > 0


def test_public_slice_strips_stats() -> None:
    config: dict = {"dashboard": {"html_json": {"max_distribution_points": 0}}}
    raw: dict = {
        "aggregations": {"group_product": {"distribution_series": []}},
        "_stats_by_mode": {"x": 1},
        "record_count": 10,
    }
    public = public_slice_payload(raw, config)
    assert "_stats_by_mode" not in public
    assert public["record_count"] == 10


def test_export_monolith_embeds_managers_no_html_dir(tmp_path: Path) -> None:
    """Monolith: один JSON со срезами и managers, без каталога *_html."""
    import json

    from src.v1.json_exporter import export_json

    config: dict = {
        "mode": "test",
        "duration_source": "columns",
        "stage_analysis_mode": "status",
        "product_analysis_mode": "group_product",
        "percentiles": [80],
        "filters": {},
        "columns": {},
        "stages_order": [],
        "aggregation": {"metrics": ["days_on_stage"]},
        "output": {"report_prefix": "kanban_report"},
        "dashboard": {
            "html_json": {
                "bundle_mode": "monolith",
                "compact": True,
                "include_statistics": False,
                "embed_managers": True,
                "max_distribution_points": 0,
            }
        },
    }
    filter_slices: dict = {
        "none": {
            "active_filters": [],
            "label": "Без фильтров",
            "aggregations": {
                "group_product": {"distribution_series": [], "pivot_flat": []},
                "group_only": {"distribution_series": [], "pivot_flat": []},
            },
            "_stats_by_mode": {"skip": True},
        }
    }
    visualizations: dict = {
        "default_view": {"filter_slice": "none", "aggregation": "group_product"},
        "filter_catalog": [],
        "filter_slices": {},
    }
    out = tmp_path / "kanban_report_20260831_999999.json"
    export_json(
        stats_by_mode={},
        dimensions={"tb": ["TB1"]},
        config=config,
        output_path=out,
        visualizations=visualizations,
        filter_catalog=[],
        filter_slices=filter_slices,
        manager_payload={
            "meta": {"percentile": 80},
            "records": [],
            "exceedances": [],
            "top_by_tb": [],
            "charts": {"by_tb": [], "facts": []},
        },
    )
    assert out.exists()
    assert not list(tmp_path.glob("*_html"))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["meta"]["json_bundle_mode"] == "monolith"
    assert "none" in data["visualizations"]["filter_slices"]
    assert "_stats_by_mode" not in data["visualizations"]["filter_slices"]["none"]
    assert "managers" in data
    assert "statistics" not in data
