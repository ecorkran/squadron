"""ReviewAction over a split task breakdown: one review part per task file (slice 930)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pipeline.resolver import ResolvedModel
from squadron.providers.errors import ProviderError
from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict
from squadron.review.persistence import REVIEWS_DIR, TASKS_DIR, save_review_result

_P = "squadron.pipeline.actions.review"
_MODEL = "claude-sonnet-4-20250514"
_DESIGN = "project-documents/user/slices/194-slice.loop-step-type.md"
_STEM = "194-review.tasks.loop-step-type"
_NAMES = ["194-tasks.loop-step-type-1.md", "194-tasks.loop-step-type-2.md"]
_PATHS = [str(TASKS_DIR / name) for name in _NAMES]

_SLICE_INFO = {
    "index": 194,
    "name": "loop-step-type",
    "slice_name": "loop-step-type",
    "design_file": _DESIGN,
    "task_files": _NAMES,
    "arch_file": "project-documents/user/architecture/100-arch.md",
    "project": "squadron",
}


def review_result(
    verdict: Verdict = Verdict.PASS,
    raw: str = "## Summary\nPASS\n",
    score: float | None = None,
    tool_calls_made: int | None = None,
) -> ReviewResult:
    findings = (
        []
        if verdict == Verdict.PASS
        else [
            ReviewFinding(
                severity=Severity.CONCERN,
                title=f"{verdict} finding",
                description="Something to fix.",
                category="testing",
            )
        ]
    )
    return ReviewResult(
        verdict=verdict,
        findings=findings,
        raw_output=raw,
        template_name="tasks",
        input_files={},
        timestamp=datetime(2026, 9, 29, 12, 0, 0),
        model=_MODEL,
        score=score,
        tools_given=["Read"] if tool_calls_made is not None else None,
        tool_calls_made=tool_calls_made,
    )


def context(cwd: Path, **params: object) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve_full.return_value = ResolvedModel(_MODEL, None)
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-12345678",
        params={"template": "tasks", "slice": 194, **params},
        step_name="review-tasks",
        step_index=1,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd=str(cwd),
    )


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A project tree with a two-part task breakdown and the slice lookup mocked."""
    monkeypatch.chdir(tmp_path)
    for doc in (*_PATHS, _DESIGN):
        (tmp_path / doc).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / doc).write_text("# doc\n")
    with (
        patch(f"{_P}.resolve_slice_info", return_value=_SLICE_INFO),
        patch("squadron.review.persistence.resolve_reviewed_sha", return_value="abc123"),
    ):
        yield tmp_path


async def run(
    project: Path, *results: ReviewResult | Exception, **params: object
) -> tuple[ActionResult, MagicMock]:
    with patch(f"{_P}.run_review_with_profile", side_effect=list(results)) as run_review:
        action_result = await ReviewAction().execute(context(project, **params))
    return action_result, run_review


def saved_names(project: Path) -> list[str]:
    return sorted(p.name for p in (project / REVIEWS_DIR).glob("*.md"))


class TestPartLoop:
    @pytest.mark.asyncio
    async def test_each_task_file_is_reviewed_and_saved_in_order(self, project: Path) -> None:
        _, run_review = await run(project, review_result(), review_result())

        assert [c.args[1]["input"] for c in run_review.call_args_list] == _PATHS
        assert saved_names(project) == [f"{_STEM}.part-1.md", f"{_STEM}.part-2.md"]
        for suffix, path in zip(("part-1", "part-2"), _PATHS, strict=True):
            body = (project / REVIEWS_DIR / f"{_STEM}.{suffix}.md").read_text()
            assert f"sourceDocument: {path}\n" in body

    @pytest.mark.asyncio
    async def test_missing_part_file_fails_before_any_model_call(self, project: Path) -> None:
        (project / _PATHS[1]).unlink()

        result, run_review = await run(project, review_result(), review_result())

        assert result.success is False
        assert "part 2/2" in (result.error or "")
        assert _PATHS[1] in (result.error or "")
        assert run_review.call_count == 0

    @pytest.mark.asyncio
    async def test_provider_failure_on_part_two_keeps_part_one(
        self, project: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger=_P):
            result, _ = await run(project, review_result(), ProviderError("model went away"))

        assert result.success is False
        assert saved_names(project) == [f"{_STEM}.part-1.md", f"{_STEM}.part-2.md"]
        assert "## Provider Failure" in (project / REVIEWS_DIR / f"{_STEM}.part-2.md").read_text()
        assert "## Provider Failure" not in (project / REVIEWS_DIR / f"{_STEM}.part-1.md").read_text()
        assert "provider failed in step review-tasks part 2/2" in caplog.text

    @pytest.mark.asyncio
    async def test_save_failure_on_part_two_is_logged_and_not_fatal(
        self, project: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with (
            patch(f"{_P}.save_review_result", side_effect=save_first_call_only()),
            caplog.at_level(logging.ERROR, logger=_P),
        ):
            result, run_review = await run(project, review_result(), review_result(Verdict.CONCERNS))

        assert run_review.call_count == 2
        assert result.success is True
        assert saved_names(project) == [f"{_STEM}.part-1.md"]
        assert (
            f"failed to persist review file for step review-tasks part 2/2: {_PATHS[1]}" in caplog.text
        )

    @pytest.mark.asyncio
    async def test_explicit_input_with_slice_is_one_unsuffixed_part(self, project: Path) -> None:
        """An explicit ``input:`` skips slice resolution, so there is nothing to fan out."""
        _, run_review = await run(project, review_result(), input=_PATHS[0], against=_DESIGN)

        assert run_review.call_count == 1
        assert run_review.call_args.args[1]["input"] == _PATHS[0]
        assert saved_names(project) == ["1-review.tasks.review-tasks.md"]


def save_first_call_only() -> Callable[..., Path]:
    """A save side effect: the first call really saves, every later one raises OSError."""
    calls: list[None] = []

    def _save(*args: Any, **kwargs: Any) -> Path:
        calls.append(None)
        if len(calls) > 1:
            raise OSError("disk full")
        return save_review_result(*args, **kwargs)

    return _save
