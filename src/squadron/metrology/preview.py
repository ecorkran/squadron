"""How many characters of a commit sha or content hash the metrology output shows."""

#: Commit shas in messages and in commands the reader may copy.
SHA_PREVIEW_CHARS = 12
#: Hashes, and commit shas in report tables where width is tight.
COMPACT_PREVIEW_CHARS = 8


def abbrev(value: str) -> str:
    """The leading ``COMPACT_PREVIEW_CHARS`` of a sha or hash."""
    return value[:COMPACT_PREVIEW_CHARS]
