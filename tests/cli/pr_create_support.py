"""Shared scaffolding for the ``sq pr create`` CLI tests.

The fixtures that use these live in ``tests/cli/conftest.py``; this module
holds the plain helpers and the scripted-call builders both test files need.
"""

from __future__ import annotations

import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from squadron.core.models import Message
from squadron.core.process_runner import ProcessResult
from squadron.providers.base import ProfileName
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"
HEAD_BRANCH = "scratch-branch"

#: ``create``'s default profile, rebound to a fake provider by the
#: ``fake_composer`` fixture so no test reaches a real model.
FAKE_PROFILE = ProfileName.SDK
FAKE_PROVIDER_TYPE = "fake-pr-create-provider"
FAKE_PROSE = "Some prose."

CREATE_CALL = ["gh", "api", "-X", "POST"]
CREATED_RESPONSE = '{"number":99,"html_url":"https://github.com/ecorkran/squadron/pull/99"}'

_FIXTURES = Path(__file__).parent.parent / "codehost" / "fixtures" / "gh"

Script = list[tuple[list[str], ProcessResult | Exception]]


def gh_fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def ok(stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


def fail(returncode: int = 1, stdout: str = "", stderr: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=returncode, stdout=stdout, stderr=stderr)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True, text=True)
    return result.stdout.strip()


def local_head_sha(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD")


class HostHarness:
    """The fake host's script and, once the command has built it, its runner."""

    def __init__(self) -> None:
        self.script: Script = []
        self._runner: FakeProcessRunner | None = None

    def build_runner(self) -> FakeProcessRunner:
        self._runner = FakeProcessRunner(self.script)
        return self._runner

    @property
    def runner(self) -> FakeProcessRunner:
        assert self._runner is not None, "the command never built a host"
        return self._runner


def make_fake_agent(content: str) -> MagicMock:
    async def _handle(message: Message) -> AsyncIterator[Message]:
        msg = MagicMock(spec=Message)
        msg.content = content
        msg.metadata = {}
        yield msg

    agent = MagicMock()
    agent.handle_message = _handle
    agent.shutdown = AsyncMock()
    return agent


#: The adapter-mediated calls of a full happy path, in order, keyed by the
#: call site each one serves. A failure test scripts every site before its
#: own and then the failing call itself.
CALL_SITES = (
    "remote_discovery",
    "identify_operator",
    "branch_exists",
    "ls_remote",
    "default_branch",
    "open_pull_request",
)


def _site_calls(local_sha: str) -> dict[str, Script]:
    return {
        "remote_discovery": [
            (["git", "remote"], ok("origin\n")),
            (["git", "remote", "get-url"], ok(f"https://{GITHUB}/ecorkran/squadron.git\n")),
            (["git", "rev-parse", "--abbrev-ref", "HEAD"], ok(f"{HEAD_BRANCH}\n")),
        ],
        "identify_operator": [(["gh", "api", "user"], ok(gh_fixture("user.json")))],
        "branch_exists": [
            (["git", "rev-parse", "HEAD"], ok(f"{local_sha}\n")),
            (
                ["gh", "api", f"repos/ecorkran/squadron/branches/{HEAD_BRANCH}"],
                ok(gh_fixture("repo.json")),
            ),
        ],
        "ls_remote": [
            (
                ["git", "ls-remote", "origin", f"refs/heads/{HEAD_BRANCH}"],
                ok(f"{local_sha}\trefs/heads/{HEAD_BRANCH}\n"),
            )
        ],
        "default_branch": [(["gh", "api", "repos/ecorkran/squadron"], ok(gh_fixture("repo.json")))],
        "open_pull_request": [(CREATE_CALL, ok(CREATED_RESPONSE))],
    }


def script_through(site: str, *, local_sha: str, skip: tuple[str, ...] = ()) -> Script:
    """Every successful call up to and including *site*, minus any in *skip*."""
    calls = _site_calls(local_sha)
    end = CALL_SITES.index(site) + 1
    return [call for name in CALL_SITES[:end] if name not in skip for call in calls[name]]


def script_before(site: str, *, local_sha: str) -> Script:
    """Every successful call preceding *site*'s own failing call.

    A site's last scripted call is the one that fails, so any calls the site
    makes before it (``branch_exists``'s local ``rev-parse``) are kept.
    """
    return script_through(site, local_sha=local_sha)[:-1]


def failing_call_of(site: str) -> list[str]:
    return _site_calls("")[site][-1][0]
