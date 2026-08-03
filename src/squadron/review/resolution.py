"""``sq review resolve`` — did the work address a prior review's findings?

This path asks the findings-addressed question outside the gate loop, against
a review file already on disk. It reads that file, measures what changed since
it was authored, consults the judge over what the deterministic screens cannot
settle, and writes a separate resolution artifact. It never touches the review
file: the review's ``verdict:`` is the reviewer's record, and a derived
resolution is evidence about it, not an amendment to it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from squadron.documents.frontmatter import read_frontmatter
from squadron.review.addressed.models import FindingRecord, records_from_frontmatter
from squadron.review.git_utils import run_git
from squadron.review.models import Verdict
from squadron.review.persistence import REVIEWS_DIR

_logger = logging.getLogger(__name__)

#: Filename shape written by ``save_review_result``/``save_review_file``:
#: ``{index}-review.{type}.{slice-name}.md``. Position 1 is the review type.
_REVIEW_TYPE_FIELD = 1


class DiffBaseSource(StrEnum):
    """Where the diff base came from — recorded on the resolution artifact.

    A reader of the artifact needs this to know how much to trust the answer:
    a ``frontmatter`` base is the exact commit the review was authored against,
    while ``file_history`` is an approximation for reviews written before the
    stamp existed.
    """

    FRONTMATTER = "frontmatter"
    FILE_HISTORY = "file-history"
    SINCE = "since"


class ResolutionError(Exception):
    """Raised when the resolve path cannot proceed on the inputs it was given.

    Every case is one the caller must see rather than absorb: no review for the
    index, several reviews with no type to disambiguate them, or a review file
    that carries no readable frontmatter.
    """


@dataclass(frozen=True)
class LoadedReview:
    """A review file's frontmatter, its recorded verdict, and its findings."""

    path: Path
    frontmatter: dict[str, object]
    verdict: str
    findings: list[FindingRecord]


def _reviews_dir(cwd: str) -> Path:
    return Path(cwd) / REVIEWS_DIR


def review_type_of(path: Path) -> str:
    """The review type encoded in *path*'s filename.

    Raises:
        ResolutionError: If the filename does not carry a type field.
    """
    fields = path.name.split(".")
    if len(fields) <= _REVIEW_TYPE_FIELD:
        raise ResolutionError(
            f"Cannot read a review type from '{path.name}' — expected "
            f"'{{index}}-review.{{type}}.{{slice-name}}.md'"
        )
    return fields[_REVIEW_TYPE_FIELD]


def locate_review(index: int, review_type: str | None, cwd: str) -> Path:
    """Find the review file for *index*, inferring its type when not given.

    An ambiguous index is an error, never a guess: which review a resolution
    is accountable to is the caller's decision, and picking one silently would
    attribute the answer to the wrong review.

    Raises:
        ResolutionError: If no review matches, or if several do and no
            ``review_type`` was given to choose between them.
    """
    reviews_dir = _reviews_dir(cwd)
    pattern = f"{index}-review.{review_type}.*.md" if review_type else f"{index}-review.*.md"
    matches = sorted(reviews_dir.glob(pattern))

    if not matches:
        raise ResolutionError(f"No review file matching '{pattern}' in {reviews_dir}")
    if len(matches) > 1:
        listed = ", ".join(path.name for path in matches)
        if review_type:
            raise ResolutionError(f"Several review files match '{pattern}' in {reviews_dir}: {listed}")
        raise ResolutionError(
            f"Several reviews exist for index {index} in {reviews_dir}: {listed} — "
            "name the review type explicitly"
        )
    return matches[0]


def load_review(path: Path) -> LoadedReview:
    """Read *path*'s frontmatter, recorded verdict, and CONCERN+-eligible findings.

    The verdict is the review's *own recorded* verdict, read here and never
    re-derived — the verdict-consistency screen compares it against the parsed
    findings, so re-deriving it from those findings would make the comparison
    vacuous.

    Raises:
        ResolutionError: If the file has no readable YAML frontmatter.
    """
    frontmatter = read_frontmatter(path)
    if frontmatter is None:
        raise ResolutionError(f"No readable YAML frontmatter in {path}")

    raw_verdict = frontmatter.get("verdict")
    verdict = str(raw_verdict).upper() if isinstance(raw_verdict, str) else Verdict.UNKNOWN
    if not isinstance(raw_verdict, str):
        _logger.warning(
            "review-resolve: %s carries no verdict: field; treating it as %s",
            path.name,
            Verdict.UNKNOWN,
        )

    raw_findings = frontmatter.get("findings")
    if raw_findings is None:
        findings: list[FindingRecord] = []
    elif isinstance(raw_findings, list):
        findings = records_from_frontmatter(list(raw_findings))  # pyright: ignore[reportUnknownArgumentType]
    else:
        _logger.warning(
            "review-resolve: %s has a findings: field that is %s, not a list; "
            "treating it as no findings",
            path.name,
            type(raw_findings).__name__,
        )
        findings = []

    return LoadedReview(
        path=path,
        frontmatter=frontmatter,
        verdict=verdict,
        findings=findings,
    )


def resolve_review_diff_base(
    frontmatter: dict[str, object],
    review_path: Path,
    *,
    since: str | None,
    cwd: str,
) -> tuple[str | None, DiffBaseSource]:
    """Decide what "since the review" means, and say where that came from.

    Named ``resolve_review_diff_base`` rather than ``resolve_diff_base``:
    ``review.git_utils`` already owns that name for a different question (which
    branch slice work forks from), and two same-named resolvers in one package
    is a patch-the-wrong-one bug waiting to happen.

    Precedence is explicit user intent first: ``--since`` always wins, and no
    git call is made to establish it — validating that the ref resolves is the
    diff's job, not this function's. Otherwise the review's own ``reviewedSha``
    stamp is the anchor. A review authored before that stamp existed falls back
    to the last commit that touched the review file, which is an approximation
    and says so at WARNING.

    A ``None`` base means the fallback could not answer either. That is not
    classified here: the caller runs the diff and reports the git failure with
    the exact command that failed.
    """
    if since is not None:
        return since, DiffBaseSource.SINCE

    stamped = frontmatter.get("reviewedSha")
    if isinstance(stamped, str) and stamped.strip():
        return stamped.strip(), DiffBaseSource.FRONTMATTER

    _logger.warning(
        "review-resolve: %s carries no reviewedSha; falling back to the last commit "
        "that touched the review file — the diff base is approximate",
        review_path.name,
    )
    completed = run_git(
        ["log", "-1", "--format=%H", "--", str(review_path)],
        cwd=cwd,
    )
    if completed is None or completed.returncode != 0:
        return None, DiffBaseSource.FILE_HISTORY
    return completed.stdout.strip() or None, DiffBaseSource.FILE_HISTORY
