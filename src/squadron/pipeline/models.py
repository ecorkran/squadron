"""Core data models for the pipeline system.

All types are plain dataclasses (no Pydantic) — internal DTOs only.
Pydantic enters the pipeline in slice 148 for YAML loading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadron.pipeline.resolver import ModelResolver
    from squadron.pipeline.sdk_session import SDKExecutionSession
    from squadron.review.persistence import CfClientProtocol


@dataclass
class ValidationError:
    """A single validation failure from an action or step-type validator."""

    field: str
    message: str
    action_type: str


@dataclass
class ActionResult:
    """Result returned by an action after execution."""

    success: bool
    action_type: str
    outputs: dict[str, object]
    error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict[str, object])
    verdict: str | None = None
    findings: list[object] = field(default_factory=list[object])


@dataclass
class ActionContext:
    """Execution context passed to every action at runtime."""

    pipeline_name: str
    run_id: str
    params: dict[str, object]
    step_name: str
    step_index: int
    prior_outputs: dict[str, ActionResult]
    resolver: ModelResolver
    cf_client: CfClientProtocol
    cwd: str
    sdk_session: SDKExecutionSession | None = None


@dataclass
class StepConfig:
    """Configuration for a single pipeline step as parsed from YAML."""

    step_type: str
    name: str
    config: dict[str, object]


@dataclass
class PipelineDefinition:
    """Top-level pipeline definition as parsed from YAML."""

    name: str
    description: str
    params: dict[str, object]
    steps: list[StepConfig]
    model: str | None = None
