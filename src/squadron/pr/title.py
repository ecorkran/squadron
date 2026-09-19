"""Title resolution for ``sq pr create`` (D4a)."""

from __future__ import annotations

import re

from squadron.pr.composer import Composer
from squadron.review.git_utils import CommitRecord

#: The design document's own heading: ``# Slice Design: {name}``. Only this
#: exact shape yields a title (D4a); anything else falls through to the
#: model rather than emitting a malformed title.
_DESIGN_H1_RE = re.compile(r"^#\s+Slice Design:\s*(.+?)\s*$", re.MULTILINE)

#: The bound on a model-composed title — the project's own commit-summary
#: convention, applied to the same kind of object (D4a).
_TITLE_MAX_CHARS = 72


async def resolve_title(
    *,
    title_flag: str | None,
    design_text: str | None,
    commits: tuple[CommitRecord, ...],
    compose: Composer,
) -> str:
    """Resolve the PR title per D4a's three-term table.

    1. ``--title`` given: use it verbatim.
    2. A resolved slice branch whose design carries a matching H1: the
       design's own human name, minus the ``Slice Design: `` prefix. Makes
       no model call — the slice is already named.
    3. Otherwise: the model composes one line within the title bound from the
       commit subjects alone. A response that is empty, multi-line, or over
       the bound falls back to the first commit's subject — always present,
       always truthful, and the slice's one deliberate degradation.
    """
    if title_flag is not None:
        return title_flag

    if design_text is not None:
        human_name = _design_h1(design_text)
        if human_name is not None:
            return human_name

    return await _compose_title(commits, compose)


def _design_h1(design_text: str) -> str | None:
    """The design's ``# Slice Design: {name}`` heading, or None if absent/mismatched."""
    match = _DESIGN_H1_RE.search(design_text)
    if match is None:
        return None
    name = match.group(1).strip()
    return name or None


async def _compose_title(commits: tuple[CommitRecord, ...], compose: Composer) -> str:
    """The model-composed title, falling back to the first commit's subject.

    *commits* is never empty here: input gathering refuses an empty range.
    """
    fallback = commits[0].subject
    subjects = "\n".join(f"- {commit.subject}" for commit in commits)
    prompt = (
        f"Write one pull-request title, at most {_TITLE_MAX_CHARS} characters, for a PR whose "
        f"commits are:\n\n{subjects}\n\nRespond with only the title line."
    )
    response = await compose(prompt)
    candidate = response.strip()
    if not candidate or "\n" in candidate or len(candidate) > _TITLE_MAX_CHARS:
        return fallback
    return candidate
