"""Characterization test: a one-task-file ``tasks`` review through ReviewAction.

Written against the code as it stood before slice 930 added per-part fan-out,
and checked in with a snapshot of the artifact it saved. It must keep passing
unedited: a single task file is one part, and one part returns exactly what the
action returned before fan-out existed. If it fails, fix the code — never
regenerate the snapshot to make it pass.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron import __version__
from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ResolvedModel
from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict
from squadron.review.persistence import REVIEWS_DIR, TASKS_DIR

_P = "squadron.pipeline.actions.review"
_SNAPSHOT = Path(__file__).parent / "snapshots" / "single_file_tasks_review.md"
_MODEL = "claude-sonnet-4-20250514"
_SHA = "0123456789abcdef0123456789abcdef01234567"
_TASK_FILE = "194-tasks.loop-step-type-for-multi-step-bodies.md"
_DESIGN_FILE = "project-documents/user/slices/194-slice.loop-step-type-for-multi-step-bodies.md"
_TASK_PATH = str(TASKS_DIR / _TASK_FILE)
_SAVED_NAME = "194-review.tasks.loop-step-type-for-multi-step-bodies.md"

_SLICE_INFO = {
    "index": 194,
    "name": "loop-step-type",
    "slice_name": "loop-step-type-for-multi-step-bodies",
    "design_file": _DESIGN_FILE,
    "task_files": [_TASK_FILE],
    "arch_file": "project-documents/user/architecture/100-arch.md",
    "project": "squadron",
}


def _review_result() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.CONCERNS,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Task 3 lacks a test",
                description="No test covers the loop exit.",
                file_ref=_TASK_PATH,
                category="testing",
                location=_TASK_PATH,
            ),
        ],
        raw_output="## Summary\nCONCERNS\n\n## Findings\n\n### [CONCERN] Task 3 lacks a test\n",
        template_name="tasks",
        input_files={"input": _TASK_PATH, "against": _DESIGN_FILE},
        timestamp=datetime(2026, 9, 29, 12, 0, 0),
        model=_MODEL,
    )


def _context(cwd: Path) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve_full.return_value = ResolvedModel(_MODEL, None)
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-12345678",
        params={"template": "tasks", "slice": 194},
        step_name="review-tasks",
        step_index=1,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd=str(cwd),
    )


@pytest.mark.asyncio
async def test_single_task_file_review_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for doc in (_TASK_PATH, _DESIGN_FILE):
        (tmp_path / doc).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / doc).write_text("# doc\n")

    with (
        patch(f"{_P}.resolve_slice_info", return_value=_SLICE_INFO),
        patch(f"{_P}.run_review_with_profile", return_value=_review_result()) as run_review,
        patch("squadron.review.persistence.resolve_reviewed_sha", return_value=_SHA),
    ):
        result = await ReviewAction().execute(_context(tmp_path))

    assert run_review.call_count == 1
    assert run_review.call_args[0][1]["input"] == _TASK_PATH

    saved = sorted(p.name for p in (tmp_path / REVIEWS_DIR).glob("*.md"))
    assert saved == [_SAVED_NAME]
    content = (tmp_path / REVIEWS_DIR / _SAVED_NAME).read_text()
    # The version stamp is the one line a release changes; everything else is pinned.
    assert content == _SNAPSHOT.read_text().replace("{squadron_version}", __version__)

    assert result.success is True
    assert result.error is None
    assert result.outputs == {
        "response": _review_result().raw_output,
        "review_file": str(REVIEWS_DIR / _SAVED_NAME),
        "input_file": _TASK_PATH,
    }
    assert result.verdict == "CONCERNS"
    assert result.provenance == "review"
    assert result.score is None
    assert result.criteria is None
    assert result.findings == [
        {
            "id": "F001",
            "severity": "concern",
            "category": "testing",
            "summary": "Task 3 lacks a test",
            "location": _TASK_PATH,
            "location_verified": None,
        }
    ]
    assert result.metadata == {
        "model": _MODEL,
        "requested_model": _MODEL,
        "profile": "sdk",
        "template": "tasks",
    }
