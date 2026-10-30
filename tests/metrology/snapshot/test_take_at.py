"""``take_snapshot_at``: measuring any commit from a temp export (slice 403, D5)."""

from __future__ import annotations

import shutil
import stat
from pathlib import Path

import pytest

from squadron.metrology.errors import SnapshotExportError, SnapshotPreflightError
from squadron.metrology.snapshot.contract import AdapterRegistry, ToolResult
from squadron.metrology.snapshot.registry import default_registry
from squadron.metrology.snapshot.runner import SubprocessToolRunner
from squadron.metrology.snapshot.take import take_snapshot, take_snapshot_at
from squadron.metrology.snapshot_models import AbsenceReason, SnapshotMetric, SourceLanguage
from squadron.metrology.store import MetrologyStore, snapshot_record_id
from tests.conftest import run_test_git
from tests.metrology.snapshot.builders import make_project_id, read_fixture
from tests.metrology.snapshot.conftest import FakeToolRunner, SnapshotRepoFactory

FILES = {"a.py": "x = 1\n\n\ndef f():\n    return x\n", "b.ts": "const y = 1;\n", "run.sh": "echo hi\n"}
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def only_git_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PATH holds git and nothing else, so every tool a test uses comes from the repo under test."""
    git = shutil.which("git")
    assert git is not None, "git is required for these tests"
    bin_dir = tmp_path / "git-only-bin"
    bin_dir.mkdir()
    (bin_dir / "git").symlink_to(git)
    monkeypatch.setenv("PATH", str(bin_dir))


def test_in_place_and_export_serialize_identically_apart_from_measured_at(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo(FILES)

    in_place = take_snapshot(repo, default_registry(), FakeToolRunner(), snapshot_store)
    exported = take_snapshot_at(repo, "HEAD", default_registry(), FakeToolRunner(), snapshot_store)

    assert exported.model_dump(mode="json", exclude={"measured_at"}) == in_place.model_dump(
        mode="json", exclude={"measured_at"}
    )


def test_a_dirty_live_checkout_is_measured_without_complaint(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo(FILES)
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")

    exported = take_snapshot_at(repo, "HEAD", default_registry(), FakeToolRunner(), snapshot_store)

    assert exported.commit_sha == run_test_git(repo, "rev-parse", "HEAD").strip()
    with pytest.raises(SnapshotPreflightError, match="not clean"):
        take_snapshot(repo, default_registry(), FakeToolRunner(), snapshot_store)


def test_an_older_commit_writes_a_record_keyed_on_that_sha(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo(FILES)
    older = run_test_git(repo, "rev-parse", "HEAD").strip()
    (repo / "c.py").write_text("z = 1\n", encoding="utf-8")
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "add c")

    snapshot = take_snapshot_at(repo, older, default_registry(), FakeToolRunner(), snapshot_store)

    project = make_project_id("github.com/manta/example-repo")
    assert snapshot.commit_sha == older
    assert snapshot.snapshot_id == snapshot_record_id(project, older)
    assert [s.commit_sha for s in snapshot_store.list_snapshots(project)] == [older]
    python = next(e for e in snapshot.languages if e.language is SourceLanguage.PYTHON)
    assert python.file_count == 1  # c.py is not in the older commit


def test_unknown_revision_raises_and_writes_nothing(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo(FILES)

    with pytest.raises(SnapshotExportError, match="no-such-rev"):
        take_snapshot_at(repo, "no-such-rev", default_registry(), FakeToolRunner(), snapshot_store)

    assert snapshot_store.list_snapshots(make_project_id("github.com/manta/example-repo")) == []


def test_a_tool_failure_inside_the_export_is_absent_tool_failed(
    snapshot_git_repo: SnapshotRepoFactory, snapshot_store: MetrologyStore
) -> None:
    repo = snapshot_git_repo(FILES)
    ruff = repo / ".venv" / "bin" / "ruff"
    ruff.parent.mkdir(parents=True)
    ruff.write_text("#!/bin/sh\n", encoding="utf-8")
    ruff.chmod(ruff.stat().st_mode | stat.S_IXUSR)
    runner = FakeToolRunner(
        {
            (str(ruff), "--version"): ToolResult(
                0, read_fixture("version_ruff.stdout", repo), "", False
            ),
            (str(ruff), "check"): ToolResult(2, "", "ruff crashed", False),
        }
    )

    snapshot = take_snapshot_at(repo, "HEAD", default_registry(), runner, snapshot_store)

    python = next(e for e in snapshot.languages if e.language is SourceLanguage.PYTHON)
    lint = next(m for m in python.measurements if m.metric is SnapshotMetric.LINT_COUNT)
    assert lint.absent is AbsenceReason.TOOL_FAILED


def live_environment(repo: Path, language: SourceLanguage) -> None:
    """Give *repo* (the live checkout) the project's real tools, or skip the test."""
    if language is SourceLanguage.PYTHON:
        venv = PROJECT_ROOT / ".venv"
        if not (venv / "bin" / "ruff").is_file():
            pytest.skip(f"live Python tools not installed: no {venv}/bin/ruff")
        (repo / ".venv").symlink_to(venv)
        return
    node_modules = PROJECT_ROOT / "node_modules"
    if not (node_modules / ".bin" / "eslint").is_file():
        pytest.skip(f"live TypeScript tools not installed: no {node_modules}/.bin/eslint")
    (repo / "node_modules").symlink_to(node_modules)


@pytest.mark.parametrize("language", sorted(default_registry(), key=lambda lang: lang.value))
def test_export_conformance_no_tool_is_missing_just_because_the_tree_is_an_export(
    language: SourceLanguage,
    snapshot_git_repo: SnapshotRepoFactory,
    snapshot_store: MetrologyStore,
) -> None:
    """The exported tree has no .venv or node_modules; the live checkout's tools must be used."""
    repo = snapshot_git_repo(FILES)
    live_environment(repo, language)
    registry: AdapterRegistry = {language: default_registry()[language]}

    snapshot = take_snapshot_at(repo, "HEAD", registry, SubprocessToolRunner(), snapshot_store)

    entry = next(e for e in snapshot.languages if e.language is language)
    measured = [m for m in entry.measurements if m.metric in registry[language].metrics]
    assert measured
    for measurement in measured:
        assert measurement.absent is not AbsenceReason.TOOL_MISSING, (
            f"{language.value} {measurement.metric.value}: {measurement.absent_detail}"
        )
