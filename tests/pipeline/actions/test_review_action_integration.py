"""Integration tests: end-to-end pipeline review with 'code' template diff injection."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.models import ActionContext
from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict
from squadron.review.templates import ReviewTemplate

_P = "squadron.pipeline.actions.review"
_DIFF_RANGE = "abc123...slice-194"

_SLICE_INFO = {
    "index": 194,
    "name": "loop-step-type",
    "slice_name": "loop-step-type-for-multi-step-bodies",
    "design_file": "project-documents/user/slices/194-slice.md",
    "task_files": ["194-tasks.loop-step-type-for-multi-step-bodies.md"],
    "arch_file": "project-documents/user/architecture/100-arch.md",
}


def _make_context(params: dict[str, object]) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-4-20250514", None)
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-12345678",
        params=params,
        step_name="code-review",
        step_index=1,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd="/tmp/test",
    )


def _mock_template() -> ReviewTemplate:
    mock = MagicMock(spec=ReviewTemplate, name="code")
    mock.required_inputs = []
    mock.optional_inputs = []
    return mock


def _make_review_result() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.CONCERNS,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Missing docstring",
                description="Public method lacks docstring.",
                file_ref="src/foo.py:10",
                category="documentation",
                location="src/foo.py:10",
            ),
        ],
        raw_output="## Review\nCONCERNS\n",
        template_name="code",
        input_files={"cwd": "/tmp/test", "diff": _DIFF_RANGE},
        timestamp=datetime(2026, 4, 25, 12, 0, 0),
        model="claude-sonnet-4-20250514",
    )


# ---------------------------------------------------------------------------
# Integration: slice + template=code → diff injected into prompt
# ---------------------------------------------------------------------------


class TestCodeReviewDiffInjectionIntegration:
    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch("squadron.review.template_inputs.resolve_slice_diff_range")
    @patch(f"{_P}.resolve_slice_info")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_diff_injected_into_run_review_call(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_rsi: MagicMock,
        mock_diff: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        """With template=code and slice=194, run_review_with_profile receives inputs
        containing the diff range string."""
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()
        mock_rsi.return_value = _SLICE_INFO
        mock_diff.return_value = _DIFF_RANGE

        ctx = _make_context({"template": "code", "slice": 194})
        result = await ReviewAction().execute(ctx)

        assert result.success is True
        assert result.verdict == "CONCERNS"

        call_inputs = mock_run_review.call_args[0][1]
        assert call_inputs["diff"] == _DIFF_RANGE

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_no_diff_when_slice_absent(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        """When 'slice' is absent from params, inputs['diff'] is not set (no crash)."""
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        ctx = _make_context({"template": "code"})
        result = await ReviewAction().execute(ctx)

        assert result.success is True
        call_inputs = mock_run_review.call_args[0][1]
        assert "diff" not in call_inputs
