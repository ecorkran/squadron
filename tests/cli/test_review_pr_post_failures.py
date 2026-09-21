"""D8: transport failure and timeout at each of the four post-path host calls.

Kept separate from ``test_review_pr_post.py``'s decision table: this is one
assertion shape (exit 1, zero writes) applied across four call sites, and
mixing it into the semantic table would obscure both.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.codehost.github_cli import HOST_COMMAND_TIMEOUT_SECONDS, GitHubCli
from squadron.codehost.models import PullRequestRecord
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError
from squadron.review.models import ReviewResult, Verdict
from squadron.review.pr_comment import marker_for
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"
_FIXTURES = Path(__file__).parent.parent / "codehost" / "fixtures" / "gh"

BASE_SHA = "4edf5f1709489da9494906b2178e27dea6a9ae10"
HEAD_SHA = "b67cf55495f01bc2da843d8f96c767a11770e330"
MERGE_BASE = "1111111111111111111111111111111111111111"

_PARITY_BASE = ["review", "pr", "83", "--no-tools", "--no-save"]

_MARKER = marker_for(
    PullRequestRecord(
        host=GITHUB,
        owner="ecorkran",
        repository="squadron",
        number=83,
        base_ref="main",
        head_ref="feature",
        head_sha=HEAD_SHA,
        url=f"https://{GITHUB}/ecorkran/squadron/pull/83",
    )
)


@pytest.fixture(autouse=True)
def _hermetic_pr_repo(pr_review_repo: Path) -> None:
    """Every test here runs `sq review pr`, whose range resolution is real git.

    Without this the tests read whatever refs the surrounding checkout happens
    to carry, so they pass on a developer machine that has run a live review and
    fail in a clean clone.
    """


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _ok(stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


def _fail(returncode: int, stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=returncode, stdout=stdout, stderr="")


def _resolve_script() -> list[tuple[list[str], ProcessResult | Exception]]:
    return [
        (["git", "remote"], _ok("origin\n")),
        (["git", "remote", "get-url"], _ok(f"https://{GITHUB}/ecorkran/squadron.git\n")),
        (["gh", "api", "graphql"], _ok(_fixture("pr83-resolve.json"))),
        (["git", "fetch"], _ok()),
        (["git", "rev-parse", "--verify"], _ok(BASE_SHA)),
        (["git", "rev-parse", "--verify"], _ok(HEAD_SHA)),
        (["git", "merge-base"], _ok(MERGE_BASE)),
        (["git", "diff", "--name-only"], _ok("src/a.py\n")),
        (["gh", "api", "graphql"], _ok(_fixture("pr83-reviewthreads.json"))),
    ]


def _pr_resolve_payload(head_sha: str = HEAD_SHA) -> str:
    return json.dumps(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "number": 83,
                        "title": "t",
                        "body": "b",
                        "state": "OPEN",
                        "author": {"login": "mikemikimike"},
                        "url": f"https://{GITHUB}/ecorkran/squadron/pull/83",
                        "baseRefName": "main",
                        "headRefName": "feature",
                        "baseRefOid": BASE_SHA,
                        "headRefOid": head_sha,
                        "isCrossRepository": True,
                        "headRepository": {"nameWithOwner": "mikemikimike/squadron"},
                        "closingIssuesReferences": {"nodes": []},
                    }
                }
            }
        }
    )


def _comments_page(*comments: dict[str, object]) -> str:
    return json.dumps(list(comments))


@pytest.fixture
def hosts_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "gh"
    config_dir.mkdir()
    (config_dir / "hosts.yml").write_text(f"{GITHUB}:\n  user: ecorkran\n")
    monkeypatch.setenv("GH_CONFIG_DIR", str(config_dir))
    return config_dir


@pytest.fixture
def patched_host(monkeypatch: pytest.MonkeyPatch, hosts_file: Path) -> Iterator[dict[str, object]]:
    captured: dict[str, object] = {"runner": None}
    script_holder: dict[str, list[tuple[list[str], ProcessResult | Exception]]] = {"script": []}

    def _build(_runner: object) -> GitHubCli:
        from squadron.codehost.github_config import read_gh_hosts

        fake = FakeProcessRunner(script_holder["script"])
        captured["runner"] = fake
        return GitHubCli(fake, frozenset({GITHUB, *read_gh_hosts()}))

    monkeypatch.setattr("squadron.cli.commands.pr.build_github_host", _build)
    captured["script_holder"] = script_holder  # type: ignore[assignment]
    yield captured


@pytest.fixture
def fake_result(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    def _fake(*_args: object, **_kwargs: object) -> ReviewResult:
        return ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="ok",
            template_name="code",
            input_files={"input": "pr"},
            timestamp=datetime(2026, 4, 1, 12, 0, 0),
            model="z-ai/glm-5.3",
        )

    monkeypatch.setattr("squadron.cli.commands.review_pr._run_review_command", _fake)
    return _fake


def _arm(
    patched_host: dict[str, object], *script_tail: tuple[list[str], ProcessResult | Exception]
) -> None:
    holder = patched_host["script_holder"]
    script = _resolve_script() + list(script_tail)
    holder["script"] = script  # type: ignore[index]


def _runner_of(patched_host: dict[str, object]) -> FakeProcessRunner:
    runner = patched_host["runner"]
    assert isinstance(runner, FakeProcessRunner)
    return runner


#: (label, script tail up to and including the failing call). Each entry's
#: failing call is the last one in the tail; sites after it are never reached
#: on a real run, so nothing follows it in the script.
_SITE_SCRIPT_PREFIXES: dict[str, list[tuple[list[str], ProcessResult | Exception]]] = {
    "identity": [],
    "discovery": [(["gh", "api", "user"], _ok(_fixture("user.json")))],
    "head_read": [
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["gh", "api", "--paginate"], _ok(_comments_page())),
    ],
    "write": [
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["gh", "api", "--paginate"], _ok(_comments_page())),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload())),
    ],
}

_SITE_FAILING_CALL: dict[str, list[str]] = {
    "identity": ["gh", "api", "user"],
    "discovery": ["gh", "api", "--paginate"],
    "head_read": ["gh", "api", "graphql"],
    "write": ["gh", "api", "-X", "POST"],
}


def _assert_no_successful_write(runner: FakeProcessRunner, *, site: str) -> None:
    """No comment was ever actually written, at any of the four sites.

    At ``identity``, ``discovery``, and ``head_read`` the failure happens
    strictly before the write call is ever made, so ``write_calls()`` — which
    counts any recorded ``-X POST``/``-X PATCH`` argv, attempted or not — is
    empty outright. At ``write`` the failing call *is* the one write attempt:
    it is recorded (an accurate account of what was tried), but it never
    returned a comment, so there is exactly one attempt and never a second
    one racing in to duplicate it.
    """
    writes = runner.write_calls()
    if site == "write":
        assert len(writes) == 1, "expected exactly one write attempt, not a retry or a duplicate"
    else:
        assert writes == []


@pytest.mark.parametrize("site", ["identity", "discovery", "head_read", "write"])
def test_transport_failure_at_each_site_exits_one_with_zero_writes(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object, site: str
) -> None:
    failing_call = _SITE_FAILING_CALL[site]
    _arm(
        patched_host,
        *_SITE_SCRIPT_PREFIXES[site],
        (failing_call, _fail(1, '{"status":"500","message":"boom"}')),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post"])

    assert result.exit_code == 1, result.output
    runner = _runner_of(patched_host)
    _assert_no_successful_write(runner, site=site)
    if site == "head_read":
        # The one site whose failure could plausibly be papered over by
        # omitting the staleness line — assert no comment reached the host.
        assert not any("POST" in call.argv or "PATCH" in call.argv for call in runner.calls)


@pytest.mark.parametrize("site", ["identity", "discovery", "head_read", "write"])
def test_scripted_timeout_at_each_site_exits_one_with_zero_writes(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object, site: str
) -> None:
    failing_call = _SITE_FAILING_CALL[site]
    _arm(
        patched_host,
        *_SITE_SCRIPT_PREFIXES[site],
        (failing_call, ProcessTimedOutError(failing_call, float(HOST_COMMAND_TIMEOUT_SECONDS))),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post"])

    assert result.exit_code == 1, result.output
    runner = _runner_of(patched_host)
    _assert_no_successful_write(runner, site=site)


def test_every_post_path_call_carries_the_host_timeout(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["gh", "api", "--paginate"], _ok(_comments_page())),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload())),
        (
            ["gh", "api", "-X", "POST"],
            _ok(json.dumps({"id": 1, "html_url": "https://example/1", "body": "x"})),
        ),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post"])

    assert result.exit_code == 0, result.output
    runner = _runner_of(patched_host)
    # The last four recorded calls are exactly identity, discovery, the head
    # re-read, and the write — everything the resolve+fetch+discussion script
    # makes precedes them.
    post_path_calls = runner.calls[-4:]
    assert len(post_path_calls) == 4
    for call in post_path_calls:
        assert call.timeout == HOST_COMMAND_TIMEOUT_SECONDS


def test_save_succeeded_write_failed_leaves_the_artifact_in_place(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object, tmp_path: Path
) -> None:
    """A failed post must never touch what the save step already wrote."""
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["gh", "api", "--paginate"], _ok(_comments_page())),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload())),
        (["gh", "api", "-X", "POST"], _fail(1, '{"status":"500","message":"boom"}')),
    )
    result = cli_runner.invoke(
        app, ["review", "pr", "83", "--no-tools", "--reviews-dir", str(tmp_path), "--post"]
    )

    assert result.exit_code == 1, result.output
    saved = list(tmp_path.glob("*review*"))
    assert saved, "expected the save step's artifact to remain on disk"
