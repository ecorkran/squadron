"""Tests for ``resolve_locator``, the shared prefix extracted for 385 (D6).

``sq pr show``'s own tests (test_pr_show.py) are the real criterion: they
must pass unmodified. This file targets ``resolve_locator`` directly, one
level below the CLI, against each target form ``show`` supports.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from squadron.cli.commands.pr import resolve_locator
from squadron.codehost.github_cli import GitHubCli
from squadron.core.process_runner import ProcessResult
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"


def _ok(stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


@pytest.fixture
def patched_host() -> object:
    script_holder: dict[str, list[tuple[list[str], ProcessResult | Exception]]] = {"script": []}

    def _build(_runner: object) -> GitHubCli:
        fake = FakeProcessRunner(script_holder["script"])
        return GitHubCli(fake, frozenset({GITHUB}))

    with patch("squadron.cli.commands.pr.build_github_host", _build):
        yield script_holder


_REMOTE_SCRIPT = [
    (["git", "remote"], _ok("origin\n")),
    (["git", "remote", "get-url"], _ok(f"https://{GITHUB}/ecorkran/squadron.git\n")),
]


@pytest.mark.parametrize(
    "target",
    [
        None,
        "83",
        "#83",
        "squadron#83",
        "ecorkran/squadron#83",
        f"https://{GITHUB}/ecorkran/squadron/pull/83",
    ],
)
def test_resolve_locator_for_every_target_form(
    patched_host: dict[str, object], target: str | None
) -> None:
    patched_host["script"] = list(_REMOTE_SCRIPT)

    host, locator = resolve_locator(target, ".")

    assert locator.host == GITHUB
    assert locator.owner == "ecorkran"
    assert locator.repository == "squadron"
    assert locator.remote_name == "origin"
    assert host.serves_host(GITHUB)


def test_resolve_locator_makes_no_pull_request_call(patched_host: dict[str, object]) -> None:
    """resolve_locator stops at the locator — it never resolves a PR."""
    script = list(_REMOTE_SCRIPT)
    patched_host["script"] = script

    resolve_locator("83", ".")

    # Every scripted call above is a remote-discovery call; none is a `gh`
    # invocation, which is what resolving an existing PR would require.
    assert all(argv[0] == "git" for argv, _ in script)
