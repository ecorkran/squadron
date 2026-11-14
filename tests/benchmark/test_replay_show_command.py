"""``sq benchmark replay-show``: the stored record and its diff (slice 424 Task 34)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands import benchmark_common as common_module
from squadron.metrology.benchmark_replay_enums import LeakRule, LeakVerdict
from squadron.metrology.benchmark_replay_models import ImplementationReplay, LeakHit, LeakScanResult
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.diff_sidecars import SIDECAR_SUBDIRECTORY, SIDECAR_SUFFIX
from squadron.metrology.store import MetrologyStore
from tests.benchmark.support import hermetic_git
from tests.metrology.test_benchmark_replay_models import _replay as make_replay

runner = CliRunner()
RECORD_ID = "implreplay-0123456789ab-0123456789ab-01234567-s0"
DIFF = b"diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b \xe2\x9c\x93\n"
LEAKED = LeakScanResult(
    verdict=LeakVerdict.LEAKED,
    rules_version=1,
    tool_calls_seen=9,
    hits=(LeakHit(rule=LeakRule.PATH, tool="Read", excerpt="/home/me/checkout/src/x.py"),),
    detail="",
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "checkout"
    path.mkdir()
    hermetic_git(path, "init", "-q", "-b", "main")
    return path


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BenchmarkRecordStore:
    directory = tmp_path / "store"
    monkeypatch.setattr(common_module, "resolve_store_dir", lambda cwd: directory)
    return BenchmarkRecordStore(MetrologyStore(store_dir=directory))


def stored(store: BenchmarkRecordStore, **update: Any) -> ImplementationReplay:
    base = make_replay()
    replay = base.model_copy(update={"diff": store.diffs.put(DIFF), **update})
    store.write_replay(RECORD_ID, replay)
    return replay


def show(repo: Path, *args: str) -> Any:
    return runner.invoke(app, ["benchmark", "replay-show", RECORD_ID, "--repo", str(repo), *args])


def test_shows_the_record_with_leak_hits_and_identities(
    store: BenchmarkRecordStore, repo: Path
) -> None:
    replay = stored(store, leak=LEAKED)
    result = show(repo)
    assert result.exit_code == 0, result.output
    assert f"record: {RECORD_ID}" in result.output
    assert "leak: leaked" in result.output
    assert "hit path  Read: /home/me/checkout/src/x.py" in result.output
    assert f"environment: {replay.environment.identity_digest}" in result.output  # type: ignore[union-attr]
    assert f"prompt: {replay.prompt.sha256}" in result.output  # type: ignore[union-attr]
    assert f"effort_sent: {replay.config.effort_sent or '-'}" in result.output
    for path, digest in replay.instruction_files:
        assert f"{digest}  {path}" in result.output
    assert f"diff: {replay.diff.sha256}" in result.output  # type: ignore[union-attr]


def test_diff_prints_the_stored_diff_exactly(store: BenchmarkRecordStore, repo: Path) -> None:
    stored(store)
    result = runner.invoke(app, ["benchmark", "replay-show", RECORD_ID, "--diff", "--repo", str(repo)])
    assert result.exit_code == 0, result.output
    assert result.stdout_bytes == DIFF


def test_a_tampered_sidecar_exits_1_with_the_hash_mismatch(
    store: BenchmarkRecordStore, repo: Path, tmp_path: Path
) -> None:
    replay = stored(store)
    assert replay.diff is not None
    sidecar = tmp_path / "store" / SIDECAR_SUBDIRECTORY / f"{replay.diff.sha256}{SIDECAR_SUFFIX}"
    sidecar.write_bytes(b"tampered")
    result = show(repo, "--diff")
    assert result.exit_code == 1
    assert "does not match its sha256" in result.output
    assert "Traceback" not in result.output


def test_a_missing_sidecar_exits_1(store: BenchmarkRecordStore, repo: Path, tmp_path: Path) -> None:
    replay = stored(store)
    assert replay.diff is not None
    (tmp_path / "store" / SIDECAR_SUBDIRECTORY / f"{replay.diff.sha256}{SIDECAR_SUFFIX}").unlink()
    result = show(repo, "--diff")
    assert result.exit_code == 1
    assert "is missing" in result.output


def test_an_unknown_id_exits_1_naming_it(store: BenchmarkRecordStore, repo: Path) -> None:
    result = show(repo)
    assert result.exit_code == 1
    assert f"no replay record {RECORD_ID}" in result.output


def test_a_record_without_a_diff_says_so_with_diff(store: BenchmarkRecordStore, repo: Path) -> None:
    stored(store, diff=None, commit_sha=None, leak=None)
    result = show(repo, "--diff")
    assert result.exit_code == 1
    assert "has no diff" in result.output
    plain = show(repo)
    assert plain.exit_code == 0
    assert "diff: -" in plain.output
    assert "leak: - (the producer never ran)" in plain.output
