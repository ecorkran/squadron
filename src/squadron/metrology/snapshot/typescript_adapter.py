"""TypeScript language adapter (slice 400).

Length, complexity and duplication come from tree-sitter (``typescript_length``); lint
comes from the project's own ESLint (``typescript_lint``); coverage comes from the
project's Cobertura report (``coverage``). Type errors aren't measured: the orchestrator
records them as ``metric_unsupported``, never this adapter.
"""

from __future__ import annotations

from collections.abc import Sequence

from squadron.metrology.snapshot.contract import AdapterContext
from squadron.metrology.snapshot.coverage import read_coverage
from squadron.metrology.snapshot.coverage_measurements import coverage_measurements
from squadron.metrology.snapshot.typescript_duplication import measure_typescript_duplication
from squadron.metrology.snapshot.typescript_length import measure_typescript_lengths
from squadron.metrology.snapshot.typescript_lint import measure_eslint_lint
from squadron.metrology.snapshot_models import Measurement, SnapshotMetric, SourceLanguage


class TypeScriptAdapter:
    """Measures TypeScript: file length, function length and ESLint lint count."""

    language = SourceLanguage.TYPESCRIPT
    metrics = frozenset(
        {
            SnapshotMetric.FILE_LENGTH,
            SnapshotMetric.FUNCTION_LENGTH,
            SnapshotMetric.CYCLOMATIC_COMPLEXITY,
            SnapshotMetric.DUPLICATED_LINES,
            SnapshotMetric.LINT_COUNT,
            SnapshotMetric.COVERED_LINES,
            SnapshotMetric.COVERABLE_LINES,
        }
    )
    convention_exclusions: tuple[str, ...] = ("**/*.d.ts", "**/node_modules/**", "**/dist/**")

    def measure(self, ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]:
        return [
            *measure_typescript_lengths(ctx, files),
            measure_typescript_duplication(ctx, files),
            measure_eslint_lint(ctx, list(files)),
            *coverage_measurements(read_coverage(ctx.repo_root), self.language, list(files)),
        ]
