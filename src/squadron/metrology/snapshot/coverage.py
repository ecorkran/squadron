"""Coverage from a Cobertura XML report (slice 401, D4, D5, D6).

The snapshot installs nothing and runs no tests: it reads a report the project already
produces. This module owns the config key, the report-path parser, the freshness check
and the Cobertura reader; each adapter builds its own measurements from one reading.
"""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

from squadron.metrology.errors import SnapshotPreflightError

KEY_COVERAGE_REPORT = "metrology.coverage_report"

_PARENT = ".."


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
