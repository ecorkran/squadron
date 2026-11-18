"""``cases add``: validate every case file before anything is written (D1, D8)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from squadron.benchmark.recall.case_models import CaseFileError
from squadron.benchmark.recall.kinds import KindContext, UnknownKindError, get_kind, read_case_kind
from squadron.metrology.recall_case_models import RealBugCase

_logger = logging.getLogger(__name__)
CASE_FILE_GLOB = "*.yaml"


@dataclass(frozen=True)
class CaseFailure:
    path: Path
    reason: str


@dataclass(frozen=True)
class IntakeResult:
    cases: list[RealBugCase] = field(default_factory=list[RealBugCase])
    failures: list[CaseFailure] = field(default_factory=list[CaseFailure])


def expand_case_paths(paths: Sequence[Path]) -> list[Path]:
    """Files as given; a directory becomes its ``*.yaml`` files, sorted, not recursive."""
    expanded: list[Path] = []
    for path in paths:
        expanded.extend(sorted(path.glob(CASE_FILE_GLOB)) if path.is_dir() else [path])
    return expanded


def validate_case_files(paths: Sequence[Path], context: KindContext) -> IntakeResult:
    """Validate and derive every file; collect every failure rather than stopping at one."""
    cases: list[RealBugCase] = []
    failures: list[CaseFailure] = []
    for path in paths:
        try:
            kind = get_kind(read_case_kind(path))
            cases.append(kind.validate(path, context))
        except CaseFileError as exc:
            failures.append(CaseFailure(path, exc.reason))
        except UnknownKindError as exc:
            failures.append(CaseFailure(path, str(exc)))
    failures.extend(_duplicate_names(cases))
    for failure in failures:
        _logger.error("case file refused: %s: %s", failure.path, failure.reason)
    return IntakeResult(cases=[] if failures else cases, failures=failures)


def _duplicate_names(cases: list[RealBugCase]) -> list[CaseFailure]:
    seen: dict[str, int] = {}
    for case in cases:
        seen[case.name] = seen.get(case.name, 0) + 1
    duplicated = sorted(name for name, count in seen.items() if count > 1)
    return [CaseFailure(Path(name), "case name appears in more than one file") for name in duplicated]
