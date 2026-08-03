"""The resolution artifact — one immutable record per ``sq review resolve`` run.

Deliberately outside the ``*-review.*`` namespace, for the same reason gate
evidence is: metrology globs that pattern, and a resolution is evidence *about*
a review rather than a review. The ``-resolution.`` segment is what keeps it
out; nothing else about the name may reintroduce ``-review.``.

Nothing here ever overwrites: each run writes the next ``-r{n}``. The artifact's
whole purpose is an audit trail a human can read after the fact, and a silent
overwrite would destroy exactly the evidence someone came looking for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from squadron.documents.frontmatter import render_frontmatter_block, yaml_safe
from squadron.review.addressed.models import FindingOutcome
from squadron.review.persistence import REVIEWS_DIR

#: Frontmatter docType — provenance-distinct from a review and from gate evidence.
RESOLUTION_DOC_TYPE = "review-resolution"

#: Filename pattern. ``{revision}`` increments; a resolution is never rewritten.
RESOLUTION_FILENAME_FORMAT = "{index}-resolution.{review_type}.{slice_name}-r{revision}.md"

#: Glob for discovering prior revisions of one index+type+slice.
RESOLUTION_GLOB_FORMAT = "{index}-resolution.{review_type}.{slice_name}-r*.md"

#: Reads the revision back off a filename the format above produced.
_REVISION_PATTERN = re.compile(r"-r(?P<revision>\d+)\.md$")

#: The revision a first resolution is written as.
FIRST_REVISION = 1

_DATE_FORMAT = "%Y%m%d"


def today_stamp() -> int:
    """Today as ``YYYYMMDD`` — the date format every artifact frontmatter uses."""
    return int(datetime.now().strftime(_DATE_FORMAT))


@dataclass(frozen=True)
class ResolutionRecord:
    """Everything one resolution run concluded, in one object.

    Mirrors ``GateEvidence``'s shape deliberately: one record backs the whole
    artifact, so the same facts are never assembled twice.
    """

    index: int
    review_file: str
    review_type: str
    slice_name: str
    project: str
    #: The review's own verdict, carried through verbatim. This artifact never
    #: edits it and never restates it as its own conclusion.
    review_verdict: str
    resolution: str
    #: ``YYYYMMDD`` as an int, matching how every other squadron-written
    #: frontmatter emits it — quoting it here would hand a cf-side reader a
    #: different type for this docType than for every review beside it.
    date_created: int
    #: What the review assessed. None when the review carried no stamp and the
    #: fallback answered instead — ``sha_source`` says which.
    reviewed_sha: str | None = None
    #: The base the diff actually ran against.
    resolved_sha: str | None = None
    sha_source: str | None = None
    judge_model: str | None = None
    outcomes: list[FindingOutcome] = field(default_factory=list[FindingOutcome])

    def finding_records(self) -> list[dict[str, object]]:
        """Per-finding outcomes as plain data, for the frontmatter block."""
        return [
            {
                "id": outcome.finding_id,
                "status": outcome.status.value,
                "screen": outcome.screen.value,
                "successor": outcome.successor_id,
                "note": outcome.note,
            }
            for outcome in self.outcomes
        ]


def resolution_frontmatter(record: ResolutionRecord) -> dict[str, object]:
    """The frontmatter mapping, as data — serialized by yaml, never by f-string."""
    data: dict[str, object] = {
        "docType": RESOLUTION_DOC_TYPE,
        "layer": "project",
        "reviewFile": record.review_file,
        "reviewType": record.review_type,
        "slice": record.slice_name,
        "project": record.project,
        "reviewVerdict": yaml_safe(record.review_verdict),
        "resolution": yaml_safe(record.resolution),
        "reviewedSha": yaml_safe(record.reviewed_sha),
        "resolvedSha": yaml_safe(record.resolved_sha),
        "shaSource": yaml_safe(record.sha_source),
        "judgeModel": yaml_safe(record.judge_model),
        "dateCreated": record.date_created,
    }
    if record.outcomes:
        data["findingStatuses"] = [
            {key: yaml_safe(value) for key, value in finding.items() if value is not None}
            for finding in record.finding_records()
        ]
    return data


def render_resolution(record: ResolutionRecord) -> str:
    """Render the artifact: frontmatter carrying the whole record, then prose."""
    lines = [
        render_frontmatter_block(resolution_frontmatter(record)),
        "",
        f"# Review Resolution — slice {record.index} ({record.review_type})",
        "",
        f"Resolution **{record.resolution}** for `{record.review_file}`, "
        f"whose recorded verdict is {record.review_verdict}.",
        "",
        f"Measured against `{record.resolved_sha or 'unresolved'}` ({record.sha_source or 'none'}).",
        "",
    ]
    if record.outcomes:
        lines.append("## Findings")
        lines.append("")
        for outcome in record.outcomes:
            note = f" — {outcome.note}" if outcome.note else ""
            successor = f" (successor: {outcome.successor_id})" if outcome.successor_id else ""
            lines.append(
                f"- `{outcome.finding_id}`: **{outcome.status.value}** "
                f"[{outcome.screen.value}]{successor}{note}"
            )
        lines.append("")
    else:
        lines.append("No CONCERN+ findings were in scope for this resolution.")
        lines.append("")
    lines.append("This artifact does not change the review's `verdict:` — it is evidence about it.")
    lines.append("")
    return "\n".join(lines)


def next_revision(reviews_dir: Path, *, index: int, review_type: str, slice_name: str) -> int:
    """The revision a new resolution for this review should be written as.

    One past the highest already on disk, so a resolution never lands on a
    filename that exists. Files whose revision segment does not parse are
    ignored rather than guessed at — a hand-renamed file must not be able to
    push the counter backwards onto a real one.
    """
    pattern = RESOLUTION_GLOB_FORMAT.format(index=index, review_type=review_type, slice_name=slice_name)
    revisions = [
        int(match.group("revision"))
        for path in reviews_dir.glob(pattern)
        if (match := _REVISION_PATTERN.search(path.name)) is not None
    ]
    return max(revisions, default=FIRST_REVISION - 1) + 1


def save_resolution(
    rendered: str,
    *,
    index: int,
    review_type: str,
    slice_name: str,
    cwd: str,
) -> Path:
    """Write *rendered* to the next free ``-r{n}`` path, never over an existing one.

    Raises:
        FileExistsError: If the computed path somehow already exists. This
            artifact is an immutable audit trail; overwriting one silently is
            the same class of bug the review overwrite guard exists to prevent,
            so a collision fails loudly rather than destroying a record.
    """
    reviews_dir = Path(cwd) / REVIEWS_DIR
    reviews_dir.mkdir(parents=True, exist_ok=True)

    revision = next_revision(reviews_dir, index=index, review_type=review_type, slice_name=slice_name)
    path = reviews_dir / RESOLUTION_FILENAME_FORMAT.format(
        index=index, review_type=review_type, slice_name=slice_name, revision=revision
    )
    if path.exists():
        raise FileExistsError(
            f"Refusing to overwrite the resolution artifact at {path} — "
            "resolutions are an append-only audit trail"
        )
    path.write_text(rendered, encoding="utf-8")
    return path
