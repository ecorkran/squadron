"""``sq review pr --post`` / ``--dry-run``: the D5 decision table (384).

Mirrors ``test_review_pr.py``'s ``patched_host`` seam. The zero-writes
assertion is the one 381 built ``FakeProcessRunner.write_calls()`` for: a
full invocation with no post flag must record no write at all, not merely no
comment write.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.codehost.github_cli import GitHubCli
from squadron.codehost.models import PullRequestRecord
from squadron.core.process_runner import ProcessResult
from squadron.review.models import ReviewResult, Verdict
from squadron.review.pr_comment import marker_for
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"
_FIXTURES = Path(__file__).parent.parent / "codehost" / "fixtures" / "gh"

BASE_SHA = "4edf5f1709489da9494906b2178e27dea6a9ae10"
HEAD_SHA = "b67cf55495f01bc2da843d8f96c767a11770e330"
MERGE_BASE = "1111111111111111111111111111111111111111"

_PARITY_BASE = ["review", "pr", "83", "--no-tools", "--no-save"]

#: The exact marker _post_review builds for PR #83 — comment fixtures must
#: quote this, not an invented placeholder, or discovery never matches.
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


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _ok(stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


def _fail(returncode: int, stdout: str = "", stderr: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=returncode, stdout=stdout, stderr=stderr)


def _resolve_script() -> list[tuple[list[str], ProcessResult | Exception]]:
    """Target resolution + fetch + discussion lookup, as one ``sq review pr`` run makes."""
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
    """A minimal GraphQL PR node, with a controllable head sha for D7 tests."""
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


def _comment(comment_id: int, login: str, body: str, created_at: str) -> dict[str, object]:
    return {
        "id": comment_id,
        "user": {"login": login},
        "body": body,
        "created_at": created_at,
        "html_url": f"https://example/{comment_id}",
    }


def _comment_from_deleted_account(comment_id: int, body: str, created_at: str) -> dict[str, object]:
    """A comment whose author account no longer exists: no ``user`` object at all."""
    return {
        "id": comment_id,
        "user": None,
        "body": body,
        "created_at": created_at,
        "html_url": f"https://example/{comment_id}",
    }


def _post_result(payload: dict[str, object]) -> str:
    return json.dumps(payload)


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
    """Stub the review call with a real, minimal ReviewResult.

    Unlike ``test_review_pr.py``'s ``captured_review``, the post path needs a
    genuine ``ReviewResult`` — ``compose_comment`` reads ``.verdict``,
    ``.model``, and ``.structured_findings`` from it.
    """

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


# ---------------------------------------------------------------------------
# Task 4.3 — the default and the --dry-run guard
# ---------------------------------------------------------------------------


def test_default_run_records_zero_write_calls(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    """No --post: FakeProcessRunner.write_calls() is empty across the whole invocation."""
    _arm(patched_host)
    result = cli_runner.invoke(app, _PARITY_BASE)

    assert result.exit_code == 0, result.output
    runner = _runner_of(patched_host)
    assert runner.write_calls() == []


def test_dry_run_without_post_exits_one_with_zero_calls(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    holder = patched_host["script_holder"]
    holder["script"] = []  # type: ignore[index]
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--dry-run"])

    assert result.exit_code == 1
    assert "--dry-run requires --post" in result.output


# ---------------------------------------------------------------------------
# Task 5.5 — the D5 decision table, row by row
# ---------------------------------------------------------------------------


def test_no_marked_comments_posts(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["gh", "api", "--paginate"], _ok(_comments_page())),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload())),
        (
            ["gh", "api", "-X", "POST"],
            _ok(_post_result({"id": 1, "html_url": "https://example/1", "body": "x"})),
        ),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post"])

    assert result.exit_code == 0, result.output
    runner = _runner_of(patched_host)
    argvs = [call.argv for call in runner.write_calls()]
    assert any("POST" in argv for argv in argvs)
    assert not any("PATCH" in argv for argv in argvs)


def test_two_consecutive_posts_by_the_same_login_update(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    """First run posts; second finds its own comment and updates it."""
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (
            ["gh", "api", "--paginate"],
            _ok(_comments_page(_comment(7, "ecorkran", f"prior {_MARKER}", "2026-01-01T00:00:00Z"))),
        ),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload())),
        (
            ["gh", "api", "-X", "PATCH"],
            _ok(_post_result({"id": 7, "html_url": "https://example/7", "body": "x"})),
        ),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post"])

    assert result.exit_code == 0, result.output
    runner = _runner_of(patched_host)
    argvs = [call.argv for call in runner.write_calls()]
    assert any("PATCH" in argv and "issues/comments/7" in " ".join(argv) for argv in argvs)


def test_another_logins_marked_comment_is_not_updated(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    """A marked comment by another login: post_comment runs, no PATCH to its id."""
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (
            ["gh", "api", "--paginate"],
            _ok(
                _comments_page(
                    _comment(9, "someone-else", f"quoting {_MARKER}", "2026-01-01T00:00:00Z")
                )
            ),
        ),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload())),
        (
            ["gh", "api", "-X", "POST"],
            _ok(_post_result({"id": 10, "html_url": "https://example/10", "body": "x"})),
        ),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post"])

    assert result.exit_code == 0, result.output
    assert "someone-else" in result.output
    runner = _runner_of(patched_host)
    argvs = [call.argv for call in runner.write_calls()]
    assert any("POST" in argv for argv in argvs)
    assert not any("issues/comments/9" in " ".join(argv) for argv in argvs)


def test_a_deleted_accounts_marked_comment_is_reported_without_a_blank_author(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    """A comment with no user object at all is still reported legibly, not as a blank name."""
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (
            ["gh", "api", "--paginate"],
            _ok(
                _comments_page(
                    _comment_from_deleted_account(11, f"quoting {_MARKER}", "2026-01-01T00:00:00Z")
                )
            ),
        ),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload())),
        (
            ["gh", "api", "-X", "POST"],
            _ok(_post_result({"id": 12, "html_url": "https://example/12", "body": "x"})),
        ),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post"])

    assert result.exit_code == 0, result.output
    assert "Marked comment by , " not in result.output
    assert "an unknown author" in result.output


def test_several_of_my_own_updates_earliest_and_reports_rest(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    """Supplied out of chronological order: update the earliest, report the rest."""
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (
            ["gh", "api", "--paginate"],
            _ok(
                _comments_page(
                    _comment(2, "ecorkran", f"later {_MARKER}", "2026-03-01T00:00:00Z"),
                    _comment(1, "ecorkran", f"earlier {_MARKER}", "2026-01-01T00:00:00Z"),
                )
            ),
        ),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload())),
        (
            ["gh", "api", "-X", "PATCH"],
            _ok(_post_result({"id": 1, "html_url": "https://example/1", "body": "x"})),
        ),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post"])

    assert result.exit_code == 0, result.output
    assert "https://example/2" in result.output
    runner = _runner_of(patched_host)
    argvs = [call.argv for call in runner.write_calls()]
    assert any("issues/comments/1" in " ".join(argv) for argv in argvs)
    assert not any("issues/comments/2" in " ".join(argv) for argv in argvs)


def test_identity_refusal_exits_one_with_no_calls_after_identity(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(json.dumps({"login": ""}))),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post"])

    assert result.exit_code == 1
    runner = _runner_of(patched_host)
    calls = runner.calls
    identity_index = next(i for i, call in enumerate(calls) if call.argv[:3] == ("gh", "api", "user"))
    assert calls[identity_index + 1 :] == []


def test_save_failed_post_succeeded_exits_one_for_save(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    """D6: the post is not gated on the save outcome."""
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["gh", "api", "--paginate"], _ok(_comments_page())),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload())),
        (
            ["gh", "api", "-X", "POST"],
            _ok(_post_result({"id": 1, "html_url": "https://example/1", "body": "x"})),
        ),
    )
    with patch(
        "squadron.cli.commands.review_pr.save_review_result",
        side_effect=OSError("read-only filesystem"),
    ):
        result = cli_runner.invoke(app, ["review", "pr", "83", "--no-tools", "--post"])

    assert result.exit_code == 1, result.output
    runner = _runner_of(patched_host)
    argvs = [call.argv for call in runner.write_calls()]
    assert any("POST" in argv for argv in argvs)


# ---------------------------------------------------------------------------
# Task 5.6 — dry-run/real equality
# ---------------------------------------------------------------------------


def test_dry_run_stdout_equals_the_real_posts_body(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["gh", "api", "--paginate"], _ok(_comments_page())),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload())),
    )
    dry_result = cli_runner.invoke(app, [*_PARITY_BASE, "--post", "--dry-run"])
    assert dry_result.exit_code == 0, dry_result.output
    dry_body = dry_result.stdout

    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["gh", "api", "--paginate"], _ok(_comments_page())),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload())),
        (
            ["gh", "api", "-X", "POST"],
            _ok(_post_result({"id": 1, "html_url": "https://example/1", "body": "x"})),
        ),
    )
    real_result = cli_runner.invoke(app, [*_PARITY_BASE, "--post"])
    assert real_result.exit_code == 0, real_result.output

    runner = _runner_of(patched_host)
    post_calls = [c for c in runner.calls if "-X" in c.argv and "POST" in c.argv]
    assert post_calls, "no POST call recorded"
    posted_body = json.loads(post_calls[0].stdin or "{}")["body"]

    assert dry_body.strip() == posted_body.strip()


# ---------------------------------------------------------------------------
# Task 6.3 — the staleness statement, both branches, and the head-read refusal
# ---------------------------------------------------------------------------

_MOVED_HEAD = "cccccccccccccccccccccccccccccccccccccccc"


def test_moved_head_includes_the_staleness_line(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    """The live head differs from what was reviewed: the comment says so."""
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["gh", "api", "--paginate"], _ok(_comments_page())),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload(head_sha=_MOVED_HEAD))),
        (
            ["gh", "api", "-X", "POST"],
            _ok(_post_result({"id": 1, "html_url": "https://example/1", "body": "x"})),
        ),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "**Stale:**" in result.stdout
    assert HEAD_SHA[:7] in result.stdout
    assert _MOVED_HEAD[:7] in result.stdout


def test_unmoved_head_has_no_staleness_line(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    """The live head still matches what was reviewed: no staleness line anywhere."""
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["gh", "api", "--paginate"], _ok(_comments_page())),
        (["gh", "api", "graphql"], _ok(_pr_resolve_payload(head_sha=HEAD_SHA))),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Stale" not in result.stdout


def test_head_read_failure_refuses_the_post_with_no_write(
    cli_runner: CliRunner, patched_host: dict[str, object], fake_result: object
) -> None:
    """The one site whose failure could plausibly be papered over (D7, D8).

    A transport failure at the post-time head re-read must exit 1 with zero
    writes and no comment posted — never a comment whose staleness statement
    could not be computed.
    """
    _arm(
        patched_host,
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["gh", "api", "--paginate"], _ok(_comments_page())),
        (["gh", "api", "graphql"], _fail(1, stdout='{"status":"500","message":"boom"}')),
    )
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--post"])

    assert result.exit_code == 1, result.output
    runner = _runner_of(patched_host)
    assert runner.write_calls() == []
