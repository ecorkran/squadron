from __future__ import annotations

import re
from pathlib import Path

import pytest

from squadron.pr.tasks import NO_REASON_GIVEN, parse_blocked_markers, parse_task_items

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TASKS_DIR = _REPO_ROOT / "project-documents" / "user" / "tasks"
_CHECKBOX_LINE_RE = re.compile(r"^\s*[-*+]\s+\[( |x|X)\]", re.MULTILINE)


def test_checked_and_unchecked_markers() -> None:
    text = "- [x] done\n- [X] also done\n- [ ] not done\n"
    items = parse_task_items(text)
    assert items.checked == ("done", "also done")
    assert items.unchecked == ("not done",)


def test_nested_items_at_two_and_three_indent_levels() -> None:
    text = "\n".join(
        [
            "- [x] **1.1 Top level**",
            "  - [ ] one indent",
            "    - [x] two indents",
            "      - [ ] three indents",
        ]
    )
    items = parse_task_items(text)
    assert items.checked == ("**1.1 Top level**", "two indents")
    assert items.unchecked == ("one indent", "three indents")


def test_mixed_parent_and_child_states_attribute_independently() -> None:
    text = "- [x] parent checked\n  - [ ] child unchecked\n"
    items = parse_task_items(text)
    assert items.checked == ("parent checked",)
    assert items.unchecked == ("child unchecked",)


def test_trailing_whitespace_after_text_is_stripped() -> None:
    text = "- [ ] item with trailing space   \n"
    items = parse_task_items(text)
    assert items.unchecked == ("item with trailing space",)


def test_line_that_is_not_a_list_item_is_ignored() -> None:
    text = "Just a paragraph.\n[x] not a list item\n- no checkbox here\n"
    items = parse_task_items(text)
    assert items.checked == ()
    assert items.unchecked == ()


def test_empty_document() -> None:
    items = parse_task_items("")
    assert items.checked == ()
    assert items.unchecked == ()


def test_different_bullet_characters() -> None:
    text = "* [x] star bullet\n+ [ ] plus bullet\n- [X] dash bullet\n"
    items = parse_task_items(text)
    assert items.checked == ("star bullet", "dash bullet")
    assert items.unchecked == ("plus bullet",)


def _real_task_file() -> Path:
    """The slice's own task file once it exists, else 384's.

    Per the project's parsing rules, the fixture must be the actual format
    the parser will consume in production, not a hand-crafted stand-in.
    """
    own_file = _TASKS_DIR / "385-tasks.create-a-pr-with-a-good-message.md"
    if own_file.exists():
        return own_file
    return _TASKS_DIR / "384-tasks.post-findings-to-the-pr.md"


def test_real_task_file_fixture() -> None:
    """Would fail if the parser required one exact indent level or bullet."""
    path = _real_task_file()
    text = path.read_text(encoding="utf-8")

    items = parse_task_items(text)

    # Not asserted per-state: a completed slice's task file is all-checked, so
    # requiring unchecked items would fail once the work it tracks is done.
    expected_total = len(_CHECKBOX_LINE_RE.findall(text))
    assert expected_total
    assert len(items.checked) + len(items.unchecked) == expected_total


# --- parse_blocked_markers (slice 947 D7) -----------------------------------------

# The line the implement agent wrote in amoeba slice 107, quoted in issue #223.
_REAL_BLOCKED_LINE = "> BLOCKED: no judge-template review artifact ... PM asked"


def test_blocked_marker_in_the_real_amoeba_format() -> None:
    text = f"- [ ] 7.2 Capture the artifact\n  {_REAL_BLOCKED_LINE}\n- [ ] 8.1 Next task\n"

    assert parse_blocked_markers(text) == ("no judge-template review artifact ... PM asked",)


@pytest.mark.parametrize(
    "line",
    [
        "BLOCKED: needs the PM",
        "  BLOCKED: needs the PM",
        "> BLOCKED: needs the PM",
        "> > BLOCKED: needs the PM",
        ">BLOCKED: needs the PM",
        "- BLOCKED: needs the PM",
        "* BLOCKED: needs the PM",
        "  - [ ] BLOCKED: needs the PM",
        "- [x] BLOCKED: needs the PM",
        "**BLOCKED:** needs the PM",
        "**BLOCKED**: needs the PM",
        "> **BLOCKED:** needs the PM",
        "__BLOCKED:__ needs the PM",
        "BLOCKED — needs the PM",
        "BLOCKED - needs the PM",
        "BLOCKED:needs the PM",
        "BLOCKED:   needs the PM   ",
    ],
)
def test_blocked_marker_forms_yield_the_text_after_the_marker(line: str) -> None:
    assert parse_blocked_markers(line) == ("needs the PM",)


@pytest.mark.parametrize(
    "line",
    [
        "This task is blocked by the review",
        "Blocked: needs the PM",
        "blocked: needs the PM",
        "UNBLOCKED: needs the PM",
        "BLOCKEDX: needs the PM",
        "see BLOCKED: in the task above",
        "- [ ] 3.1 Resolve BLOCKED: items",
        "- [ ] BLOCKED tasks list cleanup",
        "BLOCKED needs the PM",
        "",
    ],
)
def test_lines_that_are_not_markers_are_ignored(line: str) -> None:
    assert parse_blocked_markers(line) == ()


@pytest.mark.parametrize("line", ["BLOCKED:", "> **BLOCKED:**", "- [ ] BLOCKED -  "])
def test_a_marker_with_no_reason_gets_a_placeholder(line: str) -> None:
    assert parse_blocked_markers(line) == (NO_REASON_GIVEN,)


def test_markers_come_back_in_file_order() -> None:
    text = "BLOCKED: first\n- [ ] work\n> BLOCKED: second\n"

    assert parse_blocked_markers(text) == ("first", "second")


def test_no_markers_is_an_empty_tuple() -> None:
    assert parse_blocked_markers("- [ ] a task\n- [x] done\n") == ()
