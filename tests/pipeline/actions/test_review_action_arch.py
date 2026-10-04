"""An initiative-scoped review (``plan``, no slice) reviews the arch doc.

Parity with ``sq review arch <n>``: same input document, same artifact name.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ResolvedModel
from squadron.review.models import ReviewResult, Verdict
from squadron.review.persistence import REVIEWS_DIR

_P = "squadron.pipeline.actions.review"
_MODEL = "claude-haiku-4-5-20251001"
_ARCH = "project-documents/user/architecture/100-arch.tally-core.md"


def _context(cwd: Path, params: dict[str, object]) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve_full.return_value = ResolvedModel(_MODEL, None)
    return ActionContext(
        pipeline_name="P2",
        run_id="run-12345678",
        params=params,
        step_name="design-0",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd=str(cwd),
    )


def _result() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="## Summary\nPASS\n",
        template_name="arch",
        input_files={"input": _ARCH},
        timestamp=datetime(2026, 10, 3, 12, 0, 0),
        model=_MODEL,
    )


@pytest.mark.asyncio
async def test_plan_reviews_arch_doc_and_saves_as_arch_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / _ARCH).parent.mkdir(parents=True)
    (tmp_path / _ARCH).write_text("# Architecture: tally core\n")

    with (
        patch(f"{_P}.run_review_with_profile", return_value=_result()) as run_review,
        patch("squadron.review.save_target.resolve_reviewed_sha", return_value=None),
    ):
        result = await ReviewAction().execute(_context(tmp_path, {"template": "arch", "plan": 100}))

    assert result.success, result.error
    assert run_review.call_args[0][1]["input"] == _ARCH
    assert (tmp_path / REVIEWS_DIR / "100-review.arch.tally-core.md").is_file()


@pytest.mark.asyncio
async def test_plan_with_no_arch_doc_fails_the_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with patch(f"{_P}.run_review_with_profile") as run_review:
        result = await ReviewAction().execute(_context(tmp_path, {"template": "arch", "plan": 100}))

    assert not result.success
    assert "100-arch.*.md" in (result.error or "")
    run_review.assert_not_called()
