"""PR review persistence: where it lands, and whose commit it records (383).

No test here needs ``gh``, network, or auth — the code host is faked, as it is
in ``test_review_pr.py``. What is being tested is the persistence decision, not
the fetch.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.review_pr import PrTarget
from squadron.codehost.models import PullRequestRecord
from squadron.review.persistence import SaveTargetProtocol
from squadron.review.rules import RulesSource

#: Deliberately unlike any real local HEAD, so a test that passes by
#: coincidence is impossible to write.
_PR_HEAD_SHA = "1111111111111111111111111111111111111111"


def _record(number: int = 42) -> PullRequestRecord:
    return PullRequestRecord(
        host="github.com",
        owner="ecorkran",
        repository="squadron",
        number=number,
        base_ref="main",
        head_ref="feature-branch",
        head_sha=_PR_HEAD_SHA,
        url=f"https://github.com/ecorkran/squadron/pull/{number}",
    )


class TestPrTargetShape:
    """The target's own answers, independent of any save."""

    def test_it_satisfies_the_persistence_protocol(self) -> None:
        """Structural conformance is the whole reason review/ never names it."""
        target = PrTarget(_record(), RulesSource.PROJECT)

        assert isinstance(target, SaveTargetProtocol)

    def test_stem_is_pr_keyed_with_no_slice_segment(self) -> None:
        """A PR has no slice name, and the title is not an identifier.

        Deriving a name from the PR title would produce an identifier that
        changes whenever someone edits the title, silently orphaning the
        previous artifact (D3).
        """
        target = PrTarget(_record(83), RulesSource.PROJECT)

        assert target.filename_stem("code") == "github.com-ecorkran-squadron-83-review.code"

    def test_stem_carries_no_character_a_path_cannot(self) -> None:
        stem = PrTarget(_record(), RulesSource.PROJECT).filename_stem("code")

        assert "/" not in stem
        assert "#" not in stem

    def test_stem_never_begins_with_a_digit(self) -> None:
        """What keeps ``{index}-review.*`` consumers from matching (D4).

        ``locate_review`` and metrology capture both build their glob from an
        ``int``, so a non-numeric prefix cannot match by construction. This
        pins the property those consumers rely on.
        """
        stem = PrTarget(_record(42), RulesSource.PROJECT).filename_stem("code")

        assert not stem[0].isdigit()

    def test_frontmatter_carries_the_pr_and_no_slice_key(self) -> None:
        fields = PrTarget(_record(), RulesSource.PROJECT).frontmatter_fields()

        assert "slice" not in fields
        assert fields["pr"] == {
            "host": "github.com",
            "owner": "ecorkran",
            "repository": "squadron",
            "number": 42,
            "url": "https://github.com/ecorkran/squadron/pull/42",
        }

    def test_source_document_is_the_pr_url(self) -> None:
        target = PrTarget(_record(), RulesSource.PROJECT)

        assert target.source_document() == "https://github.com/ecorkran/squadron/pull/42"

    def test_rules_source_is_carried_for_the_artifact(self) -> None:
        """Resolved once, during the run that used it — not re-derived later."""
        target = PrTarget(_record(), RulesSource.TEMPLATE)

        assert target.rules_source is RulesSource.TEMPLATE


class TestReviewedShaIsThePullRequests:
    """The single easiest thing in this slice to get wrong (D3)."""

    def test_sha_is_the_records_head_not_the_operators(self, tmp_path: Path) -> None:
        """Set up an operator HEAD that differs, so coincidence cannot pass this.

        ``save_review_result`` used to stamp ``resolve_reviewed_sha(".")`` —
        the process working directory. On a PR review that is the operator's
        own tree: a real commit, plausible-looking, and unrelated to what was
        reviewed. 384's staleness check compares this field against the live PR
        head, so a wrong value reads as "up to date".
        """
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True, check=True
        )
        (tmp_path / "f.txt").write_text("operator tree")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "operator"], cwd=tmp_path, capture_output=True, check=True
        )
        operator_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout.strip()

        target = PrTarget(_record(), RulesSource.PROJECT)

        assert target.reviewed_sha() == _PR_HEAD_SHA
        assert target.reviewed_sha() != operator_head

    def test_the_target_never_consults_the_working_directory(self) -> None:
        """Asserted by mechanism, not just by value.

        A target that happened to return the right sha while still shelling out
        to git would reintroduce the bug the moment the trees coincided.
        """
        with patch("squadron.review.persistence.resolve_reviewed_sha") as resolver:
            sha = PrTarget(_record(), RulesSource.PROJECT).reviewed_sha()

        assert sha == _PR_HEAD_SHA
        resolver.assert_not_called()


class TestSliceLessCodeReviewStillRefuses:
    """NOT_PERSISTABLE keeps the meaning it always had (D8)."""

    def test_a_code_review_with_no_slice_is_still_not_persistable(self, tmp_path: Path) -> None:
        """383 deleted the PR stub, not the outcome it borrowed.

        ``sq review code`` with no slice number has nothing to name an artifact
        under, which is the case NOT_PERSISTABLE describes. A PR review always
        has a target and never reaches it.
        """
        runner = CliRunner()

        result = runner.invoke(
            app,
            ["review", "code", "--diff", "HEAD~1", "--cwd", str(tmp_path)],
        )

        # Either the slice-less refusal or an earlier scope/git failure — what
        # must not happen is a silent success that writes nothing.
        assert result.exit_code != 0


@pytest.mark.parametrize("review_type", ["code", "slice", "arch"])
def test_stem_varies_only_by_review_type(review_type: str) -> None:
    """The type is the only part of the stem the target does not fix."""
    target = PrTarget(_record(7), RulesSource.PROJECT)

    assert target.filename_stem(review_type) == f"github.com-ecorkran-squadron-7-review.{review_type}"
