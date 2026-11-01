"""The summary step names the slice's files so a resumed run's summary has content (#282)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.actions.summary import SummaryAction
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ResolvedModel
from squadron.pipeline.summary_artifacts import slice_artifact_paths, with_artifact_section
from squadron.pipeline.usage_capture import UsageCapture
from tests.pipeline.conftest import session_reply

_EXPECTED = "squadron.pipeline.summary_artifacts.expected_artifact_paths"


def _context(cwd: Path, params: dict[str, object]) -> MagicMock:
    ctx = MagicMock(spec=ActionContext)
    ctx.params = params
    ctx.cwd = str(cwd)
    ctx.cf_client = MagicMock()
    ctx.step_name = "summary-3"
    ctx.step_index = 2
    ctx.prior_outputs = {}
    ctx.resolver = MagicMock()
    ctx.resolver.resolve_full.return_value = ResolvedModel("sonnet-id", None)
    ctx.usage_capture = UsageCapture(set())
    ctx.run_id = "run-test"
    return ctx


def test_paths_are_the_existing_design_and_task_files(tmp_path: Path) -> None:
    (tmp_path / "design.md").write_text("design")
    (tmp_path / "tasks.md").write_text("tasks")
    ctx = _context(tmp_path, {"slice": "301"})
    with patch(_EXPECTED, side_effect=[["design.md", "missing.md"], ["tasks.md"]]):
        assert slice_artifact_paths(ctx) == ["design.md", "tasks.md"]


def test_no_slice_param_means_no_paths(tmp_path: Path) -> None:
    assert slice_artifact_paths(_context(tmp_path, {})) == []


def test_unresolvable_slice_warns_and_yields_no_paths(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = _context(tmp_path, {"slice": "301"})
    with (
        patch(_EXPECTED, side_effect=ContextForgeError("no such slice")),
        caplog.at_level(logging.WARNING),
    ):
        assert slice_artifact_paths(ctx) == []
    assert "cannot resolve slice" in caplog.text


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
