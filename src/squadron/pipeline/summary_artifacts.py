"""The files a run wrote for its slice, handed to the summary step (#282).

A session summary only knows what the live session holds. A resumed run starts with
an empty session, so the summary had nothing but commit subjects. The slice's design
and task files are on disk; naming them lets the summarizing session read them.
"""

from __future__ import annotations

import logging
from pathlib import Path

from squadron.events.builtin.artifact_paths import expected_artifact_paths
from squadron.integrations.context_forge import ContextForgeError, ContextForgeNotAvailable
from squadron.pipeline.commit_plan import SLICE_PARAM
from squadron.pipeline.git_ops import parse_slice_index
from squadron.pipeline.models import ActionContext
from squadron.pipeline.steps.phase import ArtifactKind

_logger = logging.getLogger(__name__)

__all__ = ["slice_artifact_paths", "with_artifact_section"]

_SECTION_HEADER = "Files this pipeline run produced for the slice. Read them before summarizing:"


def slice_artifact_paths(context: ActionContext) -> list[str]:
    """The slice's design and task files that exist on disk; empty when the run has no slice.

    A slice that cannot be resolved is logged at WARNING and yields no paths: the
    summary still runs, from whatever the session holds.
    """
    raw_slice = context.params.get(SLICE_PARAM)
    if raw_slice is None:
        return []
    try:
        slice_index = parse_slice_index(raw_slice)
        expected = [
            path
            for kind in ArtifactKind
            for path in expected_artifact_paths(kind, slice_index, context.cf_client)
        ]
    except (ValueError, TypeError, FileNotFoundError, ContextForgeError, ContextForgeNotAvailable):
        _logger.warning(
            "summary step '%s': cannot resolve slice %r artifacts; summarizing without them",
            context.step_name,
            raw_slice,
            exc_info=True,
        )
        return []
    return [path for path in expected if (Path(context.cwd) / path).is_file()]


def with_artifact_section(instructions: str, paths: list[str]) -> str:
    """The summary instructions with the artifact files named; unchanged when there are none."""
    if not paths:
        return instructions
    listed = "\n".join(f"- {path}" for path in paths)
    return f"{_SECTION_HEADER}\n{listed}\n\n{instructions}"
