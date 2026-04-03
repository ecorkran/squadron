"""Unit tests for squadron.pipeline.schema — Pydantic pipeline models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from squadron.pipeline.models import PipelineDefinition
from squadron.pipeline.schema import PipelineSchema


class TestPipelineSchemaValidParsing:
    """Valid pipeline YAML structures parse without error."""

    def test_minimal_pipeline(self) -> None:
        """Name + single step is the minimum valid pipeline."""
        raw = {
            "name": "minimal",
            "steps": [{"design": {"phase": 4}}],
        }
        schema = PipelineSchema.model_validate(raw)
        assert schema.name == "minimal"
        assert schema.description == ""
        assert schema.params == {}
        assert schema.model is None
        assert len(schema.steps) == 1

    def test_full_pipeline(self) -> None:
        """Pipeline with all optional fields parses correctly."""
        raw = {
            "name": "full",
            "description": "A full pipeline",
            "params": {"slice": "required", "model": "opus"},
            "model": "sonnet",
            "steps": [
                {"design": {"phase": 4, "review": "arch"}},
                {"tasks": {"phase": 5}},
                {"devlog": "auto"},
            ],
        }
        schema = PipelineSchema.model_validate(raw)
        assert schema.name == "full"
        assert schema.description == "A full pipeline"
        assert schema.params == {"slice": "required", "model": "opus"}
        assert schema.model == "sonnet"
        assert len(schema.steps) == 3


class TestStepShorthandExpansion:
    """Scalar step values expand to {"mode": value}."""

    def test_string_shorthand(self) -> None:
        """``devlog: auto`` becomes StepSchema(step_type="devlog", config={"mode": "auto"})."""
        raw = {
            "name": "test",
            "steps": [{"devlog": "auto"}],
        }
        schema = PipelineSchema.model_validate(raw)
        step = schema.steps[0]
        assert step.step_type == "devlog"
        assert step.config == {"mode": "auto"}

    def test_mapping_form(self) -> None:
        """``design: {phase: 4, review: arch}`` preserves config dict."""
        raw = {
            "name": "test",
            "steps": [{"design": {"phase": 4, "review": "arch"}}],
        }
        schema = PipelineSchema.model_validate(raw)
        step = schema.steps[0]
        assert step.step_type == "design"
        assert step.config == {"phase": 4, "review": "arch"}

    def test_none_value_becomes_empty_config(self) -> None:
        """A step with None config becomes an empty dict."""
        raw = {
            "name": "test",
            "steps": [{"compact": None}],
        }
        schema = PipelineSchema.model_validate(raw)
        assert schema.steps[0].config == {}


class TestPipelineSchemaValidation:
    """Invalid structures raise pydantic.ValidationError."""

    def test_missing_name_raises(self) -> None:
        raw = {"steps": [{"design": {"phase": 4}}]}
        with pytest.raises(ValidationError, match="name"):
            PipelineSchema.model_validate(raw)

    def test_empty_steps_raises(self) -> None:
        raw = {"name": "empty", "steps": []}
        with pytest.raises(ValidationError, match="at least one step"):
            PipelineSchema.model_validate(raw)

    def test_unknown_top_level_key_raises(self) -> None:
        raw = {
            "name": "test",
            "steps": [{"design": {"phase": 4}}],
            "unknown_field": "bad",
        }
        with pytest.raises(ValidationError, match="unknown_field"):
            PipelineSchema.model_validate(raw)

    def test_multi_key_step_raises(self) -> None:
        raw = {
            "name": "test",
            "steps": [{"design": {"phase": 4}, "tasks": {"phase": 5}}],
        }
        with pytest.raises(ValueError, match="single-key"):
            PipelineSchema.model_validate(raw)


class TestToDefinition:
    """PipelineSchema.to_definition() produces correct PipelineDefinition."""

    def test_returns_pipeline_definition(self) -> None:
        raw = {
            "name": "my-pipeline",
            "description": "desc",
            "model": "opus",
            "params": {"slice": "required"},
            "steps": [
                {"design": {"phase": 4}},
                {"devlog": "auto"},
            ],
        }
        schema = PipelineSchema.model_validate(raw)
        defn = schema.to_definition()

        assert isinstance(defn, PipelineDefinition)
        assert defn.name == "my-pipeline"
        assert defn.description == "desc"
        assert defn.model == "opus"
        assert defn.params == {"slice": "required"}
        assert len(defn.steps) == 2
        assert defn.steps[0].step_type == "design"
        assert defn.steps[1].step_type == "devlog"
        assert defn.steps[1].config == {"mode": "auto"}

    def test_step_auto_naming(self) -> None:
        """Steps without explicit name get '{type}-{index}'."""
        raw = {
            "name": "test",
            "steps": [
                {"design": {"phase": 4}},
                {"tasks": {"phase": 5}},
                {"compact": None},
            ],
        }
        defn = PipelineSchema.model_validate(raw).to_definition()
        assert defn.steps[0].name == "design-0"
        assert defn.steps[1].name == "tasks-1"
        assert defn.steps[2].name == "compact-2"

    def test_step_explicit_name(self) -> None:
        """Steps with an explicit ``name`` in config use that name."""
        raw = {
            "name": "test",
            "steps": [{"design": {"phase": 4, "name": "my-design"}}],
        }
        defn = PipelineSchema.model_validate(raw).to_definition()
        assert defn.steps[0].name == "my-design"
        # The name should not leak into config
        assert "name" not in defn.steps[0].config
