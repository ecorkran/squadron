"""The grading adapter seam: what a language supplies to grade a rebuilt tree (slice 425).

Its own protocol, separate from 421's ``BenchmarkAdapter`` (running a suite) and 422's
``FixCaseAdapter`` (fairness at qualification): slice cases (426) use it without any
fairness method. Registered by ``SourceLanguage`` in ``benchmark.registry``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from squadron.benchmark.tree_reader import TreeReader
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.grade_models import SuppressionCounts
from squadron.metrology.snapshot_models import SourceLanguage


class ProducerConfigError(Exception):
    """A config file the producer left cannot be read (D4, D5): the producer's fault."""

    def __init__(self, path: str, error: str) -> None:
        super().__init__(f"{path}: {error}")
        self.path = path
        self.error = error


@dataclass(frozen=True)
class RestorationResult:
    """What tool-config restoration changed; counted and reported, never graded (D4)."""

    config_edits: tuple[str, ...]


@dataclass(frozen=True)
class InjectionResult:
    """What hidden-test injection wrote (D3).

    ``id_map`` pairs each hidden node id with the id it has in the injected module;
    ``clashes`` are stable text lines the report can count.
    """

    id_map: tuple[tuple[str, str], ...]
    files_written: tuple[str, ...]
    clashes: tuple[str, ...]


@runtime_checkable
class GradingAdapter(Protocol):
    language: SourceLanguage

    def restore_tool_config(self, tree: Path, start: TreeReader) -> RestorationResult:
        """Put the start commit's tool config back by section (D4); report what differed."""
        ...

    def deps_changed(self, tree: Path, start: TreeReader) -> bool:
        """Whether the producer changed dependencies or the lock (D5)."""
        ...

    def test_side_edits(self, tree: Path, start: TreeReader) -> tuple[str, ...]:
        """Existing test-side files the producer modified or deleted, sorted (D6)."""
        ...

    def restore_test_files(self, tree: Path, start: TreeReader, paths: Sequence[str]) -> None:
        """Write the start content of *paths* back, recreating deleted files (D6)."""
        ...

    def inject_hidden(
        self, tree: Path, case: BenchmarkCase, start: TreeReader, reference: TreeReader
    ) -> InjectionResult:
        """Write the hidden tests beside the producer's files, removing nothing (D3).

        *start* is read for the conftest import difference.
        """
        ...

    def count_suppressions(self, diff: bytes) -> SuppressionCounts:
        """Suppressions added by a diff, by file side (D6)."""
        ...
