"""Classify a fix commit's diff before any sandbox exists (slice 422 D3, D4).

Runs on ``git diff --name-status parent..commit`` and on file text read from git, so
nothing here touches a tree. The ``conftest.py`` comparison is Python-specific (it uses
``ast``); Python is the only language with a fix-case adapter.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Protocol

from squadron.metrology.benchmark_models import CandidateRejection

CONFTEST_NAME = "conftest.py"


class ChangeStatus(StrEnum):
    ADDED = "A"
    MODIFIED = "M"
    DELETED = "D"


@dataclass(frozen=True)
class FileChange:
    status: ChangeStatus
    path: str


@dataclass(frozen=True)
class DiffClassification:
    """Every changed path by kind, and the subset the adapter calls test-side."""

    added: tuple[str, ...]
    changed: tuple[str, ...]
    deleted: tuple[str, ...]
    test_side: tuple[str, ...]


@dataclass(frozen=True)
class DiffRejection:
    rejection: CandidateRejection
    detail: str


class DiffAdapter(Protocol):
    """The part of ``FixCaseAdapter`` diff classification uses (ISP)."""

    def is_test_side(self, pyproject_text: str | None, path: str) -> bool: ...

    def is_test_source(self, path: str) -> bool: ...

    def lockfile_names(self) -> tuple[str, ...]: ...


ReadFile = Callable[[str], str | None]

_OCTAL_ESCAPE = re.compile(r"\\([0-7]{3})")
_SIMPLE_ESCAPES = {"\\\\": "\\", '\\"': '"', "\\t": "\t", "\\n": "\n"}


def _unquote(path: str) -> str:
    """Undo git's C-style path quoting; an unquoted path is returned as is."""
    if len(path) < 2 or not (path.startswith('"') and path.endswith('"')):
        return path
    body = path[1:-1]
    for escaped, plain in _SIMPLE_ESCAPES.items():
        body = body.replace(escaped, plain)
    if _OCTAL_ESCAPE.search(body):
        raw = _OCTAL_ESCAPE.sub(lambda match: chr(int(match.group(1), 8)), body)
        return raw.encode("latin-1").decode("utf-8", errors="replace")
    return body


def parse_name_status(text: str) -> tuple[FileChange, ...]:
    """Parse ``git diff --name-status`` output; a rename is a delete plus an add.

    A copy leaves its source in place, so it is only an add. Type changes count as
    modifications. Any other status letter is ignored: git emits nothing else for a
    plain two-commit diff.
    """
    changes: list[FileChange] = []
    for line in text.splitlines():
        fields = line.rstrip("\r").split("\t")
        if len(fields) < 2 or not fields[0].strip():
            continue
        code = fields[0].strip()[0]
        paths = [_unquote(field) for field in fields[1:] if field.strip()]
        if not paths:
            continue
        if code == "R" and len(paths) >= 2:
            changes.extend(
                [FileChange(ChangeStatus.DELETED, paths[0]), FileChange(ChangeStatus.ADDED, paths[1])]
            )
        elif code == "C" and len(paths) >= 2:
            changes.append(FileChange(ChangeStatus.ADDED, paths[1]))
        elif code in ("A", "D"):
            changes.append(FileChange(ChangeStatus(code), paths[0]))
        elif code in ("M", "T"):
            changes.append(FileChange(ChangeStatus.MODIFIED, paths[0]))
    return tuple(changes)


def _is_fixture_function(node: ast.stmt) -> bool:
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return False
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
        if name == "fixture":
            return True
    return False


def _statement_key(node: ast.stmt) -> str:
    """A stable identity for a top-level statement: its name when it has one."""
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return f"def {node.name}"
    if isinstance(node, ast.Assign):
        names = ",".join(ast.unparse(target) for target in node.targets)
        return f"assign {names}"
    if isinstance(node, ast.AnnAssign):
        return f"assign {ast.unparse(node.target)}"
    return f"stmt {ast.dump(node)}"


def _parse_module(text: str, label: str) -> ast.Module | str:
    try:
        return ast.parse(text)
    except SyntaxError as exc:
        return f"{label} {CONFTEST_NAME} does not parse: {exc.msg} (line {exc.lineno})"


def _conftest_difference(parent_text: str, reference_text: str) -> str | None:
    """The first difference beyond added fixtures and added imports, or ``None``."""
    parent = _parse_module(parent_text, "parent")
    reference = _parse_module(reference_text, "reference")
    if isinstance(parent, str):
        return parent
    if isinstance(reference, str):
        return reference
    imports_before = {ast.dump(n) for n in parent.body if isinstance(n, ast.Import | ast.ImportFrom)}
    imports_after = {ast.dump(n) for n in reference.body if isinstance(n, ast.Import | ast.ImportFrom)}
    if imports_before - imports_after:
        return "an import was removed"
    before = {
        _statement_key(n): n for n in parent.body if not isinstance(n, ast.Import | ast.ImportFrom)
    }
    after = {
        _statement_key(n): n for n in reference.body if not isinstance(n, ast.Import | ast.ImportFrom)
    }
    for key, node in before.items():
        if key not in after:
            return f"removed {key}"
        if ast.dump(after[key]) != ast.dump(node):
            return f"changed {key}"
    for key, node in after.items():
        if key not in before and not _is_fixture_function(node):
            return f"added {key}, which is not a fixture"
    return None


def _modified_support(
    changes: Sequence[FileChange], read_parent: ReadFile, read_reference: ReadFile
) -> str | None:
    """Why a changed or deleted ``conftest.py`` is not just added fixtures, or ``None``."""
    for change in changes:
        if change.status is ChangeStatus.ADDED or PurePosixPath(change.path).name != CONFTEST_NAME:
            continue
        parent_text = read_parent(change.path)
        reference_text = read_reference(change.path)
        if parent_text is None or reference_text is None:
            return f"{change.path} was deleted or is unreadable"
        difference = _conftest_difference(parent_text, reference_text)
        if difference is not None:
            return f"{change.path}: {difference}"
    return None


def classify_diff(
    changes: Sequence[FileChange],
    adapter: DiffAdapter,
    parent_pyproject: str | None,
    read_parent: ReadFile,
    read_reference: ReadFile,
) -> DiffClassification | DiffRejection:
    """The diff's classification, or the first rejection in precedence order.

    Order: no test change, test data changed, lockfile changed, test support modified.
    """
    test_side = tuple(c.path for c in changes if adapter.is_test_side(parent_pyproject, c.path))
    if not test_side:
        return DiffRejection(CandidateRejection.NO_TEST_CHANGE, "no test-side file in the diff")
    data = [path for path in test_side if not adapter.is_test_source(path)]
    if data:
        return DiffRejection(CandidateRejection.TEST_DATA_CHANGED, ", ".join(data))
    lockfiles = set(adapter.lockfile_names())
    locked = [c.path for c in changes if PurePosixPath(c.path).name in lockfiles]
    if locked:
        return DiffRejection(CandidateRejection.CHANGES_LOCKFILE, ", ".join(locked))
    support = _modified_support(changes, read_parent, read_reference)
    if support is not None:
        return DiffRejection(CandidateRejection.MODIFIES_TEST_SUPPORT, support)

    def paths(status: ChangeStatus) -> tuple[str, ...]:
        return tuple(c.path for c in changes if c.status is status)

    return DiffClassification(
        added=paths(ChangeStatus.ADDED),
        changed=paths(ChangeStatus.MODIFIED),
        deleted=paths(ChangeStatus.DELETED),
        test_side=test_side,
    )
