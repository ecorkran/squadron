"""Shared setup for the lagging pull-request-ref scenario (slice 934, #186).

One pull request (the ``pr83-resolve.json`` fixture) whose ``refs/pull/83/head``
reads a stale sha while the host API reports the real head. Used by the adapter
tests and by the ``sq review pr`` artifact test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from squadron.codehost.github_cli import GitHubCli
from squadron.codehost.models import RepositoryLocator
from squadron.codehost.targets import parse_target
from squadron.core.process_runner import ProcessResult
from tests.codehost.fake_runner import FakeProcessRunner

HOSTS = frozenset({"github.com"})
_FIXTURES = Path(__file__).parent / "fixtures" / "gh"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _ok(stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


def _fail(returncode: int, stdout: str = "", stderr: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=returncode, stdout=stdout, stderr=stderr)


RESOLVED_BASE = "4edf5f1709489da9494906b2178e27dea6a9ae10"
RESOLVED_HEAD = "b67cf55495f01bc2da843d8f96c767a11770e330"
LAGGING_PR_REF = "8888888888888888888888888888888888888888"
HEAD_BRANCH = "codex/issue-82-diff-review-context"
API_LOCAL = "refs/squadron/pr/origin/83/api-head"


def resolved_pr83(runner: FakeProcessRunner) -> tuple[GitHubCli, Any]:
    cli = GitHubCli(runner, HOSTS)
    target = parse_target("83")
    locator = RepositoryLocator("github.com", "ecorkran", "squadron", "origin")
    return cli, cli.resolve_pull_request(locator, target, cwd="/repo")


def lagging_script(*, fallback_returns: str) -> list[tuple[list[str], ProcessResult | Exception]]:
    return [
        (["gh", "api", "graphql"], _ok(_fixture("pr83-resolve.json"))),
        (
            ["git", "fetch", "--no-tags", "origin", "+refs/heads/main:refs/squadron/pr/origin/83/base"],
            _ok(),
        ),
        (
            ["git", "rev-parse", "--verify", "refs/squadron/pr/origin/83/base^{commit}"],
            _ok(RESOLVED_BASE),
        ),
        (
            ["git", "rev-parse", "--verify", "refs/squadron/pr/origin/83/head^{commit}"],
            _ok(LAGGING_PR_REF),
        ),
        (["git", "cat-file", "-e"], _fail(1)),
        (
            ["git", "fetch", "--no-tags", "origin", f"+{RESOLVED_HEAD}:{API_LOCAL}"],
            _fail(1, stderr="not our ref"),
        ),
        (["git", "fetch", "--no-tags", "origin", f"+refs/heads/{HEAD_BRANCH}:{API_LOCAL}"], _ok()),
        (["git", "rev-parse", "--verify", f"{API_LOCAL}^{{commit}}"], _ok(fallback_returns)),
        (["git", "merge-base", "--is-ancestor", LAGGING_PR_REF, RESOLVED_HEAD], _ok()),
        (["git", "update-ref"], _ok()),
        (["git", "merge-base"], _ok("1" * 40)),
        (["git", "diff", "--name-only"], _ok("src/a.py\n")),
    ]
