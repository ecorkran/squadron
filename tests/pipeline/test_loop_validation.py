"""Integration tests for loop: nested-loop validation via validate_pipeline.

Tasks 15-16: verify the nested-loop ban surfaces through the full
validate_pipeline() path, not just through LoopStepType.validate() directly.
"""

from __future__ import annotations

import squadron.pipeline.steps.loop  # noqa: F401 — trigger registration
from squadron.pipeline.loader import validate_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig


def _pipeline_with_loop(loop_cfg: dict[str, object]) -> PipelineDefinition:
    return PipelineDefinition(
        name="test",
        description="test",
        params={},
        steps=[StepConfig(step_type="loop", name="outer-loop", config=loop_cfg)],
    )


# ---------------------------------------------------------------------------
# Task 15 — nested-loop ban: sub-field form
# ---------------------------------------------------------------------------


def test_inner_step_with_loop_subfield_fails_validation() -> None:
    """loop: body containing an inner step with loop: sub-field → ValidationError.

    The inner step (review:) carries a loop: sub-field. validate_pipeline()
    must return an error naming the inner step and the violation.
    """
    pipeline = _pipeline_with_loop(
        {
            "max": 3,
            "until": "review.pass",
            "steps": [
                {"review": {"loop": {"max": 2, "until": "review.pass"}}},
            ],
        }
    )

    errors = validate_pipeline(pipeline)

    assert errors, "expected at least one validation error"
    messages = [e.message for e in errors]
    assert any("sub-field" in m and "nested" in m for m in messages), (
        f"expected nested-loop sub-field error, got: {messages}"
    )


# ---------------------------------------------------------------------------
# Task 16 — nested-loop ban: step-type form
# ---------------------------------------------------------------------------


def test_inner_loop_step_type_fails_validation() -> None:
    """loop: body containing an inner loop: step type → ValidationError.

    The inner step is itself a loop: type. validate_pipeline() must return
    an error naming the inner step and identifying the type violation.
    """
    pipeline = _pipeline_with_loop(
        {
            "max": 3,
            "until": "review.pass",
            "steps": [
                {
                    "loop": {
                        "max": 2,
                        "until": "review.pass",
                        "steps": [{"review": {}}],
                    }
                },
            ],
        }
    )

    errors = validate_pipeline(pipeline)

    assert errors, "expected at least one validation error"
    messages = [e.message for e in errors]
    assert any("type 'loop'" in m and "nested" in m for m in messages), (
        f"expected nested-loop type error, got: {messages}"
    )
