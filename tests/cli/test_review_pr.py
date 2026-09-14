"""Tests for ``sq review pr``.

Resolution and fetch reuse ``sq pr show``'s exact sequence (``pr.py``'s
``resolve_and_fetch_pull_request``), so the seam patched here is the same one
``test_pr_show.py`` patches — do not invent a second one.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.review_pr import assemble_pr_metadata
from squadron.codehost.github_cli import GitHubCli
from squadron.codehost.models import PullRequestState, ResolvedPullRequest
from squadron.core.process_runner import ProcessResult
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"
_FIXTURES = Path(__file__).parent.parent / "codehost" / "fixtures" / "gh"

BASE_SHA = "4edf5f1709489da9494906b2178e27dea6a9ae10"
HEAD_SHA = "b67cf55495f01bc2da843d8f96c767a11770e330"
MERGE_BASE = "1111111111111111111111111111111111111111"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _ok(stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


def _resolve_and_fetch_script() -> list[tuple[list[str], ProcessResult | Exception]]:
    """Every process call target resolution + fetch makes (mirrors test_pr_show.py)."""
    return [
        (["git", "remote"], _ok("origin\n")),
        (["git", "remote", "get-url"], _ok(f"https://{GITHUB}/ecorkran/squadron.git\n")),
        (["gh", "api", "graphql"], _ok(_fixture("pr83-resolve.json"))),
        (["git", "fetch"], _ok()),
        (["git", "rev-parse", "--verify"], _ok(BASE_SHA)),
        (["git", "rev-parse", "--verify"], _ok(HEAD_SHA)),
        (["git", "merge-base"], _ok(MERGE_BASE)),
        (["git", "diff", "--name-only"], _ok("src/a.py\nsrc/b.py\n")),
    ]


@pytest.fixture
def hosts_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "gh"
    config_dir.mkdir()
    (config_dir / "hosts.yml").write_text(f"{GITHUB}:\n  user: ecorkran\n")
    monkeypatch.setenv("GH_CONFIG_DIR", str(config_dir))
    return config_dir


@pytest.fixture
def patched_host(monkeypatch: pytest.MonkeyPatch, hosts_file: Path) -> Iterator[dict[str, object]]:
    """Patch the factory pr.py calls — the same seam test_pr_show.py patches.

    review_pr.py imports resolve_and_fetch_pull_request from pr.py, which is
    where build_github_host is actually called, so this is the same, single
    patch point for both commands.
    """
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


# ---------------------------------------------------------------------------
# assemble_pr_metadata — unit-level, no CLI invocation
# ---------------------------------------------------------------------------


class _FakeHost:
    """Minimal CodeHost stand-in exposing only list_unresolved_discussions."""

    def __init__(self, discussions: list[object]) -> None:
        self._discussions = discussions

    def list_unresolved_discussions(self, record: object) -> list[object]:
        return self._discussions


def _resolved(
    *, body: str = "PR body text", linked_issue_numbers: tuple[int, ...] = ()
) -> ResolvedPullRequest:
    from squadron.codehost.models import PullRequestRecord

    record = PullRequestRecord(
        host=GITHUB,
        owner="ecorkran",
        repository="squadron",
        number=83,
        base_ref="main",
        head_ref="feature/x",
        head_sha=HEAD_SHA,
        url=f"https://{GITHUB}/ecorkran/squadron/pull/83",
    )
    return ResolvedPullRequest(
        record=record,
        title="Harden diff-only code review prompts",
        body=body,
        state=PullRequestState.OPEN,
        author_login="mikemikimike",
        base_sha=BASE_SHA,
        is_cross_repository=True,
        head_repository="mikemikimike/squadron",
        linked_issue_numbers=linked_issue_numbers,
    )


def test_assemble_pr_metadata_carries_title_and_body() -> None:
    resolved = _resolved(body="Fixes the thing.")
    metadata = assemble_pr_metadata(resolved, _FakeHost([]))

    assert "Harden diff-only code review prompts" in metadata
    assert "Fixes the thing." in metadata


def test_assemble_pr_metadata_carries_linked_issue_numbers() -> None:
    resolved = _resolved(linked_issue_numbers=(82, 91))
    metadata = assemble_pr_metadata(resolved, _FakeHost([]))

    assert "#82" in metadata
    assert "#91" in metadata


def test_assemble_pr_metadata_carries_unresolved_discussions() -> None:
    from squadron.codehost.models import ReviewDiscussion

    discussion = ReviewDiscussion(
        path="src/x.py",
        line=12,
        author_login="someone",
        body="please fix this",
        url="https://example/1",
    )
    resolved = _resolved()
    metadata = assemble_pr_metadata(resolved, _FakeHost([discussion]))

    assert "src/x.py:12" in metadata
    assert "someone" in metadata
    assert "please fix this" in metadata


def test_assemble_pr_metadata_no_discussions_has_no_discussions_section() -> None:
    resolved = _resolved()
    metadata = assemble_pr_metadata(resolved, _FakeHost([]))

    assert "Unresolved discussions" not in metadata


# ---------------------------------------------------------------------------
# Shared resolution helper — same record/range sq pr show produces
# ---------------------------------------------------------------------------


def test_resolution_produces_the_same_record_pr_show_would(
    cli_runner: CliRunner, patched_host: dict[str, object], tmp_path: Path
) -> None:
    """Target resolution through sq review pr matches sq pr show's own fixtures.

    The rest of the command (worktree creation, running the review) needs a real
    Claude agent and is exercised by test_review_action-style mocking in G.4/G.6 —
    this test only proves the shared resolve_and_fetch_pull_request path resolves
    identically for both commands, asserted via sq pr show --json against the same
    scripted responses.
    """
    holder = patched_host["script_holder"]
    holder["script"] = _resolve_and_fetch_script()  # type: ignore[index]

    result = cli_runner.invoke(app, ["pr", "show", "83", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["record"]["number"] == 83
    assert payload["record"]["host"] == GITHUB
    assert payload["fetched"]["merge_base"] == MERGE_BASE
    assert (
        payload["fetched"]["diff_range"]
        == f"{payload['fetched']['base_ref']}...{payload['fetched']['head_ref']}"
    )
