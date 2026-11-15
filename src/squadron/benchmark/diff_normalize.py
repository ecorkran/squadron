"""Diff normalization for the slice-case judge (slice 426 D11).

The judge compares what two implementations changed in the code, so a diff is reduced to
the sections that matter: bookkeeping files are dropped and a binary section becomes one
line. Pure functions, no I/O. Normalization is for the judge only; grading uses the full diff.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from squadron.integrations.context_forge import DOCS_ROOT

#: Bookkeeping files at the repository root that the judge never sees.
DROPPED_ROOT_FILES = frozenset({"DEVLOG.md", "CHANGELOG.md", "uv.lock"})
#: Directories whose files the judge never sees; a path is dropped by prefix only.
DROPPED_PREFIXES = (
    f"{DOCS_ROOT}/user/tasks/",
    f"{DOCS_ROOT}/user/reviews/",
    f"{DOCS_ROOT}/user/slices/",
)
#: What the judge reads for a contestant whose whole diff was dropped.
EMPTY_DIFF_TEXT = "(no changes outside dropped paths)"
BINARY_MARKER = "Binary file {path} changed"

_SECTION_START = re.compile(r"^diff --git ", re.MULTILINE)
_HEADER_PREFIX = "diff --git "
_ESCAPES = {"\\": b"\\", '"': b'"', "t": b"\t", "n": b"\n", "r": b"\r", "a": b"\a", "b": b"\b"}
_OCTAL = re.compile(r"[0-7]{3}")
_PATH_PAIRS = (("rename from ", "rename to "), ("copy from ", "copy to "))
_NO_FILE = "/dev/null"


@dataclass(frozen=True)
class NormalizedDiff:
    """The judge's view of a diff, and what was left out of it."""

    text: str
    dropped_paths: tuple[str, ...]  # every path of a dropped section, in diff order
    binary_paths: tuple[str, ...]  # kept binary sections, shown as one marker line


def is_dropped(path: str) -> bool:
    """True when the judge never sees changes to ``path``."""
    return path in DROPPED_ROOT_FILES or path.startswith(DROPPED_PREFIXES)


def normalize(diff: bytes) -> NormalizedDiff:
    """Drop bookkeeping sections and replace binary sections with a marker line.

    A section is kept unless every path it names is dropped, so a rename with one side
    kept is kept. Kept text sections are copied verbatim, line endings included. Bytes that
    are not UTF-8 are replaced, which affects the judge's text only.
    """
    kept: list[str] = []
    dropped: list[str] = []
    binary: list[str] = []
    for section in _sections(diff.decode("utf-8", errors="replace")):
        paths = _section_paths(section)
        if paths and all(is_dropped(path) for path in paths):
            dropped.extend(path for path in paths if path not in dropped)
        elif _is_binary(section):
            path = paths[-1] if paths else "(unknown path)"
            binary.append(path)
            kept.append(BINARY_MARKER.format(path=path) + "\n")
        else:
            kept.append(section)
    return NormalizedDiff(
        text="".join(kept) or EMPTY_DIFF_TEXT,
        dropped_paths=tuple(dropped),
        binary_paths=tuple(binary),
    )


def _sections(text: str) -> list[str]:
    """The text split at each ``diff --git`` header, content before the first ignored."""
    bounds = [match.start() for match in _SECTION_START.finditer(text)] + [len(text)]
    return [text[begin:end] for begin, end in zip(bounds, bounds[1:], strict=False)]


def _is_binary(section: str) -> bool:
    return any(
        line.startswith(("GIT binary patch", "Binary files ")) for line in _header_lines(section)
    )


def _header_lines(section: str) -> list[str]:
    """The section's lines before its first hunk or binary patch body."""
    lines: list[str] = []
    for line in section.split("\n"):
        lines.append(line.removesuffix("\r"))
        if line.startswith(("@@", "GIT binary patch")):
            break
    return lines


def _section_paths(section: str) -> list[str]:
    """The distinct paths a section names: old then new, from the most explicit source."""
    lines = _header_lines(section)
    found = _path_pair(lines) or _marker_paths(lines) or _header_paths(lines[0])
    return list(dict.fromkeys(path for path in found if path))


def _path_pair(lines: list[str]) -> list[str]:
    """Paths from ``rename``/``copy`` lines."""
    for source, target in _PATH_PAIRS:
        old = [_unquote(line.removeprefix(source)) for line in lines if line.startswith(source)]
        new = [_unquote(line.removeprefix(target)) for line in lines if line.startswith(target)]
        if old and new:
            return [old[0], new[0]]
    return []


def _marker_paths(lines: list[str]) -> list[str]:
    """Paths from the ``---`` and ``+++`` lines; ``/dev/null`` names no path."""
    paths: list[str] = []
    for marker, prefix in (("--- ", "a/"), ("+++ ", "b/")):
        for line in lines:
            if line.startswith(marker):
                name = _unquote(line.removeprefix(marker).split("\t", 1)[0])
                paths.append("" if name == _NO_FILE else name.removeprefix(prefix))
                break
    return paths


def _header_paths(header: str) -> list[str]:
    """Paths from ``diff --git a/<old> b/<new>``, quoted or not; used for binary and mode-only."""
    rest = header.removeprefix(_HEADER_PREFIX)
    if rest.startswith('"'):
        first, remainder = _quoted_token(rest)
        second = remainder.removeprefix(" ")
    elif ' "' in rest:
        first, second = rest.split(' "', 1)
        second = '"' + second
    else:
        first, second = _split_unquoted(rest)
    return [_unquote(first).removeprefix("a/"), _unquote(second).removeprefix("b/")]


def _split_unquoted(rest: str) -> tuple[str, str]:
    """Split ``a/P b/Q``. With equal names the halves are the same length, which resolves
    a name containing spaces; a rename without ``rename`` lines splits at the last `` b/``."""
    half, odd = divmod(len(rest) - 1, 2)
    if not odd and rest[:half].removeprefix("a/") == rest[half + 1 :].removeprefix("b/"):
        return rest[:half], rest[half + 1 :]
    head, _, tail = rest.rpartition(" b/")
    return head, "b/" + tail


def _quoted_token(text: str) -> tuple[str, str]:
    """The quoted token at the start of ``text`` (quotes kept) and what follows it."""
    index = 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == '"':
            return text[: index + 1], text[index + 1 :]
        index += 1
    return text, ""


def _unquote(token: str) -> str:
    """Undo git's C-style path quoting (octal escapes are UTF-8 bytes); plain names pass."""
    if not (len(token) >= 2 and token.startswith('"') and token.endswith('"')):
        return token
    body, out, index = token[1:-1], bytearray(), 0
    while index < len(body):
        char = body[index]
        octal = _OCTAL.fullmatch(body[index + 1 : index + 4]) if char == "\\" else None
        if octal:
            out.append(int(octal.group(), 8))
            index += 4
        elif char == "\\" and body[index + 1 : index + 2] in _ESCAPES:
            out += _ESCAPES[body[index + 1]]
            index += 2
        else:
            out += char.encode("utf-8")
            index += 1
    return out.decode("utf-8", errors="replace")
