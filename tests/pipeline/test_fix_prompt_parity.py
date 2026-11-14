"""``sq run fix`` and ``/sq:run fix`` agree: same prompt, same commit, same refusals (slice 423 D9).

Two identical repos (file mode, ``commit-to: current``): one runs the SDK actions, the
other runs the hidden commands exactly as the rendered prompt-only commands spell them.
"""

from __future__ import annotations

import asyncio
import json
import re
import shlex
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.actions.fix_context import FixContextAction
from squadron.pipeline.commit_plan import SUBJECT_PARAM, CommitSubject
from squadron.pipeline.fix_prompt_args import REPORT_PATH_PLACEHOLDER
from squadron.pipeline.models import ActionContext, ActionResult, StepConfig, local_output_key
from squadron.pipeline.prompt_renderer import render_step_instructions
from squadron.pipeline.resolver import ResolvedModel
from tests.conftest import run_test_git

runner = CliRunner()
pytestmark = pytest.mark.usefixtures("fake_cf")

ISSUE_FILE = "issue.md"
ISSUE_TEXT = "The parser drops the last row.\n"
SUMMARY = "keep the last row when parsing"
_SHA = re.compile(r"\b[0-9a-f]{12}\b")


def _reply(**overrides: object) -> str:
    report: dict[str, object] = {
        "summary": SUMMARY,
        "failing_tests": ["tests/test_parser.py::test_last_row"],
        "failed_before_change": True,
        "gates": [{"command": "ruff check", "exit_code": 0}],
    }
    report.update(overrides)
    return f"Done.\n{json.dumps(report)}"


def _make_repo(path: Path) -> Path:
    path.mkdir()
    run_test_git(path, "init", "-q", "-b", "main")
    (path / "README.md").write_text("init\n")
    (path / ISSUE_FILE).write_text(ISSUE_TEXT, encoding="utf-8")
    run_test_git(path, "add", "-A")
    run_test_git(path, "commit", "-q", "-m", "init")
    return path


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    """(sdk, cli): two repos with the same files and history shape."""
    return _make_repo(tmp_path / "sdk"), _make_repo(tmp_path / "cli")


@pytest.fixture
def fake_cf() -> Iterator[None]:
    """The hidden commands build a cf client; ``commit-to: current`` never reads it."""
    cf = MagicMock()
    cf.get_config.side_effect = AssertionError("cf was read under commit-to current")
    with (
        patch("squadron.cli.commands.commit_run.ContextForgeClient", return_value=cf),
        patch("squadron.cli.commands.fix_prompt_run.ContextForgeClient", return_value=cf),
    ):
        yield


def _render(repo: Path) -> list[str]:
    """The prompt-only commands for the fix step, rendered against ``repo`` now."""
    step = StepConfig(
        step_type="fix",
        name="fix-0",
        config={
            "issue": "{issue}",
            "model": "{model}",
            "issue-file": "{issue-file}",
            "commit-to": "{commit-to}",
        },
    )
    resolver = MagicMock()
    resolver.resolve.return_value = ("resolved-model", None)
    resolver.resolve_full.return_value = ResolvedModel("resolved-model", None)
    rendered = render_step_instructions(
        step,
        step_index=0,
        total_steps=1,
        params={"issue": "301", "model": "sonnet", "issue-file": ISSUE_FILE, "commit-to": "current"},
        resolver=resolver,
        run_id="run-test",
        cwd=str(repo),
    )
    return [action.command or "" for action in rendered.actions]


def _cli_args(command: str, report: Path | None = None) -> list[str]:
    args = shlex.split(command)[1:]  # drop the leading "sq"
    return [str(report) if arg == REPORT_PATH_PLACEHOLDER else arg for arg in args]


def _sdk_context(repo: Path, prior: dict[str, ActionResult]) -> ActionContext:
    return ActionContext(
        pipeline_name="fix",
        run_id="run-001",
        params={
            "issue": "301",
            "issue-file": ISSUE_FILE,
            "commit-to": "current",
            SUBJECT_PARAM: CommitSubject.FIX.value,
        },
        step_name="fix",
        step_index=0,
        prior_outputs=prior,
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd=str(repo),
    )


def _sdk_fix_context(repo: Path) -> ActionResult:
    result = asyncio.run(FixContextAction().execute(_sdk_context(repo, {})))
    assert result.success, result.error
    return result


def _sdk_commit(repo: Path, context_result: ActionResult, reply: str) -> ActionResult:
    prior = {
        local_output_key(ActionType.FIX_CONTEXT, 0): context_result,
        local_output_key(ActionType.DISPATCH, 1): ActionResult(
            success=True, action_type=ActionType.DISPATCH, outputs={"response": reply}
        ),
    }
    return asyncio.run(CommitAction().execute(_sdk_context(repo, prior)))


def _edit(repo: Path) -> None:
    (repo / "README.md").write_text("fixed\n")


def _message(repo: Path) -> str:
    return run_test_git(repo, "log", "-1", "--format=%B").strip()


def _masked(text: str) -> str:
    return _SHA.sub("<sha>", text)


def test_the_prompt_is_the_same(repos: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    sdk_repo, cli_repo = repos
    sdk = _sdk_fix_context(sdk_repo)

    monkeypatch.chdir(cli_repo)
    context_command, _, _ = _render(cli_repo)
    result = runner.invoke(app, _cli_args(context_command))

    assert result.exit_code == 0, result.output
    assert result.output == f"{sdk.outputs['stdout']}\n"


def test_the_commit_message_is_the_same(
    repos: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sdk_repo, cli_repo = repos
    report = tmp_path / "report.txt"
    report.write_text(_reply(), encoding="utf-8")
    sdk_context = _sdk_fix_context(sdk_repo)
    monkeypatch.chdir(cli_repo)
    _, _, commit_command = _render(cli_repo)
    _edit(sdk_repo)
    _edit(cli_repo)

    sdk = _sdk_commit(sdk_repo, sdk_context, _reply())
    cli = runner.invoke(app, _cli_args(commit_command, report))

    assert sdk.success, sdk.error
    assert cli.exit_code == 0, cli.output
    assert _message(sdk_repo) == _message(cli_repo) == f"fix: {SUMMARY}\n\nFixes #301"


@pytest.mark.parametrize(
    "reply",
    [
        "no report at all",
        _reply(summary=""),
        _reply(summary="fix: already prefixed"),
        _reply(failing_tests=[]),
        _reply(failed_before_change=False),
        _reply(gates=[]),
        _reply(gates=[{"command": "ruff check", "exit_code": 1}]),
        json.dumps({"blocked": "needs a decision"}),
        _reply(blocked="needs a decision"),
    ],
)
def test_each_report_defect_is_refused_with_the_same_text(
    repos: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path, reply: str
) -> None:
    sdk_repo, cli_repo = repos
    report = tmp_path / "report.txt"
    report.write_text(reply, encoding="utf-8")
    sdk_context = _sdk_fix_context(sdk_repo)
    monkeypatch.chdir(cli_repo)
    _, _, commit_command = _render(cli_repo)
    _edit(sdk_repo)
    _edit(cli_repo)

    sdk = _sdk_commit(sdk_repo, sdk_context, reply)
    cli = runner.invoke(app, _cli_args(commit_command, report))

    assert not sdk.success
    assert cli.exit_code == 1
    assert cli.output == f"Error: {sdk.error}\n"


def test_a_commit_between_rendering_and_the_commit_is_refused_by_both(
    repos: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sdk_repo, cli_repo = repos
    report = tmp_path / "report.txt"
    report.write_text(_reply(), encoding="utf-8")
    sdk_context = _sdk_fix_context(sdk_repo)
    monkeypatch.chdir(cli_repo)
    _, _, commit_command = _render(cli_repo)
    for repo in (sdk_repo, cli_repo):
        run_test_git(repo, "commit", "-q", "--allow-empty", "-m", "agent commit")
        _edit(repo)

    sdk = _sdk_commit(sdk_repo, sdk_context, _reply())
    cli = runner.invoke(app, _cli_args(commit_command, report))

    assert not sdk.success
    assert "HEAD moved" in (sdk.error or "")
    assert cli.exit_code == 1
    assert _masked(cli.output) == _masked(f"Error: {sdk.error}\n")
    assert _message(sdk_repo) == _message(cli_repo) == "agent commit"
