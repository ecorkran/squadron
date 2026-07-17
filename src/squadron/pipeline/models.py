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
    # Numeric scoring foundation (slice 300) — mirror the optional verdict field.
    # provenance is reserved (added here, never set or read this slice — 301).
    score: float | None = None
    criteria: dict[str, float] | None = None
    provenance: str | None = None


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
    # Step-name -> that step's verdict-bearing review ActionResult. Additive
    # read view alongside prior_outputs (which is lossy across same-typed
    # steps); does not change prior_outputs semantics or checkpoint behavior.
    step_outputs: dict[str, ActionResult] = field(default_factory=dict[str, ActionResult])


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
    auth_policy: str | None = None
