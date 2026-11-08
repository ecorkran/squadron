"""Closing-commit discovery (slice 422 D1)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.fix_discovery import (
    CLOSING_REFERENCE,
    GIT_LOG_FORMAT,
    DiscoveryRejection,
    DiscoveryResult,
    FixCandidate,
    discover,
    resolve_locator,
)
from squadron.codehost.github_cli import GitHubCli
from squadron.codehost.models import LocalRemote, RepositoryLocator
from squadron.codehost.remotes import parse_remote_url
from squadron.core.process_runner import (
    ProcessNotFoundError,
    ProcessResult,
    ProcessTimedOutError,
    SubprocessRunner,
)
from squadron.metrology.benchmark_models import CandidateRejection
from tests.benchmark.support import (
    ClosingCommitRepo,
    RunnerCall,
    ScriptedRunner,
    closing_commit_repo,
    failed,
    ok,
)
from tests.codehost.fake_runner import FakeProcessRunner

TIMEOUT = 60.0
SAMPLES = Path(__file__).parent / "fixtures" / "git_log_samples.txt"

#: Real squadron commits captured in ``git_log_samples.txt`` (full shas live in the file).
SAMPLE_PREFIXES = {
    "216_first": "29850399",
    "216_second": "38060838",
    "291_first": "9fc4fc1c",
    "291_second": "d6535d62",
    "no_keyword": "ebd45f3f",
    "two_issues": "627abe7e",
    "recent_299": "c45d28e9",
    "recent_302": "4a45d1a8",
    "recent_303": "c3f3a211",
}


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> ClosingCommitRepo:
    return closing_commit_repo(tmp_path_factory.mktemp("discovery"))


def outcomes(result: DiscoveryResult) -> dict[str, str]:
    """sha -> ``candidate`` or the rejection value."""
    found = {candidate.sha: "candidate" for candidate in result.candidates}
    found.update({rejection.sha: rejection.rejection.value for rejection in result.rejections})
    return found


def test_each_commit_gets_the_expected_outcome(repo: ClosingCommitRepo) -> None:
    result = discover(SubprocessRunner(), repo.path, timeout_seconds=TIMEOUT)
    expected = {
        "body_line": "candidate",
        "two_issues": CandidateRejection.MULTIPLE_ISSUES_CLOSED.value,
        "split_one": CandidateRejection.MULTIPLE_CLOSING_COMMITS.value,
        "split_two": CandidateRejection.MULTIPLE_CLOSING_COMMITS.value,
        "same_twice": "candidate",
        "cross_repo": "candidate",
        "colon_form": "candidate",
        "merge": CandidateRejection.MERGE_COMMIT.value,
    }
    assert outcomes(result) == {repo.shas[name]: value for name, value in expected.items()}


def test_commits_without_a_closing_keyword_are_not_discovered(repo: ClosingCommitRepo) -> None:
    found = outcomes(discover(SubprocessRunner(), repo.path, timeout_seconds=TIMEOUT))
    for name in ("init", "suffix_only", "tidy"):
        assert repo.shas[name] not in found


def test_candidates_carry_parent_date_and_reference(repo: ClosingCommitRepo) -> None:
    result = discover(SubprocessRunner(), repo.path, timeout_seconds=TIMEOUT)
    by_sha = {candidate.sha: candidate for candidate in result.candidates}
    body_line = by_sha[repo.shas["body_line"]]
    assert body_line.parent_sha == repo.shas["suffix_only"]
    assert (body_line.issue_ref, body_line.repository, body_line.number) == ("#10", None, 10)
    assert body_line.committer_date.tzinfo is not None
    cross = by_sha[repo.shas["cross_repo"]]
    assert (cross.issue_ref, cross.repository, cross.number) == ("other/repo#15", "other/repo", 15)
    assert by_sha[repo.shas["colon_form"]].number == 17


def test_every_closing_commit_is_covered_exactly_once(repo: ClosingCommitRepo) -> None:
    result = discover(SubprocessRunner(), repo.path, timeout_seconds=TIMEOUT)
    shas = [candidate.sha for candidate in result.candidates]
    shas += [rejection.sha for rejection in result.rejections]
    assert sorted(shas) == sorted(
        repo.shas[name]
        for name in (
            "body_line",
            "two_issues",
            "split_one",
            "split_two",
            "same_twice",
            "cross_repo",
            "colon_form",
            "merge",
        )
    )


def test_the_same_issue_named_twice_counts_once(repo: ClosingCommitRepo) -> None:
    result = discover(SubprocessRunner(), repo.path, timeout_seconds=TIMEOUT)
    assert outcomes(result)[repo.shas["same_twice"]] == "candidate"


def test_rejection_details_name_the_cause(repo: ClosingCommitRepo) -> None:
    result = discover(SubprocessRunner(), repo.path, timeout_seconds=TIMEOUT)
    details = {rejection.sha: rejection.detail for rejection in result.rejections}
    assert details[repo.shas["two_issues"]] == "#11, #12"
    assert "#13" in details[repo.shas["split_one"]]
    assert details[repo.shas["merge"]] == "2 parents"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Fixes #1", [(None, "1")]),
        ("fixed #2", [(None, "2")]),
        ("CLOSES #3", [(None, "3")]),
        ("resolve:   #4", [(None, "4")]),
        ("Resolved\n#5", [(None, "5")]),
        ("fixes acme/widgets#6", [("acme/widgets", "6")]),
        ("fix: handle input (#283)", []),
        ("see #7 for background", []),
        ("prefix1 fixes #8", [(None, "8")]),
        ("affixes #9", []),
    ],
)
def test_closing_reference_pattern(message: str, expected: list[tuple[str | None, str]]) -> None:
    assert [(m.group(1), m.group(2)) for m in CLOSING_REFERENCE.finditer(message)] == expected


# --- Parser fixture from real squadron history -------------------------------


def sample_result() -> DiscoveryResult:
    text = SAMPLES.read_text(encoding="utf-8")

    def handler(call: RunnerCall) -> ProcessResult:
        return ok(call.argv, stdout=text)

    return discover(ScriptedRunner(handler), Path("/sample"), timeout_seconds=TIMEOUT)


def sample_outcome(result: DiscoveryResult, key: str) -> str | None:
    matches = {
        sha: outcome
        for sha, outcome in outcomes(result).items()
        if sha.startswith(SAMPLE_PREFIXES[key])
    }
    return next(iter(matches.values()), None)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("216_first", CandidateRejection.MULTIPLE_CLOSING_COMMITS.value),
        ("216_second", CandidateRejection.MULTIPLE_CLOSING_COMMITS.value),
        ("291_first", CandidateRejection.MULTIPLE_CLOSING_COMMITS.value),
        ("291_second", CandidateRejection.MULTIPLE_CLOSING_COMMITS.value),
        ("no_keyword", None),
        ("two_issues", CandidateRejection.MULTIPLE_ISSUES_CLOSED.value),
        ("recent_299", "candidate"),
        ("recent_302", "candidate"),
        ("recent_303", "candidate"),
    ],
)
def test_real_squadron_log_output_parses_to_the_expected_outcome(
    key: str, expected: str | None
) -> None:
    assert sample_outcome(sample_result(), key) == expected


def test_real_sample_references_are_read_from_body_lines() -> None:
    result = sample_result()
    refs = {candidate.sha[:8]: candidate.issue_ref for candidate in result.candidates}
    assert refs == {"c45d28e9": "#299", "4a45d1a8": "#302", "c3f3a211": "#303"}
    two = next(r for r in result.rejections if r.sha.startswith(SAMPLE_PREFIXES["two_issues"]))
    assert two.detail == "#132, #122"


def test_discovery_asks_git_for_the_documented_format() -> None:
    calls: list[RunnerCall] = []

    def handler(call: RunnerCall) -> ProcessResult:
        calls.append(call)
        return ok(call.argv)

    discover(ScriptedRunner(handler), Path("/sample"), timeout_seconds=TIMEOUT)
    assert calls[0].argv == ("git", "log", f"--format={GIT_LOG_FORMAT}", "HEAD")
    assert calls[0].cwd == "/sample"
    assert calls[0].timeout == TIMEOUT


# --- Failure modes: each is an ERROR log plus BuildHalted --------------------


def run_failing(handler_result: ProcessResult | Exception) -> ScriptedRunner:
    def handler(call: RunnerCall) -> ProcessResult:
        if isinstance(handler_result, Exception):
            raise handler_result
        return handler_result

    return ScriptedRunner(handler)


def test_a_git_log_timeout_halts_with_an_error_log(caplog: pytest.LogCaptureFixture) -> None:
    runner = run_failing(ProcessTimedOutError(["git", "log"], TIMEOUT))
    with caplog.at_level(logging.ERROR), pytest.raises(BuildHalted, match="git log"):
        discover(runner, Path("/x"), timeout_seconds=TIMEOUT)
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_nonzero_git_log_halts_with_an_error_log(caplog: pytest.LogCaptureFixture) -> None:
    runner = run_failing(failed(["git", "log"], code=128, stderr="not a git repository"))
    with caplog.at_level(logging.ERROR), pytest.raises(BuildHalted, match="not a git repository"):
        discover(runner, Path("/x"), timeout_seconds=TIMEOUT)
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_missing_git_halts_with_an_error_log(caplog: pytest.LogCaptureFixture) -> None:
    runner = run_failing(ProcessNotFoundError("git"))
    with caplog.at_level(logging.ERROR), pytest.raises(BuildHalted, match="not on PATH"):
        discover(runner, Path("/x"), timeout_seconds=TIMEOUT)
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_malformed_record_halts_with_an_error_log(caplog: pytest.LogCaptureFixture) -> None:
    runner = run_failing(ok(["git", "log"], stdout="\x1eabc\x1fonly-two-fields"))
    with caplog.at_level(logging.ERROR), pytest.raises(BuildHalted, match="fields"):
        discover(runner, Path("/x"), timeout_seconds=TIMEOUT)
    assert any(record.levelno == logging.ERROR for record in caplog.records)


# --- Issue repository resolution (Task 8) ------------------------------------

SERVED_HOST = "github.com"


def remote(name: str, url: str) -> LocalRemote:
    return parse_remote_url(name, url)


def issue_host() -> GitHubCli:
    return GitHubCli(FakeProcessRunner([]), frozenset({SERVED_HOST}))


def candidate_for(number: int, repository: str | None = None) -> FixCandidate:
    ref = f"{repository}#{number}" if repository else f"#{number}"
    return FixCandidate(
        sha="a" * 40,
        parent_sha="b" * 40,
        committer_date=datetime(2026, 11, 1, tzinfo=UTC),
        issue_ref=ref,
        repository=repository,
        number=number,
    )


def test_a_bare_reference_uses_the_single_served_remote() -> None:
    remotes = [remote("origin", "git@github.com:acme/widgets.git")]
    locator = resolve_locator(candidate_for(5), remotes, issue_host())
    assert isinstance(locator, RepositoryLocator)
    assert (locator.host, locator.owner, locator.repository) == ("github.com", "acme", "widgets")


def test_a_bare_reference_ignores_remotes_on_unserved_hosts() -> None:
    remotes = [
        remote("mirror", "git@gitlab.example:acme/widgets.git"),
        remote("origin", "https://github.com/acme/widgets.git"),
    ]
    locator = resolve_locator(candidate_for(5), remotes, issue_host())
    assert isinstance(locator, RepositoryLocator)
    assert locator.remote_name == "origin"


def test_an_owner_repo_reference_uses_the_matching_remotes_host() -> None:
    remotes = [
        remote("origin", "git@github.com:acme/widgets.git"),
        remote("other", "git@github.com:other/repo.git"),
    ]
    locator = resolve_locator(candidate_for(15, "other/repo"), remotes, issue_host())
    assert isinstance(locator, RepositoryLocator)
    assert (locator.owner, locator.repository, locator.remote_name) == ("other", "repo", "other")


@pytest.mark.parametrize(
    ("remotes", "repository"),
    [
        ([], None),
        ([], "other/repo"),
        ([remote("origin", "git@gitlab.example:acme/widgets.git")], None),
        ([remote("origin", "git@gitlab.example:other/repo.git")], "other/repo"),
        ([remote("origin", "git@github.com:acme/widgets.git")], "other/repo"),
        (
            [
                remote("origin", "git@github.com:acme/widgets.git"),
                remote("fork", "git@github.com:me/widgets.git"),
            ],
            None,
        ),
        ([remote("odd", "some-local-thing")], None),
    ],
    ids=[
        "no remote, bare",
        "no remote, explicit",
        "unserved host, bare",
        "unserved host, explicit",
        "explicit repo not among remotes",
        "two served remotes, bare",
        "unparseable remote",
    ],
)
def test_no_issue_host_when_selection_cannot_settle(
    remotes: list[LocalRemote], repository: str | None
) -> None:
    result = resolve_locator(candidate_for(5, repository), remotes, issue_host())
    assert isinstance(result, DiscoveryRejection)
    assert result.rejection is CandidateRejection.NO_ISSUE_HOST
    assert result.sha == "a" * 40
    assert result.detail
