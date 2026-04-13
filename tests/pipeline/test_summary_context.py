"""Unit tests for assemble_dispatch_context (T2 — slice 191)."""

from __future__ import annotations

from squadron.pipeline.actions import ActionType
from squadron.pipeline.models import ActionResult
from squadron.pipeline.summary_context import (
    _FOOTER,
    _HEADER,
    assemble_dispatch_context,
)

# ---------------------------------------------------------------------------
# Fixture helper
# ---------------------------------------------------------------------------


def _result(
    action_type: str,
    outputs: dict[str, object] | None = None,
    success: bool = True,
    error: str | None = None,
    verdict: str | None = None,
    findings: list[object] | None = None,
) -> ActionResult:
    """Create an ActionResult with minimal boilerplate."""
    return ActionResult(
        success=success,
        action_type=action_type,
        outputs=outputs or {},
        error=error,
        verdict=verdict,
        findings=findings or [],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_prior_outputs_returns_empty_string() -> None:
    assert assemble_dispatch_context({}) == ""


def test_dispatch_output_included() -> None:
    prior = {
        "design": _result(ActionType.DISPATCH, outputs={"response": "Great design"})
    }
    output = assemble_dispatch_context(prior)
    assert "Great design" in output
    assert "## Step: design (dispatch)" in output


def test_review_output_includes_verdict_and_findings() -> None:
    prior = {
        "review-1": _result(
            ActionType.REVIEW,
            verdict="CONCERNS",
            findings=["finding A", "finding B"],
        )
    }
    output = assemble_dispatch_context(prior)
    assert "Verdict: CONCERNS" in output
    assert "- finding A" in output
    assert "- finding B" in output


def test_review_verdict_only() -> None:
    prior = {"review-1": _result(ActionType.REVIEW, verdict="LGTM", findings=[])}
    output = assemble_dispatch_context(prior)
    assert "Verdict: LGTM" in output
    assert "Findings:" not in output


def test_cf_op_build_context_included() -> None:
    prior = {
        "build-ctx": _result(
            ActionType.CF_OP,
            outputs={"operation": "build_context", "stdout": "phase context text"},
        )
    }
    output = assemble_dispatch_context(prior)
    assert "phase context text" in output


def test_cf_op_non_build_context_skipped() -> None:
    prior = {
        "set-phase": _result(
            ActionType.CF_OP,
            outputs={"operation": "set_phase", "stdout": "some output"},
        )
    }
    output = assemble_dispatch_context(prior)
    assert output == ""


def test_failed_step_included_with_error() -> None:
    prior = {
        "dispatch-1": _result(
            ActionType.DISPATCH,
            success=False,
            error="connection timeout",
        )
    }
    output = assemble_dispatch_context(prior)
    assert "[Step failed: connection timeout]" in output
    assert "## Step: dispatch-1 (dispatch)" in output


def test_checkpoint_skipped() -> None:
    prior = {
        "chk": _result(ActionType.CHECKPOINT, outputs={"message": "checkpoint hit"})
    }
    output = assemble_dispatch_context(prior)
    assert output == ""


def test_commit_skipped() -> None:
    prior = {"commit-1": _result(ActionType.COMMIT, outputs={"sha": "abc123"})}
    output = assemble_dispatch_context(prior)
    assert output == ""


def test_summary_output_included() -> None:
    prior = {
        "summarize": _result(
            ActionType.SUMMARY, outputs={"summary": "Prior summary text"}
        )
    }
    output = assemble_dispatch_context(prior)
    assert "Prior summary text" in output


def test_multiple_steps_ordered() -> None:
    prior = {
        "step-a": _result(ActionType.DISPATCH, outputs={"response": "Alpha"}),
        "step-b": _result(ActionType.REVIEW, verdict="LGTM"),
        "step-c": _result(ActionType.DISPATCH, outputs={"response": "Gamma"}),
    }
    output = assemble_dispatch_context(prior)
    pos_a = output.index("Alpha")
    pos_b = output.index("Verdict: LGTM")
    pos_c = output.index("Gamma")
    assert pos_a < pos_b < pos_c


def test_step_with_empty_response_skipped() -> None:
    prior = {"design": _result(ActionType.DISPATCH, outputs={"response": ""})}
    output = assemble_dispatch_context(prior)
    assert output == ""


def test_header_and_footer_present() -> None:
    prior = {"step": _result(ActionType.DISPATCH, outputs={"response": "some content"})}
    output = assemble_dispatch_context(prior)
    assert output.startswith(_HEADER)
    assert output.endswith(_FOOTER)
