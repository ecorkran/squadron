"""Terminal-fitting column renderer for CLI listings (slice 174 D11).

A port of context-forge's ``output/tables.ts`` ``fitColumnWidths``: when a row
set is wider than the terminal, the widest shrinkable column loses one cell at a
time, never below ``MIN_TRUNCATED_COLUMN_WIDTH``. Off a terminal nothing is cut,
so piped output stays complete. Cells are ``rich.text.Text``, so styling,
cell-width measurement and ellipsis truncation come from rich, and colour is
dropped by the console on non-TTY output and under ``NO_COLOR``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rich.console import Console
from rich.text import Text

MIN_TRUNCATED_COLUMN_WIDTH = 8
COLUMN_GAP = 2
INDENT = 2
HEADER_STYLE = "bold cyan"
UNDERLINE_STYLE = "dim"
UNDERLINE_CHAR = "─"


@dataclass(frozen=True)
class Column:
    header: str | None  # None: a headerless list (pipelines)
    shrinkable: bool  # identifiers people copy (Run ID, Status, Name) are not


def available_width(console: Console) -> int | None:
    """The console's width on a terminal; ``None`` (never truncate) otherwise."""
    return console.width if console.is_terminal else None


def fit_widths(natural: list[int], shrinkable: list[bool], available: int | None) -> list[int]:
    """Column widths that fit in *available* cells, shrinking the widest first.

    A column never shrinks below ``MIN_TRUNCATED_COLUMN_WIDTH`` or its own
    narrower natural width. When nothing more can shrink the widths are returned
    as they stand and the line wraps. ``available=None`` means no limit.
    """
    widths = list(natural)
    if available is None:
        return widths
    floors = [min(width, MIN_TRUNCATED_COLUMN_WIDTH) for width in natural]
    while sum(widths) > available:
        candidates = [i for i, width in enumerate(widths) if shrinkable[i] and width > floors[i]]
        if not candidates:
            break
        widest = max(candidates, key=lambda i: widths[i])
        widths[widest] -= 1
    return widths


def render_rows(
    columns: Sequence[Column], rows: list[list[Text]], *, available: int | None
) -> list[Text]:
    """Lay *rows* out under *columns*: a header and underline when headed, then rows.

    *available* is the whole line's width (indent and gaps included), or
    ``None`` for no truncation.
    """
    headed = any(column.header is not None for column in columns)
    header_cells = [Text(column.header or "", style=HEADER_STYLE) for column in columns]
    measured = [header_cells, *rows] if headed else rows
    natural = [max((row[i].cell_len for row in measured), default=0) for i in range(len(columns))]
    budget = None if available is None else available - INDENT - COLUMN_GAP * (len(columns) - 1)
    widths = fit_widths(natural, [column.shrinkable for column in columns], budget)
    lines: list[Text] = []
    if headed:
        lines.append(_line(header_cells, widths))
        underline = [
            Text(UNDERLINE_CHAR * width if column.header else "", style=UNDERLINE_STYLE)
            for column, width in zip(columns, widths, strict=True)
        ]
        lines.append(_line(underline, widths))
    lines.extend(_line(row, widths) for row in rows)
    return lines


def _line(cells: list[Text], widths: list[int]) -> Text:
    line = Text(" " * INDENT)
    gap = " " * COLUMN_GAP
    for position, (cell, width) in enumerate(zip(cells, widths, strict=True)):
        fitted = cell.copy()
        if fitted.cell_len > width:
            fitted.truncate(width, overflow="ellipsis")
        if position:
            line.append(gap)
        line.append_text(fitted)
        line.append(" " * (width - fitted.cell_len))
    line.rstrip()
    return line
