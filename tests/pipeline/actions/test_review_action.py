"""Tests for ReviewAction."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ModelResolutionError
from squadron.providers.base import ProfileName
from squadron.review.models import (
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
)
from squadron.review.templates import ReviewTemplate

_P = "squadron.pipeline.actions.review"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(**overrides: object) -> ActionContext:
    """Build an ActionContext with review-specific defaults."""
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-4-20250514", None)
    defaults: dict[str, object] = {
        "pipeline_name": "test-pipeline",
        "run_id": "run-12345678",
        "params": {
            "template": "code",
        },
        "step_name": "review-step",
        "step_index": 0,
        "prior_outputs": {},
        "resolver": resolver,
        "cf_client": MagicMock(),
        "cwd": "/tmp/test",
    }
    defaults.update(overrides)
    return ActionContext(**defaults)  # type: ignore[arg-type]


def _make_review_result(
    verdict: Verdict = Verdict.CONCERNS,
    model: str | None = "claude-sonnet-4-20250514",
) -> ReviewResult:
    """Build a canned ReviewResult with structured findings."""
    return ReviewResult(
        verdict=verdict,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Missing error handling",
                description="No try/except.",
                file_ref="src/foo.py:10",
                category="error-handling",
                location="src/foo.py:10",
            ),
        ],
        raw_output="## Review\nCONCERNS\n",
        template_name="code",
        input_files={"cwd": "/tmp/test"},
        timestamp=datetime(2026, 4, 1, 12, 0, 0),
        model=model,
    )


def _mock_template() -> ReviewTemplate:
    mock = MagicMock(spec=ReviewTemplate, name="code")
    mock.required_inputs = []
    mock.optional_inputs = []
    return mock


# ---------------------------------------------------------------------------
# Basic properties
# ---------------------------------------------------------------------------


class TestReviewActionBasics:
    def test_action_type(self) -> None:
        assert ReviewAction().action_type == "review"

    def test_protocol_compliance(self) -> None:
        assert isinstance(ReviewAction(), Action)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestReviewValidation:
    def test_missing_template(self) -> None:
        errors = ReviewAction().validate({})
        assert len(errors) == 1
        assert errors[0].field == "template"

    def test_valid_config(self) -> None:
        errors = ReviewAction().validate({"template": "code"})
        assert errors == []


# ---------------------------------------------------------------------------
# Execute — happy path
# ---------------------------------------------------------------------------


class TestReviewExecuteHappyPath:
    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_happy_path(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        ctx = _make_context()
        result = await ReviewAction().execute(ctx)

        assert result.success is True
        assert result.action_type == "review"

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_verdict_populated(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result(Verdict.CONCERNS)

        result = await ReviewAction().execute(_make_context())
        assert result.verdict == "CONCERNS"

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_findings_as_dicts(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        result = await ReviewAction().execute(_make_context())
        assert len(result.findings) == 1
        assert isinstance(result.findings[0], dict)
        f = result.findings[0]
        assert f["id"] == "F001"  # type: ignore[index]
        assert f["severity"] == "concern"  # type: ignore[index]

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_response_in_outputs(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        review_result = _make_review_result()
        mock_run_review.return_value = review_result

        result = await ReviewAction().execute(_make_context())
        assert result.outputs["response"] == review_result.raw_output


# ---------------------------------------------------------------------------
# Execute — model and profile resolution
# ---------------------------------------------------------------------------


class TestReviewModelResolution:
    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_resolver_called_with_action_model(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        ctx = _make_context(params={"template": "code", "model": "opus"})
        await ReviewAction().execute(ctx)
        ctx.resolver.resolve.assert_called_once_with("opus", None)

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_alias_derived_profile(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        ctx = _make_context(params={"template": "code"})
        ctx.resolver.resolve.return_value = ("gpt-4o", "openrouter")

        result = await ReviewAction().execute(ctx)
        assert result.metadata["profile"] == "openrouter"

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_explicit_profile_overrides_alias(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        ctx = _make_context(params={"template": "code", "profile": "openai"})
        ctx.resolver.resolve.return_value = ("gpt-4o", "openrouter")

        result = await ReviewAction().execute(ctx)
        assert result.metadata["profile"] == "openai"

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_default_profile_is_sdk(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        ctx = _make_context(params={"template": "code"})
        ctx.resolver.resolve.return_value = ("sonnet", None)

        result = await ReviewAction().execute(ctx)
        assert result.metadata["profile"] == ProfileName.SDK


# ---------------------------------------------------------------------------
# Execute — template inputs passthrough
# ---------------------------------------------------------------------------


class TestReviewInputPassthrough:
    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_passthrough_keys(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        ctx = _make_context(
            params={
                "template": "code",
                "diff": "main",
                "files": "src/**/*.py",
                "against": "arch.md",
            }
        )
        await ReviewAction().execute(ctx)

        call_args = mock_run_review.call_args
        inputs = call_args[0][1]
        assert inputs["diff"] == "main"
        assert inputs["files"] == "src/**/*.py"
        assert inputs["against"] == "arch.md"
        assert inputs["cwd"] == "/tmp/test"


# ---------------------------------------------------------------------------
# Execute — persistence
# ---------------------------------------------------------------------------


class TestReviewPersistence:
    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_review_file_persisted(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        result = await ReviewAction().execute(_make_context())
        mock_save.assert_called_once()
        assert result.outputs["review_file"] == "/tmp/reviews/review.md"

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", side_effect=OSError("disk full"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_persistence_failure_is_nonfatal(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        result = await ReviewAction().execute(_make_context())
        assert result.success is True
        assert "review_file" not in result.outputs


# ---------------------------------------------------------------------------
# Execute — error handling
# ---------------------------------------------------------------------------


class TestReviewErrors:
    @pytest.mark.asyncio
    @patch(f"{_P}.get_template", return_value=None)
    @patch(f"{_P}.load_all_templates")
    async def test_template_not_found(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
    ) -> None:
        result = await ReviewAction().execute(_make_context())
        assert result.success is False
        assert "not found" in (result.error or "")

    @pytest.mark.asyncio
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_missing_required_input(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
    ) -> None:
        from squadron.review.templates import InputDef

        mock_tpl = _mock_template()
        mock_tpl.required_inputs = [InputDef(name="input", description="doc to review")]
        mock_get_template.return_value = mock_tpl

        result = await ReviewAction().execute(_make_context())
        assert result.success is False
        assert "missing required input" in (result.error or "").lower()
        assert "input" in (result.error or "")

    @pytest.mark.asyncio
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_model_resolution_error(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()

        ctx = _make_context()
        ctx.resolver.resolve.side_effect = ModelResolutionError("no model")

        result = await ReviewAction().execute(ctx)
        assert result.success is False
        assert "no model" in (result.error or "")

    @pytest.mark.asyncio
    @patch(f"{_P}.run_review_with_profile", side_effect=RuntimeError("API down"))
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_review_execution_error(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()

        result = await ReviewAction().execute(_make_context())
        assert result.success is False
        assert "API down" in (result.error or "")


# ---------------------------------------------------------------------------
# Execute — metadata
# ---------------------------------------------------------------------------


class TestReviewMetadata:
    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_metadata_fields(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        result = await ReviewAction().execute(_make_context())
        assert result.metadata["model"] == "claude-sonnet-4-20250514"
        assert result.metadata["template"] == "code"
        assert "profile" in result.metadata
