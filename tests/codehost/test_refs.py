"""Tests for fetching pull-request endpoints and describing the range.

The no-mutation assertion is the guarantee that lets ``sq pr show`` run against
a dirty working tree: nothing on this path checks anything out.

No enterprise-hostname leg here, deliberately. The fetch path is host-independent
by construction — ``refs.py`` takes refspec sources from its caller and names the
*remote*, never the host, so no git argv here carries a hostname. Parsing and
selection are parametrized over both hosts in the remotes tests, resolution and
identity in the adapter tests.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from squadron.codehost.errors import (
    RENDERED_BY_CALLER,
    HostCommandTimeoutError,
    NoMergeBaseError,
    PullRequestHeadUnavailableError,
    RefMovedSinceResolutionError,
    RefNotFetchableError,
)
from squadron.codehost.git_refs import GIT_FETCH_TIMEOUT_SECONDS, GIT_QUERY_TIMEOUT_SECONDS
from squadron.codehost.head_resolution import (
    HEAD_FETCHED_BY_SHA,
    HEAD_PRESENT_LOCALLY,
    api_head_ref,
    ensure_api_head,
)
from squadron.codehost.models import RefRole
from squadron.codehost.refs import fetch_and_range, local_ref
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError, SubprocessRunner
from tests.codehost.fake_runner import FakeProcessRunner

BASE_SHA = "4edf5f1709489da9494906b2178e27dea6a9ae10"
HEAD_SHA = "b67cf55495f01bc2da843d8f96c767a11770e330"
MERGE_BASE = "1111111111111111111111111111111111111111"
REMOTE = "origin"
NUMBER = 83

BASE_LOCAL = local_ref(REMOTE, NUMBER, RefRole.BASE)
HEAD_LOCAL = local_ref(REMOTE, NUMBER, RefRole.HEAD)


def _ok(stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str = "boom") -> ProcessResult:
    return ProcessResult(argv=(), returncode=1, stdout="", stderr=stderr)


def _script(
    *,
    fetch: ProcessResult | None = None,
    base_rev: ProcessResult | None = None,
    head_rev: ProcessResult | None = None,
    merge_base: ProcessResult | None = None,
    diff: ProcessResult | None = None,
) -> list[tuple[list[str], ProcessResult | Exception]]:
    """The happy-path call sequence, with individual steps overridable."""
    return [
        (["git", "fetch"], fetch or _ok()),
        (["git", "rev-parse", "--verify", f"{BASE_LOCAL}^{{commit}}"], base_rev or _ok(BASE_SHA)),
        (["git", "rev-parse", "--verify", f"{HEAD_LOCAL}^{{commit}}"], head_rev or _ok(HEAD_SHA)),
        (["git", "merge-base"], merge_base or _ok(MERGE_BASE)),
        (["git", "diff", "--name-only"], diff or _ok("src/a.py\nsrc/b.py\n")),
    ]


def _run(runner: FakeProcessRunner, *, head_fallback_sources: tuple[str, ...] = ()):
    return fetch_and_range(
        runner,
        cwd="/repo",
        remote_name=REMOTE,
        namespace=NUMBER,
        base_refspec_source="refs/heads/main",
        head_refspec_source=f"refs/pull/{NUMBER}/head",
        expected_base_sha=BASE_SHA,
        expected_head_sha=HEAD_SHA,
        head_fallback_sources=head_fallback_sources,
    )


# --- Happy path ------------------------------------------------------------


def test_fetch_and_range_describes_the_range() -> None:
    runner = FakeProcessRunner(_script())
    fetched = _run(runner)

    assert fetched.base_sha == BASE_SHA
    assert fetched.head_sha == HEAD_SHA
    assert fetched.merge_base == MERGE_BASE
    assert len(fetched.merge_base) == 40
    assert fetched.diff_range == f"{BASE_LOCAL}...{HEAD_LOCAL}"
    assert fetched.changed_paths == ("src/a.py", "src/b.py")


def test_local_refs_are_namespaced_by_remote_and_number() -> None:
    assert BASE_LOCAL == f"refs/squadron/pr/{REMOTE}/{NUMBER}/base"
    assert HEAD_LOCAL == f"refs/squadron/pr/{REMOTE}/{NUMBER}/head"
    # PR 12 on origin stays distinct from PR 12 on upstream.
    assert local_ref("upstream", 12, RefRole.BASE) != local_ref("origin", 12, RefRole.BASE)


# --- The no-mutation guarantee ---------------------------------------------


def test_nothing_on_this_path_mutates_the_working_tree() -> None:
    """What lets sq pr show run against a dirty tree."""
    runner = FakeProcessRunner(_script())
    _run(runner)

    forbidden = {"checkout", "switch", "reset", "branch", "worktree"}
    for call in runner.calls:
        assert not forbidden.intersection(call.argv), f"mutating argv: {call.argv}"


def test_no_git_argv_on_this_path_carries_a_hostname() -> None:
    """Why there is no enterprise leg here: the path names remotes, not hosts."""
    runner = FakeProcessRunner(_script())
    _run(runner)

    for call in runner.calls:
        joined = " ".join(call.argv)
        assert "github.com" not in joined
        assert "ghe.corp.example" not in joined
        assert "--hostname" not in call.argv


# --- Fetch argv and timeouts ------------------------------------------------


def test_fetch_argv_carries_no_tags_and_both_forced_refspecs() -> None:
    runner = FakeProcessRunner(_script())
    _run(runner)

    fetch_call = runner.calls[0]
    assert fetch_call.argv[:4] == ("git", "fetch", "--no-tags", REMOTE)
    assert f"+refs/heads/main:{BASE_LOCAL}" in fetch_call.argv
    assert f"+refs/pull/{NUMBER}/head:{HEAD_LOCAL}" in fetch_call.argv


def test_fetch_uses_the_fetch_bound_and_queries_use_the_query_bound() -> None:
    """Fetch moves data; the query bound is far too tight for it."""
    runner = FakeProcessRunner(_script())
    _run(runner)

    assert runner.calls[0].timeout == GIT_FETCH_TIMEOUT_SECONDS
    for call in runner.calls[1:]:
        assert call.timeout == GIT_QUERY_TIMEOUT_SECONDS
    assert GIT_FETCH_TIMEOUT_SECONDS > GIT_QUERY_TIMEOUT_SECONDS


# --- Failure cases ----------------------------------------------------------


def test_fetch_failing_for_base_names_base(caplog: pytest.LogCaptureFixture) -> None:
    runner = FakeProcessRunner(
        [
            (["git", "fetch"], _fail("couldn't find remote ref refs/heads/main")),
            (["git", "rev-parse", "--verify", f"{BASE_LOCAL}^{{commit}}"], _fail()),
        ]
    )
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefNotFetchableError) as excinfo:
            _run(runner)

    assert excinfo.value.role is RefRole.BASE
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_fetch_failing_for_head_names_head(caplog: pytest.LogCaptureFixture) -> None:
    runner = FakeProcessRunner(
        [
            (["git", "fetch"], _fail("couldn't find remote ref refs/pull/83/head")),
            (["git", "rev-parse", "--verify", f"{BASE_LOCAL}^{{commit}}"], _ok(BASE_SHA)),
            (["git", "rev-parse", "--verify", f"{HEAD_LOCAL}^{{commit}}"], _fail()),
        ]
    )
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefNotFetchableError) as excinfo:
            _run(runner)

    assert excinfo.value.role is RefRole.HEAD
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def _is_ancestor_step(result: ProcessResult) -> tuple[list[str], ProcessResult]:
    """The ancestry probe a moved base triggers. Must precede the generic
    merge-base entry: the fake answers the first matching prefix."""
    return (["git", "merge-base", "--is-ancestor", BASE_SHA], result)


def _script_with_moved_base(moved: str, ancestry: ProcessResult):
    script = _script(base_rev=_ok(moved))
    script.insert(2, _is_ancestor_step(ancestry))
    return script


def test_base_advanced_past_host_report_uses_fetched_tip(caplog: pytest.LogCaptureFixture) -> None:
    """#131: GitHub's baseRefOid trails the branch after a merge; the fetched
    tip descends from it. Accepted, observably."""
    advanced = "7777777777777777777777777777777777777777"
    runner = FakeProcessRunner(_script_with_moved_base(advanced, _ok()))
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        fetched = _run(runner)

    assert fetched.base_sha == advanced
    assert any(
        r.levelno == logging.WARNING and "advanced since resolution" in r.getMessage()
        for r in caplog.records
    )


def test_base_ancestry_probe_error_fails_closed(caplog: pytest.LogCaptureFixture) -> None:
    """Exit 128 (e.g. the reported sha absent locally) is not a yes."""
    advanced = "7777777777777777777777777777777777777777"
    probe_error = ProcessResult(argv=(), returncode=128, stdout="", stderr="fatal: bad object")
    runner = FakeProcessRunner(_script_with_moved_base(advanced, probe_error))
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefMovedSinceResolutionError):
            _run(runner)

    assert any("could not test ancestry" in r.getMessage() for r in caplog.records)


def test_moved_base_reports_expected_and_actual(caplog: pytest.LogCaptureFixture) -> None:
    """A base that did not merely advance (rewound, force-pushed) still fails."""
    moved = "9999999999999999999999999999999999999999"
    runner = FakeProcessRunner(_script_with_moved_base(moved, _fail("")))
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefMovedSinceResolutionError) as excinfo:
            _run(runner)

    assert excinfo.value.role is RefRole.BASE
    assert excinfo.value.expected == BASE_SHA
    assert excinfo.value.actual == moved
    assert any(r.levelno == logging.WARNING for r in caplog.records)


PR_REF_SHA = "8888888888888888888888888888888888888888"
_API_PRESENT = (["git", "cat-file", "-e", f"{HEAD_SHA}^{{commit}}"], _ok())
_PR_BEHIND_API = ["git", "merge-base", "--is-ancestor", PR_REF_SHA, HEAD_SHA]
_API_BEHIND_PR = ["git", "merge-base", "--is-ancestor", HEAD_SHA, PR_REF_SHA]


def _script_with_head_disagreement(*steps: tuple[list[str], ProcessResult | Exception]):
    """The PR ref reads PR_REF_SHA while the API says HEAD_SHA.

    The ancestry probes precede the generic merge-base entry: the fake answers the
    first matching prefix."""
    script = _script(head_rev=_ok(PR_REF_SHA))
    script[3:3] = list(steps)
    return script


def test_head_pushed_after_resolution_is_a_moved_error(caplog: pytest.LogCaptureFixture) -> None:
    """The PR ref descends from the API head: new commits are different code to review."""
    runner = FakeProcessRunner(
        _script_with_head_disagreement(
            _API_PRESENT, (_PR_BEHIND_API, _fail("")), (_API_BEHIND_PR, _ok())
        )
    )
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefMovedSinceResolutionError) as excinfo:
            _run(runner)

    assert excinfo.value.role is RefRole.HEAD
    assert excinfo.value.expected == HEAD_SHA
    assert excinfo.value.actual == PR_REF_SHA
    assert excinfo.value.actual_source == f"refs/pull/{NUMBER}/head"


def test_head_unrelated_to_the_api_head_is_a_moved_error() -> None:
    runner = FakeProcessRunner(
        _script_with_head_disagreement(
            _API_PRESENT, (_PR_BEHIND_API, _fail("")), (_API_BEHIND_PR, _fail(""))
        )
    )
    with pytest.raises(RefMovedSinceResolutionError):
        _run(runner)


def test_head_ancestry_probe_error_is_answered_no_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    probe_error = ProcessResult(argv=(), returncode=128, stdout="", stderr="fatal: bad object")
    runner = FakeProcessRunner(
        _script_with_head_disagreement(
            _API_PRESENT, (_PR_BEHIND_API, probe_error), (_API_BEHIND_PR, probe_error)
        )
    )
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefMovedSinceResolutionError):
            _run(runner)

    assert any("could not test ancestry" in r.getMessage() for r in caplog.records)


def test_head_ancestry_timeout_is_a_code_host_error() -> None:
    timeout = ProcessTimedOutError(_PR_BEHIND_API, 30.0)
    runner = FakeProcessRunner(_script_with_head_disagreement(_API_PRESENT, (_PR_BEHIND_API, timeout)))
    with pytest.raises(HostCommandTimeoutError):
        _run(runner)


_UPDATE_REF = ["git", "update-ref", HEAD_LOCAL, HEAD_SHA]


def test_lagging_ref_builds_the_range_on_the_api_head() -> None:
    runner = FakeProcessRunner(
        _script_with_head_disagreement(_API_PRESENT, (_PR_BEHIND_API, _ok()), (_UPDATE_REF, _ok()))
    )

    fetched = _run(runner)

    assert fetched.head_sha == HEAD_SHA
    assert len(fetched.adjustments) == 1
    adjustment = fetched.adjustments[0]
    assert adjustment.role is RefRole.HEAD
    assert (adjustment.reported_sha, adjustment.used_sha) == (PR_REF_SHA, HEAD_SHA)
    assert adjustment.source == HEAD_PRESENT_LOCALLY
    assert any(call.argv[:2] == ("git", "update-ref") for call in runner.calls)


def test_lagging_ref_from_the_issue_fetches_the_api_head_from_the_fallback() -> None:
    """The API head is absent locally and refused by sha; the head branch has it."""
    api_local = api_head_ref(REMOTE, NUMBER)
    runner = FakeProcessRunner(
        _script_with_head_disagreement(
            (["git", "cat-file", "-e", f"{HEAD_SHA}^{{commit}}"], _fail("")),
            (["git", "fetch", "--no-tags", REMOTE, f"+{HEAD_SHA}:{api_local}"], _fail("not our ref")),
            (["git", "fetch", "--no-tags", REMOTE, f"+refs/heads/dev/jane:{api_local}"], _ok()),
            (["git", "rev-parse", "--verify", f"{api_local}^{{commit}}"], _ok(HEAD_SHA)),
            (_PR_BEHIND_API, _ok()),
            (_UPDATE_REF, _ok()),
        )
    )

    fetched = _run(runner, head_fallback_sources=("refs/heads/dev/jane",))

    assert fetched.head_sha == HEAD_SHA
    assert fetched.adjustments[0].source == "fetched from refs/heads/dev/jane"
    kinds = [call.argv[1] for call in runner.calls]
    assert kinds.index("cat-file") < kinds.index("merge-base")


def test_lagging_ref_update_failure_is_a_rendered_ref_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = FakeProcessRunner(
        _script_with_head_disagreement(
            _API_PRESENT, (_PR_BEHIND_API, _ok()), (_UPDATE_REF, _fail("cannot lock ref"))
        )
    )
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefNotFetchableError) as excinfo:
            _run(runner)

    assert excinfo.value.role is RefRole.HEAD
    tagged = [r for r in caplog.records if getattr(r, RENDERED_BY_CALLER, False)]
    assert any("could not point" in r.getMessage() for r in tagged)


def test_lagging_ref_update_timeout_is_a_code_host_error() -> None:
    runner = FakeProcessRunner(
        _script_with_head_disagreement(
            _API_PRESENT,
            (_PR_BEHIND_API, _ok()),
            (_UPDATE_REF, ProcessTimedOutError(_UPDATE_REF, 30.0)),
        )
    )
    with pytest.raises(HostCommandTimeoutError):
        _run(runner)


def test_unrelated_histories_raise_no_merge_base(caplog: pytest.LogCaptureFixture) -> None:
    runner = FakeProcessRunner(_script(merge_base=_fail("no merge base")))
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(NoMergeBaseError):
            _run(runner)

    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_empty_merge_base_output_also_raises() -> None:
    """A zero exit with no sha is still no merge base."""
    runner = FakeProcessRunner(_script(merge_base=_ok("")))
    with pytest.raises(NoMergeBaseError):
        _run(runner)


# --- Cross-repository -------------------------------------------------------


def test_cross_repository_head_fetches_from_refs_pull_with_one_remote() -> None:
    """A fork head needs no second remote: refs/pull/<n>/head is on the base repo."""
    runner = FakeProcessRunner(_script())
    _run(runner)

    fetch_call = runner.calls[0]
    remotes_named = [arg for arg in fetch_call.argv if arg == REMOTE]
    assert len(remotes_named) == 1
    assert f"+refs/pull/{NUMBER}/head:{HEAD_LOCAL}" in fetch_call.argv


def test_changed_paths_applies_no_exclusions() -> None:
    """382 applies the template's patterns; filtering here would double them."""
    runner = FakeProcessRunner(_script(diff=_ok("src/a.py\nuv.lock\ndist/bundle.js\n")))
    fetched = _run(runner)
    assert fetched.changed_paths == ("src/a.py", "uv.lock", "dist/bundle.js")


# --- Real git: the #131 scenario ----------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


def test_real_git_base_merged_after_resolution(tmp_path: Path) -> None:
    """Resolution reported base A; another PR then merged, so the remote's main
    is B. Real git, real ancestry: the review proceeds against B, and a rewound
    base is still refused."""
    remote = tmp_path / "remote"
    remote.mkdir()
    _git(remote, "init", "-q", "-b", "main")
    reported_base = _commit(remote, "a.txt")
    _git(remote, "checkout", "-q", "-b", "feature")
    head = _commit(remote, "feature.txt")
    _git(remote, "update-ref", f"refs/pull/{NUMBER}/head", head)
    _git(remote, "checkout", "-q", "main")
    merged_base = _commit(remote, "other-pr.txt")

    local = tmp_path / "local"
    _git(tmp_path, "clone", "-q", str(remote), str(local))

    def fetch(expected_base: str):
        return fetch_and_range(
            SubprocessRunner(),
            cwd=str(local),
            remote_name=REMOTE,
            namespace=NUMBER,
            base_refspec_source="refs/heads/main",
            head_refspec_source=f"refs/pull/{NUMBER}/head",
            expected_base_sha=expected_base,
            expected_head_sha=head,
        )

    fetched = fetch(reported_base)
    assert fetched.base_sha == merged_base
    assert fetched.changed_paths == ("feature.txt",)

    # Rewind: host reports B, but main was reset to A.
    _git(remote, "reset", "-q", "--hard", reported_base)
    with pytest.raises(RefMovedSinceResolutionError):
        fetch(merged_base)


# --- Source-naming errors and adjustments (slice 934 D7, D9) -------------------


def test_moved_error_message_names_each_source_and_sha() -> None:
    error = RefMovedSinceResolutionError(
        RefRole.HEAD,
        "ae1cbf2" + "0" * 33,
        "d3008a6" + "0" * 33,
        expected_source="host API",
        actual_source="refs/pull/49/head",
    )
    assert str(error) == (
        "head moved since resolution: host API reported ae1cbf2…, refs/pull/49/head fetched d3008a6…"
    )
    assert error.fix_hint == "Rerun to resolve the pull request again."
    assert (error.expected_source, error.actual_source) == ("host API", "refs/pull/49/head")


def test_head_unavailable_error_names_every_attempt_and_has_a_hint() -> None:
    error = PullRequestHeadUnavailableError(
        "ae1cbf2" + "0" * 33,
        "refs/pull/49/head",
        "d3008a6" + "0" * 33,
        "origin",
        [("fetch by sha", "not our ref"), ("refs/heads/dev/jane", "sha did not match")],
    )
    assert str(error) == (
        "pull request head ae1cbf2… (host API) could not be fetched; "
        "refs/pull/49/head on origin is d3008a6…; fetch by sha: not our ref; "
        "refs/heads/dev/jane: sha did not match"
    )
    assert error.role is RefRole.HEAD
    assert error.fix_hint is not None and "Rerun later" in error.fix_hint


def test_adjustments_default_to_empty() -> None:
    assert _run(FakeProcessRunner(_script())).adjustments == ()


def test_a_base_side_move_through_verify_names_its_sources(
    caplog: pytest.LogCaptureFixture,
) -> None:
    moved = "9999999999999999999999999999999999999999"
    runner = FakeProcessRunner(_script_with_moved_base(moved, _fail("")))
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefMovedSinceResolutionError) as excinfo:
            _run(runner)

    assert excinfo.value.expected_source == "host API"
    assert excinfo.value.actual_source == "refs/heads/main"
    assert "refs/heads/main fetched 9999999…" in str(excinfo.value)
    moved_records = [r for r in caplog.records if "moved since resolution" in r.getMessage()]
    assert moved_records and getattr(moved_records[0], RENDERED_BY_CALLER) is True


def test_base_fast_forward_is_recorded_as_one_adjustment() -> None:
    advanced = "7777777777777777777777777777777777777777"
    runner = FakeProcessRunner(_script_with_moved_base(advanced, _ok()))

    fetched = _run(runner)

    assert len(fetched.adjustments) == 1
    adjustment = fetched.adjustments[0]
    assert adjustment.role is RefRole.BASE
    assert (adjustment.reported_sha, adjustment.used_sha) == (BASE_SHA, advanced)
    assert adjustment.source == "fetched from refs/heads/main"


def test_primary_fetch_timeout_raises_a_code_host_error_not_a_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    argv = ["git", "fetch", "--no-tags", REMOTE]
    runner = FakeProcessRunner([(["git", "fetch"], ProcessTimedOutError(argv, 300.0))])

    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(HostCommandTimeoutError) as excinfo:
            _run(runner)

    assert excinfo.value.seconds == 300.0
    timeout_records = [r for r in caplog.records if "exceeded" in r.getMessage()]
    assert len(timeout_records) == 1
    assert timeout_records[0].levelno == logging.WARNING
    assert getattr(timeout_records[0], RENDERED_BY_CALLER) is True


# --- ensure_api_head (slice 934 D6 step 1, D10) --------------------------------

API_SHA = "ae1cbf2" + "0" * 33
OTHER_SHA = "d3008a6" + "0" * 33
API_LOCAL = api_head_ref(REMOTE, NUMBER)
FALLBACK = "refs/heads/dev/jane"
_CAT_FILE = ["git", "cat-file", "-e", f"{API_SHA}^{{commit}}"]
_API_REV = ["git", "rev-parse", "--verify", f"{API_LOCAL}^{{commit}}"]


def _ensure(runner: FakeProcessRunner) -> str:
    return ensure_api_head(
        runner,
        cwd="/repo",
        remote_name=REMOTE,
        api_sha=API_SHA,
        api_local=API_LOCAL,
        pr_ref=f"refs/pull/{NUMBER}/head",
        pr_ref_sha=OTHER_SHA,
        head_fallback_sources=(FALLBACK,),
    )


def test_a_present_commit_needs_no_fetch() -> None:
    runner = FakeProcessRunner([(_CAT_FILE, _ok())])
    assert _ensure(runner) == HEAD_PRESENT_LOCALLY
    assert [call.argv[1] for call in runner.calls] == ["cat-file"]


def test_presence_check_timeout_is_a_code_host_error() -> None:
    runner = FakeProcessRunner([(_CAT_FILE, ProcessTimedOutError(_CAT_FILE, 30.0))])
    with pytest.raises(HostCommandTimeoutError):
        _ensure(runner)


def test_an_absent_commit_is_fetched_by_sha() -> None:
    runner = FakeProcessRunner(
        [(_CAT_FILE, _fail("")), (["git", "fetch"], _ok()), (_API_REV, _ok(API_SHA))]
    )
    assert _ensure(runner) == HEAD_FETCHED_BY_SHA
    fetch = next(call for call in runner.calls if call.argv[1] == "fetch")
    assert f"+{API_SHA}:{API_LOCAL}" in fetch.argv


def test_a_refused_sha_fetch_falls_back_to_the_head_branch() -> None:
    runner = FakeProcessRunner(
        [
            (_CAT_FILE, _fail("")),
            (["git", "fetch"], _fail("upload-pack: not our ref")),
            (["git", "fetch"], _ok()),
            (_API_REV, _ok(API_SHA)),
        ]
    )
    assert _ensure(runner) == FALLBACK
    fetches = [call for call in runner.calls if call.argv[1] == "fetch"]
    assert f"+{FALLBACK}:{API_LOCAL}" in fetches[1].argv


def test_a_fallback_that_returns_a_different_sha_is_rejected() -> None:
    runner = FakeProcessRunner(
        [
            (_CAT_FILE, _fail("")),
            (["git", "fetch"], _fail("not our ref")),
            (["git", "fetch"], _ok()),
            (_API_REV, _ok(OTHER_SHA)),
        ]
    )
    with pytest.raises(PullRequestHeadUnavailableError) as excinfo:
        _ensure(runner)
    reasons = dict(excinfo.value.attempts)
    assert "not the API head" in reasons[FALLBACK]


def test_a_fallback_timeout_is_recorded_as_the_reason() -> None:
    argv = ["git", "fetch"]
    runner = FakeProcessRunner(
        [
            (_CAT_FILE, _fail("")),
            (["git", "fetch"], _fail("not our ref")),
            (["git", "fetch"], ProcessTimedOutError(argv, 300.0)),
        ]
    )
    with pytest.raises(PullRequestHeadUnavailableError) as excinfo:
        _ensure(runner)
    assert dict(excinfo.value.attempts)[FALLBACK] == "timed out after 300s"


def test_when_every_source_fails_the_error_names_each_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = FakeProcessRunner(
        [
            (_CAT_FILE, _fail("")),
            (["git", "fetch"], _fail("not our ref")),
            (["git", "fetch"], _fail("couldn't find remote ref")),
        ]
    )
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(PullRequestHeadUnavailableError) as excinfo:
            _ensure(runner)
    assert excinfo.value.attempts == (
        (HEAD_FETCHED_BY_SHA, "not our ref"),
        (FALLBACK, "couldn't find remote ref"),
    )
    assert str(excinfo.value).count(FALLBACK) == 1
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and getattr(warnings[0], RENDERED_BY_CALLER) is True


# --- Which warnings the command renders itself (slice 934 D8) -------------------


def _tagged(caplog: pytest.LogCaptureFixture, fragment: str) -> bool:
    """Whether the one record containing ``fragment`` carries the rendered-by-caller tag."""
    matches = [r for r in caplog.records if fragment in r.getMessage()]
    assert len(matches) == 1, f"expected one record containing {fragment!r}"
    return bool(getattr(matches[0], RENDERED_BY_CALLER, False))


def test_per_endpoint_fetch_failure_warning_is_tagged(caplog: pytest.LogCaptureFixture) -> None:
    runner = FakeProcessRunner(
        [(["git", "fetch"], _fail("no route")), (["git", "rev-parse"], _fail(""))]
    )
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefNotFetchableError):
            _run(runner)
    assert _tagged(caplog, "fetch of base from")


def test_fetch_exit_with_both_refs_present_warning_is_tagged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = FakeProcessRunner(
        [
            (["git", "fetch"], _fail("odd")),
            (["git", "rev-parse"], _ok(BASE_SHA)),
            (["git", "rev-parse"], _ok(HEAD_SHA)),
        ]
    )
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefNotFetchableError):
            _run(runner)
    assert _tagged(caplog, "git fetch exited")


def test_ref_missing_after_fetch_warning_is_tagged(caplog: pytest.LogCaptureFixture) -> None:
    runner = FakeProcessRunner(_script(base_rev=_fail("")))
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefNotFetchableError):
            _run(runner)
    assert _tagged(caplog, "is missing after fetch")


def test_no_merge_base_warning_is_tagged(caplog: pytest.LogCaptureFixture) -> None:
    runner = FakeProcessRunner(_script(merge_base=_fail("none")))
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(NoMergeBaseError):
            _run(runner)
    assert _tagged(caplog, "no merge base between")


def test_the_ancestry_answered_no_warning_is_not_tagged(caplog: pytest.LogCaptureFixture) -> None:
    """Nothing renders this one: it is a diagnostic, so it must stay visible."""
    probe_error = ProcessResult(argv=(), returncode=128, stdout="", stderr="fatal: bad object")
    runner = FakeProcessRunner(_script_with_moved_base("7" * 40, probe_error))
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefMovedSinceResolutionError):
            _run(runner)
    assert not _tagged(caplog, "could not test ancestry")


def test_adjustment_warnings_are_tagged_because_the_command_prints_the_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    lag = FakeProcessRunner(
        _script_with_head_disagreement(_API_PRESENT, (_PR_BEHIND_API, _ok()), (_UPDATE_REF, _ok()))
    )
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        _run(lag)
    assert _tagged(caplog, "lags the host API head")

    caplog.clear()
    forward = FakeProcessRunner(_script_with_moved_base("7" * 40, _ok()))
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        _run(forward)
    assert _tagged(caplog, "advanced since resolution")


def test_adjustment_describes_itself_as_the_line_the_command_prints() -> None:
    runner = FakeProcessRunner(
        _script_with_head_disagreement(_API_PRESENT, (_PR_BEHIND_API, _ok()), (_UPDATE_REF, _ok()))
    )
    [adjustment] = _run(runner).adjustments
    assert adjustment.describe() == (
        f"head: refs/pull/{NUMBER}/head lags; reviewed {HEAD_SHA[:7]}… present locally"
    )
