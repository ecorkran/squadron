"""Rebuild a ``FixCandidate`` from a stored fix case, for re-qualification (slice 424 D5).

A case keeps its closing commit (``reference_sha``), that commit's parent (``start_sha``) and
the issue reference as written. The committer date is not stored on the case, so it is read
back from the project's repository.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from squadron.benchmark.build_errors import halt
from squadron.benchmark.fix_discovery import FixCandidate
from squadron.core.process_runner import ProcessNotFoundError, ProcessRunner, ProcessTimedOutError
from squadron.metrology.benchmark_models import BenchmarkCase

_logger = logging.getLogger(__name__)

#: ``#123`` or ``owner/repo#123``, as 422 records ``source_ref``.
_ISSUE_REFERENCE = re.compile(r"^\s*(?:([\w.-]+/[\w.-]+))?#(\d+)\s*$")


def parse_issue_ref(source_ref: str) -> tuple[str | None, int] | None:
    """``(repository, number)`` of an issue reference as written, ``None`` when unparseable."""
    match = _ISSUE_REFERENCE.match(source_ref)
    return None if match is None else (match.group(1), int(match.group(2)))


def issue_number(case: BenchmarkCase) -> int | None:
    """The issue number the case came from, ``None`` when its provenance holds no usable ref."""
    parsed = parse_issue_ref(case.provenance.source_ref)
    return None if parsed is None else parsed[1]


def candidate_from_case(
    case: BenchmarkCase, runner: ProcessRunner, repo_root: Path, timeout_seconds: float
) -> FixCandidate:
    """The candidate *case* was built from; raises ``BuildHalted`` (after logging) when the
    reference or the commit date cannot be read."""
    parsed = parse_issue_ref(case.provenance.source_ref)
    if parsed is None:
        raise halt(f"case {case.case_id} has no readable issue ref: {case.provenance.source_ref!r}")
    argv = ["git", "show", "-s", "--format=%cI", case.reference_sha]
    try:
        result = runner.run(argv, cwd=str(repo_root), timeout=timeout_seconds)
    except ProcessTimedOutError as exc:
        _logger.exception("%s timed out", " ".join(argv))
        raise halt(f"{' '.join(argv)} exceeded {timeout_seconds}s in {repo_root}") from exc
    except ProcessNotFoundError as exc:
        _logger.exception("git is not available")
        raise halt("git is not on PATH") from exc
    if result.returncode != 0:
        raise halt(f"{' '.join(argv)} exited {result.returncode}: {result.stderr.strip()}")
    repository, number = parsed
    return FixCandidate(
        sha=case.reference_sha,
        parent_sha=case.start_sha,
        committer_date=datetime.fromisoformat(result.stdout.strip()),
        issue_ref=case.provenance.source_ref,
        repository=repository,
        number=number,
    )
