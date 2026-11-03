"""Per-file splitting and capping of an injected git diff (#278)."""

from __future__ import annotations

from squadron.review.models import DiffFileInjection

_FILE_HEADER_PREFIX = "diff --git "
_NEW_PATH_SEPARATOR = " b/"
# Label for a diff with no `diff --git` headers (hand-built input); it is one section.
UNSPLIT_DIFF_LABEL = "(whole diff)"


def _path_from_header(header_line: str) -> str:
    """The post-change path from a ``diff --git a/old b/new`` line."""
    rest = header_line[len(_FILE_HEADER_PREFIX) :].rstrip("\r\n")
    separator_at = rest.rfind(_NEW_PATH_SEPARATOR)
    return rest[separator_at + len(_NEW_PATH_SEPARATOR) :] if separator_at != -1 else rest


def split_diff_by_file(diff: str) -> list[tuple[str, str]]:
    """Split *diff* into ``(path, section)`` pairs, one per ``diff --git`` header.

    Text before the first header joins the first section. A diff with no header
    is returned whole, so nothing is ever dropped by splitting.
    """
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    for line in diff.splitlines(keepends=True):
        if line.startswith(_FILE_HEADER_PREFIX):
            sections.append((_path_from_header(line), [line]))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    if not sections:
        return [(UNSPLIT_DIFF_LABEL, diff)]
    first_path, first_lines = sections[0]
    sections[0] = (first_path, [*preamble, *first_lines])
    return [(path, "".join(lines)) for path, lines in sections]


def cap_sections(
    sections: list[tuple[str, str]], max_chars: int
) -> tuple[str, tuple[DiffFileInjection, ...]]:
    """Cap each file's section at *max_chars*; return the joined diff and the per-file record.

    A cut section ends with a marker naming how much was shown. The record's
    ``injected_chars`` never counts the marker.
    """
    parts: list[str] = []
    record: list[DiffFileInjection] = []
    for path, section in sections:
        total = len(section)
        shown = min(total, max_chars)
        text = section[:shown]
        if shown < total:
            text += (
                f"\n[diff for this file truncated: {shown} of {total} characters shown; "
                "read the file for the rest]\n"
            )
        parts.append(text)
        record.append(DiffFileInjection(path=path, total_chars=total, injected_chars=shown))
    return "".join(parts), tuple(record)


def omit_all(sections: list[tuple[str, str]]) -> tuple[DiffFileInjection, ...]:
    """The record for a diff the total-injection limit dropped entirely."""
    return tuple(
        DiffFileInjection(path=path, total_chars=len(section), injected_chars=0)
        for path, section in sections
    )


def describe_cut_files(files: tuple[DiffFileInjection, ...]) -> str | None:
    """Prompt text naming the files whose diff was cut or omitted, or None when none was."""
    cut = [f for f in files if f.cut]
    if not cut:
        return None
    lines = [
        "Part of this diff did not reach you. Read these files with your file tools "
        "before judging them; do not report PASS on them from this text alone:",
    ]
    for f in cut:
        state = "omitted" if f.omitted else f"cut ({f.injected_chars} of {f.total_chars} characters)"
        lines.append(f"- {f.path}: {state}")
    return "\n".join(lines)
