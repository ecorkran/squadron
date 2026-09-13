"""Which built-in templates exclude the reviews directory from their tool jail, and why.

Slice 918 / issue #94: a document review could read its own archived and live predecessors,
because they sit inside the tool jail under the reviewed document's name prefix. It quoted
phrases deleted two revisions ago and re-raised dispositioned findings; the third consecutive
run escalated to FAIL on unchanged text.

These tests pin the *policy*: which templates carry the exclusion, which deliberately do not,
that the declared value stays tied to the constant that writes reviews, and that no template
carrying an exclusion also grants a tool the exclusion cannot constrain.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.data import data_dir
from squadron.review.persistence import REVIEWS_DIR
from squadron.review.templates import ReviewTemplate, load_template

#: Document reviews: they grade one artifact, so their own predecessors are the hazard.
EXCLUDING_TEMPLATES = (
    "arch.yaml",
    "slice.yaml",
    "tasks.yaml",
    "judge-slice-vs-arch.yaml",
    "judge-tasks-vs-slice.yaml",
)

#: Deliberate omissions. Each YAML carries the reason at the point of omission; these are
#: the reasons in one line, so a future reader sees both halves without opening the files.
NON_EXCLUDING_TEMPLATES = {
    # D2: code reviews read the source tree broadly by design.
    "code.yaml": "reads the tree broadly by design",
    # 918 non-goal: this is 305's prior-findings injection path; findings arrive as input.
    "judge-findings-addressed.yaml": "receives findings as an input, not by discovery",
}

#: A path deny-list cannot constrain a subprocess, so this tool defeats any exclusion.
JAIL_ESCAPING_TOOL = "bash"


def _builtin_templates_dir() -> Path:
    return data_dir() / "templates"


def _load(name: str) -> ReviewTemplate:
    return load_template(_builtin_templates_dir() / name)


def _all_builtin_paths() -> list[Path]:
    return sorted(_builtin_templates_dir().glob("*.yaml"))


def test_every_builtin_template_is_classified() -> None:
    """A new template must be placed in one list or the other, not silently default.

    Without this, adding a document-review template and forgetting the exclusion reopens #94
    with nothing failing.
    """
    classified = set(EXCLUDING_TEMPLATES) | set(NON_EXCLUDING_TEMPLATES)
    on_disk = {path.name for path in _all_builtin_paths()}

    assert on_disk == classified


@pytest.mark.parametrize("name", EXCLUDING_TEMPLATES)
def test_document_review_templates_exclude_the_reviews_directory(name: str) -> None:
    template = _load(name)

    assert template.tool_exclude_patterns == [str(REVIEWS_DIR)]


@pytest.mark.parametrize("name", sorted(NON_EXCLUDING_TEMPLATES))
def test_deliberate_omissions_declare_no_tool_exclusions(name: str) -> None:
    """The reason for each omission is written in the YAML at the point of omission."""
    template = _load(name)

    assert template.tool_exclude_patterns is None


@pytest.mark.parametrize("name", sorted(NON_EXCLUDING_TEMPLATES))
def test_each_omission_carries_its_reason_in_the_yaml(name: str) -> None:
    """A bare absence reads as an oversight; the comment is what makes it a decision."""
    body = (_builtin_templates_dir() / name).read_text()

    assert "Deliberately NO tool_exclude_patterns" in body


def test_excluded_pattern_tracks_the_constant_that_writes_reviews() -> None:
    """D4's single named seam.

    ``REVIEWS_DIR`` is where reviews are written; the templates declare where they may not
    be read. If the constant moves (slice 383 is adding ``review.external_reviews_dir``) and
    the templates do not follow, the exclusion points at an empty directory and the hole
    silently reopens. This test is what turns the constant into the source of truth for a
    value YAML cannot import.
    """
    declared = {
        _load(name).tool_exclude_patterns[0]  # type: ignore[index]
        for name in EXCLUDING_TEMPLATES
    }

    assert declared == {str(REVIEWS_DIR)}


@pytest.mark.parametrize("path", _all_builtin_paths(), ids=lambda p: p.name)
def test_no_template_with_tool_exclusions_grants_a_tool_that_defeats_them(path: Path) -> None:
    """The ``bash`` boundary.

    A path deny-list constrains the file tools, which route every path through the jail
    predicates. It does not constrain a subprocess: ``bash`` runs with the jail root as its
    working directory and reads whatever it likes, so a document-review template granting it
    would silently defeat the exclusion.

    No built-in template grants ``bash`` today (verified on 42bd0e05, slice 918 breakdown) —
    all seven declare ``[read_file, list_files, grep]``. This test is what keeps that true
    rather than merely currently-true.
    """
    template = load_template(path)
    if not template.tool_exclude_patterns:
        pytest.skip(f"{path.name} declares no tool exclusions")

    assert JAIL_ESCAPING_TOOL not in template.allowed_tools
