"""Tests for the pull-request target grammar.

The classification *order* is the specification. Most of these cases exist to
pin exclusivity: a reordering of the rules would silently reclassify them.
"""

from __future__ import annotations

import pytest

from squadron.codehost.errors import TargetSyntaxError
from squadron.codehost.targets import TargetForm, parse_target


@pytest.mark.parametrize("text", [None, "", "   "])
def test_absent_target_is_current_branch(text: str | None) -> None:
    assert parse_target(text).form is TargetForm.CURRENT_BRANCH


def test_url_carries_host_owner_repository_and_number() -> None:
    target = parse_target("https://github.com/ecorkran/squadron/pull/83")
    assert target.form is TargetForm.URL
    assert target.host == "github.com"
    assert target.owner == "ecorkran"
    assert target.repository == "squadron"
    assert target.number == 83


def test_enterprise_url_keeps_its_own_host() -> None:
    target = parse_target("https://git.example.com/acme/widgets/pull/7")
    assert target.form is TargetForm.URL
    assert target.host == "git.example.com"


@pytest.mark.parametrize(
    "text",
    [
        "https://github.com/ecorkran/squadron/pull/83",
        "https://github.com/ecorkran/squadron/pull/83/",
        "https://github.com/ecorkran/squadron/pull/83?w=1",
        "https://github.com/ecorkran/squadron/pull/83#discussion",
        "https://github.com/ecorkran/squadron.git/pull/83",
    ],
)
def test_url_tolerates_suffixes_and_fragments(text: str) -> None:
    target = parse_target(text)
    assert target.form is TargetForm.URL
    assert target.repository == "squadron"
    assert target.number == 83


def test_a_url_that_is_not_a_pull_request_is_a_syntax_error() -> None:
    with pytest.raises(TargetSyntaxError):
        parse_target("https://github.com/ecorkran/squadron/issues/83")


# --- Exclusivity: the cases a reordering would break -----------------------


def test_owner_repo_number_is_form_three_never_four_or_six() -> None:
    target = parse_target("ecorkran/squadron#7")
    assert target.form is TargetForm.OWNER_REPO_NUMBER
    assert (target.owner, target.repository, target.number) == (
        "ecorkran",
        "squadron",
        7,
    )


def test_repo_number_is_form_four_never_six() -> None:
    target = parse_target("squadron#7")
    assert target.form is TargetForm.REPO_NUMBER
    assert target.repository == "squadron"
    assert target.number == 7
    assert target.owner is None


@pytest.mark.parametrize("text", ["7", "#7"])
def test_bare_number_is_form_five_never_six(text: str) -> None:
    target = parse_target(text)
    assert target.form is TargetForm.NUMBER
    assert target.number == 7


def test_branch_named_only_digits_is_unreachable_by_design() -> None:
    """A branch literally named "7" cannot be addressed. Intended, not a bug.

    Rule 5 precedes rule 6, so an all-digit string is always the number form.
    Such a branch is reachable through its PR number or an explicit form.
    """
    assert parse_target("7").form is TargetForm.NUMBER


def test_branch_is_the_fallthrough() -> None:
    target = parse_target("feat/add-widget")
    assert target.form is TargetForm.BRANCH
    assert target.branch == "feat/add-widget"


@pytest.mark.parametrize(
    "text",
    [
        "has a space",
        "tab\there",
        "ctrl\x01char",
        "..leading-dots",
        "trailing.",
        "caret^ref",
        "tilde~1",
        "colon:ref",
        "question?",
        "star*",
        "bracket[0]",
        "double//slash",
        "reflog@{0}",
        "feature.lock",
    ],
)
def test_invalid_branch_names_raise_syntax_error(text: str) -> None:
    with pytest.raises(TargetSyntaxError):
        parse_target(text)


def test_syntax_error_carries_a_fix_hint() -> None:
    with pytest.raises(TargetSyntaxError) as excinfo:
        parse_target("not a target")
    assert excinfo.value.fix_hint is not None
