"""Report renderers (slice 425 Task 41, D13)."""

from __future__ import annotations

from pathlib import Path

from squadron.benchmark.bench_report_render import render_json, render_text
from squadron.benchmark.report_models import BenchmarkReport
from tests.benchmark.report_support import fixture_world

GOLDEN = Path(__file__).parent / "fixtures" / "report_golden.txt"
HEADINGS_IN_ORDER = (
    "objective grade",
    "paired (95% bootstrap over cases)",
    "checks vs baseline",
    "review findings (",
    "cost / turns / time",
    "absences and exclusions",
)


def test_the_section_headings_appear_in_d13s_order(tmp_path: Path) -> None:
    text = render_text(fixture_world(tmp_path).build())
    positions = [text.index(heading) for heading in HEADINGS_IN_ORDER]
    assert positions == sorted(positions)


def test_the_sample_count_section_comes_last_when_an_estimate_exists(tmp_path: Path) -> None:
    from tests.benchmark.test_bench_report_review import estimate_for

    world = fixture_world(tmp_path)
    text = render_text(world.build(estimate=estimate_for(world)))
    assert text.index("absences and exclusions") < text.index("sample count (measured")


def test_the_json_loads_back_into_the_report_model(tmp_path: Path) -> None:
    report = fixture_world(tmp_path).build()
    loaded = BenchmarkReport.model_validate_json(render_json(report))
    assert loaded == report


def test_the_text_carries_the_unmeasured_reviewer_flag(tmp_path: Path) -> None:
    text = render_text(fixture_world(tmp_path).build())
    assert "review findings (unmeasured reviewer: no recall data for gpt-review)" in text


def test_the_text_matches_the_golden_for_the_hand_computed_fixture(tmp_path: Path) -> None:
    text = render_text(fixture_world(tmp_path).build())
    assert text + "\n" == GOLDEN.read_text(encoding="utf-8")
