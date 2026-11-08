"""Fix-case fairness: the adapter seam, its result types and the rule version (slice 422).

``FixCaseAdapter`` is separate from 421's ``BenchmarkAdapter`` (ISP): languages that only
build slice cases need none of these methods. Concrete adapters are reached only through
``registry.py`` (D13).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from squadron.benchmark.adapter import SandboxContext
from squadron.metrology.benchmark_models import ConftestFixture, GraderCommand, TestRejection
from squadron.metrology.snapshot_models import SourceLanguage

#: Bumped whenever any fairness check changes: stored qualification records carry it, and
#: a record with another version is re-qualified rather than reused (D10).
FAIRNESS_RULE_VERSION = 1


@dataclass(frozen=True)
class CollectedTests:
    """What collection found in one file state of the sandbox."""

    #: node id -> closure digest (the test plus every test-side definition it reaches).
    digests: Mapping[str, str]
    #: node id -> the conftest fixtures its closure reaches.
    fixtures_reached: Mapping[str, tuple[ConftestFixture, ...]]
    #: every conftest fixture defined, by path and name.
    conftest_fixtures: frozenset[ConftestFixture]


@dataclass(frozen=True)
class AllowedBoundary:
    """The packaging boundary: ``(module, qualname)`` entries tests may reach."""

    entries: frozenset[tuple[str, str]] = field(default_factory=frozenset[tuple[str, str]])

    def allows(self, module: str, qualname: str) -> bool:
        return (module, qualname) in self.entries


@dataclass(frozen=True)
class FairnessVerdict:
    """One hidden test's trace result: ``rejection`` is ``None`` when it is fair."""

    rejection: TestRejection | None
    detail: str = ""


class BoundaryUndecidable(Exception):
    """The packaging boundary cannot be determined (the package would not import)."""


class CollectionFailed(Exception):
    """A test-side file failed collection; ``file`` names it."""

    def __init__(self, file: str, message: str) -> None:
        super().__init__(f"{file}: {message}")
        self.file = file
        self.message = message


class HarnessFailure(Exception):
    """The harness could not run a check (timeout, missing output, I/O error).

    Never a verdict on the candidate: qualification records it as ``harness_error``.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class FixCaseAdapter(Protocol):
    language: SourceLanguage

    def is_test_side(self, pyproject_text: str | None, path: str) -> bool:
        """Whether ``path`` is a test-side file, per the parent's project config text."""
        ...

    def is_test_source(self, path: str) -> bool:
        """Whether a test-side ``path`` is source code (as opposed to test data)."""
        ...

    def lockfile_names(self) -> tuple[str, ...]:
        """File names that pin the environment; a diff touching one is not qualifiable."""
        ...

    def collect(self, ctx: SandboxContext) -> CollectedTests: ...

    def overlay(self, ctx: SandboxContext, files: Mapping[str, bytes | None]) -> None:
        """Write each ``path -> bytes`` and remove each ``path -> None`` inside the tree."""
        ...

    def boundary(self, ctx: SandboxContext) -> AllowedBoundary: ...

    def trace(
        self, ctx: SandboxContext, node_ids: Sequence[str], allowed: AllowedBoundary
    ) -> Mapping[str, FairnessVerdict]: ...

    def grader_commands(self, tree: Path) -> tuple[GraderCommand, ...]: ...
