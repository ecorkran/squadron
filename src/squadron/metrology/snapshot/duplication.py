"""Token-window duplication detection, for any language (slice 401, D3).

Each adapter supplies a tokenizer; this module reads the files, runs one linear pass
over their token streams and reports the lines under any run of
``DUPLICATION_WINDOW_TOKENS`` tokens that occurs twice (type-1 clones: exact token
match, comments and layout already dropped by the tokenizer). Files are only compared
with files of the same language because the caller passes one language's files.
"""

from __future__ import annotations

import logging
from array import array
from collections.abc import Callable, Sequence
from pathlib import Path

from squadron.metrology.snapshot.lengths import decode_source, read_source_bytes
from squadron.metrology.snapshot.tool_support import tool_failed
from squadron.metrology.snapshot_models import (
    Measurement,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)

_logger = logging.getLogger(__name__)

#: Consecutive tokens that make a clone. Part of the counting definition, not a preference.
DUPLICATION_WINDOW_TOKENS = 100
#: Per language. About 133 bytes per token, so roughly 530 MiB at the ceiling (D3).
DUPLICATION_MAX_TOKENS = 4_000_000

DUPLICATION_COUNTING = (
    "non-blank lines under any run of "
    f"{DUPLICATION_WINDOW_TOKENS} consecutive tokens that occurs twice in the language's "
    "files; exact token match (type-1: renamed identifiers are not matched), comments and "
    "layout dropped; two runs in one file that overlap are not copies of each other; "
    f"absent past {DUPLICATION_MAX_TOKENS} tokens"
)

#: Repo-relative path and file text in, ordered (token text, 1-based line) pairs out.
Tokenizer = Callable[[str, str], list[tuple[str, int]]]

_HASH_BASE = 1_000_003
_HASH_MODULUS = (1 << 61) - 1

_COMMAND = "duplication token-window pass"


def duplication_tool_identity(parser: ToolIdentity) -> ToolIdentity:
    """The adapter's in-process parser identity, with the duplication counting text."""
    return parser.model_copy(update={"counting": DUPLICATION_COUNTING})


class _TokenizedFile:
    """One file as two parallel arrays: token ids and the line each token starts on."""

    def __init__(self, path: str, ids: array[int], lines: array[int]) -> None:
        self.path = path
        self.ids = ids
        self.lines = lines
        self.covered = bytearray(len(ids))


def _window_hashes(ids: array[int]) -> list[int]:
    """The hash of every window of ``DUPLICATION_WINDOW_TOKENS`` ids, by rolling hash."""
    width = DUPLICATION_WINDOW_TOKENS
    if len(ids) < width:
        return []
    leading = pow(_HASH_BASE, width - 1, _HASH_MODULUS)
    current = 0
    for token in ids[:width]:
        current = (current * _HASH_BASE + token) % _HASH_MODULUS
    hashes = [current]
    for start in range(len(ids) - width):
        current = ((current - ids[start] * leading) * _HASH_BASE + ids[start + width]) % _HASH_MODULUS
        hashes.append(current)
    return hashes


def _tokenize_file(
    repo_root: Path,
    path: str,
    tokenizer: Tokenizer,
    token_errors: tuple[type[Exception], ...],
    token_ids: dict[str, int],
) -> _TokenizedFile | None:
    """The file's token arrays, or None (with a WARNING) when it can't be tokenized."""
    raw = read_source_bytes(repo_root, path, "duplication")
    if raw is None:
        return None
    text = decode_source(raw, path, "not compared for duplication")
    if text is None:
        return None
    try:
        tokens = tokenizer(path, text)
    except MemoryError:
        raise
    except token_errors as exc:
        _logger.warning(
            "Can't tokenize %s (%s: %s); not compared for duplication", path, type(exc).__name__, exc
        )
        return None
    ids = array("I", (token_ids.setdefault(token, len(token_ids)) for token, _line in tokens))
    return _TokenizedFile(path, ids, array("I", (line for _token, line in tokens)))


def _mark(file: _TokenizedFile, start: int) -> None:
    width = DUPLICATION_WINDOW_TOKENS
    file.covered[start : start + width] = b"\x01" * width


def _find_repeats(files: Sequence[_TokenizedFile]) -> None:
    """Mark the tokens under every confirmed repeated window."""
    width = DUPLICATION_WINDOW_TOKENS
    # Every distinct window seen per hash: a collision adds an entry, so it can't hide a clone.
    seen_by_hash: dict[int, list[tuple[int, int]]] = {}
    for file_index, file in enumerate(files):
        for start, window_hash in enumerate(_window_hashes(file.ids)):
            window = file.ids[start : start + width]
            candidates = seen_by_hash.setdefault(window_hash, [])
            # Compare the ids themselves: a hash match alone is never a clone.
            match = next(
                (c for c in candidates if files[c[0]].ids[c[1] : c[1] + width] == window), None
            )
            if match is None:
                candidates.append((file_index, start))
                continue
            other_index, other_start = match
            if other_index == file_index and start - other_start < width:
                continue  # overlapping runs in one file are not copies of each other
            _mark(files[other_index], other_start)
            _mark(file, start)


def _duplicated_line_counts(files: Sequence[_TokenizedFile]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for file in files:
        lines = {file.lines[i] for i, flag in enumerate(file.covered) if flag}
        if lines:
            counts[file.path] = len(lines)
    return counts


def measure_duplication(
    repo_root: Path,
    files: Sequence[str],
    language: SourceLanguage,
    tool: ToolIdentity,
    tokenizer: Tokenizer,
    token_errors: tuple[type[Exception], ...],
) -> Measurement:
    """Duplicated lines per file for *files*, all of one language.

    A file that can't be read, decoded or tokenized is listed in ``unparsed_files`` and
    contributes no tokens. Past ``DUPLICATION_MAX_TOKENS`` tokens, or on ``MemoryError``,
    the measurement is ``tool_failed``: never a partial figure.
    """
    token_ids: dict[str, int] = {}
    tokenized: list[_TokenizedFile] = []
    unparsed: list[str] = []
    total = 0
    try:
        for path in files:
            file = _tokenize_file(repo_root, path, tokenizer, token_errors, token_ids)
            if file is None:
                unparsed.append(path)
                continue
            total += len(file.ids)
            if total > DUPLICATION_MAX_TOKENS:
                return tool_failed(
                    language,
                    SnapshotMetric.DUPLICATED_LINES,
                    f"{total} tokens passed the ceiling of {DUPLICATION_MAX_TOKENS}",
                    command=_COMMAND,
                )
            tokenized.append(file)
        _find_repeats(tokenized)
    except MemoryError:
        return tool_failed(
            language,
            SnapshotMetric.DUPLICATED_LINES,
            f"out of memory after {total} tokens (ceiling {DUPLICATION_MAX_TOKENS})",
            command=_COMMAND,
        )
    return Measurement(
        metric=SnapshotMetric.DUPLICATED_LINES,
        language=language,
        tool=tool,
        per_file=_duplicated_line_counts(tokenized),
        unparsed_files=unparsed,
    )
