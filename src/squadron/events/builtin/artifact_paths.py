"""Shared artifact-path resolution for the dispatch-artifact and
revision-stamp built-ins — the one place both consult Context Forge for a
phase's expected artifact path(s), so they cannot drift apart."""

from __future__ import annotations

from squadron.pipeline.steps.phase import ArtifactKind
from squadron.review.persistence import (
    TASKS_DIR,
    CfClientProtocol,
    SliceInfo,
    resolve_slice_info,
)


def artifact_paths(kind: ArtifactKind, info: SliceInfo) -> list[str]:
    """The artifact path(s) of ``kind`` for an already-resolved slice."""
    if kind is ArtifactKind.DESIGN:
        return [info["design_file"]] if info["design_file"] else []
    return [str(TASKS_DIR / f) for f in info["task_files"]]


def expected_artifact_paths(
    kind: ArtifactKind, slice_index: int, cf_client: CfClientProtocol
) -> list[str]:
    """Resolve the expected artifact path(s) for a phase's artifact kind.

    Raises:
        ValueError, TypeError: If the slice cannot be resolved via CF —
            propagated to the caller, which treats it as "path unresolvable".
    """
    return artifact_paths(kind, resolve_slice_info(cf_client, slice_index))
