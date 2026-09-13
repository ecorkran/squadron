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

import pytest

from squadron.codehost.errors import (
    NoMergeBaseError,
    RefMovedSinceResolutionError,
    RefNotFetchableError,
)
from squadron.codehost.models import RefRole
from squadron.codehost.refs import (
    GIT_FETCH_TIMEOUT_SECONDS,
    GIT_QUERY_TIMEOUT_SECONDS,
    fetch_and_range,
    local_ref,
)
from squadron.core.process_runner import ProcessResult
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


def _run(runner: FakeProcessRunner):
    return fetch_and_range(
        runner,
        cwd="/repo",
        remote_name=REMOTE,
        namespace=NUMBER,
        base_refspec_source="refs/heads/main",
        head_refspec_source=f"refs/pull/{NUMBER}/head",
        expected_base_sha=BASE_SHA,
        expected_head_sha=HEAD_SHA,
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


def test_moved_base_reports_expected_and_actual(caplog: pytest.LogCaptureFixture) -> None:
    moved = "9999999999999999999999999999999999999999"
    runner = FakeProcessRunner(_script(base_rev=_ok(moved)))
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.refs"):
        with pytest.raises(RefMovedSinceResolutionError) as excinfo:
            _run(runner)

    assert excinfo.value.role is RefRole.BASE
    assert excinfo.value.expected == BASE_SHA
    assert excinfo.value.actual == moved
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_moved_head_reports_expected_and_actual() -> None:
    moved = "8888888888888888888888888888888888888888"
    runner = FakeProcessRunner(_script(head_rev=_ok(moved)))
    with pytest.raises(RefMovedSinceResolutionError) as excinfo:
        _run(runner)

    assert excinfo.value.role is RefRole.HEAD
    assert excinfo.value.actual == moved


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
