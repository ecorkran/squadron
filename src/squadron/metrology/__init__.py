"""Metrology data layer — the durable, user-level home for oracle verdicts.

The keystone of initiative 320: a surface-agnostic core that both the CLI and
the future MCP surface call, preserving interface parity by construction. The
public surface is filled in as the slice's tasks land (identity, models,
store, capture); today it exports the typed exception hierarchy.
"""

from __future__ import annotations

from squadron.metrology.capture import (
    CaptureOutcome,
    CapturePayload,
    build_capture_payload,
    record_sample,
    resolve_target,
    reveal,
)
from squadron.metrology.errors import (
    MetrologyError,
    MetrologyIdentityError,
    MetrologyStoreError,
    MetrologyTargetError,
)
from squadron.metrology.identity import (
    derive_judge_config_id,
    derive_project_id,
    derive_result_ref,
)
from squadron.metrology.models import (
    RECORD_TYPE_AUDIT_FINDING,
    RECORD_TYPE_SAMPLE,
    JudgeConfigId,
    JudgeResultRef,
    MetrologyRecord,
    ProjectId,
    ProjectIdSource,
    SampleVerdict,
)
from squadron.metrology.store import (
    MetrologyStore,
    SchemaVersionError,
    generate_sample_id,
    resolve_store_dir,
)

__all__ = [
    "MetrologyError",
    "MetrologyIdentityError",
    "MetrologyStoreError",
    "MetrologyTargetError",
    "ProjectId",
    "ProjectIdSource",
    "JudgeResultRef",
    "JudgeConfigId",
    "SampleVerdict",
    "MetrologyRecord",
    "RECORD_TYPE_SAMPLE",
    "RECORD_TYPE_AUDIT_FINDING",
    "MetrologyStore",
    "SchemaVersionError",
    "generate_sample_id",
    "resolve_store_dir",
    "CapturePayload",
    "CaptureOutcome",
    "resolve_target",
    "build_capture_payload",
    "record_sample",
    "reveal",
    "derive_project_id",
    "derive_result_ref",
    "derive_judge_config_id",
]
