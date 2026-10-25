"""Tests for the squash rewrite, its backup tag and its restore on failure (slice 948 D3-D5)."""

from __future__ import annotations

import dataclasses
import logging
import re
import subprocess
from pathlib import Path

import pytest

import squadron.pipeline.squash as squash_module
import squadron.pipeline.squash_rewrite as squash_rewrite
from squadron.pipeline.squash import (
    SquashPlan,
    SquashRefusedError,
    SquashRewriteError,
    apply_squash,
    plan_squash,
)
from squadron.review.git_utils import run_git, run_git_bytes
from tests.conftest import run_test_git
from tests.pipeline.commit_fixtures import SLICE, cf_client
from tests.pipeline.squash_helpers import head, planning_run, squash_target

_LOGGER = "squadron.pipeline.squash"


def _plan(repo: Path) -> SquashPlan:
    plan = plan_squash(squash_target(), "main", repo, cf_client())
    assert plan is not None
    return plan


def _show(repo: Path, rev: str, fmt: str) -> str:
    return run_test_git(repo, "show", "-s", f"--format={fmt}", rev).strip()


def test_seven_commit_run_becomes_one_commit(temp_git_repo: Path) -> None:
    parent = head(temp_git_repo)
    shas = planning_run(temp_git_repo, 7)
    old_tree = run_test_git(temp_git_repo, "rev-parse", "HEAD^{tree}").strip()

    new_sha = apply_squash(_plan(temp_git_repo), temp_git_repo)

    assert new_sha == head(temp_git_repo)
    assert run_test_git(temp_git_repo, "rev-parse", "HEAD^").strip() == parent
    assert run_test_git(temp_git_repo, "rev-parse", "HEAD^{tree}").strip() == old_tree
    assert _show(temp_git_repo, "HEAD", "%B") == _show(temp_git_repo, shas[0], "%B")
    assert _show(temp_git_repo, "HEAD", "%an <%ae>") == _show(temp_git_repo, shas[0], "%an <%ae>")


def test_backup_tag_points_at_old_head_and_matches_format(temp_git_repo: Path) -> None:
    shas = planning_run(temp_git_repo, 3)
    plan = _plan(temp_git_repo)

    apply_squash(plan, temp_git_repo)

    assert re.fullmatch(rf"squash-backup/slice-{SLICE}-[0-9a-f]{{8}}", plan.backup_tag)
    assert plan.backup_tag.endswith(shas[-1][:8])
    assert run_test_git(temp_git_repo, "rev-parse", f"{plan.backup_tag}^{{commit}}").strip() == shas[-1]


def _refuse_update_ref(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
    if args[0] == "update-ref":
        return subprocess.CompletedProcess(args, 128, "", "fatal: simulated ref lock")
    return run_git(args, cwd=cwd)


def test_failing_ref_update_restores_head(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    planning_run(temp_git_repo, 3)
    old_head = head(temp_git_repo)
    plan = _plan(temp_git_repo)
    monkeypatch.setattr(squash_module, "run_git", _refuse_update_ref)

    with caplog.at_level(logging.ERROR, logger=_LOGGER):
        with pytest.raises(SquashRewriteError, match="restored"):
            apply_squash(plan, temp_git_repo)

    assert head(temp_git_repo) == old_head
    assert any(r.levelno == logging.ERROR and "update-ref" in r.getMessage() for r in caplog.records)


def test_failing_object_write_restores_head(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    planning_run(temp_git_repo, 3)
    old_head = head(temp_git_repo)
    plan = _plan(temp_git_repo)

    def refuse_hash_object(
        args: list[str], *, cwd: str, stdin: bytes | None = None
    ) -> subprocess.CompletedProcess[bytes] | None:
        if args[0] == "hash-object":
            return subprocess.CompletedProcess(args, 128, b"", b"fatal: simulated disk full")
        return run_git_bytes(args, cwd=cwd, stdin=stdin)

    monkeypatch.setattr(squash_rewrite, "run_git_bytes", refuse_hash_object)
    with caplog.at_level(logging.ERROR, logger=_LOGGER):
        with pytest.raises(SquashRewriteError, match="simulated disk full"):
            apply_squash(plan, temp_git_repo)

    assert head(temp_git_repo) == old_head


def test_tree_mismatch_restores_head(temp_git_repo: Path, caplog: pytest.LogCaptureFixture) -> None:
    planning_run(temp_git_repo, 3)
    old_head = head(temp_git_repo)
    plan = dataclasses.replace(_plan(temp_git_repo), tree="0" * 40)

    with caplog.at_level(logging.ERROR, logger=_LOGGER):
        with pytest.raises(SquashRewriteError, match="tree mismatch"):
            apply_squash(plan, temp_git_repo)

    assert head(temp_git_repo) == old_head
    assert any(r.levelno == logging.ERROR and "tree mismatch" in r.getMessage() for r in caplog.records)


def test_existing_backup_tag_at_head_is_reused(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    planning_run(temp_git_repo, 2)
    run_test_git(temp_git_repo, "tag", _plan(temp_git_repo).backup_tag, "HEAD")
    plan = _plan(temp_git_repo)

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        apply_squash(plan, temp_git_repo)

    assert run_test_git(temp_git_repo, "tag", "-l", "squash-backup/*").split() == [plan.backup_tag]
    assert any("reusing existing backup tag" in r.getMessage() for r in caplog.records)


def test_head_moved_since_plan_refuses_and_touches_nothing(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 2)
    plan = _plan(temp_git_repo)
    planning_run(temp_git_repo, 1)
    moved_head = head(temp_git_repo)

    with pytest.raises(SquashRefusedError, match="HEAD moved"):
        apply_squash(plan, temp_git_repo)

    assert head(temp_git_repo) == moved_head
    assert run_test_git(temp_git_repo, "tag", "-l", "squash-backup/*").strip() == ""


def test_tree_dirtied_since_plan_refuses(temp_git_repo: Path) -> None:
    planning_run(temp_git_repo, 2)
    plan = _plan(temp_git_repo)
    (temp_git_repo / "README.md").write_text("edited after planning\n")

    with pytest.raises(SquashRefusedError, match="working tree changed"):
        apply_squash(plan, temp_git_repo)

    assert (temp_git_repo / "README.md").read_text() == "edited after planning\n"


def test_failed_restore_prints_the_recovery_command(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    planning_run(temp_git_repo, 3)
    plan = _plan(temp_git_repo)

    def refuse_hard_reset(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        if args[:3] == ["reset", "-q", "--hard"]:
            return subprocess.CompletedProcess(args, 128, "", "fatal: simulated restore failure")
        return _refuse_update_ref(args, cwd=cwd)

    monkeypatch.setattr(squash_module, "run_git", refuse_hard_reset)
    with caplog.at_level(logging.ERROR, logger=_LOGGER):
        with pytest.raises(SquashRewriteError) as raised:
            apply_squash(plan, temp_git_repo)

    assert f"recover with: git reset --hard {plan.backup_tag}" in str(raised.value)
    assert any("restore failed" in r.getMessage() for r in caplog.records)
