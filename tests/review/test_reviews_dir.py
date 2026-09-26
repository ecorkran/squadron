"""Reviews-directory precedence and its failure modes (slice 383, D5).

The chain is table-tested rather than asserted one rule at a time: the bugs
worth catching here are ordering bugs, and a test per rule in isolation cannot
see an ordering bug. Each case sets up *more* than one rule's precondition and
asserts the earlier one wins.

The failure modes get their own tests because D5 enumerates them and the
architecture's "failure modes are observable" principle applies to a new I/O
path directly. The one that matters most is the non-obvious one: a failure of
the selected directory must never advance to the next rule. Falling through
would write the review somewhere the operator did not ask for while reporting
success, which is worse than not writing it.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.review.persistence import REVIEWS_DIR
from squadron.review.reviews_dir import (
    ReviewsDirRule,
    resolve_reviews_dir,
    user_reviews_root,
)

_HOST = "github.com"
_OWNER = "ecorkran"
_REPO = "squadron"


def _resolve(flag: str | None, cwd: Path) -> tuple[Path, ReviewsDirRule]:
    return resolve_reviews_dir(
        flag=flag,
        cwd=str(cwd),
        host=_HOST,
        owner=_OWNER,
        repository=_REPO,
    )


class TestPrecedenceOrder:
    """Each case satisfies several rules at once; the earlier must win."""

    def test_flag_beats_an_existing_project_directory(self, tmp_path: Path) -> None:
        (tmp_path / REVIEWS_DIR).mkdir(parents=True)
        override = tmp_path / "elsewhere"

        with patch("squadron.review.reviews_dir.get_config", return_value=None):
            chosen, rule = _resolve(str(override), tmp_path)

        assert chosen == override
        assert rule is ReviewsDirRule.FLAG

    def test_flag_beats_the_config_key(self, tmp_path: Path) -> None:
        override = tmp_path / "elsewhere"

        with patch(
            "squadron.review.reviews_dir.get_config",
            return_value=str(tmp_path / "configured"),
        ):
            chosen, rule = _resolve(str(override), tmp_path)

        assert chosen == override
        assert rule is ReviewsDirRule.FLAG

    def test_existing_project_directory_beats_the_config_key(self, tmp_path: Path) -> None:
        project_reviews = tmp_path / REVIEWS_DIR
        project_reviews.mkdir(parents=True)

        with patch(
            "squadron.review.reviews_dir.get_config",
            return_value=str(tmp_path / "configured"),
        ):
            chosen, rule = _resolve(None, tmp_path)

        assert chosen == project_reviews
        assert rule is ReviewsDirRule.PROJECT

    def test_config_key_beats_the_built_in_default(self, tmp_path: Path) -> None:
        configured = tmp_path / "configured"

        with patch("squadron.review.reviews_dir.get_config", return_value=str(configured)):
            chosen, rule = _resolve(None, tmp_path)

        assert chosen == configured
        assert rule is ReviewsDirRule.CONFIG

    def test_built_in_default_is_keyed_by_host_owner_repo(self, tmp_path: Path) -> None:
        with (
            patch("squadron.review.reviews_dir.get_config", return_value=None),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            chosen, rule = _resolve(None, tmp_path)

        assert chosen == tmp_path / ".config" / "squadron" / "reviews" / _HOST / _OWNER / _REPO
        assert rule is ReviewsDirRule.DEFAULT


class TestRuleTwoNeverCreatesAProjectDirectory:
    """The one rule that requires its directory to exist rather than making it."""

    def test_absent_project_directory_is_skipped_not_created(self, tmp_path: Path) -> None:
        """Reviewing a PR must not put project-documents/ in someone's repo.

        This is why rule 2 tests for existence instead of creating: a squadron
        user reviewing a pull request in a repository that never adopted the
        convention would otherwise find a new directory tree in their checkout
        as a side effect.
        """
        configured = tmp_path / "configured"

        with patch("squadron.review.reviews_dir.get_config", return_value=str(configured)):
            chosen, rule = _resolve(None, tmp_path)

        assert chosen == configured
        assert rule is ReviewsDirRule.CONFIG
        assert not (tmp_path / "project-documents").exists()

    def test_a_file_where_the_project_directory_would_be_is_not_treated_as_one(
        self, tmp_path: Path
    ) -> None:
        """``is_dir()`` rather than ``exists()``, asserted.

        A path that exists but is a file would satisfy ``exists()`` and then
        fail at write time, having already displaced the rules that could have
        succeeded.
        """
        project_reviews = tmp_path / REVIEWS_DIR
        project_reviews.parent.mkdir(parents=True)
        project_reviews.write_text("not a directory")

        with patch(
            "squadron.review.reviews_dir.get_config",
            return_value=str(tmp_path / "configured"),
        ):
            chosen, rule = _resolve(None, tmp_path)

        assert rule is ReviewsDirRule.CONFIG


class TestSelectionHappensOnce:
    """A failure of the chosen directory is an error, never the next rule."""

    def test_an_unwritable_flag_path_does_not_fall_through(self, tmp_path: Path) -> None:
        """The silent fallback the project rules forbid, pinned.

        ``--reviews-dir`` pointing somewhere unwritable must surface as a
        failed save naming that path. If the resolver advanced to the next rule
        the review would land in the project directory instead and report
        success — the operator asked for one location and silently got another.
        """
        project_reviews = tmp_path / REVIEWS_DIR
        project_reviews.mkdir(parents=True)
        unwritable = tmp_path / "unwritable" / "nested"

        with patch("squadron.review.reviews_dir.get_config", return_value=None):
            chosen, rule = _resolve(str(unwritable), tmp_path)

        # Selection is the flag's, full stop. Whether the path can be created
        # is save_review_result's problem and is reported, not worked around.
        assert chosen == unwritable
        assert rule is ReviewsDirRule.FLAG
        # The next rule's location is untouched: nothing was written there.
        assert list(project_reviews.iterdir()) == []

    def test_the_resolver_creates_nothing(self, tmp_path: Path) -> None:
        """Creation belongs to the save path, so a failure is reportable there.

        A resolver that created directories would make every precedence query
        a filesystem mutation, including the ones a caller makes just to print
        where a review *would* go.
        """
        target = tmp_path / "does-not-exist"

        with patch("squadron.review.reviews_dir.get_config", return_value=None):
            chosen, _ = _resolve(str(target), tmp_path)

        assert chosen == target
        assert not target.exists()


class TestConfigValueHandling:
    def test_an_empty_config_value_is_not_a_location(self, tmp_path: Path) -> None:
        """``review.external_reviews_dir = ""`` means unset, not the cwd.

        An empty string would otherwise resolve to ``Path("")`` — the current
        directory — and scatter reviews wherever the operator happened to be.
        """
        with (
            patch("squadron.review.reviews_dir.get_config", return_value=""),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            chosen, rule = _resolve(None, tmp_path)

        assert rule is ReviewsDirRule.DEFAULT

    @pytest.mark.parametrize("value", [None, 42, [], {}])
    def test_a_non_string_config_value_is_ignored(self, value: object, tmp_path: Path) -> None:
        """Config values arrive untyped; anything but a non-empty string is unset."""
        with (
            patch("squadron.review.reviews_dir.get_config", return_value=value),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            _, rule = _resolve(None, tmp_path)

        assert rule is ReviewsDirRule.DEFAULT


class TestRuleIsReportable:
    def test_every_rule_names_itself_in_operator_terms(self) -> None:
        """The rule is printed with the result, so its value is user-facing.

        An operator who does not know where their review went has been failed
        whether or not the file was written (D5), and "DEFAULT" tells them
        less than the name of the thing they would have to change.
        """
        assert ReviewsDirRule.FLAG.value == "--reviews-dir"
        assert ReviewsDirRule.CONFIG.value == "review.external_reviews_dir"
        assert ReviewsDirRule.PROJECT.value == "project reviews directory"
        assert ReviewsDirRule.DEFAULT.value == "built-in default"


class TestRepositoryScoped:
    """Whether a rule's directory holds one repository's reviews (slice 926, D1)."""

    @pytest.mark.parametrize("rule", list(ReviewsDirRule))
    def test_every_rule_has_an_explicit_answer(self, rule: ReviewsDirRule) -> None:
        """A rule added without deciding its scoping fails here, not silently."""
        assert isinstance(rule.repository_scoped, bool)

    @pytest.mark.parametrize(
        ("rule", "scoped"),
        [
            (ReviewsDirRule.PROJECT, True),
            (ReviewsDirRule.DEFAULT, True),
            (ReviewsDirRule.CONFIG, False),
            (ReviewsDirRule.FLAG, False),
        ],
    )
    def test_mapping_matches_design_table(self, rule: ReviewsDirRule, scoped: bool) -> None:
        assert rule.repository_scoped is scoped


class TestUserRoot:
    def test_the_user_root_is_not_the_installed_package(self) -> None:
        """``data_dir()`` is the installed package's read-only directory.

        382's D3 recorded this correction for worktrees; the same mistake here
        would put reviews inside site-packages.
        """
        root = user_reviews_root()

        assert root == Path.home() / ".config" / "squadron" / "reviews"
        assert "site-packages" not in str(root)
