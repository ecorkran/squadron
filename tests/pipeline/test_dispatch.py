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
