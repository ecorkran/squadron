"""The adapter contract for code snapshots (slice 400).

Everything the orchestrator needs to know about a language lives behind
``LanguageAdapter``; ``take_snapshot`` imports this module and never a concrete
adapter. The registry type is defined here but holds no adapters: ``registry.py``
builds the default one, and the caller passes it in.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from squadron.metrology.snapshot_models import (
    LengthLimits,
    Measurement,
    SnapshotMetric,
    SourceLanguage,
)

#: File extensions (lowercase, with the dot) that identify each language.
LANGUAGE_EXTENSIONS: Mapping[SourceLanguage, frozenset[str]] = {
    SourceLanguage.PYTHON: frozenset({".py"}),
    SourceLanguage.TYPESCRIPT: frozenset({".ts", ".tsx", ".mts", ".cts"}),
    SourceLanguage.JAVASCRIPT: frozenset({".js", ".mjs", ".cjs"}),
    SourceLanguage.SHELL: frozenset({".sh"}),
}


@dataclass(frozen=True)
class ToolResult:
    """The outcome of one tool subprocess call."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


class ToolRunner(Protocol):
    """Runs an external tool. ``timeout_s`` is required: no caller may omit the bound."""

    def run(self, argv: Sequence[str], *, cwd: Path, timeout_s: int) -> ToolResult: ...


@dataclass(frozen=True)
class AdapterContext:
    """What an adapter needs to measure one language."""

    repo_root: Path
    limits: LengthLimits
    runner: ToolRunner
    tool_timeout_s: int


class LanguageAdapter(Protocol):
    """Measures one language.

    The contract:
    - ``measure`` returns exactly one ``Measurement`` per member of ``metrics``.
    - ``files`` are repo-relative POSIX paths.
    - An adapter never writes inside ``repo_root``.
    """

    language: SourceLanguage
    metrics: frozenset[SnapshotMetric]
    convention_exclusions: tuple[str, ...]

    def measure(self, ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]: ...


#: Language to adapter. Holds no adapters itself.
AdapterRegistry = Mapping[SourceLanguage, LanguageAdapter]
