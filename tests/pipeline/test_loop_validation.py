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


# ---------------------------------------------------------------------------
# Multi-verdict validation — ambiguous until: gating (#43)
# ---------------------------------------------------------------------------


def _target_shape(**loop_overrides: object) -> dict[str, object]:
    """The slice-305 target loop body: dispatch → review → findings-addressed gate."""
    cfg: dict[str, object] = {
        "max": 3,
        "until": "review.pass",
        "commit_each_iteration": True,
        "steps": [
            {"dispatch": {"name": "revise", "prompt": "fix the findings"}},
            {"review": {"name": "fresh-review", "template": "design"}},
            {
                "gate": {
                    "name": "settled",
                    "review_from": "fresh-review",
                    "policy": "findings-addressed",
                }
            },
        ],
    }
    cfg.update(loop_overrides)
    return cfg


def test_target_shape_validates_clean() -> None:
    """dispatch + review + findings-addressed gate: the review is consumed by
    the gate, so only the gate's verdict counts toward until:."""
    errors = validate_pipeline(_pipeline_with_loop(_target_shape()))
    assert errors == [], f"expected the target shape to validate clean, got: {errors}"


def test_two_reviews_with_gate_naming_one_still_rejects() -> None:
    """The unnamed review is unconsumed; with the gate's own verdict that is two."""
    pipeline = _pipeline_with_loop(
        _target_shape(
            steps=[
                {"review": {"name": "fresh-review", "template": "design"}},
                {"review": {"name": "other-review", "template": "tasks"}},
                {
                    "gate": {
                        "name": "settled",
                        "review_from": "fresh-review",
                        "policy": "findings-addressed",
                    }
                },
            ]
        )
    )

    errors = validate_pipeline(pipeline)
    assert any("verdict-bearing" in e.message for e in errors), (
        f"expected ambiguous-verdict error, got: {[e.message for e in errors]}"
    )


def test_gate_naming_a_step_outside_the_body_rejects() -> None:
    """An unresolvable reference consumes nothing, so review + gate is two
    verdicts — and the reference itself is reported."""
    pipeline = _pipeline_with_loop(
        _target_shape(
            steps=[
                {"review": {"name": "fresh-review", "template": "design"}},
                {
                    "gate": {
                        "name": "settled",
                        "review_from": "review-from-another-pipeline",
                        "policy": "findings-addressed",
                    }
                },
            ]
        )
    )

    errors = validate_pipeline(pipeline)
    messages = [e.message for e in errors]
    assert any("verdict-bearing" in m for m in messages), messages
    assert any("not an earlier step in this loop body" in m for m in messages), messages


def test_gate_naming_a_later_step_rejects() -> None:
    """The named step exists but runs after the gate — nothing to decide on."""
    pipeline = _pipeline_with_loop(
        _target_shape(
            steps=[
                {
                    "gate": {
                        "name": "settled",
                        "review_from": "fresh-review",
                        "policy": "findings-addressed",
                    }
                },
                {"review": {"name": "fresh-review", "template": "design"}},
            ]
        )
    )

    errors = validate_pipeline(pipeline)
    assert any("not an earlier step in this loop body" in e.message for e in errors), (
        f"expected an earlier-step error, got: {[e.message for e in errors]}"
    )


def test_findings_addressed_without_commit_source_rejects() -> None:
    """No per-round commit source → the prior round's evidence is absent by
    configuration, so the loop is rejected at load time with the fix named."""
    cfg = _target_shape()
    del cfg["commit_each_iteration"]

    errors = validate_pipeline(_pipeline_with_loop(cfg))
    commit_errors = [e for e in errors if e.field == "commit_each_iteration"]
    assert len(commit_errors) == 1, f"got: {[e.message for e in errors]}"
    assert "findings-addressed" in commit_errors[0].message
    assert "commit_each_iteration: true" in commit_errors[0].message


def test_phase_bodied_loop_satisfies_the_commit_source_requirement() -> None:
    """A phase step commits every iteration on its own, so no
    commit_each_iteration is needed (and adding it would double-commit)."""
    pipeline = _pipeline_with_loop(
        {
            "max": 3,
            "until": "review.pass",
            "steps": [
                {"implement": {"name": "build", "phase": 6}},
                {"review": {"name": "fresh-review", "template": "design"}},
                {
                    "gate": {
                        "name": "settled",
                        "review_from": "fresh-review",
                        "policy": "findings-addressed",
                    }
                },
            ],
        }
    )

    errors = validate_pipeline(pipeline)
    assert [e for e in errors if e.field == "commit_each_iteration"] == [], (
        f"expected no commit-source error, got: {[e.message for e in errors]}"
    )


def test_most_severe_gate_in_a_loop_needs_no_commit_source() -> None:
    """The commit-source requirement belongs to findings-addressed alone."""
    pipeline = _pipeline_with_loop(
        {
            "max": 3,
            "until": "review.pass",
            "steps": [
                {"review": {"name": "judge-slice", "template": "judge.slice-vs-arch"}},
                {"review": {"name": "fresh-review", "template": "design"}},
                {
                    "gate": {
                        "name": "settled",
                        "judge_from": "judge-slice",
                        "review_from": "fresh-review",
                    }
                },
            ],
        }
    )

    errors = validate_pipeline(pipeline)
    assert errors == [], f"expected a most-severe loop to validate clean, got: {errors}"


def test_loop_with_two_reviews_and_until_fails_full_pipeline_validation() -> None:
    """A loop: body with two reviews and until: fails validate_pipeline().

    Exercises the full validate_pipeline() path (not just
    LoopStepType.validate() directly), naming both offending steps.
    """
    pipeline = _pipeline_with_loop(
        {
            "max": 3,
            "until": "review.pass",
            "steps": [
                {"review": {"template": "design"}},
                {"review": {"template": "tasks"}},
            ],
        }
    )

    errors = validate_pipeline(pipeline)

    assert errors, "expected at least one validation error"
    messages = [e.message for e in errors]
    assert any("verdict-bearing" in m for m in messages), (
        f"expected ambiguous-verdict error, got: {messages}"
    )
