"""Rich views shared by the run, pipelines and runs commands (slice 199)."""

from __future__ import annotations

import dataclasses
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from rich.console import Console

from squadron.cli.run_views import (
    RESUME_PROBLEM_MARKERS,
    activity_cell,
    at_cell,
    display_status,
    format_duration,
    render_pipeline_listing,
    render_run_listing,
    render_run_status,
    resume_cell,
    target_cell,
)
from squadron.data import data_dir
from squadron.pipeline.loader import discover_pipelines
from squadron.pipeline.run_listing import ResumeKind, ResumePoint, ResumeProblem, RunSummary
from squadron.pipeline.run_liveness import LivenessAssessment, RunLiveness
from squadron.pipeline.state import RUNNING_STATUS, ActiveItem, CheckpointState, RunState


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
            (False, "No running or resumable runs. Use --all to include completed runs."),
            (True, "No running or resumable runs."),
        ],
    )
    def test_empty_result(
        self, capsys: pytest.CaptureFixture[str], include_all: bool, expected: str
    ) -> None:
        render_run_listing([], include_all=include_all)
        assert capsys.readouterr().out.strip() == expected


def test_status_panel_escapes_markup_in_run_values(capsys: pytest.CaptureFixture[str]) -> None:
    """A bracketed param or pause reason prints literally instead of breaking Rich (review F002)."""
    state = RunState(
        run_id="run-x",
        pipeline="p4",
        params={"note": "[/oops]"},
        status="paused",
        started_at=datetime(2026, 10, 6, tzinfo=UTC),
        updated_at=datetime(2026, 10, 6, tzinfo=UTC),
        checkpoint=CheckpointState(
            reason="[bold]why[/bold]", step="[red]s", paused_at=datetime(2026, 10, 6, tzinfo=UTC)
        ),
    )

    render_run_status(state)
    out = capsys.readouterr().out

    assert "[/oops]" in out
    assert "[bold]why[/bold]" in out
    assert "'[red]s'" in out


# ---------------------------------------------------------------------------
# Running rows, liveness statuses and column fitting (slice 174)
# ---------------------------------------------------------------------------


def _running(
    liveness: RunLiveness,
    *,
    owned: bool = True,
    active_step: str | None = "slices",
    active_item: ActiveItem | None = None,
    params: dict[str, object] | None = None,
) -> RunSummary:
    assessment = LivenessAssessment(
        liveness,
        elapsed=timedelta(hours=1, minutes=4) if owned else None,
        progress_age=timedelta(seconds=40),
        heartbeat_age=timedelta(minutes=12),
    )
    return dataclasses.replace(
        _summary(status=RUNNING_STATUS, params=params),
        liveness=assessment,
        active_step=active_step,
        active_item=active_item,
    )


def _render(summaries: list[RunSummary], *, width: int, terminal: bool) -> str:
    buffer = io.StringIO()
    # Off a terminal rich picks no colour system, as it does for a real pipe.
    console = (
        Console(file=buffer, width=width, force_terminal=True, color_system="truecolor")
        if terminal
        else Console(file=buffer, width=width)
    )
    render_run_listing(summaries, include_all=False, console=console)
    return buffer.getvalue()


class TestRunningRows:
    @pytest.mark.parametrize(
        ("liveness", "text", "color"),
        [
            (RunLiveness.LIVE, "running", "cyan"),
            (RunLiveness.UNOWNED, "running", "cyan"),
            (RunLiveness.STALE, "stale", "yellow"),
            (RunLiveness.ORPHANED, "orphaned", "red"),
        ],
    )
    def test_display_status_and_colour(self, liveness: RunLiveness, text: str, color: str) -> None:
        assert display_status(_running(liveness)) == (text, color)

    def test_stored_statuses_keep_their_colours(self) -> None:
        assert display_status(_summary(status="paused")) == ("paused", "yellow")
        assert display_status(_summary(status="failed")) == ("failed", "red")

    def test_at_shows_step_and_item(self) -> None:
        item = ActiveItem(position=2, total=12, index="182")
        assert at_cell(_running(RunLiveness.LIVE, active_item=item)) == "slices [item 3/12 · 182]"
        no_index = ActiveItem(position=0, total=4, index=None)
        assert at_cell(_running(RunLiveness.LIVE, active_item=no_index)) == "slices [item 1/4]"
        assert at_cell(_running(RunLiveness.ORPHANED)) == "slices"

    @pytest.mark.parametrize(
        ("liveness", "expected"),
        [
            (RunLiveness.LIVE, "1h04m · 40s ago"),
            (RunLiveness.ORPHANED, "1h04m · 40s ago"),
            (RunLiveness.STALE, "1h04m · 40s ago · heartbeat 12m00s ago"),
        ],
    )
    def test_activity(self, liveness: RunLiveness, expected: str) -> None:
        assert activity_cell(_running(liveness)) == expected

    def test_unowned_activity_is_empty(self) -> None:
        assert activity_cell(_running(RunLiveness.UNOWNED, owned=False)) == ""

    @pytest.mark.parametrize(
        ("delta", "text"),
        [
            (timedelta(seconds=40), "40s"),
            (timedelta(minutes=12, seconds=5), "12m05s"),
            (timedelta(hours=1, minutes=4), "1h04m"),
            (timedelta(days=3, hours=2), "3d02h"),
        ],
    )
    def test_format_duration(self, delta: timedelta, text: str) -> None:
        assert format_duration(delta) == text


class TestRunListingWidth:
    LONG = {"plan": "180", "model": "opus", "max-revisions": "2", "note": "x" * 60}

    def test_terminal_truncates_target_and_keeps_run_id(self) -> None:
        out = _render([_running(RunLiveness.LIVE, params=self.LONG)], width=90, terminal=True)
        lines = [line for line in out.splitlines() if "run-20261006-p4-abc" in line]

        assert len(lines) == 1
        assert "…" in lines[0]
        assert "\x1b[36mrunning" in lines[0]  # cyan

    def test_piped_output_is_never_truncated(self) -> None:
        out = _render([_running(RunLiveness.LIVE, params=self.LONG)], width=90, terminal=False)

        assert "…" not in out
        assert "x" * 60 in out
        assert "\x1b[" not in out
