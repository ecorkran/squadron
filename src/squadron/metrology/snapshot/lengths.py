"""Shared length counting for the language adapters (D1, D6).

File and function length are the number of non-blank physical lines, matching the
"excluding whitespace" wording of the project's size rules. Both adapters build
their length measurements here, so the definitions can't drift apart.
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from squadron.metrology.snapshot_models import (
    Distribution,
    FunctionOverLimit,
    LengthLimits,
    Measurement,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)

_logger = logging.getLogger(__name__)

#: Physical line breaks as Python's tokenizer and tree-sitter count them. Not
#: ``str.splitlines``, which also splits on form feeds and Unicode separators.
_LINE_BREAK = re.compile(r"\r\n|\r|\n")

_P50 = 50
_P90 = 90


@dataclass(frozen=True)
class FunctionLength:
    """One measured function."""

    path: str
    qualified_name: str
    start_line: int
    length: int


def physical_lines(text: str) -> list[str]:
    """Split *text* into physical lines. A trailing newline adds no empty line."""
    lines = _LINE_BREAK.split(text)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def count_non_blank(text: str) -> int:
    """Non-blank physical lines in *text*."""
    return sum(1 for line in physical_lines(text) if line.strip())


def count_non_blank_span(lines: Sequence[str], start: int, end: int) -> int:
    """Non-blank lines in the 1-based inclusive span ``start..end`` of *lines*."""
    return sum(1 for line in lines[start - 1 : end] if line.strip())


def _nearest_rank(ordered: Sequence[int], percentile: int) -> int:
    rank = math.ceil(percentile * len(ordered) / 100)
    return ordered[max(rank, 1) - 1]


def distribution(values: Sequence[int]) -> Distribution | None:
    """Count, total, min, p50, p90 and max of *values*; None when there are none.

    Percentiles use the nearest-rank method: the value at rank ``ceil(p * n / 100)``
    of the ascending sort. It always returns a value that was observed, which keeps
    the record integral and the result independent of interpolation conventions.
    An empty input has no minimum, so it yields None, never zeros.
    """
    if not values:
        return None
    ordered = sorted(values)
    return Distribution(
        count=len(ordered),
        total=sum(ordered),
        min=ordered[0],
        p50=_nearest_rank(ordered, _P50),
        p90=_nearest_rank(ordered, _P90),
        max=ordered[-1],
    )


def file_length_measurement(
    language: SourceLanguage,
    tool: ToolIdentity,
    per_file: Mapping[str, int],
    limit: int | None,
) -> Measurement:
    """File length for every measured file, its distribution, and the declared limit."""
    return Measurement(
        metric=SnapshotMetric.FILE_LENGTH,
        language=language,
        tool=tool,
        per_file=dict(per_file),
        distribution=distribution(list(per_file.values())),
        limit=limit,
    )


def files_over_limit(measurement: Measurement) -> dict[str, int]:
    """Files longer than the measurement's limit; empty when no limit was declared.

    Derived from ``per_file`` rather than stored, so it can't disagree with it.
    """
    if measurement.limit is None:
        return {}
    return {path: n for path, n in measurement.per_file.items() if n > measurement.limit}


def function_length_measurement(
    language: SourceLanguage,
    tool: ToolIdentity,
    functions: Sequence[FunctionLength],
    limit: int | None,
    unparsed_files: Sequence[str],
) -> Measurement:
    """Function length: a distribution over functions, plus rows only over the limit."""
    over_limit = (
        [
            FunctionOverLimit(
                path=fn.path,
                qualified_name=fn.qualified_name,
                start_line=fn.start_line,
                length=fn.length,
            )
            for fn in functions
            if fn.length > limit
        ]
        if limit is not None
        else []
    )
    return Measurement(
        metric=SnapshotMetric.FUNCTION_LENGTH,
        language=language,
        tool=tool,
        distribution=distribution([fn.length for fn in functions]),
        limit=limit,
        over_limit=over_limit,
        unparsed_files=list(unparsed_files),
    )


#: Parses one file's text into its functions. May raise any of the adapter's
#: declared parse errors, which mark the file unparsed instead of failing the snapshot.
FunctionExtractor = Callable[[str, str], list[FunctionLength]]


def _measure_source(
    repo_root: Path,
    path: str,
    extract: FunctionExtractor,
    parse_errors: tuple[type[Exception], ...],
    per_file: dict[str, int],
    functions: list[FunctionLength],
    unparsed: list[str],
) -> None:
    try:
        raw = (repo_root / path).read_bytes()
    except OSError as exc:
        _logger.warning("Can't read %s for length (%s); not measured", path, exc)
        unparsed.append(path)
        return
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        # Still counts for file length (with replacement characters); it just
        # contributes no functions.
        _logger.warning("%s isn't valid UTF-8 (%s); no functions measured", path, exc)
        per_file[path] = count_non_blank(raw.decode("utf-8", errors="replace"))
        unparsed.append(path)
        return
    per_file[path] = count_non_blank(text)
    try:
        functions.extend(extract(path, text))
    except parse_errors as exc:
        # A file the parser can't handle keeps its file length and contributes no
        # functions; it's listed so the gap is visible.
        _logger.warning("Can't parse %s (%s: %s); no functions measured", path, type(exc).__name__, exc)
        unparsed.append(path)


def measure_length_metrics(
    repo_root: Path,
    files: Sequence[str],
    language: SourceLanguage,
    tool: ToolIdentity,
    limits: LengthLimits,
    extract: FunctionExtractor,
    parse_errors: tuple[type[Exception], ...],
) -> list[Measurement]:
    """File length and function length for *files*, shared by every adapter.

    The adapter supplies only ``extract`` (text to functions) and the parse errors it
    can raise. Reading, decoding, counting, warnings and the measurement shape are
    defined once here, so the two languages can't drift apart.
    """
    per_file: dict[str, int] = {}
    functions: list[FunctionLength] = []
    unparsed: list[str] = []
    for path in files:
        _measure_source(repo_root, path, extract, parse_errors, per_file, functions, unparsed)
    return [
        file_length_measurement(language, tool, per_file, limits.max_file_lines),
        function_length_measurement(language, tool, functions, limits.max_function_lines, unparsed),
    ]
