"""Planning-document readers for the effort reports (slice 176 D4).

Reads task files and slice plans from disk. Formats vary across the repo's history, so
each field is parsed by its meaning, not its layout. No git and no Typer here.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from squadron.documents.frontmatter import read_frontmatter
from squadron.documents.schema import STATUS_ALIASES, DocumentStatus
from squadron.integrations.context_forge import ARCHITECTURE_DIR
from squadron.review.persistence import SLICES_DIR, TASKS_DIR

_logger = logging.getLogger(__name__)

# `**Task N: Title**`, `### Task N: Title`, `### TN: Title`, `**TN. Title**`, with an
# optional bullet, checkbox and indent.
_TASK_HEADING = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\[[ xX]\]\s+)?(?:(?P<hashes>#{1,6})\s+)?\**\s*"
    r"(?:Task\s+(?P<long>\d+)|T(?P<short>\d+))\s*[:.]\s*(?P<title>.+?)[\s*]*$"
)
_MARKDOWN_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s")
_CHECKBOX = re.compile(r"^\s*[-*]\s+\[(?P<mark>[ xX])\]")
# `Effort: 3`, `Effort: 3/5`, `**Effort**: 3`, `**Effort:** 3`.
# It must start the item: prose that quotes the format is not an effort line.
_EFFORT = re.compile(r"^\s*(?:[-*]\s+)?(?:\[[ xX]\]\s+)?\**Effort\**\s*:\s*\**\s*(?P<value>\S.*)")
_EFFORT_NUMBER = re.compile(r"(?P<number>\d+)(?:\s*/\s*\d+)?\b")
_COMMIT_PRESCRIBED = re.compile(r"Commit:\s*`(?P<subject>[^`]+)`")
_GIT_COMMIT = re.compile(r"git commit -m\s+([\"'])(?P<subject>.+?)\1")
#: A `-1`, `-2` suffix before `.md` marks one part of a split task file.
_SPLIT_SUFFIX = re.compile(r"-(?P<part>\d+)$")
# `1. [x] **(175) Title** ...`: the `(NNN)` index marks a slice entry; backlog items have none.
_PLAN_ENTRY = re.compile(r"^\s*\d+\.\s+\[[ xX]\]\s+\*\*\((?P<index>\d+)\)\s*(?P<title>.+?)\*\*")
# A checkbox item or a heading ends an entry; plain numbered lines inside one do not.
_PLAN_ITEM = re.compile(r"^\s*\d+\.\s+\[[ xX]\]")
_PLAN_EFFORT = re.compile(r"Effort\**\s*:\s*\**\s*(?P<number>\d+)\s*/\s*\d+")
#: A block that starts at a bullet (not a markdown heading) ends at any heading.
_ANY_HEADING_LEVEL = 6


@dataclass(frozen=True)
class PlannedTask:
    number: int
    title: str
    effort: int | None
    checked: int
    total: int
    commit_subjects: tuple[str, ...]


@dataclass(frozen=True)
class PlannedSlice:
    index: int
    title: str
    effort: int | None
    complete: bool
    tasks: tuple[PlannedTask, ...] | None  # None when there is no task file


@dataclass
class _TaskDraft:
    """A task being read: its heading, then every line up to the next boundary."""

    path: Path
    number: int
    title: str
    end_level: int
    #: Set for a bullet task: its block holds only lines indented deeper than this.
    bullet_indent: int | None = None
    effort: int | None = None
    effort_seen: bool = False
    checked: int = 0
    total: int = 0
    commit_subjects: list[str] | None = None

    def add(self, lineno: int, line: str) -> None:
        if (box := _CHECKBOX.match(line)) is not None:
            self.total += 1
            self.checked += box["mark"] != " "
        if not self.effort_seen and (found := _EFFORT.match(line)) is not None:
            self.effort_seen = True
            self.effort = _read_effort(self.path, lineno, found["value"])
        subjects = [m["subject"] for m in _COMMIT_PRESCRIBED.finditer(line)]
        subjects += [m["subject"] for m in _GIT_COMMIT.finditer(line)]
        if subjects:
            self.commit_subjects = [*(self.commit_subjects or []), *subjects]

    def build(self) -> PlannedTask:
        return PlannedTask(
            number=self.number,
            title=self.title,
            effort=self.effort,
            checked=self.checked,
            total=self.total,
            commit_subjects=tuple(dict.fromkeys(self.commit_subjects or [])),
        )


def _read_effort(path: Path, lineno: int, value: str) -> int | None:
    if (number := _EFFORT_NUMBER.match(value.strip())) is not None:
        return int(number["number"])
    _logger.warning("%s:%d: Effort %r is not a number; reading no effort", path, lineno, value)
    return None


def _draft_for(path: Path, line: str) -> _TaskDraft | None:
    heading = _TASK_HEADING.match(line)
    if heading is None:
        return None
    hashes = heading["hashes"]
    return _TaskDraft(
        path=path,
        number=int(heading["long"] or heading["short"]),
        title=heading["title"].strip("* "),
        end_level=len(hashes) if hashes else _ANY_HEADING_LEVEL,
        bullet_indent=None if hashes else len(line) - len(line.lstrip()),
    )


def _ends_block(line: str, draft: _TaskDraft) -> bool:
    heading = _MARKDOWN_HEADING.match(line)
    if heading is not None and len(heading["hashes"]) <= draft.end_level:
        return True
    if draft.bullet_indent is None or not line.strip():
        return False
    # A bullet task's content is indented; a flush paragraph after it (a slice-level
    # "Effort: 3/5 overall." note, for instance) is not part of the task.
    return len(line) - len(line.lstrip()) <= draft.bullet_indent


def _parse_tasks(path: Path) -> list[PlannedTask]:
    tasks: list[PlannedTask] = []
    current: _TaskDraft | None = None
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if (draft := _draft_for(path, line)) is not None:
            if current is not None:
                tasks.append(current.build())
            current = draft
        elif current is not None and _ends_block(line, current):
            tasks.append(current.build())
            current = None
            continue
        if current is not None:
            current.add(lineno, line)
    if current is not None:
        tasks.append(current.build())
    return tasks


def read_task_file(paths: Sequence[Path]) -> tuple[PlannedTask, ...]:
    """Read one task file, or the ordered parts of a split one, as a single task list."""
    return tuple(task for path in paths for task in _parse_tasks(path))


def task_file_paths(index: int, project_root: Path) -> tuple[Path, ...]:
    """The task file(s) for slice ``index``, split parts in suffix order; empty when none.

    More than one distinct task file name for an index logs at INFO and the first (by name)
    wins, the rule ``resolve_arch_file`` uses. INFO, because the repo's own index 100 has two
    task files for good and a rollup would repeat the line on every run.
    """
    found = sorted((project_root / TASKS_DIR).glob(f"{index}-tasks.*.md"))
    by_base: dict[str, list[Path]] = {}
    for path in found:
        by_base.setdefault(_SPLIT_SUFFIX.sub("", path.stem), []).append(path)
    if not by_base:
        return ()
    base = min(by_base)
    if len(by_base) > 1:
        _logger.info("Multiple task files for index %d, using %s", index, base)
    return tuple(sorted(by_base[base], key=_part_number))


def _part_number(path: Path) -> int:
    suffix = _SPLIT_SUFFIX.search(path.stem)
    return int(suffix["part"]) if suffix else 0


def read_task_files_for(index: int, project_root: Path) -> tuple[PlannedTask, ...] | None:
    """Slice ``index``'s tasks, or ``None`` when it has no task file."""
    paths = task_file_paths(index, project_root)
    return read_task_file(paths) if paths else None


class UnknownSliceError(Exception):
    """A slice index is in no slice plan; carries the plan files that were searched."""

    def __init__(self, index: int, searched: Sequence[Path]) -> None:
        names = ", ".join(path.name for path in searched) or "no plan files found"
        super().__init__(f"slice {index} is in no slice plan (searched: {names})")
        self.index = index
        self.searched = tuple(searched)


@dataclass(frozen=True)
class _PlanEntry:
    index: int
    title: str
    effort: int | None


def _plan_files(project_root: Path) -> list[Path]:
    return sorted((project_root / ARCHITECTURE_DIR).glob("*-slices.*.md"))


def _parse_plan(path: Path) -> list[_PlanEntry]:
    """Entries of one slice plan; an entry runs to the next numbered item or heading."""
    entries: list[_PlanEntry] = []
    head: re.Match[str] | None = None
    block: list[str] = []

    def close() -> None:
        if head is None:
            return
        effort = _PLAN_EFFORT.search("\n".join(block))
        entries.append(
            _PlanEntry(
                index=int(head["index"]),
                title=head["title"].strip(),
                effort=int(effort["number"]) if effort else None,
            )
        )

    for line in path.read_text(encoding="utf-8").splitlines():
        starts_item = _PLAN_ITEM.match(line) is not None
        if starts_item or _MARKDOWN_HEADING.match(line):
            close()
            head, block = (_PLAN_ENTRY.match(line) if starts_item else None), []
        block.append(line)
    close()
    return entries


def _plan_entries(project_root: Path) -> tuple[dict[int, _PlanEntry], list[Path], set[int]]:
    """Entries by index (the first wins), the plan files read, and the repeated indexes."""
    files = _plan_files(project_root)
    entries: dict[int, _PlanEntry] = {}
    repeated: set[int] = set()
    for path in files:
        for entry in _parse_plan(path):
            if entry.index in entries:
                repeated.add(entry.index)
            else:
                entries[entry.index] = entry
    return entries, files, repeated


def slice_status(index: int, project_root: Path) -> tuple[bool, str | None]:
    """``(complete, dateCreated)`` from slice ``index``'s design frontmatter (D4).

    Complete means the design says ``status: complete``; the plan checkbox is not used
    because it can lag. A missing design is ``(False, None)``.
    """
    designs = sorted((project_root / SLICES_DIR).glob(f"{index}-slice.*.md"))
    if not designs:
        return False, None
    if len(designs) > 1:
        _logger.warning("Multiple slice designs for index %d, using %s", index, designs[0].name)
    front = read_frontmatter(designs[0]) or {}
    status = str(front.get("status", ""))
    complete = STATUS_ALIASES.get(status, status) == DocumentStatus.COMPLETE
    created = front.get("dateCreated")
    return complete, None if created is None else str(created)


def _planned_slice(entry: _PlanEntry, project_root: Path) -> PlannedSlice:
    return PlannedSlice(
        index=entry.index,
        title=entry.title,
        effort=entry.effort,
        complete=slice_status(entry.index, project_root)[0],
        tasks=read_task_files_for(entry.index, project_root),
    )


def read_slice_plans(project_root: Path) -> dict[int, PlannedSlice]:
    """Every slice in every ``*-slices.*.md`` plan, with its tasks when a task file exists."""
    entries, _, repeated = _plan_entries(project_root)
    if repeated:
        # Old initiatives reuse small indexes; harmless to a report, so not a WARNING.
        _logger.debug("Slice indexes in more than one plan entry (first wins): %s", sorted(repeated))
    return {index: _planned_slice(entry, project_root) for index, entry in entries.items()}


def planned_slice(index: int, project_root: Path) -> PlannedSlice:
    """One slice's plan entry; raises ``UnknownSliceError`` when no plan lists ``index``."""
    entries, files, repeated = _plan_entries(project_root)
    if index not in entries:
        raise UnknownSliceError(index, files)
    if index in repeated:
        _logger.warning("Slice %d appears in more than one plan entry; using the first", index)
    return _planned_slice(entries[index], project_root)
