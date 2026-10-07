"""Rich views shared by the run, pipelines and runs commands (slice 199)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from squadron.cli.run_views import (
    RESUME_PROBLEM_MARKERS,
    render_pipeline_listing,
    render_run_listing,
    resume_cell,
    target_cell,
)
from squadron.data import data_dir
from squadron.pipeline.loader import discover_pipelines
from squadron.pipeline.run_listing import ResumeKind, ResumePoint, ResumeProblem, RunSummary


def write_pipeline(directory: Path, name: str, description: str = "") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    data = {
        "name": name,
        "description": description or f"{name} pipeline",
        "steps": [{"design": {"phase": 4}}],
    }
    (directory / f"{name}.yaml").write_text(yaml.dump(data))


class TestPipelineListing:
    def test_groups_in_listing_order_with_shadowing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project, user = tmp_path / "project", tmp_path / "user"
        write_pipeline(project, "zeta")
        write_pipeline(project, "alpha")
        write_pipeline(project, "p4", "project copy of p4")
        write_pipeline(user, "mine")

        render_pipeline_listing(discover_pipelines(project_dir=project, user_dir=user))
        out = capsys.readouterr().out

        built_in_count = len(list((data_dir() / "pipelines").glob("*.yaml"))) - 1  # p4 shadowed
        built_in = out.index(f"Built-in ({built_in_count})")
        project_at = out.index("Project (3)")
        user_at = out.index("User (1)")
        assert built_in < project_at < user_at
        assert out.index("alpha") < out.index("zeta")
        # p4 appears only under Project, as its project copy.
        assert "project copy of p4" in out[project_at:user_at]
        assert " p4 " not in out[built_in:project_at]

    def test_empty_group_is_omitted(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        render_pipeline_listing(
            discover_pipelines(project_dir=tmp_path / "none", user_dir=tmp_path / "none")
        )
        out = capsys.readouterr().out

        assert "Built-in (" in out
        assert "Project (" not in out
        assert "User (" not in out

    def test_no_pipelines(self, capsys: pytest.CaptureFixture[str]) -> None:
        render_pipeline_listing([])
        assert capsys.readouterr().out.strip() == "No pipelines found."


def _summary(
    resume: ResumePoint | None = None,
    problem: ResumeProblem | None = None,
    status: str = "paused",
    params: dict[str, object] | None = None,
) -> RunSummary:
    return RunSummary(
        run_id="run-20261006-p4-abc",
        pipeline="p4",
        params=params if params is not None else {"slice": "199"},
        status=status,
        resume=resume,
        problem=problem,
        started_at=datetime(2026, 10, 6, 14, 2, tzinfo=UTC),
    )


class TestRunListing:
    def test_every_problem_has_marker_text(self) -> None:
        assert set(RESUME_PROBLEM_MARKERS) == set(ResumeProblem)
        assert all(RESUME_PROBLEM_MARKERS[p] for p in ResumeProblem)

    @pytest.mark.parametrize(
        ("summary", "expected"),
        [
            (_summary(ResumePoint(ResumeKind.STEP, "review-design")), "review-design"),
            (_summary(ResumePoint(ResumeKind.ITEMS, "slices", 3, 1)), "3 items in slices (1 accept)"),
            (_summary(ResumePoint(ResumeKind.ITEMS, "slices", 2, 0)), "2 items in slices"),
            (
                _summary(problem=ResumeProblem.PIPELINE_UNAVAILABLE),
                "<pipeline unavailable>",
            ),
            (_summary(status="completed"), ""),
        ],
    )
    def test_resume_cell(self, summary: RunSummary, expected: str) -> None:
        assert resume_cell(summary) == expected

    def test_target_joins_params(self) -> None:
        assert target_cell({"slice": "199", "model": "opus"}) == "slice=199 model=opus"

    def test_table_row_and_hints(self, capsys: pytest.CaptureFixture[str]) -> None:
        render_run_listing([_summary(problem=ResumeProblem.REPORT_UNREADABLE)], include_all=False)
        out = " ".join(capsys.readouterr().out.split())

        # At the pinned 80 columns the run-id, status and resume cell are never folded.
        assert "run-20261006-p4-abc" in out
        assert "<report unreadable>" in out
        assert "Resume a step: sq run --resume <run-id>" in out
        assert "--item N --decision retry" in out

    @pytest.mark.parametrize(
        ("include_all", "expected"),
        [
            (False, "No resumable runs. Use --all to include completed runs."),
            (True, "No resumable runs."),
        ],
    )
    def test_empty_result(
        self, capsys: pytest.CaptureFixture[str], include_all: bool, expected: str
    ) -> None:
        render_run_listing([], include_all=include_all)
        assert capsys.readouterr().out.strip() == expected
