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
from squadron.review.templates import InputDef, ReviewTemplate

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
    score: float | None = None,
    criteria: dict[str, float] | None = None,
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
        score=score,
        criteria=criteria,
    )


def _mock_template() -> ReviewTemplate:
    mock = MagicMock(spec=ReviewTemplate, name="code")
    mock.required_inputs = []
    mock.optional_inputs = []
    mock.judge = None
    mock.is_judge = False
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
# Execute — numeric scoring foundation (slice 300)
# ---------------------------------------------------------------------------


class TestReviewScoreThreading:
    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_score_and_criteria_threaded(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result(score=87.5, criteria={"alignment": 90.0})

        result = await ReviewAction().execute(_make_context())
        assert result.score == 87.5
        assert result.criteria == {"alignment": 90.0}

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_score_less_result_yields_none(
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
        assert result.score is None
        assert result.criteria is None
        assert result.provenance == "review"


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
        tmp_path: Path,
    ) -> None:
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        # against must name a real file (issue #18 existence guard)
        against_doc = tmp_path / "arch.md"
        against_doc.write_text("# arch\n")

        ctx = _make_context(
            params={
                "template": "code",
                "diff": "main",
                "files": "src/**/*.py",
                "against": str(against_doc),
            }
        )
        await ReviewAction().execute(ctx)

        call_args = mock_run_review.call_args
        inputs = call_args[0][1]
        assert inputs["diff"] == "main"
        assert inputs["files"] == "src/**/*.py"
        assert inputs["against"] == str(against_doc)
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
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_nonexistent_input_file_fails_before_review(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A resolved input path that names no real file must fail the action
        before the model is called (issue #18) — previously the review ran
        with the document silently absent and fabricated a verdict."""
        mock_tpl = _mock_template()
        mock_tpl.required_inputs = [InputDef(name="input", description="")]
        mock_get_template.return_value = mock_tpl

        missing = str(tmp_path / "never-written-tasks.md")
        ctx = _make_context(params={"template": "tasks", "input": missing})
        result = await ReviewAction().execute(ctx)

        assert result.success is False
        assert "not found" in (result.error or "")
        assert "never-written-tasks.md" in (result.error or "")
        mock_run_review.assert_not_called()

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
# Execute — judge enforcement (slice 301)
# ---------------------------------------------------------------------------


def _mock_judge_template(judge: dict[str, object] | None = None) -> ReviewTemplate:
    mock = MagicMock(spec=ReviewTemplate, name="judge.test")
    mock.required_inputs = []
    mock.optional_inputs = []
    mock.judge = judge if judge is not None else {"pass_floor": 75, "concerns_floor": 50}
    mock.is_judge = True
    return mock


class TestJudgeEnforcement:
    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_judge_template_verdict_is_threshold_derived(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_judge_template()
        # Parsed verdict says FAIL, but score is well above pass_floor — score must win.
        mock_run_review.return_value = _make_review_result(Verdict.FAIL, score=90.0)

        result = await ReviewAction().execute(_make_context())
        assert result.verdict == "PASS"
        assert result.provenance == "judge"

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_judge_template_no_score_yields_unknown(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        mock_get_template.return_value = _mock_judge_template()
        mock_run_review.return_value = _make_review_result(score=None)

        result = await ReviewAction().execute(_make_context())
        assert result.verdict == "UNKNOWN"
        assert result.provenance == "judge"

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_standard_template_provenance_is_review_verdict_unchanged(
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
        assert result.provenance == "review"
        assert result.verdict == "CONCERNS"

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_step_level_judge_override_wins_over_template_default(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        # Template default pass_floor=75; step override raises it to 95.
        mock_get_template.return_value = _mock_judge_template({"pass_floor": 75, "concerns_floor": 50})
        mock_run_review.return_value = _make_review_result(score=90.0)

        ctx = _make_context(params={"template": "judge.test", "judge": {"pass_floor": 95}})
        result = await ReviewAction().execute(ctx)
        # 90.0 would PASS under the template default (75) but not under the
        # step override (95) — CONCERNS proves the override was applied.
        assert result.verdict == "CONCERNS"
        assert result.provenance == "judge"

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_rogue_model_emitted_verdict_is_discarded(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        """302: a judge template's model emits a verdict despite the prompt
        forbidding it. enforce_judge() never reads result.verdict — the
        threshold-derived verdict must win regardless of what was parsed."""
        mock_get_template.return_value = _mock_judge_template()
        # Parsed verdict says FAIL, but score (90) clears pass_floor (75).
        mock_run_review.return_value = _make_review_result(Verdict.FAIL, score=90.0)

        result = await ReviewAction().execute(_make_context())
        assert result.verdict == "PASS"
        assert result.provenance == "judge"

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.resolve_slice_info")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_template_inputs_resolution_failure_yields_unknown(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_resolve_slice_info: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        """302: a SliceInfo missing arch_file leaves `against` unresolved for
        judge.slice-vs-arch. The required-input KeyError must surface as a
        judge-aware UNKNOWN via execute()'s exception handler, not a silent
        skip.

        Uses the real "judge.slice-vs-arch" template name (not a synthetic
        "judge.test") so this exercises the actual TEMPLATE_INPUTS registry
        entry added in T5 — the empty arch_file, not an unregistered
        template name, must be what causes `against` to stay unresolved.
        run_review_with_profile is mocked to succeed so that, if inputs did
        fully resolve, the test would fail loudly (success=True) instead of
        an unrelated provider error masquerading as this failure mode.
        """
        template = _mock_judge_template()
        template.required_inputs = [
            InputDef(name="input", description=""),
            InputDef(name="against", description=""),
        ]
        mock_get_template.return_value = template
        mock_run_review.return_value = _make_review_result(score=90.0)
        mock_resolve_slice_info.return_value = {
            "index": 302,
            "name": "design-phase-judge-templates",
            "slice_name": "design-phase-judge-templates",
            "design_file": "project-documents/user/slices/302-slice.md",
            "task_files": ["302-tasks.md"],
            "arch_file": "",
        }

        ctx = _make_context(params={"template": "judge.slice-vs-arch", "slice": "302"})
        result = await ReviewAction().execute(ctx)

        assert result.success is False
        assert result.verdict == "UNKNOWN"
        assert result.provenance == "judge"
        mock_run_review.assert_not_called()

    @pytest.mark.asyncio
    @patch(f"{_P}.run_review_with_profile", side_effect=RuntimeError("provider down"))
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_judge_template_exception_yields_unknown_with_warning_log(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_get_template.return_value = _mock_judge_template()

        with caplog.at_level("WARNING"):
            result = await ReviewAction().execute(_make_context())

        assert result.success is False
        assert result.verdict == "UNKNOWN"
        assert result.provenance == "judge"
        assert any(r.levelno >= 30 for r in caplog.records)


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


# ---------------------------------------------------------------------------
# Rules wiring — parity with CLI (get_template_rules + language auto-detection)
# ---------------------------------------------------------------------------


class TestReviewActionRulesWiring:
    """The pipeline review action must load template rules and auto-detected
    language rules in the same way `sq review code` does. Guards against the
    divergence that existed before these were routed through load_review_rules.
    """

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_template_rules_loaded_from_rules_dir(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
        tmp_path: Path,
    ) -> None:
        """`review-code.md` in cwd/.claude/rules is injected into rules_content."""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "review-code.md").write_text("Code review principles.")

        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        ctx = _make_context(
            cwd=str(tmp_path),
            params={"template": "code"},
        )
        await ReviewAction().execute(ctx)

        kwargs = mock_run_review.call_args.kwargs
        rc = kwargs["rules_content"]
        assert rc is not None
        assert "Code review principles." in rc

    @pytest.mark.asyncio
    @patch(f"{_P}.extract_diff_paths", return_value=["src/foo.py"])
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_language_auto_detection_from_diff(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
        mock_diff: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A .py file in the diff triggers python.md auto-detection."""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "python.md").write_text("---\npaths: [**/*.py]\n---\nPython auto rules.")

        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        ctx = _make_context(
            cwd=str(tmp_path),
            params={"template": "code", "diff": "main"},
        )
        await ReviewAction().execute(ctx)

        kwargs = mock_run_review.call_args.kwargs
        rc = kwargs["rules_content"]
        assert rc is not None
        assert "Python auto rules." in rc

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_explicit_rules_content_preserved_and_combined(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Explicit rules_content param is preserved alongside template rules."""
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "review-code.md").write_text("Template code rules.")

        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        ctx = _make_context(
            cwd=str(tmp_path),
            params={
                "template": "code",
                "rules_content": "Caller-supplied rules.",
            },
        )
        await ReviewAction().execute(ctx)

        kwargs = mock_run_review.call_args.kwargs
        rc = kwargs["rules_content"]
        assert rc is not None
        assert "Template code rules." in rc
        assert "Caller-supplied rules." in rc

    @pytest.mark.asyncio
    @patch(f"{_P}.save_review_file", return_value=None)
    @patch(f"{_P}.format_review_markdown", return_value="# Review")
    @patch(f"{_P}.run_review_with_profile")
    @patch(f"{_P}.get_template")
    @patch(f"{_P}.load_all_templates")
    async def test_no_rules_dir_yields_none_rules_content(
        self,
        mock_load: MagicMock,
        mock_get_template: MagicMock,
        mock_run_review: MagicMock,
        mock_format: MagicMock,
        mock_save: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When no rules_dir resolves, rules_content is None (no crash)."""
        mock_get_template.return_value = _mock_template()
        mock_run_review.return_value = _make_review_result()

        # Force resolve_rules_dir to return None regardless of dev environment
        with patch(f"{_P}.resolve_rules_dir", return_value=None):
            ctx = _make_context(
                cwd=str(tmp_path),
                params={"template": "code"},
            )
            await ReviewAction().execute(ctx)

        kwargs = mock_run_review.call_args.kwargs
        assert kwargs["rules_content"] is None


# ---------------------------------------------------------------------------
# _resolve_slice_inputs regression — registry rewrite
# ---------------------------------------------------------------------------


class TestResolveSliceInputsRegression:
    """Verify _resolve_slice_inputs produces identical inputs after registry rewrite."""

    _SLICE_INFO = {
        "index": 194,
        "name": "loop-step-type",
        "slice_name": "loop-step-type-for-multi-step-bodies",
        "design_file": "project-documents/user/slices/194-slice.md",
        "task_files": ["194-tasks.loop-step-type-for-multi-step-bodies.md"],
        "arch_file": "project-documents/user/architecture/100-arch.md",
    }

    def _make_cf_client(self) -> MagicMock:
        cf = MagicMock()
        cf.list_slices.return_value = []  # unused — we mock resolve_slice_info
        return cf

    @patch(f"{_P}.resolve_slice_info")
    def test_slice_template_populates_input_and_against(self, mock_rsi: MagicMock) -> None:
        mock_rsi.return_value = self._SLICE_INFO
        inputs: dict[str, str] = {"cwd": "/tmp"}
        action = ReviewAction()
        action._resolve_slice_inputs("slice", 194, self._make_cf_client(), inputs)
        assert inputs["input"] == self._SLICE_INFO["design_file"]
        assert inputs["against"] == self._SLICE_INFO["arch_file"]

    @patch(f"{_P}.resolve_slice_info")
    def test_tasks_template_populates_input_and_against(self, mock_rsi: MagicMock) -> None:
        mock_rsi.return_value = self._SLICE_INFO
        inputs: dict[str, str] = {"cwd": "/tmp"}
        action = ReviewAction()
        action._resolve_slice_inputs("tasks", 194, self._make_cf_client(), inputs)
        assert inputs["input"] == (f"project-documents/user/tasks/{self._SLICE_INFO['task_files'][0]}")
        assert inputs["against"] == self._SLICE_INFO["design_file"]

    @patch(f"{_P}.resolve_slice_info")
    def test_arch_template_populates_input(self, mock_rsi: MagicMock) -> None:
        mock_rsi.return_value = self._SLICE_INFO
        inputs: dict[str, str] = {"cwd": "/tmp"}
        action = ReviewAction()
        action._resolve_slice_inputs("arch", 194, self._make_cf_client(), inputs)
        assert inputs["input"] == self._SLICE_INFO["arch_file"]

    @patch("squadron.review.template_inputs.resolve_slice_diff_range")
    @patch(f"{_P}.resolve_slice_info")
    def test_code_template_populates_diff(self, mock_rsi: MagicMock, mock_diff: MagicMock) -> None:
        mock_rsi.return_value = self._SLICE_INFO
        mock_diff.return_value = "abc123...slice-194"
        inputs: dict[str, str] = {"cwd": "/tmp"}
        action = ReviewAction()
        action._resolve_slice_inputs("code", 194, self._make_cf_client(), inputs)
        assert inputs["diff"] == "abc123...slice-194"

    @patch(f"{_P}.resolve_slice_info")
    def test_unknown_template_inputs_unchanged(self, mock_rsi: MagicMock) -> None:
        mock_rsi.return_value = self._SLICE_INFO
        inputs: dict[str, str] = {"cwd": "/tmp"}
        action = ReviewAction()
        action._resolve_slice_inputs("nonexistent", 194, self._make_cf_client(), inputs)
        assert inputs == {"cwd": "/tmp"}

    def test_slice_lookup_failure_returns_none(self) -> None:
        cf = self._make_cf_client()
        with patch(f"{_P}.resolve_slice_info", side_effect=ValueError("not found")):
            inputs: dict[str, str] = {"cwd": "/tmp"}
            result = ReviewAction()._resolve_slice_inputs("slice", 999, cf, inputs)
        assert result is None
        assert inputs == {"cwd": "/tmp"}
