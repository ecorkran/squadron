"""The summary step names the run's files so a resumed run's summary has content (#282)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.review_outputs import ReviewOutputKey
from squadron.pipeline.actions.summary import SummaryAction
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pipeline.resolver import ResolvedModel
from squadron.pipeline.summary_artifacts import (
    SUMMARY_READ_TOOLS,
    summary_sources,
    with_artifact_section,
)
from squadron.pipeline.usage_capture import UsageCapture
from tests.pipeline.conftest import session_reply

_EXPECTED = "squadron.pipeline.summary_artifacts.expected_artifact_paths"


def _review_result(review_file: str) -> ActionResult:
    return ActionResult(
        success=True,
        action_type=ActionType.REVIEW,
        outputs={ReviewOutputKey.REVIEW_FILE: review_file},
    )


def _context(
    cwd: Path,
    params: dict[str, object],
    prior_outputs: dict[str, ActionResult] | None = None,
) -> MagicMock:
    ctx = MagicMock(spec=ActionContext)
    ctx.params = params
    ctx.cwd = str(cwd)
    ctx.cf_client = MagicMock()
    ctx.step_name = "summary-3"
    ctx.step_index = 2
    ctx.prior_outputs = prior_outputs or {}
    ctx.resolver = MagicMock()
    ctx.resolver.resolve_full.return_value = ResolvedModel("sonnet-id", None)
    ctx.usage_capture = UsageCapture(set())
    ctx.run_id = "run-test"
    return ctx


def _sdk_paths(ctx: MagicMock) -> list[str]:
    return summary_sources(ctx, is_sdk=True, declared_tools=None, model_allows_tools=True).paths


def test_paths_are_the_existing_design_and_task_files(tmp_path: Path) -> None:
    (tmp_path / "design.md").write_text("design")
    (tmp_path / "tasks.md").write_text("tasks")
    ctx = _context(tmp_path, {"slice": "301"})
    with patch(_EXPECTED, side_effect=[["design.md", "missing.md"], ["tasks.md"]]):
        assert _sdk_paths(ctx) == ["design.md", "tasks.md"]


def test_each_loop_slice_record_resolves_by_its_index(tmp_path: Path) -> None:
    (tmp_path / "design.md").write_text("design")
    record = {"index": "180", "name": "Slice-Writing Pipeline", "dependencies": [100]}
    ctx = _context(tmp_path, {"slice": record})
    with patch(_EXPECTED, side_effect=[["design.md"], []]) as expected:
        assert _sdk_paths(ctx) == ["design.md"]
    assert expected.call_args_list[0].args[1] == 180


def test_no_slice_param_and_no_reviews_means_no_paths(tmp_path: Path) -> None:
    assert _sdk_paths(_context(tmp_path, {})) == []


def test_unresolvable_slice_warns_and_yields_no_paths(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = _context(tmp_path, {"slice": "301"})
    with (
        patch(_EXPECTED, side_effect=ContextForgeError("no such slice")),
        caplog.at_level(logging.WARNING),
    ):
        assert _sdk_paths(ctx) == []
    assert "cannot resolve slice" in caplog.text


def test_review_files_are_listed_once_across_rounds(tmp_path: Path) -> None:
    (tmp_path / "tasks-review.md").write_text("review")
    prior = {
        "tasks:review-0": _review_result("tasks-review.md"),
        "tasks:review-1": _review_result("tasks-review.md"),
    }
    assert _sdk_paths(_context(tmp_path, {}, prior)) == ["tasks-review.md"]


def test_review_file_missing_on_disk_is_dropped(tmp_path: Path) -> None:
    prior = {"tasks:review-0": _review_result("gone.md")}
    assert _sdk_paths(_context(tmp_path, {}, prior)) == []


def test_non_sdk_step_without_tools_gets_read_file_when_there_are_files(tmp_path: Path) -> None:
    (tmp_path / "r.md").write_text("review")
    ctx = _context(tmp_path, {}, {"s:review-0": _review_result("r.md")})
    sources = summary_sources(ctx, is_sdk=False, declared_tools=None, model_allows_tools=True)
    assert sources.tools == list(SUMMARY_READ_TOOLS)
    assert sources.paths == ["r.md"]


def test_non_sdk_step_without_files_gets_no_tools(tmp_path: Path) -> None:
    sources = summary_sources(
        _context(tmp_path, {}), is_sdk=False, declared_tools=None, model_allows_tools=True
    )
    assert sources.tools is None
    assert sources.paths == []


def test_non_sdk_declared_tools_are_kept_as_declared(tmp_path: Path) -> None:
    (tmp_path / "r.md").write_text("review")
    ctx = _context(tmp_path, {}, {"s:review-0": _review_result("r.md")})
    sources = summary_sources(
        ctx, is_sdk=False, declared_tools=["read_file", "grep"], model_allows_tools=True
    )
    assert sources.tools == ["read_file", "grep"]
    assert sources.paths == ["r.md"]


@pytest.mark.parametrize(
    ("declared", "allows"),
    [(["grep"], True), (None, False)],
    ids=["declared-without-read_file", "model-without-tool-use"],
)
def test_non_sdk_is_not_told_about_files_it_cannot_read(
    tmp_path: Path, declared: list[str] | None, allows: bool
) -> None:
    (tmp_path / "r.md").write_text("review")
    ctx = _context(tmp_path, {}, {"s:review-0": _review_result("r.md")})
    sources = summary_sources(ctx, is_sdk=False, declared_tools=declared, model_allows_tools=allows)
    assert sources.paths == []


def test_section_lists_paths_before_instructions() -> None:
    text = with_artifact_section("INSTRUCTIONS", ["a.md", "b.md"])
    assert text.index("- a.md") < text.index("- b.md") < text.index("INSTRUCTIONS")


def test_section_is_absent_without_paths() -> None:
    assert with_artifact_section("INSTRUCTIONS", []) == "INSTRUCTIONS"


@pytest.mark.asyncio
async def test_sdk_summary_instructions_name_the_slice_files(tmp_path: Path) -> None:
    (tmp_path / "design.md").write_text("design")
    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value=session_reply("SUMMARY"))
    ctx = _context(tmp_path, {"slice": "301", "model": "sonnet", "emit": ["stdout"]})
    ctx.sdk_session = session
    with patch(_EXPECTED, side_effect=[["design.md"], []]):
        result = await SummaryAction().execute(ctx)
    assert result.success
    sent = session.capture_summary.call_args.kwargs["instructions"]
    assert "- design.md" in sent


@pytest.mark.asyncio
async def test_non_sdk_summary_gets_read_file_and_the_review_path(tmp_path: Path) -> None:
    (tmp_path / "r.md").write_text("review")
    ctx = _context(
        tmp_path,
        {"model": "minimax", "emit": ["stdout"]},
        {"s:review-0": _review_result("r.md")},
    )
    ctx.resolver.resolve_full.return_value = ResolvedModel("mm-id", "openrouter")
    capture = AsyncMock(return_value=("SUMMARY", {}))
    with patch("squadron.pipeline.actions.summary.capture_summary_via_profile_with_telemetry", capture):
        result = await SummaryAction().execute(ctx)
    assert result.success, result.error
    assert capture.call_args.kwargs["allowed_tools"] == list(SUMMARY_READ_TOOLS)
    assert "- r.md" in capture.call_args.kwargs["instructions"]
