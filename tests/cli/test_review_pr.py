"""Tests for ``sq review pr``.

Resolution and fetch reuse ``sq pr show``'s exact sequence (``pr.py``'s
``resolve_and_fetch_pull_request``), so the seam patched here is the same one
``test_pr_show.py`` patches — do not invent a second one.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.review_pr import assemble_pr_metadata
from squadron.codehost.github_cli import GitHubCli
from squadron.codehost.models import PullRequestState, ResolvedPullRequest
from squadron.core.process_runner import ProcessResult
from squadron.review.persistence import REVIEWS_DIR
from squadron.review.reviews_dir import ReviewsDirRule
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"
_FIXTURES = Path(__file__).parent.parent / "codehost" / "fixtures" / "gh"

BASE_SHA = "4edf5f1709489da9494906b2178e27dea6a9ae10"
HEAD_SHA = "b67cf55495f01bc2da843d8f96c767a11770e330"
MERGE_BASE = "1111111111111111111111111111111111111111"


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


def test_discussion_fetch_failure_renders_as_an_adapter_error_not_a_traceback(
    patched_host: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F002 of the 382 code review: ``assemble_pr_metadata`` reaches the network too.

    It fetches unresolved discussions over the adapter, so a transport/auth failure there
    is an adapter failure like any other and must take the same rendered exit-1 path as a
    failed resolve — not escape as an unhandled traceback.
    """
    from squadron.codehost.errors import HostResponseMalformedError

    _arm(patched_host)

    def _raise(_self: object, _record: object) -> list[object]:
        raise HostResponseMalformedError(("gh", "graphql"), "reviewThreads missing from response")

    monkeypatch.setattr(GitHubCli, "list_unresolved_discussions", _raise)

    result = CliRunner().invoke(app, ["review", "pr", "83"])

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_assemble_pr_metadata_no_discussions_has_no_discussions_section() -> None:
    resolved = _resolved()
    metadata = assemble_pr_metadata(resolved, _FakeHost([]))

    assert "Unresolved discussions" not in metadata


# ---------------------------------------------------------------------------
# Shared resolution helper — same record/range sq pr show produces
# ---------------------------------------------------------------------------


@pytest.fixture
def captured_review(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Capture what each flag actually delivers to the review call.

    Asserting on the kwargs rather than on rendered output: this is the seam every
    flag converges on, and it does not move when display formatting changes.
    """
    calls: list[dict[str, object]] = []

    class _Result:
        verdict = "PASS"

    def _fake(*args: object, **kwargs: object) -> _Result:
        calls.append({"args": args, **kwargs})
        return _Result()

    monkeypatch.setattr("squadron.cli.commands.review_pr._run_review_command", _fake)
    return calls


def _arm(patched_host: dict[str, object]) -> None:
    """Load the script the fake runner replays for one ``sq review pr`` invocation.

    One call beyond ``_resolve_and_fetch_script()``: ``assemble_pr_metadata`` asks the
    host for unresolved discussions, which ``sq pr show`` never does. Kept here rather
    than in that helper, which is deliberately scoped to what ``pr show`` calls.
    """
    holder = patched_host["script_holder"]
    script = _resolve_and_fetch_script()
    script.append((["gh", "api", "graphql"], _ok(_fixture("pr83-reviewthreads.json"))))
    holder["script"] = script  # type: ignore[index]


#: Every case here runs on the ``--no-tools`` path. The flags under test are
#: unit-level — does this option reach the review call — and the worktree lifecycle
#: they would otherwise drive is real git work covered against a real repository in
#: ``test_review_pr_worktree.py``. ``--no-tools`` itself is covered there too, by
#: ``test_no_tools_uses_checkout_alone_no_worktree``.
_PARITY_BASE = ["review", "pr", "83", "--no-tools"]


@pytest.mark.parametrize(
    ("flags", "kwarg", "expected"),
    [
        (["--model", "opus"], "model_flag", "opus"),
        (["--profile", "sdk"], "profile_flag", "sdk"),
        (["--no-save"], "no_save", True),
        ([], "no_save", False),
    ],
)
def test_flag_parity_reaches_the_review_call(
    cli_runner: CliRunner,
    patched_host: dict[str, object],
    captured_review: list[dict[str, object]],
    flags: list[str],
    kwarg: str,
    expected: object,
) -> None:
    """Each flag on `sq review pr` lands the same way it does on `sq review code`."""
    _arm(patched_host)
    result = cli_runner.invoke(app, [*_PARITY_BASE, *flags])

    assert captured_review, f"review was never invoked: {result.output}"
    assert captured_review[0][kwarg] == expected


def test_no_rules_suppresses_rules_content(
    cli_runner: CliRunner,
    patched_host: dict[str, object],
    captured_review: list[dict[str, object]],
) -> None:
    """--no-rules suppresses rule injection entirely (parity with review_code)."""
    _arm(patched_host)
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--no-rules", "--no-save"])

    assert captured_review, f"review was never invoked: {result.output}"
    assert None in captured_review[0]["args"]


def test_json_flag_selects_json_output(
    cli_runner: CliRunner,
    patched_host: dict[str, object],
    captured_review: list[dict[str, object]],
) -> None:
    """--json overrides --output, as on review_code."""
    _arm(patched_host)
    result = cli_runner.invoke(app, [*_PARITY_BASE, "--json", "--no-save"])

    assert captured_review, f"review was never invoked: {result.output}"
    assert "json" in captured_review[0]["args"]


def test_pr_review_no_longer_reports_persistence_unavailable(
    cli_runner: CliRunner,
    patched_host: dict[str, object],
    captured_review: list[dict[str, object]],
) -> None:
    """383 replaced 382's stub, so neither refusal wording can appear.

    This test asserted the opposite until this slice — that the run warned
    "PR review persistence is not yet available (383)". NOT_PERSISTABLE
    survives for the case it actually describes, a slice-less ``sq review
    code`` with nothing to name an artifact under (D8); a PR review always has
    a target and never reaches it.

    Runs *without* ``--no-save``, which is what makes the assertion able to
    fail. Under ``--no-save`` this asserted nothing: ``_resolve_save_outcome``
    returns SUPPRESSED before reaching the ``target is None`` branch, so 382's
    stub printed no refusal either and the test passed against the code it was
    meant to guard (383 review, F004). ``save_review_result`` is mocked because
    this suite's fake ``_Result`` carries only a verdict and cannot render an
    artifact; the real save, its location, and its filename are covered in
    ``test_review_pr_persistence.py``.
    """
    _arm(patched_host)
    with patch("squadron.cli.commands.review_pr.save_review_result") as save:
        save.return_value = Path("/tmp/github.com-ecorkran-squadron-83-review.code.md")
        result = cli_runner.invoke(app, _PARITY_BASE)

    assert "not yet available" not in result.output
    assert "383" not in result.output
    assert "slice identifier" not in result.output
    # The save was reached, so the absence above is the save path's silence
    # rather than a suppressed branch's.
    assert save.called, f"persistence was never attempted: {result.output}"


def test_a_failed_pr_save_reports_unsaved_and_exits_one(
    cli_runner: CliRunner,
    patched_host: dict[str, object],
    captured_review: list[dict[str, object]],
) -> None:
    """An unwritten review must never look like a written one (D5).

    The slice's success criteria name this case directly: a failed write
    reports UNSAVED with a non-zero exit and a message naming the path. Nothing
    drove it through the CLI until now — the resolver and the target were each
    unit-tested, but not the composition that reports the failure.
    """
    _arm(patched_host)
    with patch(
        "squadron.cli.commands.review_pr.save_review_result",
        side_effect=OSError("read-only filesystem"),
    ) as save:
        result = cli_runner.invoke(app, [*_PARITY_BASE, "--reviews-dir", "/nonexistent/place"])

    assert save.called, f"persistence was never attempted: {result.output}"
    assert result.exit_code == 1, result.output
    assert "/nonexistent/place" in result.output


_UNQUALIFIED = "pr-83-review.code.md"
_QUALIFIED = "pr-83-review.code.ecorkran-squadron.md"


@pytest.mark.parametrize(
    ("rule", "expected_name"),
    [
        (ReviewsDirRule.PROJECT, _UNQUALIFIED),
        (ReviewsDirRule.DEFAULT, _UNQUALIFIED),
        (ReviewsDirRule.CONFIG, _QUALIFIED),
        (ReviewsDirRule.FLAG, _QUALIFIED),
    ],
)
def test_each_reviews_dir_rule_decides_the_artifact_qualifier(
    cli_runner: CliRunner,
    patched_host: dict[str, object],
    captured_review: list[dict[str, object]],
    pr_review_repo: Path,
    tmp_path: Path,
    rule: ReviewsDirRule,
    expected_name: str,
) -> None:
    """The rule that chose the directory reaches ``PrTarget`` as ``qualify`` (slice 926, D1).

    Driven through the real command for every rule, so a wiring bug isolated to one
    rule — branching on ``rule == FLAG`` rather than ``repository_scoped`` — fails
    here. ``save_review_result`` is mocked because the fake ``_Result`` cannot render
    an artifact; the name is rebuilt from the directory and target it was handed.
    Config is patched in every case so an operator's real
    ``review.external_reviews_dir`` cannot pick the rule instead.
    """
    elsewhere = tmp_path / "elsewhere"
    home = tmp_path / "home"
    expected_dir = {
        ReviewsDirRule.PROJECT: pr_review_repo / REVIEWS_DIR,
        ReviewsDirRule.DEFAULT: home / ".config/squadron/reviews/github.com/ecorkran/squadron",
        ReviewsDirRule.CONFIG: elsewhere,
        ReviewsDirRule.FLAG: elsewhere,
    }[rule]
    if rule is ReviewsDirRule.PROJECT:
        (pr_review_repo / REVIEWS_DIR).mkdir(parents=True)
    configured = str(elsewhere) if rule is ReviewsDirRule.CONFIG else None
    flags = ["--reviews-dir", str(elsewhere)] if rule is ReviewsDirRule.FLAG else []

    _arm(patched_host)
    with (
        patch("squadron.review.reviews_dir.get_config", return_value=configured),
        patch("pathlib.Path.home", return_value=home),
        patch("squadron.cli.commands.review_pr.save_review_result") as save,
    ):
        save.return_value = expected_dir / expected_name
        result = cli_runner.invoke(app, [*_PARITY_BASE, *flags])

    assert save.called, f"persistence was never attempted: {result.output}"
    kwargs = save.call_args.kwargs
    assert kwargs["reviews_dir"] == expected_dir
    assert f"{kwargs['target'].filename_stem('code')}.md" == expected_name
    assert f"({rule})" in result.output


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
