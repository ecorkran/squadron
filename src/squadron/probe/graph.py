"""Detect the understand-anything knowledge graph and how stale it is.

Read-only: runs only ``git rev-parse``, ``merge-base --is-ancestor`` and
``rev-list --count``, and never reads the graph's contents. Every value the probe
cannot determine is ``None`` with a WARNING naming the cause.
"""

import json
import logging
from pathlib import Path
from typing import cast

from squadron.probe.report import GraphReport
from squadron.review.git_utils import run_git

logger = logging.getLogger(__name__)

GRAPH_DIR_NAME = ".understand-anything"
GRAPH_FILE_NAME = "knowledge-graph.json"
META_FILE_NAME = "meta.json"
COMMIT_KEY = "gitCommitHash"


def project_root(cwd: Path) -> Path:
    """The git toplevel containing ``cwd``, else ``cwd`` itself."""
    result = run_git(["rev-parse", "--show-toplevel"], cwd=str(cwd))
    if result is None or result.returncode != 0:
        return cwd
    return Path(result.stdout.strip())


def probe_graph(root: Path) -> GraphReport:
    """Report the graph under ``root``: presence, path, build commit, staleness."""
    graph_file = root / GRAPH_DIR_NAME / GRAPH_FILE_NAME
    if not graph_file.is_file():
        return GraphReport(present=False, path=None, commit=None, commits_behind=None)
    commit = _graph_commit(graph_file.parent / META_FILE_NAME)
    return GraphReport(
        present=True,
        path=str(graph_file),
        commit=commit,
        commits_behind=None if commit is None else _commits_behind(root, commit),
    )


def _graph_commit(meta_file: Path) -> str | None:
    if not meta_file.is_file():
        logger.warning("graph commit unknown: %s is absent", meta_file)
        return None
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        # An unreadable or malformed meta file means the commit is unknown, not a probe failure.
        logger.warning("graph commit unknown: cannot read %s: %s", meta_file, error)
        return None
    commit = cast(dict[str, object], meta).get(COMMIT_KEY) if isinstance(meta, dict) else None
    if not isinstance(commit, str):
        logger.warning("graph commit unknown: %s has no string %s", meta_file, COMMIT_KEY)
        return None
    return commit


def _commits_behind(root: Path, commit: str) -> int | None:
    cwd = str(root)
    head = run_git(["rev-parse", "HEAD"], cwd=cwd)
    if head is None or head.returncode != 0:
        logger.warning("commits_behind unknown: HEAD cannot be resolved in %s", root)
        return None
    if head.stdout.strip() == commit:
        return 0
    ancestor = run_git(["merge-base", "--is-ancestor", commit, "HEAD"], cwd=cwd)
    if ancestor is None or ancestor.returncode != 0:
        logger.warning("commits_behind unknown: graph commit %s is not an ancestor of HEAD", commit)
        return None
    count = run_git(["rev-list", "--count", f"{commit}..HEAD"], cwd=cwd)
    if count is None or count.returncode != 0:
        logger.warning("commits_behind unknown: rev-list failed for %s..HEAD", commit)
        return None
    try:
        return int(count.stdout.strip())
    except ValueError:
        logger.warning("commits_behind unknown: unparseable count %r", count.stdout.strip())
        return None
