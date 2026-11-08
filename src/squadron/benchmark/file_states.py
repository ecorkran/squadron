"""The three file states of one parent sandbox (slice 422 D4).

Every fairness check runs in the parent sandbox, in the environment replays use. The
harness moves the tree between states by rewriting whole files the diff touched, with
content read from the user's checkout through git. The environment is untouched, so its
``EnvironmentIdentity`` does not change.

Content is read through ``ProcessRunner``, which decodes text: a file that is not valid
UTF-8 is refused (it would be silently altered) and CRLF line endings become LF. Both are
acceptable for the Python source and test files fix cases touch.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from squadron.benchmark.adapter import SandboxContext
from squadron.benchmark.diff_classify import DiffClassification
from squadron.benchmark.fairness import FixCaseAdapter, HarnessFailure
from squadron.core.process_runner import ProcessNotFoundError, ProcessRunner, ProcessTimedOutError

_logger = logging.getLogger(__name__)
_REPLACEMENT_CHARACTER = "�"


class FileState(StrEnum):
    PARENT = "parent"
    REFERENCE = "reference"
    PARENT_PLUS_OVERLAY = "parent_plus_overlay"


def _read_at(
    runner: ProcessRunner, repo_root: Path, sha: str, path: str, timeout_seconds: float
) -> bytes:
    argv = ["git", "show", f"{sha}:{path}"]
    try:
        result = runner.run(argv, cwd=str(repo_root), timeout=timeout_seconds)
    except (ProcessTimedOutError, ProcessNotFoundError) as exc:
        _logger.exception("git show %s:%s failed", sha, path)
        raise HarnessFailure(f"git show {sha[:12]}:{path} failed: {exc}") from exc
    if result.returncode != 0:
        detail = f"git show {sha[:12]}:{path} exited {result.returncode}: {result.stderr.strip()}"
        _logger.error("fix-case harness failure: %s", detail)
        raise HarnessFailure(detail)
    if _REPLACEMENT_CHARACTER in result.stdout:
        detail = f"{path} at {sha[:12]} is not valid UTF-8 text, so it cannot be restored exactly"
        _logger.error("fix-case harness failure: %s", detail)
        raise HarnessFailure(detail)
    return result.stdout.encode("utf-8")


@dataclass(frozen=True)
class FileStates:
    """Whole-file content for each path the diff touched, per state.

    ``None`` means absent: at the reference for a deleted file, at the parent for a file the
    diff added. ``overlay_files`` is the test-side subset of ``reference_files``.
    """

    reference_files: Mapping[str, bytes | None]
    overlay_files: Mapping[str, bytes | None]
    parent_files: Mapping[str, bytes | None]

    @classmethod
    def build(
        cls,
        runner: ProcessRunner,
        repo_root: Path,
        classification: DiffClassification,
        parent_sha: str,
        fix_sha: str,
        timeout_seconds: float,
    ) -> FileStates:
        """Read every touched file at both commits from the user's checkout."""
        reference: dict[str, bytes | None] = {}
        parent: dict[str, bytes | None] = {}
        for path in (*classification.added, *classification.changed):
            reference[path] = _read_at(runner, repo_root, fix_sha, path, timeout_seconds)
        for path in (*classification.changed, *classification.deleted):
            parent[path] = _read_at(runner, repo_root, parent_sha, path, timeout_seconds)
        for path in classification.added:
            parent[path] = None
        for path in classification.deleted:
            reference[path] = None
        overlay = {path: reference[path] for path in classification.test_side}
        return cls(reference_files=reference, overlay_files=overlay, parent_files=parent)

    def files_for(self, state: FileState) -> dict[str, bytes | None]:
        """Every touched path with the content it has in ``state``."""
        if state is FileState.REFERENCE:
            return dict(self.reference_files)
        if state is FileState.PARENT:
            return dict(self.parent_files)
        return {
            path: self.overlay_files[path] if path in self.overlay_files else content
            for path, content in self.parent_files.items()
        }

    def switch_to(self, ctx: SandboxContext, adapter: FixCaseAdapter, state: FileState) -> None:
        """Move the sandbox to ``state`` by rewriting every touched file; any state to any state."""
        adapter.overlay(ctx, self.files_for(state))
