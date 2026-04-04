"""Pipeline package — public surface for squadron.pipeline.

Re-exports all types needed by pipeline consumers:
  - Data models: ActionContext, ActionResult, PipelineDefinition, StepConfig,
    ValidationError
  - Prompt-only: ActionInstruction, StepInstructions, CompletionResult,
    render_step_instructions
  - Resolver: ModelResolver, ModelResolutionError, ModelPoolNotImplemented
  - Enums: ActionType, StepTypeName
"""

from __future__ import annotations

from squadron.pipeline.actions import ActionType
from squadron.pipeline.models import (
    ActionContext,
    ActionResult,
    PipelineDefinition,
    StepConfig,
    ValidationError,
)
from squadron.pipeline.prompt_renderer import (
    ActionInstruction,
    CompletionResult,
    StepInstructions,
    render_step_instructions,
)
from squadron.pipeline.resolver import (
    ModelPoolNotImplemented,
    ModelResolutionError,
    ModelResolver,
)
from squadron.pipeline.steps import StepTypeName

__all__ = [
    "ActionContext",
    "ActionInstruction",
    "ActionResult",
    "ActionType",
    "CompletionResult",
    "ModelPoolNotImplemented",
    "ModelResolutionError",
    "ModelResolver",
    "PipelineDefinition",
    "StepConfig",
    "StepInstructions",
    "StepTypeName",
    "ValidationError",
    "render_step_instructions",
]
