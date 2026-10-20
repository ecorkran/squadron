import json
import logging
from pathlib import Path

import pytest

from squadron.probe.graph import (
    COMMIT_KEY,
    GRAPH_DIR_NAME,
    GRAPH_FILE_NAME,
    META_FILE_NAME,
    probe_graph,
    project_root,
)
from tests.conftest import run_test_git

FABRICATED_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name)
    run_test_git(repo, "add", name)
    run_test_git(repo, "commit", "-q", "-m", name)
    return run_test_git(repo, "rev-parse", "HEAD").strip()


def _write_graph(root: Path, meta: str | None) -> None:
    """Write a graph file, plus ``meta.json`` containing ``meta`` verbatim unless None."""
    graph_dir = root / GRAPH_DIR_NAME
    graph_dir.mkdir(exist_ok=True)
    (graph_dir / GRAPH_FILE_NAME).write_text("{}")
    if meta is not None:
        (graph_dir / META_FILE_NAME).write_text(meta)


def _meta_for(commit: str) -> str:
    return json.dumps({COMMIT_KEY: commit})


def _warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.levelno == logging.WARNING]


def test_graph_at_head_is_zero_commits_behind(temp_git_repo: Path) -> None:
    head = _commit(temp_git_repo, "a")
    _write_graph(temp_git_repo, _meta_for(head))

    report = probe_graph(temp_git_repo)

    assert report["present"] is True
    assert report["path"] == str(temp_git_repo / GRAPH_DIR_NAME / GRAPH_FILE_NAME)
    assert report["commit"] == head
    assert report["commits_behind"] == 0


def test_graph_two_commits_behind(temp_git_repo: Path) -> None:
    built_at = _commit(temp_git_repo, "a")
    _write_graph(temp_git_repo, _meta_for(built_at))
    _commit(temp_git_repo, "b")
    _commit(temp_git_repo, "c")

    assert probe_graph(temp_git_repo)["commits_behind"] == 2


def test_commit_that_is_not_an_ancestor_is_unknown(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write_graph(temp_git_repo, _meta_for(FABRICATED_COMMIT))

    report = probe_graph(temp_git_repo)

    assert report["commit"] == FABRICATED_COMMIT
    assert report["commits_behind"] is None
    assert _warnings(caplog)


def test_non_repository_with_graph_has_unknown_commits_behind(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write_graph(tmp_path, _meta_for(FABRICATED_COMMIT))

    root = project_root(tmp_path)
    report = probe_graph(root)

    assert root == tmp_path
    assert report["present"] is True
    assert report["commits_behind"] is None
    assert _warnings(caplog)


def test_no_graph_reports_absent(temp_git_repo: Path) -> None:
    report = probe_graph(temp_git_repo)

    assert report == {"present": False, "path": None, "commit": None, "commits_behind": None}


@pytest.mark.parametrize(
    "meta",
    [None, json.dumps({"other": "value"}), "not json at all"],
    ids=["meta-absent", "no-commit-hash", "not-json"],
)
def test_unusable_meta_leaves_commit_unknown(
    temp_git_repo: Path, meta: str | None, caplog: pytest.LogCaptureFixture
) -> None:
    _write_graph(temp_git_repo, meta)

    report = probe_graph(temp_git_repo)

    assert report["present"] is True
    assert report["commit"] is None
    assert report["commits_behind"] is None
    assert _warnings(caplog)


def test_project_root_from_subdirectory_is_repository_root(temp_git_repo: Path) -> None:
    subdirectory = temp_git_repo / "nested" / "deeper"
    subdirectory.mkdir(parents=True)

    assert project_root(subdirectory).resolve() == temp_git_repo.resolve()
