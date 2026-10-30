"""Export a commit to a temp tree so it can be measured without touching the checkout (403 D5).

``git archive`` writes the commit's tracked files to a tar, which is extracted into a
temporary directory with the ``data`` filter (no absolute paths, no links out of the
tree). The live checkout is never read or written, so nothing about its state matters.
The temp directory is removed on every path, including an error inside the ``with`` block.
"""

from __future__ import annotations

import logging
import os
import tarfile
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from squadron.metrology.errors import SnapshotExportError
from squadron.metrology.snapshot.files import exclude_pathspecs
from squadron.review.git_utils import GIT_COMMAND_TIMEOUT_SECONDS, run_git

_logger = logging.getLogger(__name__)

_ARCHIVE_NAME = "export.tar"
_TREE_NAME = "tree"
_NODE_MODULES = "node_modules"


@dataclass(frozen=True)
class ExportedTree:
    """An exported commit: the tree's root and its regular files, sorted, repo-relative."""

    root: Path
    files: list[str]


def _failure(message: str) -> SnapshotExportError:
    """Log *message* at ERROR and return the error to raise."""
    _logger.error(message)
    return SnapshotExportError(message)


def resolve_commit(repo_root: Path, rev: str) -> str:
    """The commit sha *rev* names, or ``SnapshotExportError`` naming the revision."""
    call = f"git rev-parse --verify {rev}^{{commit}}"
    completed = run_git(["rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"], cwd=str(repo_root))
    if completed is None:
        raise _failure(
            f"`{call}` returned no result in {repo_root} (git missing or timed out after "
            f"{GIT_COMMAND_TIMEOUT_SECONDS}s). Check that git works there."
        )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise _failure(
            f"Unknown revision {rev!r} in {repo_root}. Pass a commit, branch or tag that exists."
        )
    return completed.stdout.strip()


def _archive(repo_root: Path, sha: str, exclusions: Iterable[str], tar_path: Path) -> None:
    args = [
        "archive",
        "--format=tar",
        "-o",
        str(tar_path),
        sha,
        "--",
        ".",
        *exclude_pathspecs(exclusions),
    ]
    completed = run_git(args, cwd=str(repo_root))
    if completed is None:
        raise _failure(
            f"`git archive {sha}` returned no result in {repo_root}: git is missing or it "
            f"did not finish within the {GIT_COMMAND_TIMEOUT_SECONDS}s timeout."
        )
    if completed.returncode != 0:
        raise _failure(
            f"`git archive {sha}` failed in {repo_root}: {completed.stderr.strip()}. "
            "Check the exclusion patterns in metrology.snapshot_exclude."
        )


def _extract(tar_path: Path, tree: Path) -> list[str]:
    """Extract with the ``data`` filter; return the regular files' names, sorted."""
    try:
        with tarfile.open(tar_path) as archive:
            files = sorted(member.name for member in archive.getmembers() if member.isfile())
            archive.extractall(tree, filter="data")
    except tarfile.FilterError as exc:
        raise _failure(
            f"The archive member {exc.tarinfo.name!r} was refused ({exc}); "
            "it would land outside the export tree."
        ) from exc
    except (OSError, tarfile.TarError) as exc:
        raise _failure(f"Could not extract {tar_path} into {tree}: {exc}") from exc
    return files


def _link_node_modules(environment_root: Path, tree: Path) -> None:
    live = environment_root / _NODE_MODULES
    if not live.exists():
        return
    link = tree / _NODE_MODULES
    try:
        os.symlink(live, link)
    except OSError as exc:
        raise _failure(f"Could not link {link} to {live}: {exc}") from exc


@contextmanager
def export_commit(
    repo_root: Path, sha: str, exclusions: Iterable[str], environment_root: Path
) -> Iterator[ExportedTree]:
    """Export commit *sha* to a temp tree; the directory is removed when the block exits.

    *exclusions* are the effective snapshot exclusions. When the live checkout has a
    ``node_modules``, the tree gets a link to it so JavaScript tools resolve.
    """
    with tempfile.TemporaryDirectory(prefix="sq-export-") as tmp:
        base = Path(tmp)
        tar_path = base / _ARCHIVE_NAME
        _archive(repo_root, sha, exclusions, tar_path)
        tree = base / _TREE_NAME
        files = _extract(tar_path, tree)
        _link_node_modules(environment_root, tree)
        yield ExportedTree(root=tree, files=files)
