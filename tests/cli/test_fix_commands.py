"""The hidden ``sq _fix-prompt`` and ``sq _commit --subject fix`` commands (slice 423 D9)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.fix_report import FixReportError, parse_fix_report
from tests.conftest import run_test_git

runner = CliRunner()

ISSUE_TEXT = "Parser drops the last row.\n"
SUMMARY = "keep the last row when parsing"


def _reply(**overrides: object) -> str:
    report: dict[str, object] = {
        "summary": SUMMARY,
        "failing_tests": ["tests/test_parser.py::test_last_row"],
        "failed_before_change": True,
        "gates": [{"command": "ruff check", "exit_code": 0}],
    }
    report.update(overrides)
    return f"Done.\n{json.dumps(report)}"


@pytest.fixture
def in_repo(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """The cwd is the temp repo; the cf clients the commands build are fakes."""
    monkeypatch.chdir(temp_git_repo)
    cf = MagicMock()
    cf.get_config.return_value = ""
    with (
        patch("squadron.cli.commands.commit_run.ContextForgeClient", return_value=cf),
        patch("squadron.cli.commands.fix_prompt_run.ContextForgeClient", return_value=cf),
    ):
        yield temp_git_repo


@pytest.fixture
def io_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "io"
    directory.mkdir()
    (directory / "issue.md").write_text(ISSUE_TEXT, encoding="utf-8")
    return directory


def _head(repo: Path) -> str:
    return run_test_git(repo, "rev-parse", "HEAD").strip()


def _fix_prompt(io_dir: Path, *extra: str) -> Result:
    return runner.invoke(
        app,
        [
            "_fix-prompt",
            "--issue",
            "#301",
            "--issue-file",
            "issue.md",
            "--io-dir",
            str(io_dir),
            "--commit-to",
            "current",
            *extra,
        ],
    )


def _commit_args(repo: Path, report: Path, **overrides: str | None) -> list[str]:
    values: dict[str, str | None] = {
        "--subject": "fix",
        "--issue": "301",
        "--commit-to": "current",
        "--start-head": _head(repo),
        "--start-branch": "main",
        "--report-file": str(report),
    }
    values.update(overrides)
    args: list[str] = []
    for flag, value in values.items():
        if value is not None:
            args += [flag, value]
    return args


def _report_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "report.txt"
    path.write_text(text, encoding="utf-8")
    return path


# --- sq _fix-prompt ---


def test_fix_prompt_prints_the_prompt(in_repo: Path, io_dir: Path) -> None:
    result = _fix_prompt(io_dir)
    assert result.exit_code == 0, result.output
    assert "# Fix issue #301" in result.output
    assert ISSUE_TEXT.strip() in result.output


def test_fix_prompt_refuses_a_dirty_tree(in_repo: Path, io_dir: Path) -> None:
    (in_repo / "scratch.txt").write_text("x")
    result = _fix_prompt(io_dir)
    assert result.exit_code == 1
    assert "scratch.txt" in result.output


def test_fix_prompt_exits_1_on_an_unreadable_cf_config(in_repo: Path, io_dir: Path) -> None:
    cf = MagicMock()
    cf.get_config.side_effect = ContextForgeError("cf is down")
    with patch("squadron.cli.commands.fix_prompt_run.ContextForgeClient", return_value=cf):
        result = runner.invoke(
            app,
            ["_fix-prompt", "--issue", "301", "--issue-file", "issue.md", "--io-dir", str(io_dir)]
            + ["--commit-to", "target"],
        )
    assert result.exit_code == 1
    assert "git.integration_branch" in result.output


def test_fix_prompt_accepts_the_io_dir_flag_and_is_hidden(in_repo: Path, io_dir: Path) -> None:
    assert _fix_prompt(io_dir).exit_code == 0
    assert "_fix-prompt" not in runner.invoke(app, ["--help"]).output


# --- sq _commit --subject fix ---


def test_commit_makes_the_fix_commit(in_repo: Path, tmp_path: Path) -> None:
    args = _commit_args(in_repo, _report_file(tmp_path, _reply()))
    (in_repo / "README.md").write_text("fixed\n")

    result = runner.invoke(app, ["_commit", *args])

    assert result.exit_code == 0, result.output
    assert run_test_git(in_repo, "log", "-1", "--format=%B").strip() == (
        f"fix: {SUMMARY}\n\nFixes #301"
    )


@pytest.mark.parametrize(
    "flag", ["--issue", "--commit-to", "--start-head", "--start-branch", "--report-file"]
)
def test_commit_refuses_each_missing_flag_by_name(in_repo: Path, tmp_path: Path, flag: str) -> None:
    args = _commit_args(in_repo, _report_file(tmp_path, _reply()), **{flag: None})
    result = runner.invoke(app, ["_commit", *args])
    assert result.exit_code == 1
    assert flag in result.output


@pytest.mark.parametrize(
    "reply",
    [
        _reply(gates=[]),
        _reply(failed_before_change=False),
        json.dumps({"blocked": "needs a decision"}),
        "no report at all",
    ],
)
def test_commit_refuses_a_bad_report_with_the_parser_text(
    in_repo: Path, tmp_path: Path, reply: str
) -> None:
    (in_repo / "README.md").write_text("fixed\n")
    with pytest.raises(FixReportError) as expected:
        parse_fix_report(reply)

    result = runner.invoke(app, ["_commit", *_commit_args(in_repo, _report_file(tmp_path, reply))])

    assert result.exit_code == 1
    assert str(expected.value) in result.output.replace("\n", " ")
    assert run_test_git(in_repo, "log", "-1", "--format=%s").strip() == "init"


def test_commit_exits_1_on_an_unreadable_report_file(in_repo: Path, tmp_path: Path) -> None:
    result = runner.invoke(app, ["_commit", *_commit_args(in_repo, tmp_path / "missing.txt")])
    assert result.exit_code == 1
    assert "missing.txt" in result.output


def test_commit_exits_1_on_a_non_utf8_report_file(in_repo: Path, tmp_path: Path) -> None:
    report = tmp_path / "report.bin"
    report.write_bytes(b"\xff\xfe\x00bad")
    result = runner.invoke(app, ["_commit", *_commit_args(in_repo, report)])
    assert result.exit_code == 1
    assert "report.bin" in result.output


@pytest.mark.parametrize("flag", ["--issue", "--commit-to", "--start-head", "--start-branch"])
def test_fix_flags_are_rejected_for_another_subject(in_repo: Path, flag: str) -> None:
    result = runner.invoke(app, ["_commit", "--subject", "devlog", flag, "x"])
    assert result.exit_code == 1
    assert flag in result.output
    assert "--subject fix" in result.output


def test_report_file_flag_is_rejected_without_a_subject(in_repo: Path, tmp_path: Path) -> None:
    result = runner.invoke(app, ["_commit", "--report-file", str(tmp_path / "r.txt")])
    assert result.exit_code == 1
    assert "--report-file" in result.output


@pytest.mark.parametrize(
    "extra",
    [
        ["--slice", "5"],
        ["--plan", "100"],
        ["--template", "code"],
        ["--round", "2"],
        ["--path", "a.txt"],
        ["--message", "text"],
    ],
)
def test_commit_fix_refuses_the_scoped_commit_flags_it_would_ignore(
    in_repo: Path, tmp_path: Path, extra: list[str]
) -> None:
    args = _commit_args(in_repo, _report_file(tmp_path, _reply()))
    result = runner.invoke(app, ["_commit", *args, *extra])
    assert result.exit_code == 1
    assert "--subject fix does not take" in result.output
    assert extra[0] in result.output


@pytest.mark.parametrize(
    ("flag", "value", "fragment"),
    [
        ("--commit-to", "elsewhere", "--commit-to must be one of"),
        ("--start-head", "  ", "--start-head must not be blank"),
        ("--start-branch", "", "--start-branch must not be blank"),
    ],
)
def test_commit_fix_validates_its_values_at_the_boundary(
    in_repo: Path, tmp_path: Path, flag: str, value: str, fragment: str
) -> None:
    args = _commit_args(in_repo, _report_file(tmp_path, _reply()), **{flag: value})
    result = runner.invoke(app, ["_commit", *args])
    assert result.exit_code == 1
    assert fragment in result.output
