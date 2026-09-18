"""Input gathering for ``sq pr create`` (D7): commits, slice artifacts, review.

Every input here is either present or explicitly absent. A branch or an
artifact that cannot be resolved degrades to "absent" with a WARNING —
never fatal, because a PR should still open — except where the design
requires a refusal (base selection, preconditions), which live elsewhere.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from squadron.integrations.context_forge import ContextForgeError, ContextForgeNotAvailable
from squadron.pr.branch import parse_slice_branch
from squadron.pr.tasks import TaskItems, parse_task_items
from squadron.review.git_utils import CommitRecord, commits_in_range
from squadron.review.persistence import TASKS_DIR, CfClientProtocol, SliceInfo, resolve_slice_info

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SliceInputs:
    """Slice artifacts gathered for a branch that names a slice, or None fields."""

    index: int | None
    design_file: str | None
    task_items: TaskItems | None


@dataclass(frozen=True)
class PrInputs:
    """Every input assembly needs, each present or explicitly absent."""

    commits: tuple[CommitRecord, ...]
    slice: SliceInputs


def gather_commits_and_slice(
    cf_client: CfClientProtocol,
    *,
    base: str,
    head: str,
    cwd: str,
) -> PrInputs:
    """Gather the commit range and, when ``head`` names a slice, its artifacts.

    A branch that does not match the slice convention yields no slice
    inputs and makes no ``cf`` call. A slice index ``cf`` cannot resolve, or
    a missing/unreadable task file, degrades to absent with a WARNING
    naming the condition — not fatal, because a PR should still open.
    """
    commits = tuple(commits_in_range(base, head, cwd=cwd))

    index = parse_slice_branch(head)
    if index is None:
        no_slice = SliceInputs(index=None, design_file=None, task_items=None)
        return PrInputs(commits=commits, slice=no_slice)

    try:
        info: SliceInfo = resolve_slice_info(cf_client, index)
    except (ValueError, ContextForgeNotAvailable, ContextForgeError) as exc:
        _logger.warning(
            "sq pr create: branch names slice %d, but cf could not resolve it (%s); "
            "describing commits only",
            index,
            exc,
        )
        unresolved = SliceInputs(index=index, design_file=None, task_items=None)
        return PrInputs(commits=commits, slice=unresolved)

    task_items = _read_task_items(info, cwd)
    return PrInputs(
        commits=commits,
        slice=SliceInputs(index=index, design_file=info["design_file"], task_items=task_items),
    )


def _read_task_items(info: SliceInfo, cwd: str) -> TaskItems | None:
    """Read and parse the slice's first task file, or None when absent/unreadable."""
    if not info["task_files"]:
        return None
    path = Path(cwd) / TASKS_DIR / info["task_files"][0]
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        _logger.warning(
            "sq pr create: slice %d's task file %s could not be read; "
            "leaving the design file as the only 'why' input",
            info["index"],
            path,
        )
        return None
    return parse_task_items(text)
