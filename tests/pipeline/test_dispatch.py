"""Tests for dispatch action — override_instructions injection."""

from __future__ import annotations

from unittest.mock import MagicMock

from squadron.pipeline.models import ActionContext, ActionResult


def _make_context(
    params: dict[str, object],
    prior_outputs: dict[str, ActionResult] | None = None,
) -> ActionContext:
    return ActionContext(
        pipeline_name="test",
        run_id="run-123",
        params=params,
        step_name="step-1",
        step_index=0,
        prior_outputs=prior_outputs or {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd="/tmp",
        sdk_session=None,
    )


# ---------------------------------------------------------------------------
# T160-4 — override_instructions injection in _resolve_prompt
# ---------------------------------------------------------------------------


class TestDispatchOverrideInstructions:
    def _dispatch_action(self) -> object:
        from squadron.pipeline.actions.dispatch import DispatchAction

        return DispatchAction()

    def test_override_present_prepends_delimited_block(self) -> None:
        """When override_instructions is set, prompt starts with the delimited block."""
        action = self._dispatch_action()

        ctx = _make_context(
            params={
                "prompt": "Original context",
                "override_instructions": "do X",
            }
        )
        result = action._resolve_prompt(ctx)  # type: ignore[union-attr]
        assert result.startswith("--- Instructions from checkpoint resolution ---\n")
        assert "do X\n--- End instructions ---\n\n" in result
        assert result.endswith("Original context")

    def test_override_absent_no_prefix(self) -> None:
        """When override_instructions is absent, prompt is returned unchanged."""
        action = self._dispatch_action()

        ctx = _make_context(params={"prompt": "Original context"})
        result = action._resolve_prompt(ctx)  # type: ignore[union-attr]
        assert result == "Original context"
        assert "Instructions from checkpoint" not in result

    def test_override_empty_string_no_prefix(self) -> None:
        """Empty override_instructions does not add a prefix (strip guard)."""
        action = self._dispatch_action()

        ctx = _make_context(
            params={
                "prompt": "Original context",
                "override_instructions": "",
            }
        )
        result = action._resolve_prompt(ctx)  # type: ignore[union-attr]
        assert result == "Original context"
        assert "Instructions from checkpoint" not in result

    def test_override_whitespace_only_no_prefix(self) -> None:
        """Whitespace-only override_instructions is treated as absent."""
        action = self._dispatch_action()

        ctx = _make_context(
            params={
                "prompt": "Original context",
                "override_instructions": "   ",
            }
        )
        result = action._resolve_prompt(ctx)  # type: ignore[union-attr]
        assert "Instructions from checkpoint" not in result


# ---------------------------------------------------------------------------
# Slice 303 F001 — fix step must see the prior judge review's findings
# ---------------------------------------------------------------------------


class TestDispatchPriorReviewFallback:
    """No explicit prompt, no build_context output: fall back to the most
    recent prior ``review`` action's findings (the judge-gated loop flow)."""

    def _dispatch_action(self) -> object:
        from squadron.pipeline.actions.dispatch import DispatchAction

        return DispatchAction()

    def test_no_explicit_prompt_uses_prior_review_findings(self) -> None:
        action = self._dispatch_action()
        prior_review = ActionResult(
            success=True,
            action_type="review",
            outputs={},
            verdict="CONCERNS",
            findings=[
                {
                    "id": "F001",
                    "severity": "concern",
                    "category": "correctness",
                    "summary": "Missing null check",
                    "location": "src/foo.py:10",
                }
            ],
        )
        ctx = _make_context(params={}, prior_outputs={"review-0": prior_review})
        result = action._resolve_prompt(ctx)  # type: ignore[union-attr]
        assert "Missing null check" in result
        assert "src/foo.py:10" in result
        assert "CONCERNS" in result

    def test_prior_review_with_no_findings_uses_initial_pass_message(self) -> None:
        action = self._dispatch_action()
        prior_review = ActionResult(
            success=True,
            action_type="review",
            outputs={},
            verdict="PASS",
            findings=[],
        )
        ctx = _make_context(params={}, prior_outputs={"review-0": prior_review})
        result = action._resolve_prompt(ctx)  # type: ignore[union-attr]
        assert "initial improvement pass" in result

    def test_no_prompt_no_build_context_no_review_raises(self) -> None:
        action = self._dispatch_action()
        ctx = _make_context(params={})
        try:
            action._resolve_prompt(ctx)  # type: ignore[union-attr]
        except KeyError as exc:
            assert "No 'prompt' param" in str(exc)
        else:
            raise AssertionError("expected KeyError")

    def test_explicit_prompt_still_wins_over_prior_review(self) -> None:
        """A static prompt (e.g. an initial-pass step) must still take
        priority — only steps that omit `prompt:` fall through to review
        findings."""
        action = self._dispatch_action()
        prior_review = ActionResult(
            success=True,
            action_type="review",
            outputs={},
            verdict="CONCERNS",
            findings=[{"id": "F001", "severity": "concern", "summary": "x"}],
        )
        ctx = _make_context(
            params={"prompt": "Explicit prompt"},
            prior_outputs={"review-0": prior_review},
        )
        result = action._resolve_prompt(ctx)  # type: ignore[union-attr]
        assert result == "Explicit prompt"
