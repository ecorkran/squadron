"""The cyclomatic complexity measurement, shared by the language adapters (slice 401, D1, D2).

Complexity is a field on each ``MeasuredFunction``, set by the same walk that measures
function length, so both metrics cover exactly the same functions. This module only
shapes the ``Measurement``; counting lives in the language modules, and ``lengths``
computes the distribution (this module can't import it: ``lengths`` imports this one).
"""

from __future__ import annotations

from collections.abc import Sequence

from squadron.metrology.snapshot_models import (
    Distribution,
    Measurement,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)


def complexity_measurement(
    language: SourceLanguage,
    tool: ToolIdentity,
    complexities: Distribution | None,
    unparsed_files: Sequence[str],
) -> Measurement:
    """The distribution of complexity over functions. No per-file counts, no limit (D2)."""
    return Measurement(
        metric=SnapshotMetric.CYCLOMATIC_COMPLEXITY,
        language=language,
        tool=tool,
        distribution=complexities,
        unparsed_files=list(unparsed_files),
    )
