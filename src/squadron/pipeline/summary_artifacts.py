"""The files a run wrote, handed to the summary step (#282).

A session summary only knows what the live session holds. A resumed run starts with
an empty session, so the summary had nothing but commit subjects. The slice's design
and task files and the run's reviews are on disk; naming them lets the summarizer
read them. An SDK session reads them with its own tools. A non-SDK one-shot has none
unless the step declares them, so it gets ``read_file`` here, and is only told about
files it can actually read.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from squadron.events.builtin.artifact_paths import expected_artifact_paths
from squadron.integrations.context_forge import ContextForgeError, ContextForgeNotAvailable
from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.review_outputs import ReviewOutputKey
from squadron.pipeline.commit_plan import SLICE_PARAM
from squadron.pipeline.git_ops import parse_slice_index
from squadron.pipeline.models import ActionContext
from squadron.pipeline.steps.phase import ArtifactKind
from squadron.tools.builtin._shared import READ_FILE_NAME

_logger = logging.getLogger(__name__)

__all__ = ["SUMMARY_READ_TOOLS", "SummarySources", "summary_sources", "with_artifact_section"]

# What a non-SDK summary gets when the step declares no tools but has files to read.
SUMMARY_READ_TOOLS: tuple[str, ...] = (READ_FILE_NAME,)

_SECTION_HEADER = "Files this pipeline run produced. Read them before summarizing:"


@dataclass(frozen=True)
class SummarySources:
    """The files a summarizer is told to read, and the tools a non-SDK one-shot gets."""

    paths: list[str]
    tools: list[str] | None


def summary_sources(
    context: ActionContext,
    *,
    is_sdk: bool,
    declared_tools: list[str] | None,
    model_allows_tools: bool,
) -> SummarySources:
    """What this summary reads and with which tools.

    SDK: every file the run produced; the session brings its own tools. Non-SDK: the
    same files, but only when the model may use tools and ``read_file`` is among them;
    a step that declares none gets ``SUMMARY_READ_TOOLS``. A step that declares tools
    keeps exactly what it declared.
    """
    files = _run_files(context)
    if is_sdk:
        return SummarySources(paths=files, tools=declared_tools)
    tools = declared_tools
    if tools is None and files:
        tools = list(SUMMARY_READ_TOOLS)
    can_read = model_allows_tools and READ_FILE_NAME in (tools or [])
    return SummarySources(paths=files if can_read else [], tools=tools)


def with_artifact_section(instructions: str, paths: list[str]) -> str:
    """The summary instructions with the files named; unchanged when there are none."""
    if not paths:
        return instructions
    listed = "\n".join(f"- {path}" for path in paths)
    return f"{_SECTION_HEADER}\n{listed}\n\n{instructions}"


def _run_files(context: ActionContext) -> list[str]:
    """The slice's design and task files, then the run's reviews, those on disk."""
    candidates = [*_slice_files(context), *_review_files(context)]
    return [path for path in candidates if (Path(context.cwd) / path).is_file()]


def _slice_ref(raw_slice: object) -> object:
    """The slice index; inside an ``each`` loop ``slice`` is the whole cf record."""
    if not isinstance(raw_slice, dict):
        return raw_slice
    record = cast("dict[str, object]", raw_slice)
    return record.get("index", record)


def _slice_files(context: ActionContext) -> list[str]:
    """The slice's design and task paths; empty when the run has no slice.

    A slice that cannot be resolved is logged at WARNING and yields none: the
    summary still runs, from whatever the session holds.
    """
    raw_slice = context.params.get(SLICE_PARAM)
    if raw_slice is None:
        return []
    try:
        slice_index = parse_slice_index(_slice_ref(raw_slice))
        return [
            path
            for kind in ArtifactKind
            for path in expected_artifact_paths(kind, slice_index, context.cf_client)
        ]
    except (ValueError, TypeError, FileNotFoundError, ContextForgeError, ContextForgeNotAvailable):
        _logger.warning(
            "summary step '%s': cannot resolve slice %r files; summarizing without them",
            context.step_name,
            raw_slice,
            exc_info=True,
        )
        return []


def _review_files(context: ActionContext) -> list[str]:
    """Each review file this run saved, once.

    Every round of a review writes the same path (earlier rounds are archived), so the
    distinct paths are the current reviews; the archive is not read.
    """
    paths: dict[str, None] = {}
    for result in context.prior_outputs.values():
        if result.action_type != ActionType.REVIEW:
            continue
        path = result.outputs.get(ReviewOutputKey.REVIEW_FILE)
        if isinstance(path, str):
            paths[path] = None
    return list(paths)
