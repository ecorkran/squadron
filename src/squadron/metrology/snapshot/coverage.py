"""Coverage from a Cobertura XML report (slice 401, D4, D5, D6).

The snapshot installs nothing and runs no tests: it reads a report the project already
produces. This module owns the config key, the report-path parser, the freshness check
and the Cobertura reader; each adapter builds its own measurements from one reading.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from squadron.config.manager import get_config
from squadron.metrology.errors import SnapshotIntegrityError, SnapshotPreflightError
from squadron.metrology.snapshot.tool_support import repo_relative
from squadron.metrology.snapshot_models import AbsenceReason
from squadron.review.git_utils import run_git

_logger = logging.getLogger(__name__)

KEY_COVERAGE_REPORT = "metrology.coverage_report"

_PARENT = ".."
_COVERAGE_ROOT_TAG = "coverage"


def parse_report_path(value: object) -> str | None:
    """The configured report path as a repo-relative POSIX path; None when unset.

    Raises ``SnapshotPreflightError`` for an empty, non-string, absolute or ``..``
    value, naming the value and the fix.
    """
    if value is None:
        return None
    fix = f"Fix it with `sq config set {KEY_COVERAGE_REPORT} <repo-relative path> --project`."
    if not isinstance(value, str) or not value.strip():
        raise SnapshotPreflightError(
            f"{KEY_COVERAGE_REPORT} must be a non-empty repo-relative path, got {value!r}. {fix}"
        )
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or windows.root:
        raise SnapshotPreflightError(
            f"{KEY_COVERAGE_REPORT} must be relative to the repository root, got {value!r}. {fix}"
        )
    if _PARENT in posix.parts or _PARENT in windows.parts:
        raise SnapshotPreflightError(
            f"{KEY_COVERAGE_REPORT} must stay inside the repository (no '..'), got {value!r}. {fix}"
        )
    return posix.as_posix()


@dataclass(frozen=True)
class FileCoverage:
    """The line numbers a report lists for one file, and the subset with ``hits > 0``."""

    coverable: frozenset[int]
    covered: frozenset[int]


@dataclass(frozen=True)
class CoverageReading:
    """One parsed report: per repo-relative path, plus the producer's version."""

    report_path: str
    producer_version: str
    files: dict[str, FileCoverage]


@dataclass(frozen=True)
class CoverageFailure:
    """The report exists but can't be used; *detail* names the report and the problem."""

    report_path: str
    detail: str


def _class_lines(class_element: ElementTree.Element, report_path: str) -> dict[int, int] | str:
    """``{line number: hits}`` for a ``<class>``, or the problem as text.

    Only ``<line>`` elements directly under ``<class><lines>`` count. They sum to the
    root ``lines-valid`` in both writers; Istanbul also repeats a function's first line
    inside ``<method>``, which the root totals leave out.
    """
    lines: dict[int, int] = {}
    for element in class_element.findall("lines/line"):
        try:
            number = int(element.attrib["number"])
            hits = int(element.attrib["hits"])
        except KeyError as exc:
            return f"{report_path}: a <line> has no {exc.args[0]} attribute"
        except ValueError:
            return f"{report_path}: a <line> has a non-integer number or hits ({element.attrib})"
        lines[number] = max(hits, lines.get(number, 0))
    return lines


def _resolve_class_path(filename: str, sources: list[str], repo_root: Path) -> str | None:
    """The repo-relative path of a ``<class filename>``; None when outside the repo.

    The filename is relative to one of the report's ``<source>`` roots. The first
    resolution under the repo that exists on disk wins; otherwise the first under it.
    """
    inside = [
        relative
        for source in sources
        if (relative := repo_relative(str(Path(source) / filename), repo_root)) is not None
    ]
    if not inside:
        return None
    return next((relative for relative in inside if (repo_root / relative).exists()), inside[0])


def read_cobertura(report: Path, repo_path: str, repo_root: Path) -> CoverageReading | CoverageFailure:
    """Parse the Cobertura XML at *report* (named *repo_path* in messages).

    Every problem is returned as a ``CoverageFailure`` rather than raised: malformed
    XML, a root other than ``<coverage>``, no root ``version`` or ``<source>``, a
    non-integer ``number`` or ``hits``, or a file that can't be read.
    """
    try:
        root = ElementTree.parse(report).getroot()
    except OSError as exc:
        return CoverageFailure(repo_path, f"{repo_path} can't be read: {exc}")
    except ElementTree.ParseError as exc:
        return CoverageFailure(repo_path, f"{repo_path} is not well-formed XML: {exc}")
    if root.tag != _COVERAGE_ROOT_TAG:
        return CoverageFailure(
            repo_path, f"{repo_path} is not a Cobertura report (root is <{root.tag}>)"
        )
    version = root.attrib.get("version", "").strip()
    if not version:
        return CoverageFailure(repo_path, f"{repo_path} has no root version attribute")
    sources = [
        source.text.strip() for source in root.iter("source") if source.text and source.text.strip()
    ]
    if not sources:
        return CoverageFailure(repo_path, f"{repo_path} lists no <source> directory")
    collected: dict[str, dict[int, int]] = {}
    for class_element in root.iter("class"):
        filename = class_element.attrib.get("filename")
        if not filename:
            return CoverageFailure(repo_path, f"{repo_path} has a <class> with no filename")
        path = _resolve_class_path(filename, sources, repo_root)
        if path is None:
            continue
        lines = _class_lines(class_element, repo_path)
        if isinstance(lines, str):
            return CoverageFailure(repo_path, lines)
        merged = collected.setdefault(path, {})
        for number, hits in lines.items():
            merged[number] = max(hits, merged.get(number, 0))
    files = {
        path: FileCoverage(
            coverable=frozenset(lines),
            covered=frozenset(number for number, hits in lines.items() if hits > 0),
        )
        for path, lines in collected.items()
    }
    return CoverageReading(repo_path, version, files)


@dataclass(frozen=True)
class CoverageAbsence:
    """Coverage can't be reported for this commit, with the reason the record keeps."""

    reason: AbsenceReason
    detail: str


def _absence(reason: AbsenceReason, detail: str) -> CoverageAbsence:
    _logger.warning("coverage: %s (%s)", detail, reason.value)
    return CoverageAbsence(reason, detail)


def _failure(report_path: str, detail: str) -> CoverageFailure:
    _logger.warning("coverage: %s", detail)
    return CoverageFailure(report_path, detail)


def _tracked_files(repo_root: Path) -> list[str]:
    """Every tracked path, from ``git ls-files -z``; git failing is never an empty list."""
    call = "git ls-files -z"
    completed = run_git(["ls-files", "-z"], cwd=str(repo_root))
    if completed is None or completed.returncode != 0:
        _logger.error("%s failed in %s", call, repo_root)
        raise SnapshotIntegrityError(
            f"`{call}` failed in {repo_root}, so the coverage report's freshness can't be checked. "
            "Run it by hand to see why, then re-run `sq metrology snapshot`."
        )
    return [path for path in completed.stdout.split("\0") if path]


def _newest_tracked(repo_root: Path, tracked: list[str]) -> tuple[int, str] | None:
    """The newest mtime (ns) among *tracked* and its path; None for no tracked files.

    Raises ``OSError`` for a file that can't be stat'ed: it is never skipped.
    """
    newest: tuple[int, str] | None = None
    for path in tracked:
        mtime = (repo_root / path).lstat().st_mtime_ns
        if newest is None or mtime > newest[0]:
            newest = (mtime, path)
    return newest


def read_coverage(repo_root: Path) -> CoverageReading | CoverageAbsence | CoverageFailure:
    """The coverage report for the measured repo, if it is configured, present and fresh.

    A report is fresh when its mtime is at or after the newest tracked file's (D5).
    Absences and failures are data and log at WARNING; only a failing ``git ls-files``
    raises (``SnapshotIntegrityError``).
    """
    try:
        configured = parse_report_path(get_config(KEY_COVERAGE_REPORT, cwd=str(repo_root)))
    except SnapshotPreflightError as exc:
        return _failure(KEY_COVERAGE_REPORT, str(exc))
    if configured is None:
        return _absence(AbsenceReason.COVERAGE_NOT_CONFIGURED, f"{KEY_COVERAGE_REPORT} is not set")
    report = repo_root / configured
    if not report.exists():
        return _absence(AbsenceReason.REPORT_MISSING, f"{configured} does not exist")
    tracked = _tracked_files(repo_root)
    try:
        report_mtime = report.stat().st_mtime_ns
        newest = _newest_tracked(repo_root, tracked)
    except OSError as exc:
        return _failure(configured, f"can't stat {exc.filename} to check {configured} is fresh: {exc}")
    if newest is not None and report_mtime < newest[0]:
        return _absence(
            AbsenceReason.REPORT_STALE,
            f"{configured} is older than tracked file {newest[1]}; re-run the tests to refresh it",
        )
    result = read_cobertura(report, configured, repo_root)
    if isinstance(result, CoverageFailure):
        return _failure(result.report_path, result.detail)
    return result
