"""Source registry for the ``each`` step type.

A source is named in pipeline YAML as ``namespace.function(args)`` — e.g.
``cf.unfinished_slices("{plan}")`` — and returns the list of items ``each``
iterates over. Each item is a dict bound to the step's ``as:`` name.
"""

from __future__ import annotations

import heapq
import logging
import re
from collections.abc import Awaitable
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from squadron.documents.frontmatter import read_frontmatter
from squadron.pipeline.batch_report import FlagKind
from squadron.pipeline.git_ops import (
    merged_slice_branches,
    read_integration_target,
    slice_branch_name,
)
from squadron.pipeline.loop_config import LoopCondition
from squadron.review.models import Verdict
from squadron.review.parts import review_stems, worst_verdict
from squadron.review.persistence import REVIEWS_DIR, slice_name_for, slice_review_stem
from squadron.review.templates import BuiltinReviewTemplate

if TYPE_CHECKING:
    from squadron.integrations.context_forge import ContextForgeClient, SliceEntry, TaskEntry

_logger = logging.getLogger(__name__)


class SourceFn(Protocol):
    """An ``each`` source: selects the items a batch runs over.

    ``cwd`` is the repository the run works in, for sources that read git state.
    """

    def __call__(
        self,
        args: list[str],
        cf_client: ContextForgeClient,
        params: dict[str, object],
        *,
        cwd: str,
    ) -> Awaitable[list[dict[str, object]]]: ...


SOURCE_REGISTRY: dict[tuple[str, str], SourceFn] = {}

_SOURCE_RE = re.compile(r"(\w+)\.(\w+)\(([^)]*)\)")
_LEADING_INT_RE = re.compile(r"\s*(\d+)")


class CfSliceStatus(StrEnum):
    """cf slice statuses a source selects on (slice 195 D1)."""

    COMPLETE = "complete"
    DEFERRED = "deferred"


_EXCLUDED_STATUSES = frozenset({CfSliceStatus.COMPLETE, CfSliceStatus.DEFERRED})


def _plan_arg(args: list[str]) -> str | None:
    """The source's ``plan`` argument as a cf arch index, or None when absent.

    Raises ValueError when the value is not all digits — a slice-plan name or
    an unresolved ``{plan}`` placeholder would otherwise reach cf as garbage.
    """
    if not args:
        return None
    plan = args[0]
    if not plan.isdigit():
        raise ValueError(f"plan must be an architecture index, got {plan!r}")
    return plan


def _slice_item(entry: SliceEntry) -> dict[str, object]:
    return {
        "index": str(entry.index),
        "name": entry.name,
        "status": entry.status,
        "design_file": entry.design_file or "",
        "dependencies": _design_dependencies(entry),
    }


def _design_dependencies(entry: SliceEntry) -> list[int]:
    """The slice indices *entry*'s design lists under ``dependencies:`` (slice 196 D9).

    Parsing is lenient: each element is taken as its leading integer, so ``195``,
    ``"195"`` and ``"195-slice.foo"`` all give 195. An element with no leading integer
    is dropped with a WARNING naming the slice and the value, never silently. A slice
    with no design has no dependencies.
    """
    if not entry.design_file:
        return []
    path = Path(entry.design_file)
    if not path.is_file():
        _logger.warning(
            "slice %d: design file %s not found; its dependencies were not read",
            entry.index,
            entry.design_file,
        )
        return []
    try:
        frontmatter = read_frontmatter(path)
    except (OSError, UnicodeDecodeError) as exc:
        # One unreadable design must not abort source evaluation for the whole batch.
        _logger.warning(
            "slice %d: cannot read design %s (%s); its dependencies were not read",
            entry.index,
            entry.design_file,
            exc,
        )
        return []
    raw = frontmatter.get("dependencies") if frontmatter is not None else None
    if raw is None:
        return []
    elements = cast(list[object], raw) if isinstance(raw, list) else [raw]
    dependencies: list[int] = []
    for element in elements:
        match = _LEADING_INT_RE.match(str(element))
        if match is None:
            _logger.warning(
                "slice %d: dependency %r has no leading slice index; dropped",
                entry.index,
                element,
            )
            continue
        dependencies.append(int(match.group(1)))
    return dependencies


async def _cf_unfinished_slices(
    args: list[str],
    cf_client: ContextForgeClient,
    params: dict[str, object],
    *,
    cwd: str,
) -> list[dict[str, object]]:
    """Return slices of the plan whose status is not 'complete'."""
    slices = cf_client.list_slices(_plan_arg(args))
    return [_slice_item(entry) for entry in slices if entry.status != CfSliceStatus.COMPLETE]


async def _cf_undesigned_slices(
    args: list[str],
    cf_client: ContextForgeClient,
    params: dict[str, object],
    *,
    cwd: str,
) -> list[dict[str, object]]:
    """Return open slices of the plan that have no design file yet."""
    slices = cf_client.list_slices(_plan_arg(args))
    return [
        _slice_item(entry)
        for entry in slices
        if entry.status not in _EXCLUDED_STATUSES and not entry.design_file
    ]


def _accept_arg(args: list[str]) -> LoopCondition:
    """The ``accept`` threshold: a verdict-bearing LoopCondition value."""
    if len(args) < 2:
        raise ValueError("this source requires (plan, accept) arguments")
    try:
        accept = LoopCondition(args[1])
    except ValueError:
        valid = [c.value for c in LoopCondition if c is not LoopCondition.ACTION_SUCCESS]
        raise ValueError(f"Invalid accept threshold {args[1]!r}. Valid: {valid}") from None
    if accept is LoopCondition.ACTION_SUCCESS:
        raise ValueError(f"{accept.value} is not a review verdict threshold")
    return accept


# The design review's template is ``slice``; reason strings call it a design review.
_DESIGN_REVIEW_TEMPLATE = BuiltinReviewTemplate.SLICE
_TASKS_REVIEW_TEMPLATE = BuiltinReviewTemplate.TASKS
_REVIEW_LABELS: dict[str, str] = {_DESIGN_REVIEW_TEMPLATE: "design"}


def _review_flag(
    entry: SliceEntry, template: str, accept: LoopCondition, inputs: list[str]
) -> str | None:
    """Why *entry*'s review of *template* is not settled at *accept*, or None if it is.

    *inputs* are the reviewed files; a split review has one artifact per input
    (``.part-1`` .. ``.part-N``) and is judged by the worst part, as the review
    action folds it. Paths are computed exactly as the save path names them —
    never searched — so an archived predecessor is never read (195 D1). The reason
    names the review, for example ``tasks review below threshold (CONCERNS < PASS)``.
    """
    label = _REVIEW_LABELS.get(template, template)
    stem = slice_review_stem(entry.index, template, slice_name_for(entry.design_file, entry.name))
    verdicts: list[str] = []
    for part in review_stems(stem, inputs):
        path = REVIEWS_DIR / f"{part}.md"
        if not path.is_file():
            return f"no {label} review found"
        frontmatter = read_frontmatter(path)
        raw_verdict = frontmatter.get("verdict") if frontmatter is not None else None
        if raw_verdict not in {v.value for v in Verdict}:
            return f"{label} review verdict unreadable"
        verdicts.append(str(raw_verdict))
    verdict = Verdict(worst_verdict(verdicts))
    if not accept.met_by_verdict(verdict):
        return f"{label} review below threshold ({verdict} < {accept.minimum_verdict})"
    return None


async def _cf_slices_needing_tasks(
    args: list[str],
    cf_client: ContextForgeClient,
    params: dict[str, object],
    *,
    cwd: str,
) -> list[dict[str, object]]:
    """Return open, designed slices of the plan whose tasks still need work.

    A slice needs tasks when it has no task file, or has one whose tasks review is
    missing, unreadable, or below *accept* (slice 196 D11). A slice whose design
    review is missing, unreadable, or below *accept* carries ``flag_reason``, which
    applies first; ``each`` records it FLAGGED without running it.
    """
    plan = _plan_arg(args)
    accept = _accept_arg(args)
    task_files = {task.index: task.files for task in cf_client.list_tasks(plan)}
    items: list[dict[str, object]] = []
    for entry in cf_client.list_slices(plan):
        if entry.status in _EXCLUDED_STATUSES or not entry.design_file:
            continue
        # For selection a non-None tasks result means "selected", not "flagged".
        files = task_files.get(entry.index)
        if files and _review_flag(entry, _TASKS_REVIEW_TEMPLATE, accept, files) is None:
            continue
        item = _slice_item(entry)
        flag_reason = _review_flag(entry, _DESIGN_REVIEW_TEMPLATE, accept, [entry.design_file])
        if flag_reason is not None:
            item["flag_reason"] = flag_reason
        items.append(item)
    return items


# Item keys a source sets on an item that must not run.
FLAG_REASON_KEY = "flag_reason"
FLAG_KIND_KEY = "flag_kind"


def _not_ready_reason(entry: SliceEntry, task: TaskEntry | None, accept: LoopCondition) -> str | None:
    """Why a designed, open slice is not ready to implement (197 D2); first hit wins."""
    if not entry.design_file:
        return "no design file"
    if (
        reason := _review_flag(entry, _DESIGN_REVIEW_TEMPLATE, accept, [entry.design_file])
    ) is not None:
        return reason
    if task is None or not task.files:
        return "no task file"
    if (reason := _review_flag(entry, _TASKS_REVIEW_TEMPLATE, accept, task.files)) is not None:
        return reason
    if task.total > 0 and task.completed == task.total:
        # Implemented and merged but not closed out; rerunning would reimplement it.
        return "all tasks checked but slice not marked complete"
    return None


def _flag(item: dict[str, object], reason: str, kind: FlagKind) -> None:
    item[FLAG_REASON_KEY] = reason
    item[FLAG_KIND_KEY] = kind


def _merged_open_slices(entries: list[SliceEntry], cf_client: ContextForgeClient, cwd: str) -> set[int]:
    """Open-per-cf slices whose branch git shows merged (#188); each is warned about once.

    Git is the record of a merged slice. cf marks a slice complete from its task
    checkboxes, so a slice merged with unchecked tasks reads as open and would be
    reimplemented, and its dependents flagged. A git failure propagates
    (``GitStateUnknownError``) and fails the step before any item runs.
    """
    candidates = [e for e in entries if e.status not in _EXCLUDED_STATUSES and e.design_file]
    target = read_integration_target(cf_client)
    merged = merged_slice_branches(candidates, target, cwd=cwd)
    for entry in sorted((e for e in candidates if e.index in merged), key=lambda e: e.index):
        _logger.warning(
            "slice %d: branch %s is merged into %s but cf reports %s; treating it as complete. "
            "Check off its tasks to close it in cf.",
            entry.index,
            slice_branch_name(entry.index, entry.design_file),
            target,
            entry.status,
        )
    return merged


async def _cf_slices_ready_to_implement(
    args: list[str],
    cf_client: ContextForgeClient,
    params: dict[str, object],
    *,
    cwd: str,
) -> list[dict[str, object]]:
    """Open, designed slices of the plan, in dependency order (slice 197 D2, D3).

    A slice that is not ready is still returned, with ``flag_reason`` and ``flag_kind``,
    so the report names it and ``each`` flags its dependents.
    """
    plan = _plan_arg(args)
    accept = _accept_arg(args)
    tasks = {task.index: task for task in cf_client.list_tasks(plan)}
    entries = cf_client.list_slices(plan)
    merged = _merged_open_slices(entries, cf_client, cwd)
    in_plan = {entry.index for entry in entries}
    open_in_plan = {
        e.index for e in entries if e.status not in _EXCLUDED_STATUSES and e.index not in merged
    }
    items: list[dict[str, object]] = []
    for entry in entries:
        if entry.status in _EXCLUDED_STATUSES or not entry.design_file or entry.index in merged:
            continue
        item = _slice_item(entry)
        reason = _not_ready_reason(entry, tasks.get(entry.index), accept)
        if reason is not None:
            _flag(item, reason, FlagKind.NOT_READY)
        items.append(item)

    returned = {int(str(item["index"])) for item in items}
    for item in items:
        for dependency in cast(list[int], item["dependencies"]):
            if dependency not in in_plan:
                _logger.warning(
                    "slice %s: dependency %d is outside plan %s; not checked",
                    item["index"],
                    dependency,
                    plan,
                )
            elif dependency in open_in_plan and dependency not in returned:
                if FLAG_REASON_KEY not in item:
                    _flag(item, f"dependency {dependency} not designed", FlagKind.DEPENDENCY)
    try:
        return order_by_dependencies(items, plan)
    except ValueError:
        _logger.exception("cf.slices_ready_to_implement: cannot order plan %s", plan)
        raise


def order_by_dependencies(
    items: list[dict[str, object]], plan: str | None = None
) -> list[dict[str, object]]:
    """Items in dependency order: a stable topological sort, ties by input order (197 D3).

    Only dependencies between the given items count. A cycle raises ``ValueError``
    naming its path, for example ``dependency cycle in plan 180: 196 → 197 → 196``.
    """
    indices = [int(str(item["index"])) for item in items]
    position = {index: pos for pos, index in enumerate(indices)}
    needs = {
        index: {d for d in cast(list[int], item.get("dependencies", [])) if d in position}
        for index, item in zip(indices, items, strict=True)
    }
    ready = [pos for pos, index in enumerate(indices) if not needs[index]]
    heapq.heapify(ready)
    ordered: list[dict[str, object]] = []
    placed: set[int] = set()
    while ready:
        pos = heapq.heappop(ready)
        ordered.append(items[pos])
        placed.add(indices[pos])
        for index in indices:
            if index not in placed and indices[pos] in needs[index]:
                needs[index].discard(indices[pos])
                if not needs[index]:
                    heapq.heappush(ready, position[index])
    if len(ordered) < len(items):
        cycle = _find_cycle(needs, placed)
        raise ValueError(f"dependency cycle in plan {plan}: " + " → ".join(map(str, cycle)))
    return ordered


def _find_cycle(needs: dict[int, set[int]], placed: set[int]) -> list[int]:
    """One cycle among the unplaced items, as a path that ends where it starts."""
    start = min(index for index in needs if index not in placed)
    path = [start]
    while True:
        following = min(needs[path[-1]])
        if following in path:
            return [*path[path.index(following) :], following]
        path.append(following)


SOURCE_REGISTRY[("cf", "unfinished_slices")] = _cf_unfinished_slices
SOURCE_REGISTRY[("cf", "undesigned_slices")] = _cf_undesigned_slices
SOURCE_REGISTRY[("cf", "slices_needing_tasks")] = _cf_slices_needing_tasks
SOURCE_REGISTRY[("cf", "slices_ready_to_implement")] = _cf_slices_ready_to_implement


def parse_source(
    source_str: str,
) -> tuple[str, str, list[str]]:
    """Parse a source string like ``cf.unfinished_slices("{plan}")``.

    Returns (namespace, function, args_list).
    Raises ValueError for unknown namespace/function combinations.
    """
    match = _SOURCE_RE.fullmatch(source_str.strip())
    if not match:
        raise ValueError(
            f"Invalid source string {source_str!r}. Expected format: namespace.function(args)"
        )
    namespace = match.group(1)
    function = match.group(2)
    args_raw = match.group(3).strip()
    args = [a.strip().strip("\"'") for a in args_raw.split(",") if a.strip()] if args_raw else []

    key = (namespace, function)
    if key not in SOURCE_REGISTRY:
        raise ValueError(
            f"Unknown source '{namespace}.{function}'. Registered sources: {list(SOURCE_REGISTRY)}"
        )
    return namespace, function, args
