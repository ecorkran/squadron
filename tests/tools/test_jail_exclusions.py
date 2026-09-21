"""End-to-end: a document review cannot reach the reviews directory (slice 918, #94).

The predicate tests in ``test_jail.py`` pin the rule. This module pins what the model
actually experiences, through real materialized executors bound to a real fixture tree —
the test that would have caught #94.

Three properties matter, and each is asserted on returned *content*, not just on an error
flag:

* every tool the document templates grant (``read_file``, ``list_files``, ``grep``) refuses
  every path under the reviews directory;
* ``list_files`` does not even **enumerate** it — an excluded review artifact is named after
  the document under review, so leaking the name leaks the fact;
* a code review, which declares no exclusion, is unaffected.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from squadron.data import data_dir
from squadron.review.persistence import REVIEWS_DIR
from squadron.review.templates import load_template
from squadron.tools import ToolResult, materialize
from squadron.tools.builtin import GREP_NAME, LIST_FILES_NAME, READ_FILE_NAME

#: A phrase that exists only in an archived review. If it reaches the model, the exclusion
#: failed — this is the literal shape of #94: a finding quoting text deleted revisions ago.
STALE_PHRASE = "PHRASE_DELETED_TWO_REVISIONS_AGO"

#: The reviewed document's name prefix. Review artifacts carry it, which is why a listing
#: that names them is itself a leak.
DOCUMENT_STEM = "380-arch.pull-request-workflow"

DOCUMENT_TOOLS = [READ_FILE_NAME, LIST_FILES_NAME, GREP_NAME]


@pytest.fixture
def review_tree(tmp_path: Path) -> Path:
    """A project tree holding a document under review plus its live and archived reviews."""
    docs = tmp_path / "project-documents" / "user" / "architecture"
    docs.mkdir(parents=True)
    (docs / f"{DOCUMENT_STEM}.md").write_text(
        "# Pull Request Workflow\n\nThe current text, freshly revised.\n"
    )

    reviews = tmp_path / REVIEWS_DIR
    archive = reviews / "archive"
    archive.mkdir(parents=True)
    (reviews / f"{DOCUMENT_STEM}.review.md").write_text(
        f"Verdict: CONCERNS\n\nF001: {STALE_PHRASE} is still unaddressed.\n"
    )
    (archive / f"{DOCUMENT_STEM}.review.md").write_text(
        f"Verdict: FAIL\n\nF001: {STALE_PHRASE} appears here too.\n"
    )
    return tmp_path


def _template_exclusions(name: str) -> list[str]:
    template = load_template(data_dir() / "templates" / name)
    return list(template.tool_exclude_patterns or [])


def _call(executor: object, args: dict[str, object]) -> ToolResult:
    """Invoke a materialized executor synchronously."""
    return asyncio.run(executor(args))  # type: ignore[operator]


@pytest.fixture
def arch_tools(review_tree: Path) -> dict[str, object]:
    """Executors bound exactly as an ``arch`` review binds them."""
    return materialize(DOCUMENT_TOOLS, review_tree, _template_exclusions("arch.yaml"))


# -- The three tools refuse -----------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        f"{REVIEWS_DIR}/{DOCUMENT_STEM}.review.md",
        f"{REVIEWS_DIR}/archive/{DOCUMENT_STEM}.review.md",
    ],
)
def test_read_file_refuses_a_review_artifact(
    arch_tools: dict[str, object], path: str, caplog: pytest.LogCaptureFixture
) -> None:
    # Slice 922 D6: a policy exclusion logs at DEBUG, not WARNING.
    with caplog.at_level(logging.DEBUG):
        result = _call(arch_tools[READ_FILE_NAME], {"path": path})

    assert result.is_error
    assert STALE_PHRASE not in result.content
    assert any("excluded" in r.getMessage() for r in caplog.records)


def test_read_file_still_reads_the_document_under_review(arch_tools: dict[str, object]) -> None:
    """The exclusion must not cost the review the artifact it is grading."""
    result = _call(
        arch_tools[READ_FILE_NAME],
        {"path": f"project-documents/user/architecture/{DOCUMENT_STEM}.md"},
    )

    assert not result.is_error
    assert "freshly revised" in result.content


def test_list_files_does_not_enumerate_the_excluded_directory(
    arch_tools: dict[str, object], caplog: pytest.LogCaptureFixture
) -> None:
    """A refusal that still lists names leaks the filenames, which are the point.

    Review artifacts are named after the document under review, so a listing naming them
    tells the model its own predecessors exist and what they are called. Asserted on the
    content, not on ``is_error``.
    """
    # Slice 922 D6: a policy exclusion logs at DEBUG, not WARNING.
    with caplog.at_level(logging.DEBUG):
        result = _call(arch_tools[LIST_FILES_NAME], {"path": ".", "recursive": True})

    assert DOCUMENT_STEM + ".review.md" not in result.content
    assert "archive" not in result.content
    # The document itself is still visible — the walk ran, it just refused one subtree.
    assert f"{DOCUMENT_STEM}.md" in result.content
    assert any("excluded" in r.getMessage() for r in caplog.records)


def test_list_files_refuses_the_excluded_directory_as_an_explicit_target(
    arch_tools: dict[str, object],
) -> None:
    result = _call(arch_tools[LIST_FILES_NAME], {"path": str(REVIEWS_DIR)})

    assert result.is_error
    assert DOCUMENT_STEM not in result.content


def test_grep_returns_no_match_from_an_excluded_file(
    arch_tools: dict[str, object], caplog: pytest.LogCaptureFixture
) -> None:
    """The pattern matches the archived content; the exclusion is what suppresses the hit."""
    # Slice 922 D6: a policy exclusion logs at DEBUG, not WARNING.
    with caplog.at_level(logging.DEBUG):
        result = _call(arch_tools[GREP_NAME], {"pattern": STALE_PHRASE})

    assert STALE_PHRASE not in result.content
    assert "review.md" not in result.content
    assert any("excluded" in r.getMessage() for r in caplog.records)


def test_grep_refuses_the_excluded_directory_as_an_explicit_path(
    arch_tools: dict[str, object],
) -> None:
    result = _call(arch_tools[GREP_NAME], {"pattern": STALE_PHRASE, "path": str(REVIEWS_DIR)})

    assert STALE_PHRASE not in result.content


# -- The refusal is invisible to the model --------------------------------------------


def test_a_refusal_is_indistinguishable_from_a_nonexistent_path(
    arch_tools: dict[str, object], review_tree: Path
) -> None:
    """Design D6: "you were denied" invites probing for the boundary.

    An excluded path and a path that was never there must produce the same message, so the
    model cannot map the exclusion by asking about paths one at a time. Both messages name
    the resolved path, so each is normalized against its own before comparison — what must
    match is the wording, not the path the model chose.
    """
    excluded_rel = f"{REVIEWS_DIR}/{DOCUMENT_STEM}.review.md"
    absent_rel = "no/such/file.md"

    excluded = _call(arch_tools[READ_FILE_NAME], {"path": excluded_rel})
    absent = _call(arch_tools[READ_FILE_NAME], {"path": absent_rel})

    assert excluded.is_error and absent.is_error
    assert excluded.content.replace(str(review_tree / excluded_rel), "X") == (
        absent.content.replace(str(review_tree / absent_rel), "X")
    )
    assert excluded.content != absent.content  # the paths differ; only the wording matches


def test_no_refusal_wording_reaches_the_model(arch_tools: dict[str, object]) -> None:
    """Nothing in tool output names an exclusion, a denial, or the reviews directory."""
    results = [
        _call(arch_tools[READ_FILE_NAME], {"path": f"{REVIEWS_DIR}/{DOCUMENT_STEM}.review.md"}),
        _call(arch_tools[LIST_FILES_NAME], {"path": ".", "recursive": True}),
        _call(arch_tools[GREP_NAME], {"pattern": STALE_PHRASE}),
    ]

    for result in results:
        lowered = result.content.lower()
        assert "exclud" not in lowered
        assert "denied" not in lowered


# -- Code reviews are unaffected ------------------------------------------------------


def test_code_template_declares_no_tool_exclusions() -> None:
    """D2: code reviews read the tree broadly by design."""
    assert _template_exclusions("code.yaml") == []


def test_a_code_review_can_read_under_the_reviews_directory(review_tree: Path) -> None:
    """The same tree, bound as a ``code`` review binds it, reaches what arch cannot.

    This is what makes the arch refusals above meaningful: the file is readable, and the
    exclusion is the only thing standing between the review and it.
    """
    code_tools = materialize(DOCUMENT_TOOLS, review_tree, _template_exclusions("code.yaml"))

    result = _call(code_tools[READ_FILE_NAME], {"path": f"{REVIEWS_DIR}/{DOCUMENT_STEM}.review.md"})

    assert not result.is_error
    assert STALE_PHRASE in result.content
