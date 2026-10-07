"""Terminal-fitting column renderer (slice 174 D11)."""

from __future__ import annotations

import io

from rich.console import Console
from rich.text import Text

from squadron.cli.columns import (
    COLUMN_GAP,
    INDENT,
    MIN_TRUNCATED_COLUMN_WIDTH,
    Column,
    available_width,
    fit_widths,
    render_rows,
)


class TestFitWidths:
    def test_already_fits(self) -> None:
        assert fit_widths([10, 20], [True, True], 40) == [10, 20]

    def test_one_column_shrinks(self) -> None:
        assert fit_widths([10, 30], [True, True], 35) == [10, 25]

    def test_several_shrink_widest_first(self) -> None:
        assert fit_widths([20, 30], [True, True], 40) == [20, 20]
        assert fit_widths([20, 30], [True, True], 36) == [18, 18]

    def test_floor_of_eight(self) -> None:
        assert fit_widths([20, 30], [True, True], 4) == [MIN_TRUNCATED_COLUMN_WIDTH] * 2

    def test_narrow_natural_width_is_its_own_floor(self) -> None:
        assert fit_widths([5, 30], [True, True], 4) == [5, MIN_TRUNCATED_COLUMN_WIDTH]

    def test_non_shrinkable_column_is_never_cut(self) -> None:
        assert fit_widths([40, 30], [False, True], 50) == [40, 10]
        assert fit_widths([40, 30], [False, True], 10) == [40, MIN_TRUNCATED_COLUMN_WIDTH]

    def test_no_limit(self) -> None:
        assert fit_widths([200, 300], [True, True], None) == [200, 300]


def _plain(lines: list[Text]) -> list[str]:
    return [line.plain for line in lines]


class TestRenderRows:
    COLUMNS = [Column("Run ID", shrinkable=False), Column("Target", shrinkable=True)]

    def test_header_underline_and_rows(self) -> None:
        rows = [[Text("run-1"), Text("slice=174")]]

        lines = _plain(render_rows(self.COLUMNS, rows, available=None))

        assert lines == [
            "  Run ID  Target",
            "  ──────  ─────────",
            "  run-1   slice=174",
        ]

    def test_truncates_shrinkable_with_ellipsis_and_keeps_run_id(self) -> None:
        run_id = "run-20261007-implement-plan-4b07a1c2"
        target = "plan=180 model=opus max-revisions=2"
        available = INDENT + len(run_id) + COLUMN_GAP + 12

        lines = _plain(render_rows(self.COLUMNS, [[Text(run_id), Text(target)]], available=available))

        assert run_id in lines[2]
        assert lines[2].endswith("…")
        assert all(len(line) <= available for line in lines)

    def test_headerless_list_has_no_header_lines(self) -> None:
        columns = [Column(None, shrinkable=False), Column(None, shrinkable=True)]

        lines = _plain(render_rows(columns, [[Text("p4"), Text("Slice design")]], available=None))

        assert lines == ["  p4  Slice design"]

    def test_wide_characters_measured_by_cell_width(self) -> None:
        columns = [Column(None, shrinkable=False), Column(None, shrinkable=False)]
        rows = [[Text("日本"), Text("x")], [Text("abcd"), Text("y")]]

        lines = _plain(render_rows(columns, rows, available=None))

        # "日本" is four cells wide, the same as "abcd", so column 2 aligns.
        assert lines == ["  日本  x", "  abcd  y"]

    def test_non_tty_console_has_no_ansi_and_no_ellipsis(self) -> None:
        buffer = io.StringIO()
        console = Console(file=buffer, width=40)
        target = "plan=180 model=opus max-revisions=2 extra=" + "x" * 80
        rows = [[Text("run-20261007-p6-8bc5e634", style="cyan"), Text(target)]]

        for line in render_rows(self.COLUMNS, rows, available=available_width(console)):
            console.print(line, soft_wrap=True)

        out = buffer.getvalue()
        assert available_width(console) is None
        assert "\x1b[" not in out
        assert "…" not in out
        assert target in out
