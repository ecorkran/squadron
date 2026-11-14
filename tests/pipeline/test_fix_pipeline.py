"""The built-in ``fix`` pipeline run end to end by the executor (slice 423, Task 11).

A real temporary git repo, file mode and ``commit-to: current`` (no cf, no code host),
with a fake dispatch standing in for the agent.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.codehost.errors import HostCommandTimeoutError
from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.actions.cf_op import CfOperation
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.actions.fix_context import OPERATION_KEY, PROMPT_KEY, FixContextAction
from squadron.pipeline.control_params import RUN_IO_DIR, RUN_MAX_COST
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY, FailureKind
from squadron.pipeline.fix_keys import (
    COMMIT_TO_KEY,
    ISSUE_SOURCE_KEY,
    ISSUE_TEXT_SHA256_KEY,
    START_BRANCH_KEY,
    START_HEAD_KEY,
    IssueSource,
)
from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pipeline.state import StateManager
from squadron.providers.base import USAGE_KEY
from tests.conftest import run_test_git
from tests.pipeline.conftest import usage_dict
from tests.pipeline.fix_fetch_helpers import FakeHost, add_github_remote, loader_for

SUMMARY = "keep the last row when parsing"
ISSUE_TEXT = "The parser drops the last row.\n"
ISSUE_NUMBER = 301
AgentWork = Callable[[ActionContext], Awaitable[None]]


def _report(**overrides: object) -> str:
    report: dict[str, object] = {
        "summary": SUMMARY,
        "failing_tests": ["tests/test_parser.py::test_last_row"],
        "failed_before_change": True,
        "gates": [{"command": "ruff check", "exit_code": 0}],
    }
    report.update(overrides)
    return f"Fixed it.\n{json.dumps(report)}"


class _FakeAgent:
    """A dispatch action that does some work in the repo and replies with ``reply``."""

    def __init__(self, reply: str, work: AgentWork | None = None, cost_usd: float | None = None):
        self.reply = reply
        self.work = work
        self.cost_usd = cost_usd
        self.received_prompt: str | None = None
        self.execute = AsyncMock(side_effect=self._execute)

    async def _execute(self, context: ActionContext) -> ActionResult:
        # What the dispatch is handed: the context an earlier action built. The dispatch's
        # own fallback onto it is tested in test_dispatch_prompt_identity.
        built = [
            str(result.outputs[PROMPT_KEY])
            for result in context.prior_outputs.values()
            if result.outputs.get(OPERATION_KEY) == CfOperation.BUILD_CONTEXT
        ]
        self.received_prompt = built[-1] if built else None
        if self.work is not None:
            await self.work(context)
        metadata: dict[str, object] = {}
        if self.cost_usd is not None:
            metadata[USAGE_KEY] = usage_dict(self.cost_usd)
        return ActionResult(
            success=True,
            action_type="dispatch",
            outputs={"response": self.reply},
            metadata=metadata,
        )


def _write_fix(cwd: str) -> None:
    Path(cwd, "README.md").write_text("fixed\n")
    Path(cwd, "test_parser.py").write_text("def test_last_row(): ...\n")


async def _edit_readme(context: ActionContext) -> None:
    await asyncio.to_thread(_write_fix, context.cwd)


async def _commit_itself(context: ActionContext) -> None:
    await _edit_readme(context)
    run_test_git(Path(context.cwd), "add", "-A")
    run_test_git(Path(context.cwd), "commit", "-q", "-m", "agent commit")


async def _switch_branch(context: ActionContext) -> None:
    run_test_git(Path(context.cwd), "checkout", "-q", "-b", "sidetrack")
    await _edit_readme(context)


def _commit_count(repo: Path) -> int:
    return int(run_test_git(repo, "rev-list", "--count", "HEAD").strip())


@pytest.fixture
def io_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "io"
    directory.mkdir()
    (directory / "issue.md").write_text(ISSUE_TEXT, encoding="utf-8")
    return directory


async def _run(
    repo: Path,
    agent: _FakeAgent,
    io_dir: Path,
    tmp_path: Path,
    *,
    commit_to: str = "current",
    cf_client: MagicMock | None = None,
    max_cost: float | None = None,
    issue_file: str = "issue.md",
    fix_context: FixContextAction | None = None,
) -> tuple[PipelineResult, str]:
    runs_dir = tmp_path / "runs"
    state = StateManager(runs_dir=runs_dir)
    run_id = state.init_run("fix", {})
    params: dict[str, object] = {
        "issue": str(ISSUE_NUMBER),
        "issue-file": issue_file,
        "commit-to": commit_to,
        RUN_IO_DIR: str(io_dir),
    }
    if max_cost is not None:
        params[RUN_MAX_COST] = max_cost
    result = await execute_pipeline(
        load_pipeline("fix"),
        params,
        resolver=MagicMock(),
        cf_client=cf_client or MagicMock(),
        cwd=str(repo),
        run_id=run_id,
        runs_dir=runs_dir,
        observer=state.observer(run_id),
        _action_registry={
            "fix-context": fix_context or FixContextAction(),
            "dispatch": agent,
            "commit": CommitAction(),
        },
    )
    return result, run_id


def _failed(result: PipelineResult) -> ActionResult:
    return next(a for step in result.step_results for a in step.action_results if not a.success)


def _persisted_actions(tmp_path: Path, run_id: str) -> list[dict[str, Any]]:
    state = StateManager(runs_dir=tmp_path / "runs").load(run_id)
    return [action for step in state.completed_steps for action in step.action_results]


async def test_a_valid_fix_makes_one_commit_and_records_the_run(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path
) -> None:
    agent = _FakeAgent(_report(), _edit_readme)
    before = _commit_count(temp_git_repo)
    start_head = run_test_git(temp_git_repo, "rev-parse", "HEAD").strip()

    result, run_id = await _run(temp_git_repo, agent, io_dir, tmp_path)

    assert result.status is ExecutionStatus.COMPLETED, result.error
    assert _commit_count(temp_git_repo) == before + 1
    assert run_test_git(temp_git_repo, "log", "-1", "--format=%B").strip() == (
        f"fix: {SUMMARY}\n\nFixes #{ISSUE_NUMBER}"
    )
    context_result, dispatch_result, commit_result = result.step_results[0].action_results
    assert context_result.outputs[ISSUE_SOURCE_KEY] == IssueSource.FILE.value
    assert (
        context_result.outputs[ISSUE_TEXT_SHA256_KEY] == hashlib.sha256(ISSUE_TEXT.encode()).hexdigest()
    )
    assert context_result.outputs[START_HEAD_KEY] == start_head
    assert context_result.outputs[START_BRANCH_KEY] == "main"
    assert context_result.outputs[COMMIT_TO_KEY] == "current"
    assert dispatch_result.success
    assert commit_result.outputs["committed"] is True
    assert agent.received_prompt == context_result.outputs["stdout"]
    persisted = _persisted_actions(tmp_path, run_id)
    assert persisted[0]["outputs"] == context_result.outputs


async def test_the_pipeline_invokes_neither_gh_nor_cf(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "tripwire"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    for name in ("gh", "cf"):
        script = bin_dir / name
        script.write_text(f'#!/bin/sh\necho "{name} $@" >> "{log}"\nexit 127\n')
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GH_TOKEN", "")

    result, _ = await _run(temp_git_repo, _FakeAgent(_report(), _edit_readme), io_dir, tmp_path)

    assert result.status is ExecutionStatus.COMPLETED, result.error
    assert not log.exists() or log.read_text() == ""


async def test_an_agent_commit_fails_the_run_and_the_pipeline_adds_none(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path
) -> None:
    before = _commit_count(temp_git_repo)

    result, _ = await _run(temp_git_repo, _FakeAgent(_report(), _commit_itself), io_dir, tmp_path)

    assert result.status is ExecutionStatus.FAILED
    assert "HEAD moved" in (_failed(result).error or "")
    assert _commit_count(temp_git_repo) == before + 1  # the agent's own, none from the pipeline
    assert run_test_git(temp_git_repo, "log", "-1", "--format=%s").strip() == "agent commit"


async def test_a_branch_switch_at_the_same_commit_fails_naming_the_branch(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path
) -> None:
    before = _commit_count(temp_git_repo)

    result, _ = await _run(temp_git_repo, _FakeAgent(_report(), _switch_branch), io_dir, tmp_path)

    assert result.status is ExecutionStatus.FAILED
    assert "sidetrack" in (_failed(result).error or "")
    assert _commit_count(temp_git_repo) == before


async def test_a_report_defect_fails_with_the_kind_and_keeps_the_edits(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path
) -> None:
    agent = _FakeAgent(_report(gates=[]), _edit_readme)
    before = _commit_count(temp_git_repo)

    result, run_id = await _run(temp_git_repo, agent, io_dir, tmp_path)

    assert result.status is ExecutionStatus.FAILED
    assert _failed(result).metadata[FAILURE_KIND_KEY] == FailureKind.FIX_REPORT.value
    persisted_failed = next(a for a in _persisted_actions(tmp_path, run_id) if not a["success"])
    assert persisted_failed["metadata"][FAILURE_KIND_KEY] == FailureKind.FIX_REPORT.value
    assert _commit_count(temp_git_repo) == before
    assert (temp_git_repo / "test_parser.py").exists()
    assert "README.md" in run_test_git(temp_git_repo, "status", "--porcelain")


async def test_a_valid_report_with_no_edit_fails_with_the_kind(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path
) -> None:
    before = _commit_count(temp_git_repo)

    result, _ = await _run(temp_git_repo, _FakeAgent(_report()), io_dir, tmp_path)

    assert result.status is ExecutionStatus.FAILED
    failed = _failed(result)
    assert failed.metadata[FAILURE_KIND_KEY] == FailureKind.FIX_REPORT.value
    assert "no changes" in (failed.error or "")
    assert _commit_count(temp_git_repo) == before


async def test_a_blocked_report_fails_with_the_reason(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path
) -> None:
    agent = _FakeAgent(json.dumps({"blocked": "needs a product decision"}), _edit_readme)
    before = _commit_count(temp_git_repo)

    result, _ = await _run(temp_git_repo, agent, io_dir, tmp_path)

    assert result.status is ExecutionStatus.FAILED
    assert _failed(result).error == "fix blocked: needs a product decision"
    assert _commit_count(temp_git_repo) == before


async def test_a_dirty_tree_fails_at_fix_context_and_never_dispatches(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path
) -> None:
    (temp_git_repo / "scratch.txt").write_text("x")
    agent = _FakeAgent(_report(), _edit_readme)

    result, _ = await _run(temp_git_repo, agent, io_dir, tmp_path)

    assert result.status is ExecutionStatus.FAILED
    assert "scratch.txt" in (_failed(result).error or "")
    agent.execute.assert_not_awaited()


async def test_target_mode_with_unreadable_cf_ends_the_run_before_dispatch(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path
) -> None:
    cf = MagicMock()
    cf.get_config.side_effect = ContextForgeError("cf is down")
    agent = _FakeAgent(_report(), _edit_readme)

    with pytest.raises(GitEnvironmentError, match="cf is down"):
        await _run(temp_git_repo, agent, io_dir, tmp_path, commit_to="target", cf_client=cf)

    agent.execute.assert_not_awaited()


async def test_the_cost_cap_stops_the_run_before_the_commit(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path
) -> None:
    agent = _FakeAgent(_report(), _edit_readme, cost_usd=1.0)
    before = _commit_count(temp_git_repo)

    result, _ = await _run(temp_git_repo, agent, io_dir, tmp_path, max_cost=0.05)

    assert result.status is ExecutionStatus.FAILED
    assert _failed(result).metadata[FAILURE_KIND_KEY] == FailureKind.COST_CAP.value
    assert _commit_count(temp_git_repo) == before


async def test_a_host_error_fails_at_fix_context_and_never_dispatches(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path
) -> None:
    add_github_remote(temp_git_repo)
    error = HostCommandTimeoutError(["gh", "api"], 30.0)
    agent = _FakeAgent(_report(), _edit_readme)

    result, _ = await _run(
        temp_git_repo,
        agent,
        io_dir,
        tmp_path,
        issue_file="",
        fix_context=FixContextAction(loader_for(FakeHost(error))),
    )

    assert result.status is ExecutionStatus.FAILED
    assert str(error) in (_failed(result).error or "")
    agent.execute.assert_not_awaited()


async def test_a_fetched_issue_is_recorded_as_github(
    temp_git_repo: Path, io_dir: Path, tmp_path: Path
) -> None:
    add_github_remote(temp_git_repo)
    agent = _FakeAgent(_report(), _edit_readme)

    result, _ = await _run(
        temp_git_repo,
        agent,
        io_dir,
        tmp_path,
        issue_file="",
        fix_context=FixContextAction(loader_for(FakeHost())),
    )

    assert result.status is ExecutionStatus.COMPLETED, result.error
    assert result.step_results[0].action_results[0].outputs[ISSUE_SOURCE_KEY] == "github"
    assert "early" in (agent.received_prompt or "")
