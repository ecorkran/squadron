"""Tests for FixStepType and the built-in ``fix`` pipeline (slice 423 D1, D7)."""

from __future__ import annotations

import pytest

from squadron.pipeline.actions import ActionType
from squadron.pipeline.commit_plan import SUBJECT_PARAM, CommitSubject
from squadron.pipeline.loader import load_pipeline, validate_pipeline
from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps import StepTypeName, bootstrap_step_types, get_step_type
from squadron.pipeline.steps.fix import FixStepType
from squadron.pipeline.steps.utils import any_step_needs_context_forge


def _config(**config: object) -> StepConfig:
    return StepConfig(step_type="fix", name="fix-0", config=dict(config))


def _valid(**overrides: object) -> StepConfig:
    config: dict[str, object] = {"issue": "301", "commit-to": "target"}
    config.update(overrides)
    return _config(**config)


def test_step_type_is_registered_under_its_name() -> None:
    bootstrap_step_types()
    assert StepTypeName.FIX == "fix"
    assert isinstance(get_step_type(StepTypeName.FIX), FixStepType)


def test_known_keys() -> None:
    assert FixStepType().known_keys == {"issue", "model", "issue-file", "commit-to"}


@pytest.mark.parametrize("issue", ["301", "#301", 301, " #7 "])
def test_valid_issue_refs_pass(issue: object) -> None:
    assert FixStepType().validate(_valid(issue=issue)) == []


@pytest.mark.parametrize("issue", ["abc", "0", "-1", "1.5", "#", "{301", "12x"])
def test_invalid_issue_ref_names_the_field_and_value(issue: str) -> None:
    errors = FixStepType().validate(_valid(issue=issue))
    assert [e.field for e in errors] == ["issue"]
    assert repr(issue) in errors[0].message


def test_placeholders_are_accepted_for_every_param() -> None:
    config = _config(
        **{
            "issue": "{issue}",
            "model": "{model}",
            "issue-file": "{issue-file}",
            "commit-to": "{commit-to}",
        }
    )
    assert FixStepType().validate(config) == []


def test_malformed_commit_to_and_issue_file_are_checked_now() -> None:
    errors = FixStepType().validate(_valid(**{"commit-to": "{target", "issue-file": "../{x}"}))
    assert sorted(e.field for e in errors) == ["commit-to", "issue-file"]


@pytest.mark.parametrize("commit_to", ["target", "current"])
def test_valid_commit_to(commit_to: str) -> None:
    assert FixStepType().validate(_valid(**{"commit-to": commit_to})) == []


def test_invalid_commit_to_is_an_error() -> None:
    errors = FixStepType().validate(_valid(**{"commit-to": "elsewhere"}))
    assert [e.field for e in errors] == ["commit-to"]
    assert "elsewhere" in errors[0].message


@pytest.mark.parametrize("name", ["issue", "commit-to"])
def test_required_keys(name: str) -> None:
    config = {"issue": "301", "commit-to": "target"}
    del config[name]
    errors = FixStepType().validate(_config(**config))
    assert [e.field for e in errors] == [name]
    assert "required" in errors[0].message


def test_issue_file_accepts_empty_as_fetch_mode_and_a_relative_path() -> None:
    assert FixStepType().validate(_valid(**{"issue-file": ""})) == []
    assert FixStepType().validate(_valid(**{"issue-file": "issues/301.md"})) == []


@pytest.mark.parametrize("path", ["../issue.md", "/abs/issue.md"])
def test_issue_file_refuses_paths_that_climb_or_are_absolute(path: str) -> None:
    errors = FixStepType().validate(_valid(**{"issue-file": path}))
    assert [e.field for e in errors] == ["issue-file"]


def test_issue_file_and_model_must_be_strings() -> None:
    errors = FixStepType().validate(_valid(**{"issue-file": 3, "model": 4}))
    assert sorted(e.field for e in errors) == ["issue-file", "model"]


def test_unknown_key_is_an_error() -> None:
    errors = FixStepType().validate(_valid(colour="red"))
    assert [e.field for e in errors] == ["colour"]


def test_expand_order_and_configs() -> None:
    actions = FixStepType().expand(
        _valid(model="sonnet", **{"issue-file": "issue.md", "commit-to": "current"})
    )
    assert actions == [
        (
            ActionType.FIX_CONTEXT,
            {"issue": "301", "issue-file": "issue.md", "commit-to": "current"},
        ),
        (ActionType.DISPATCH, {"model": "sonnet"}),
        (ActionType.COMMIT, {SUBJECT_PARAM: CommitSubject.FIX}),
    ]


def test_expand_leaves_issue_file_out_when_the_step_names_none() -> None:
    (_, context_params), _, _ = FixStepType().expand(_valid())
    assert "issue-file" not in context_params


def test_context_forge_is_not_needed() -> None:
    assert FixStepType().needs_context_forge(_valid()) is False


def test_builtin_fix_pipeline_loads_and_passes_strict_validation() -> None:
    definition = load_pipeline("fix")
    assert definition.params == {
        "issue": "required",
        "model": "sonnet",
        "issue-file": "",
        "commit-to": "target",
    }
    assert [step.step_type for step in definition.steps] == ["fix"]
    assert validate_pipeline(definition, strict=True) == []
    assert any_step_needs_context_forge(definition.steps) is False
