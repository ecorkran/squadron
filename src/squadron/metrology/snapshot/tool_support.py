"""Helpers shared by the tool-backed adapters (ruff, pyright, ESLint).

An unmeasurable metric is data, not an exception: these build the absent
``Measurement`` and log the failure at WARNING with the tool, command and stderr head,
so every absence is observable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from squadron.metrology.snapshot.contract import AdapterContext
from squadron.metrology.snapshot.runner import chunk_files, probe_version, stderr_head
from squadron.metrology.snapshot_models import (
    AbsenceReason,
    Measurement,
    SnapshotMetric,
    SourceLanguage,
)

_logger = logging.getLogger(__name__)


def absent(
    language: SourceLanguage, metric: SnapshotMetric, reason: AbsenceReason, detail: str
) -> Measurement:
    """An absent measurement with its reason and detail."""
    return Measurement(metric=metric, language=language, absent=reason, absent_detail=detail)


def tool_missing(
    language: SourceLanguage, metric: SnapshotMetric, tool: str, looked_in: str | None = None
) -> Measurement:
    """The tool isn't installed where it's allowed to come from."""
    detail = f"{tool} not found" if looked_in is None else f"{tool} not found in {looked_in}"
    _logger.warning("%s: %s", metric.value, detail)
    return absent(language, metric, AbsenceReason.TOOL_MISSING, detail)


def tool_failed(
    language: SourceLanguage,
    metric: SnapshotMetric,
    detail: str,
    *,
    command: str,
    stderr: str = "",
) -> Measurement:
    """The tool ran (or was meant to) and gave no usable answer. Logged at WARNING."""
    _logger.warning(
        "%s: %s (command: %s; stderr: %s)", metric.value, detail, command, stderr_head(stderr)
    )
    return absent(language, metric, AbsenceReason.TOOL_FAILED, detail)


def repo_relative(filename: str, repo_root: Path) -> str | None:
    """A tool-reported path as a repo-relative POSIX path; None when outside the repo."""
    path = Path(filename)
    for root in (repo_root, repo_root.resolve()):
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            continue
    return None


def probe_or_failure(
    ctx: AdapterContext, language: SourceLanguage, metric: SnapshotMetric, tool_path: Path
) -> str | Measurement:
    """The tool's version, or the ``tool_failed`` measurement to return when it can't be read."""
    probe = probe_version(ctx.runner, tool_path, ctx.repo_root, ctx.tool_timeout_s)
    if probe.version is not None:
        return probe.version
    return tool_failed(
        language,
        metric,
        probe.failure or "version probe failed",
        command=f"{tool_path} --version",
    )


def run_chunked(
    ctx: AdapterContext,
    *,
    language: SourceLanguage,
    metric: SnapshotMetric,
    tool_name: str,
    tool_path: Path,
    files: Sequence[str],
    build_argv: Callable[[list[str]], list[str]],
    ok_exits: frozenset[int],
    fold: Callable[[str], str | None],
) -> Measurement | None:
    """Run a tool over *files* in argv-sized chunks, folding each chunk's stdout.

    Returns None when every chunk ran, exited with a code in *ok_exits* and *fold*
    accepted its output. Otherwise returns the ``tool_failed`` measurement for the first
    failure (timeout, abnormal exit, or the detail *fold* returned), so a count is never
    partial. *fold* adds one chunk's output to the caller's accumulators.
    """
    for chunk in chunk_files(files):
        result = ctx.runner.run(build_argv(chunk), cwd=ctx.repo_root, timeout_s=ctx.tool_timeout_s)
        command = f"{tool_path} ({len(chunk)} files)"
        if result.timed_out:
            detail = f"{tool_name} timed out after {ctx.tool_timeout_s}s"
        elif result.exit_code not in ok_exits:
            detail = f"{tool_name} exited {result.exit_code}: {stderr_head(result.stderr)}"
        else:
            failure = fold(result.stdout)
            if failure is None:
                continue
            detail = failure
        return tool_failed(language, metric, detail, command=command, stderr=result.stderr)
    return None
