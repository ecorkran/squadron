"""Tests for FixContextAction (slice 423 D2, D5), file mode on a real temporary git repo."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.codehost.errors import CodeHostError, HostCommandTimeoutError, IssueNotFoundError
from squadron.codehost.issue_text import render_issue
from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions import fix_context as fix_context_module
from squadron.pipeline.actions.fix_context import FixContextAction
from squadron.pipeline.control_params import RUN_IO_DIR
from squadron.pipeline.fix_git import SUBPROCESS_GIT, FixGit
from squadron.pipeline.fix_keys import (
    COMMIT_TO_KEY,
    ISSUE_NUMBER_KEY,
    ISSUE_SOURCE_KEY,
    ISSUE_TEXT_SHA256_KEY,
    START_BRANCH_KEY,
    START_HEAD_KEY,
    CommitTo,
    IssueSource,
)
from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.pipeline.models import ActionContext, ActionResult
from tests.conftest import run_test_git
from tests.pipeline.fix_fetch_helpers import FakeHost, add_github_remote, loader_for, snapshot
from tests.pipeline.fix_git_fake import FakeFixGit

ISSUE_TEXT = "Parser drops the last row.\n\nSee {braces} too.\n"


@pytest.fixture
def io_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "io"
    directory.mkdir()
    (directory / "issue.md").write_text(ISSUE_TEXT, encoding="utf-8")
    return directory


def _cf(integration_branch: str = "") -> MagicMock:
    cf = MagicMock()
    cf.get_config.return_value = integration_branch
    return cf


def _context(
    repo: Path,
    io_dir: Path,
    *,
    cf: MagicMock | None = None,
    **overrides: object,
) -> ActionContext:
    params: dict[str, object] = {
        "issue": "#301",
        "issue-file": "issue.md",
        "commit-to": CommitTo.CURRENT.value,
        RUN_IO_DIR: str(io_dir),
    }
    params.update(overrides)
    return ActionContext(
        pipeline_name="fix",
        run_id="run-001",
        params=params,
        step_name="fix",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=cf or _cf(),
        cwd=str(repo),
    )


async def _run(
    repo: Path, io_dir: Path, *, git: FixGit = SUBPROCESS_GIT, **kwargs: object
) -> ActionResult:
    cf = kwargs.pop("cf", None)
    assert cf is None or isinstance(cf, MagicMock)
    return await FixContextAction(git=git).execute(_context(repo, io_dir, cf=cf, **kwargs))


def _head(repo: Path) -> str:
    return run_test_git(repo, "rev-parse", "HEAD").strip()


@pytest.mark.parametrize("commit_to", [CommitTo.CURRENT, CommitTo.TARGET])
async def test_success_outputs_and_prompt(
    temp_git_repo: Path, io_dir: Path, commit_to: CommitTo
) -> None:
    result = await _run(temp_git_repo, io_dir, **{"commit-to": commit_to.value})

    assert result.success, result.error
    assert result.action_type == ActionType.FIX_CONTEXT
    outputs = result.outputs
    assert outputs["operation"] == "build_context"
    assert outputs[ISSUE_NUMBER_KEY] == 301
    assert outputs[ISSUE_SOURCE_KEY] == IssueSource.FILE.value
    assert outputs[ISSUE_TEXT_SHA256_KEY] == hashlib.sha256(ISSUE_TEXT.encode()).hexdigest()
    assert outputs[START_HEAD_KEY] == _head(temp_git_repo)
    assert outputs[START_BRANCH_KEY] == "main"
    assert outputs[COMMIT_TO_KEY] == commit_to.value
    prompt = str(outputs["stdout"])
    assert "#301" in prompt
    assert ISSUE_TEXT in prompt
    assert "{issue_number}" not in prompt
    assert "{issue_text}" not in prompt


async def test_untracked_file_is_listed_in_the_refusal(
    temp_git_repo: Path, io_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (temp_git_repo / "scratch.txt").write_text("x")
    with caplog.at_level(logging.WARNING):
        result = await _run(temp_git_repo, io_dir)
    assert not result.success
    assert "scratch.txt" in (result.error or "")
    assert any("scratch.txt" in record.getMessage() for record in caplog.records)


async def test_target_refuses_a_branch_that_is_not_the_target(
    temp_git_repo: Path, io_dir: Path
) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "elsewhere")
    result = await _run(temp_git_repo, io_dir, **{"commit-to": "target"})
    assert not result.success
    assert "'main'" in (result.error or "")
    assert "'elsewhere'" in (result.error or "")


async def test_current_accepts_any_branch(temp_git_repo: Path, io_dir: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "elsewhere")
    result = await _run(temp_git_repo, io_dir)
    assert result.success
    assert result.outputs[START_BRANCH_KEY] == "elsewhere"


@pytest.mark.parametrize("commit_to", [CommitTo.CURRENT, CommitTo.TARGET])
async def test_detached_head_is_refused_under_each_destination(
    temp_git_repo: Path, io_dir: Path, commit_to: CommitTo
) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "--detach")
    result = await _run(temp_git_repo, io_dir, **{"commit-to": commit_to.value})
    assert not result.success
    assert "detached" in (result.error or "")


@pytest.mark.parametrize("issue", ["", "0", "abc", "1.5", "#"])
async def test_invalid_issue_ref_is_refused(temp_git_repo: Path, io_dir: Path, issue: str) -> None:
    result = await _run(temp_git_repo, io_dir, issue=issue)
    assert not result.success
    assert "positive integer" in (result.error or "")


async def test_invalid_commit_to_is_refused(temp_git_repo: Path, io_dir: Path) -> None:
    result = await _run(temp_git_repo, io_dir, **{"commit-to": "elsewhere"})
    assert not result.success
    assert "commit-to" in (result.error or "")
    assert "target" in (result.error or "")


async def test_missing_issue_file_is_refused(temp_git_repo: Path, io_dir: Path) -> None:
    result = await _run(temp_git_repo, io_dir, **{"issue-file": "nope.md"})
    assert not result.success
    assert "does not exist" in (result.error or "")


async def test_empty_issue_file_is_refused(temp_git_repo: Path, io_dir: Path) -> None:
    (io_dir / "empty.md").write_text("  \n")
    result = await _run(temp_git_repo, io_dir, **{"issue-file": "empty.md"})
    assert not result.success
    assert "is empty" in (result.error or "")


async def test_unreadable_head_is_refused(temp_git_repo: Path, io_dir: Path) -> None:
    def unreadable(cwd: str) -> None:
        return None

    result = await _run(temp_git_repo, io_dir, git=FakeFixGit(head=unreadable))
    assert not result.success
    assert "cannot read HEAD" in (result.error or "")


async def test_unreadable_working_tree_state_is_refused_naming_the_git_error(
    temp_git_repo: Path, io_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def unreadable(cwd: str) -> str:
        return "fatal: unable to read the index\n"

    with caplog.at_level(logging.WARNING):
        result = await _run(temp_git_repo, io_dir, git=FakeFixGit(changed=unreadable))
    assert not result.success
    assert result.error == "cannot read the working tree state: fatal: unable to read the index"
    assert any("unable to read the index" in record.getMessage() for record in caplog.records)


async def test_target_with_unreadable_cf_config_raises_naming_the_key(
    temp_git_repo: Path, io_dir: Path
) -> None:
    cf = MagicMock()
    cf.get_config.side_effect = ContextForgeError("cf is down")
    with pytest.raises(GitEnvironmentError, match="git.integration_branch"):
        await _run(temp_git_repo, io_dir, cf=cf, **{"commit-to": "target"})


async def test_unreadable_branch_propagates(temp_git_repo: Path, io_dir: Path) -> None:
    def boom(cwd: str) -> str:
        raise GitEnvironmentError("cannot read the current branch: boom")

    with pytest.raises(GitEnvironmentError, match="boom"):
        await _run(temp_git_repo, io_dir, git=FakeFixGit(branch=boom))


async def test_current_with_issue_file_never_touches_cf_or_a_host(
    temp_git_repo: Path, io_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_host(runner: object) -> None:
        raise AssertionError("a code host was built in file mode")

    monkeypatch.setattr(fix_context_module, "build_github_host", no_host)
    cf = MagicMock()
    cf.get_config.side_effect = AssertionError("cf was read under commit-to current")
    result = await _run(temp_git_repo, io_dir, cf=cf)
    assert result.success, result.error
    cf.get_config.assert_not_called()


# --- fetched source (slice 423 D2, D3) ---


@pytest.fixture
def github_repo(temp_git_repo: Path) -> Path:
    add_github_remote(temp_git_repo)
    return temp_git_repo


async def _run_fetch(repo: Path, host: FakeHost) -> ActionResult:
    context = _context(repo, repo.parent)
    context.params.update({"issue-file": "", "issue": "301"})
    return await FixContextAction(loader_for(host)).execute(context)


async def test_fetched_issue_text_is_in_the_prompt_with_every_comment(github_repo: Path) -> None:
    result = await _run_fetch(github_repo, FakeHost())

    assert result.success, result.error
    prompt = str(result.outputs["stdout"])
    assert render_issue(snapshot(), None) in prompt
    assert "early" in prompt
    assert "late" in prompt
    assert result.outputs[ISSUE_SOURCE_KEY] == IssueSource.GITHUB.value
    assert result.outputs[ISSUE_NUMBER_KEY] == 301


@pytest.mark.parametrize(
    "error",
    [
        HostCommandTimeoutError(["gh", "api"], 30.0),
        IssueNotFoundError("issue 301 not found in o/r"),
    ],
    ids=lambda error: type(error).__name__,
)
async def test_a_host_error_fails_the_action_with_the_hosts_message(
    github_repo: Path, caplog: pytest.LogCaptureFixture, error: CodeHostError
) -> None:
    with caplog.at_level(logging.WARNING):
        result = await _run_fetch(github_repo, FakeHost(error))

    assert not result.success
    assert str(error) in (result.error or "")
    assert logging.ERROR in [record.levelno for record in caplog.records]


async def test_no_served_remote_fails_the_action(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        result = await _run_fetch(temp_git_repo, FakeHost())

    assert not result.success
    assert "cannot fetch issue #301" in (result.error or "")
    assert logging.ERROR in [record.levelno for record in caplog.records]
