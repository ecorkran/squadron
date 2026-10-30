"""File-set resolution for a code snapshot (D4).

The measured set is ``git ls-files`` at a clean HEAD, which matches the commit
exactly: untracked ``node_modules/`` and ``.venv/`` never enter. Exclusions go to
git as ``:(exclude,glob)`` pathspecs, so git does all the matching and squadron
needs no glob library.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from squadron.metrology.errors import SnapshotIntegrityError
from squadron.metrology.snapshot.contract import LANGUAGE_EXTENSIONS, LanguageAdapter
from squadron.metrology.snapshot_models import SourceLanguage
from squadron.review.git_utils import run_git

_logger = logging.getLogger(__name__)

_EXCLUDE_MAGIC = ":(exclude,glob)"


def effective_exclusions(
    project_patterns: Iterable[str], adapters: Iterable[LanguageAdapter]
) -> list[str]:
    """The sorted, de-duplicated union of project patterns and adapter conventions."""
    patterns = set(project_patterns)
    for adapter in adapters:
        patterns.update(adapter.convention_exclusions)
    return sorted(patterns)


def exclude_pathspecs(exclusions: Iterable[str]) -> list[str]:
    """*exclusions* as the ``:(exclude,glob)`` pathspecs git matches itself."""
    return [f"{_EXCLUDE_MAGIC}{pattern}" for pattern in exclusions]


def resolve_files(repo_root: Path, exclusions: Iterable[str]) -> list[str]:
    """Tracked files at HEAD, less *exclusions*, as sorted repo-relative POSIX paths.

    Public so 404's scope report can list the post-exclusion set without a snapshot.
    A git call that returns nothing or fails is never an empty file set: it logs
    ERROR and raises ``SnapshotIntegrityError`` naming the call.
    """
    args = ["ls-files", "-z", "--", ".", *exclude_pathspecs(exclusions)]
    completed = run_git(args, cwd=str(repo_root))
    if completed is None or completed.returncode != 0:
        _logger.error("git ls-files failed in %s", repo_root)
        raise SnapshotIntegrityError(
            f"`git ls-files` failed in {repo_root}"
            + ("" if completed is None else f": {completed.stderr.strip()}")
            + ". Check the exclusion patterns in metrology.snapshot_exclude and that git works there."
        )
    return sorted(path for path in completed.stdout.split("\0") if path)


def group_by_language(files: Iterable[str]) -> dict[SourceLanguage, list[str]]:
    """Group *files* by extension. A file with no mapped extension isn't grouped."""
    by_extension = {
        extension: language
        for language, extensions in LANGUAGE_EXTENSIONS.items()
        for extension in extensions
    }
    grouped: dict[SourceLanguage, list[str]] = {}
    for file in files:
        language = by_extension.get(Path(file).suffix.lower())
        if language is not None:
            grouped.setdefault(language, []).append(file)
    return grouped
