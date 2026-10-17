"""Shared artifact-path resolution for the dispatch-artifact, revision-stamp and
usage-stamp built-ins — the one place both consult Context Forge for a
phase's expected artifact path(s), so they cannot drift apart."""

from __future__ import annotations

from dataclasses import dataclass

from squadron.pipeline.commit_plan import PLAN_PARAM, SLICE_PARAM
from squadron.pipeline.steps.phase import ArtifactKind
from squadron.review.persistence import (
    TASKS_DIR,
    CfClientProtocol,
    SliceInfo,
    resolve_arch_file,
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


@dataclass(frozen=True)
class DispatchScope:
    """What a phase dispatch writes for: a slice, or an initiative (plan, no slice)."""

    param: str
    index: int

    @property
    def label(self) -> str:
        return f"{'initiative' if self.param == PLAN_PARAM else 'slice'} {self.index}"


def dispatch_scope(slice_param: object, plan_param: object) -> DispatchScope:
    """The scope a dispatch with these params writes for.

    Raises:
        ValueError: No slice or plan param, or the param is not a numeric index.
    """
    if slice_param is None and plan_param is not None:
        return DispatchScope(PLAN_PARAM, _numeric_index(PLAN_PARAM, plan_param))
    if slice_param is None:
        raise ValueError(f"no '{SLICE_PARAM}' param in scope")
    return DispatchScope(SLICE_PARAM, _numeric_index(SLICE_PARAM, slice_param))


def dispatch_artifact_paths(
    kind: ArtifactKind,
    slice_param: object,
    plan_param: object,
    cf_client: CfClientProtocol,
    cwd: str,
) -> list[str]:
    """The candidate artifact path(s) a phase dispatch with these params writes.

    A slice index resolves through Context Forge; a plan index with no slice is the
    initiative's architecture doc. The caller decides how to report a failure.

    Raises:
        ValueError: A param is missing or not a numeric index (``dispatch_scope``), or
            the slice cannot be resolved (``expected_artifact_paths``).
        TypeError, FileNotFoundError, ContextForgeError: As the resolvers raise them.
    """
    scope = dispatch_scope(slice_param, plan_param)
    if scope.param == PLAN_PARAM:
        return [resolve_arch_file(scope.index, cwd or ".")]
    return expected_artifact_paths(kind, scope.index, cf_client)


def _numeric_index(name: str, value: object) -> int:
    try:
        return int(str(value))
    except ValueError:
        raise ValueError(f"'{name}' param {value!r} is not a numeric index") from None
