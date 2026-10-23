"""The default tool runner, tool resolution and version probe (D8).

No adapter-specific logic lives here. Tools are invoked as argv lists, never through
a shell, with a timeout on every call.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from squadron.metrology.snapshot.contract import ToolResult, ToolRunner

_logger = logging.getLogger(__name__)

#: Exit codes reported for a call that produced none. A real exit code is never negative.
TIMED_OUT_EXIT_CODE = -1
LAUNCH_FAILED_EXIT_CODE = -2

#: Per-call budget for the characters of file arguments, well under the OS argv limit.
ARGV_FILE_CHARS_BUDGET = 60_000

#: How much of a tool's stderr goes into a log line or an absence detail.
STDERR_HEAD_CHARS = 300

_VERSION = re.compile(r"\d+(?:\.\d+)+")


class SubprocessToolRunner:
    """Runs a tool as a subprocess: argv list, no shell, bounded by ``timeout_s``."""

    def run(self, argv: Sequence[str], *, cwd: Path, timeout_s: int) -> ToolResult:
        try:
            done = subprocess.run(
                list(argv),
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ToolResult(
                exit_code=TIMED_OUT_EXIT_CODE,
                stdout=_decode(exc.stdout),
                stderr=_decode(exc.stderr),
                timed_out=True,
            )
        except OSError as exc:
            # The binary vanished or isn't executable between resolution and launch;
            # reported as a failed call so the adapter records tool_failed.
            return ToolResult(
                exit_code=LAUNCH_FAILED_EXIT_CODE, stdout="", stderr=str(exc), timed_out=False
            )
        return ToolResult(
            exit_code=done.returncode, stdout=done.stdout, stderr=done.stderr, timed_out=False
        )


def _decode(captured: str | bytes | None) -> str:
    if captured is None:
        return ""
    if isinstance(captured, bytes):
        return captured.decode("utf-8", errors="replace")
    return captured


def stderr_head(stderr: str) -> str:
    """The start of *stderr*, for log lines and absence details."""
    stripped = stderr.strip()
    return stripped[:STDERR_HEAD_CHARS]


def resolve_tool(
    repo_root: Path, name: str, project_dirs: Sequence[str], *, use_path: bool
) -> Path | None:
    """Find tool *name*: the measured project's own directories first, then ``PATH``.

    ``use_path`` is False for a tool that must come from the project (ESLint), so a
    global binary can never stand in for the project's own plugins and version.
    Returns None when the tool isn't found.
    """
    for directory in project_dirs:
        candidate = repo_root / directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    if use_path:
        found = shutil.which(name)
        if found is not None:
            return Path(found)
    return None


@dataclass(frozen=True)
class VersionProbe:
    """A version, or why it couldn't be read. Exactly one is set."""

    version: str | None
    failure: str | None


def probe_version(runner: ToolRunner, tool_path: Path, cwd: Path, timeout_s: int) -> VersionProbe:
    """Run ``<tool> --version`` and parse a version from stdout.

    A hang, a non-zero exit or output with no version is a failure with detail
    ``version probe failed: ...``, logged at WARNING with the tool, command and
    stderr head. A count without a version has no identity, so the tool isn't run.
    """
    argv = [str(tool_path), "--version"]
    result = runner.run(argv, cwd=cwd, timeout_s=timeout_s)
    if result.timed_out:
        reason = f"timed out after {timeout_s}s"
    elif result.exit_code != 0:
        reason = f"exit {result.exit_code}"
    else:
        match = _VERSION.search(result.stdout)
        if match is not None:
            return VersionProbe(version=match.group(0), failure=None)
        reason = "no version in output"
    detail = f"version probe failed: {reason}"
    _logger.warning(
        "%s: `%s` (%s); stderr: %s", detail, " ".join(argv), tool_path.name, stderr_head(result.stderr)
    )
    return VersionProbe(version=None, failure=detail)


def chunk_files(files: Sequence[str], budget: int = ARGV_FILE_CHARS_BUDGET) -> Iterator[list[str]]:
    """Split *files* into chunks whose combined length stays within *budget*.

    Every file lands in exactly one chunk, in order. A single path longer than the
    budget gets a chunk of its own rather than being dropped.
    """
    chunk: list[str] = []
    used = 0
    for file in files:
        cost = len(file) + 1
        if chunk and used + cost > budget:
            yield chunk
            chunk, used = [], 0
        chunk.append(file)
        used += cost
    if chunk:
        yield chunk
