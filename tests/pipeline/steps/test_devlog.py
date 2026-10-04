"""Tests for DevlogStepType."""

from __future__ import annotations

from squadron.pipeline.commit_plan import CommitSubject
from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.devlog import DevlogStepType


def _make_config(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="devlog", name="test-step", config=config)


def test_step_type() -> None:
    assert DevlogStepType().step_type == "devlog"


# --- validate() ---


def test_validate_empty_config() -> None:
    errors = DevlogStepType().validate(_make_config({}))
    assert errors == []


def test_validate_mode_auto() -> None:
    errors = DevlogStepType().validate(_make_config({"mode": "auto"}))
    assert errors == []


def test_validate_mode_explicit_without_content() -> None:
    errors = DevlogStepType().validate(_make_config({"mode": "explicit"}))
    assert len(errors) == 1
    assert errors[0].field == "content"
    assert "required" in errors[0].message


def test_validate_mode_explicit_with_content() -> None:
    errors = DevlogStepType().validate(
        _make_config({"mode": "explicit", "content": "Phase 4 complete"})
    )
    assert errors == []


def test_validate_invalid_mode() -> None:
    errors = DevlogStepType().validate(_make_config({"mode": "unknown"}))
    assert len(errors) == 1
    assert errors[0].field == "mode"


# --- expand() ---


def test_expand_mode_auto() -> None:
    actions = DevlogStepType().expand(_make_config({"mode": "auto"}))
    assert actions == [
        ("devlog", {"mode": "auto"}),
        ("commit", {"commit_subject": CommitSubject.DEVLOG}),
    ]


def test_expand_mode_explicit_with_content() -> None:
    actions = DevlogStepType().expand(_make_config({"mode": "explicit", "content": "Done"}))
    assert len(actions) == 2
    assert actions[0] == ("devlog", {"mode": "explicit", "content": "Done"})


def test_expand_no_mode_defaults_to_auto() -> None:
    actions = DevlogStepType().expand(_make_config({}))
    assert len(actions) == 2
    assert actions[0] == ("devlog", {"mode": "auto"})


def test_commit_takes_an_explicit_slice_from_the_step() -> None:
    """Inside an ``each`` the slice is a record, so the step names ``{slice.index}``."""
    actions = DevlogStepType().expand(_make_config({"mode": "auto", "slice": "{slice.index}"}))
    assert actions[1] == (
        "commit",
        {"commit_subject": CommitSubject.DEVLOG, "slice": "{slice.index}"},
    )


def test_commit_leaves_the_slice_to_the_pipeline_params_by_default() -> None:
    _, commit_config = DevlogStepType().expand(_make_config({"mode": "auto"}))[1]
    assert "slice" not in commit_config
