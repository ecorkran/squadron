"""Where a review artifact lands, and which rule decided (slice 383, D5).

A PR review has no project to live in when the checkout is someone else's
repository, which is the enterprise case the 380 initiative exists to serve.
That makes the reviews directory a decision rather than a constant, and a
decision an operator must be able to see: one who does not know where their
review went has been failed whether or not the file was written.

The order is fixed:

1. ``--reviews-dir`` — this invocation only.
2. the checkout's own ``project-documents/user/reviews/``, **when it already
   exists**.
3. the ``review.external_reviews_dir`` config key.
4. ``~/.config/squadron/reviews/<host>/<owner>/<repo>/``.

Rule 2 requires the directory to exist rather than creating it. Creating it is
what would put a ``project-documents/`` tree inside a repository that never
asked for one, as a side effect of reviewing a pull request.

Takes host, owner and repository as plain strings rather than a
``PullRequestRecord``: this module sits in ``review/``, which must never import
``codehost`` (enforced by ``tests/codehost/test_import_boundaries.py``). The
caller in the CLI layer, which already imports both, passes the three fields.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from squadron.config.manager import get_config
from squadron.review.persistence import REVIEWS_DIR


class ReviewsDirRule(StrEnum):
    """Which rule chose the directory. Printed with the result, never inferred."""

    FLAG = "--reviews-dir"
    PROJECT = "project reviews directory"
    CONFIG = "review.external_reviews_dir"
    DEFAULT = "built-in default"


def user_reviews_root() -> Path:
    """The per-user reviews root.

    Under ``~/.config/squadron/`` — the directory squadron already owns —
    deliberately **not** ``data_dir()``, which resolves to the installed
    package's read-only ``squadron/data/``. 382's D3 recorded the same
    correction for worktrees; the same reasoning applies here.
    """
    return Path.home() / ".config" / "squadron" / "reviews"


def resolve_reviews_dir(
    *,
    flag: str | None,
    cwd: str,
    host: str,
    owner: str,
    repository: str,
) -> tuple[Path, ReviewsDirRule]:
    """Choose the reviews directory and report which rule chose it.

    Selection happens **once**. A failure of the chosen directory — it cannot
    be created, or the write fails — is an error reported to the operator, not
    a fall-through to the next rule. Falling through would silently write
    somewhere the operator did not ask for, which is the silent fallback the
    project rules forbid: the review would appear to succeed while landing
    somewhere nobody looks.

    The directory is not created here. ``save_review_result`` creates it, and
    an ``OSError`` there is reported as an unsaved review with the path and the
    rule named.
    """
    if flag is not None:
        return Path(flag), ReviewsDirRule.FLAG

    project_reviews = Path(cwd) / REVIEWS_DIR
    if project_reviews.is_dir():
        return project_reviews, ReviewsDirRule.PROJECT

    configured = get_config("review.external_reviews_dir")
    if isinstance(configured, str) and configured:
        return Path(configured), ReviewsDirRule.CONFIG

    return user_reviews_root() / host / owner / repository, ReviewsDirRule.DEFAULT
