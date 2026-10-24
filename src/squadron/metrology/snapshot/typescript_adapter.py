"""TypeScript language adapter (slice 400).

Length comes from tree-sitter (``typescript_length``); lint comes from the project's own
ESLint (``typescript_lint``). Type errors aren't measured: the orchestrator records them
as ``metric_unsupported``, never this adapter.
"""

from __future__ import annotations

from collections.abc import Sequence

from squadron.metrology.snapshot.contract import AdapterContext
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
            SnapshotMetric.LINT_COUNT,
        }
    )
    convention_exclusions: tuple[str, ...] = ("**/*.d.ts", "**/node_modules/**", "**/dist/**")

    def measure(self, ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]:
        return [*measure_typescript_lengths(ctx, files), measure_eslint_lint(ctx, list(files))]
