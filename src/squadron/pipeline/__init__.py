"""Pipeline package — public surface for squadron.pipeline.

Re-exports all types needed by pipeline consumers:
  - Data models: ActionContext, ActionResult, PipelineDefinition, StepConfig,
    ValidationError
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
from squadron.pipeline.resolver import (
    ModelPoolNotImplemented,
    ModelResolutionError,
    ModelResolver,
)
from squadron.pipeline.steps import StepTypeName

__all__ = [
    "ActionContext",
    "ActionResult",
    "ActionType",
    "ModelPoolNotImplemented",
    "ModelResolutionError",
    "ModelResolver",
    "PipelineDefinition",
    "StepConfig",
    "StepTypeName",
    "ValidationError",
]
