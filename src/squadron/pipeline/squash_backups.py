"""List and drop the backup tags ``sq squash`` leaves at each old HEAD (slice 948 D4)."""

from __future__ import annotations

import logging
from pathlib import Path

from squadron.pipeline.squash import BACKUP_TAG_PREFIX
from squadron.pipeline.squash_rewrite import git_stdout

_logger = logging.getLogger(__name__)


def backup_tags(cwd: Path) -> list[str]:
    """Every squash backup tag in the repository, sorted by name.

    Raises:
        GitEnvironmentError: git could not answer.
    """
    return git_stdout(["tag", "-l", f"{BACKUP_TAG_PREFIX}*"], cwd).split()


def drop_backup_tags(cwd: Path) -> list[str]:
    """Delete every squash backup tag; returns the names deleted.

    Raises:
        GitEnvironmentError: git could not delete them.
    """
    tags = backup_tags(cwd)
    if tags:
        git_stdout(["tag", "-d", *tags], cwd)
        _logger.info("squash: dropped %d backup tag(s)", len(tags))
    return tags
