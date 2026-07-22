"""Metrology data layer — the durable, user-level home for oracle verdicts.

The keystone of initiative 320: a surface-agnostic core that both the CLI and
the future MCP surface call, preserving interface parity by construction. The
public surface is filled in as the slice's tasks land (identity, models,
store, capture); today it exports the typed exception hierarchy.
"""

from __future__ import annotations

from squadron.metrology.errors import (
    MetrologyError,
    MetrologyIdentityError,
    MetrologyStoreError,
    MetrologyTargetError,
)
from squadron.metrology.identity import derive_project_id
from squadron.metrology.models import ProjectId, ProjectIdSource

__all__ = [
    "MetrologyError",
    "MetrologyIdentityError",
    "MetrologyStoreError",
    "MetrologyTargetError",
    "ProjectId",
    "ProjectIdSource",
    "derive_project_id",
]
