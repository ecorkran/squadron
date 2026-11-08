"""``--validate --strict`` reports a no-tools step that cannot be isolated (#299)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from squadron.pipeline.isolation_validation import no_tools_isolation_errors
from squadron.pipeline.loader import validate_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.providers.base import ProviderCapabilities

_MOD = "squadron.pipeline.isolation_validation"


def _definition(config: dict[str, object], *, model: str | None = None) -> PipelineDefinition:
    step = StepConfig(step_type="dispatch", name="answer", config=config)
    return PipelineDefinition(name="p", description="", params={}, steps=[step], model=model)


def _provider(*, honors_empty_tools: bool) -> SimpleNamespace:
    return SimpleNamespace(
        capabilities=ProviderCapabilities(can_read_files=True, honors_empty_tools=honors_empty_tools)
    )


def test_sdk_model_passes() -> None:
    definition = _definition({"model": "sonnet", "allowed_tools": []})
    assert no_tools_isolation_errors(definition) == []


def test_provider_that_cannot_drop_tools_is_reported_with_the_missing_property() -> None:
    definition = _definition({"model": "sonnet", "allowed_tools": []})
    with patch(f"{_MOD}.get_provider", return_value=_provider(honors_empty_tools=False)):
        errors = no_tools_isolation_errors(definition)

    assert [e.field for e in errors] == ["allowed_tools"]
    assert "cannot run with none" in errors[0].message
    assert "answer" in errors[0].message


def test_pipeline_level_model_is_used_when_the_step_names_none() -> None:
    definition = _definition({"allowed_tools": []}, model="sonnet")
    with patch(f"{_MOD}.get_provider", return_value=_provider(honors_empty_tools=False)):
        assert len(no_tools_isolation_errors(definition)) == 1


def test_placeholder_model_is_left_to_dispatch() -> None:
    definition = _definition({"model": "{model}", "allowed_tools": []})
    with patch(f"{_MOD}.get_provider", return_value=_provider(honors_empty_tools=False)):
        assert no_tools_isolation_errors(definition) == []


def test_steps_with_tools_or_without_the_key_are_not_checked() -> None:
    with patch(f"{_MOD}.get_provider", return_value=_provider(honors_empty_tools=False)):
        assert no_tools_isolation_errors(_definition({"model": "sonnet"})) == []
        assert (
            no_tools_isolation_errors(_definition({"model": "sonnet", "allowed_tools": ["read_file"]}))
            == []
        )


def test_only_strict_validation_runs_the_check() -> None:
    definition = _definition({"model": "sonnet", "allowed_tools": [], "prompt": "x"})
    with patch(f"{_MOD}.get_provider", return_value=_provider(honors_empty_tools=False)):
        assert not [e for e in validate_pipeline(definition) if e.field == "allowed_tools"]
        assert [e for e in validate_pipeline(definition, strict=True) if e.field == "allowed_tools"]
