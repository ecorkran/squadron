"""Blob identity of a reviewed document and of its parent (#374, part 1).

``reviewedSha`` is the commit HEAD was at when a review ran. It names the text
that was reviewed only when the document was committed and unchanged since, so
a review of an uncommitted or edited document stamps a commit that does not
hold the reviewed text. These keys record the document's working-tree blob, and
whether that blob equals the version at HEAD, for the document and for the
parent its frontmatter names. ``reviewedSha`` itself is unchanged: its
consumers read it as a commit.

Paths are relative to the working directory, as every ``project-documents``
path in squadron is.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

from squadron.documents.frontmatter import read_frontmatter
from squadron.review.git_utils import run_git

_logger = logging.getLogger(__name__)

PARENT_FRONTMATTER_KEY = "parent"
DOCUMENT_BLOB_KEY = "reviewedBlob"
DOCUMENT_BLOB_CURRENT_KEY = "reviewedBlobCurrent"
PARENT_BLOB_KEY = "parentBlob"
PARENT_BLOB_CURRENT_KEY = "parentBlobCurrent"


class BlobStamp(NamedTuple):
    """A document's working-tree blob, and whether it equals the blob at HEAD."""

    blob: str
    current: bool


class DocumentBlobs(NamedTuple):
    """Stamps for a reviewed document and its parent. Either is None when unresolved."""

    document: BlobStamp | None
    parent: BlobStamp | None


def local_path(source: str | None) -> Path | None:
    """``source`` as a path, or None when it names no document."""
    return Path(source) if source else None


def resolve_blob_stamp(path: Path) -> BlobStamp | None:
    """Stamp ``path``, or return None with a WARNING when it cannot be stamped.

    A file that is not at HEAD (new or uncommitted) gives ``current=False``.
    That is the case this stamp exists to show, so it is not an error.
    """
    if not path.is_file():
        _logger.warning("review: %s is not a file; its blob will not be stamped", path)
        return None
    absolute = path.resolve()
    directory = str(absolute.parent)
    top = run_git(["rev-parse", "--show-toplevel"], cwd=directory)
    if top is None or top.returncode != 0:
        _logger.warning("review: %s is not in a git repository; its blob will not be stamped", path)
        return None
    repo_root = top.stdout.strip()
    relative = absolute.relative_to(repo_root).as_posix()
    blob = run_git(["hash-object", "--", str(absolute)], cwd=directory)
    head = run_git(["rev-parse", "-q", "--verify", f"HEAD:{relative}"], cwd=repo_root)
    if blob is None or blob.returncode != 0 or head is None:
        _logger.warning("review: git could not hash %s; its blob will not be stamped", path)
        return None
    current_blob = blob.stdout.strip()
    head_blob = head.stdout.strip() if head.returncode == 0 else ""
    return BlobStamp(blob=current_blob, current=current_blob == head_blob)


def resolve_document_blobs(document: Path | None) -> DocumentBlobs | None:
    """Stamps for ``document`` and the parent its frontmatter names; None when there is no document."""
    if document is None:
        return None
    return DocumentBlobs(
        document=resolve_blob_stamp(document),
        parent=_resolve_parent_stamp(document),
    )


def _resolve_parent_stamp(document: Path) -> BlobStamp | None:
    """Stamp the document's frontmatter ``parent:``; None when it names none."""
    if not document.is_file():
        # resolve_blob_stamp has already logged this; there is no frontmatter to read.
        return None
    frontmatter = read_frontmatter(document)
    parent_value = frontmatter.get(PARENT_FRONTMATTER_KEY) if frontmatter else None
    if parent_value is None:
        return None
    if not isinstance(parent_value, str):
        _logger.warning("review: %s has a non-string parent; parentBlob will not be stamped", document)
        return None
    return resolve_blob_stamp(Path(parent_value))


def document_blob_lines(blobs: DocumentBlobs) -> list[str]:
    """Frontmatter lines for the resolved stamps. An unresolved stamp writes no keys."""
    lines: list[str] = []
    if blobs.document is not None:
        lines += _stamp_lines(DOCUMENT_BLOB_KEY, DOCUMENT_BLOB_CURRENT_KEY, blobs.document)
    if blobs.parent is not None:
        lines += _stamp_lines(PARENT_BLOB_KEY, PARENT_BLOB_CURRENT_KEY, blobs.parent)
    return lines


def _stamp_lines(blob_key: str, current_key: str, stamp: BlobStamp) -> list[str]:
    return [
        f"{blob_key}: {stamp.blob}",
        f"{current_key}: {'true' if stamp.current else 'false'}",
    ]
