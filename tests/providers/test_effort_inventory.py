"""Every place squadron builds an agent config or opens a session is accounted for (slice 420 D7).

The inventory of dispatch paths lives in the slice design. This test keeps it honest: a new
``AgentConfig(...)`` or ``open_pipeline_session(...)`` call in ``src/`` fails here until it is
classified as sending effort (with the test that proves it) or as having no alias to send.

Path coverage: PATH_TESTS maps each inventory path (1-12) to the tests that assert its
effort, and a test checks that every named test exists, so the map cannot go stale.
"""

from __future__ import annotations

import ast
from enum import StrEnum
from pathlib import Path
from typing import NamedTuple

import pytest

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _TESTS_ROOT.parent / "src" / "squadron"
_CONSTRUCTORS = ("AgentConfig", "open_pipeline_session")


class SiteKind(StrEnum):
    SENDS_ALIAS_EFFORT = "sends_alias_effort"
    SENDS_SESSION_EFFORT = "sends_session_effort"
    NO_ALIAS = "no_alias"


class Site(NamedTuple):
    """A source file's calls to one constructor, and how they treat effort."""

    path: str
    constructor: str
    count: int
    kind: SiteKind
    evidence: str  # the proving test (``file::name``) for a sender, else why there is no alias


_SITES = [
    Site(
        "review/review_client.py",
        "AgentConfig",
        1,
        SiteKind.SENDS_ALIAS_EFFORT,
        "tests/cli/test_review_profile.py::test_alias_effort_reaches_the_review",
    ),
    Site(
        "pipeline/actions/dispatch.py",
        "AgentConfig",
        1,
        SiteKind.SENDS_ALIAS_EFFORT,
        "tests/pipeline/test_effort_plumbing.py::test_dispatch_puts_effort_on_its_config",
    ),
    Site(
        "pipeline/summary_oneshot.py",
        "AgentConfig",
        1,
        SiteKind.SENDS_ALIAS_EFFORT,
        "tests/pipeline/test_effort_plumbing.py::test_summary_one_shot_puts_effort_on_its_config",
    ),
    Site(
        "pipeline/run_session.py",
        "open_pipeline_session",
        1,
        SiteKind.SENDS_SESSION_EFFORT,
        "tests/pipeline/test_run_session.py::test_session_opens_at_the_classifications_effort",
    ),
    Site(
        "pipeline/executor.py",
        "open_pipeline_session",
        1,
        SiteKind.SENDS_SESSION_EFFORT,
        "tests/cli/commands/test_run_pipeline_lazy.py::"
        "test_lazy_session_opens_at_the_first_steps_alias_effort",
    ),
    Site(
        "metrology/audit.py",
        "AgentConfig",
        1,
        SiteKind.NO_ALIAS,
        "`metrology.audit_model` is passed to the CLI raw, so no alias resolves",
    ),
    Site(
        "pr/composer.py",
        "AgentConfig",
        1,
        SiteKind.NO_ALIAS,
        "`--model` is passed raw, so no alias resolves",
    ),
    Site(
        "server/routes/agents.py",
        "AgentConfig",
        2,
        SiteKind.NO_ALIAS,
        "daemon agents take their model from the request body, not an alias",
    ),
    Site(
        "providers/auth.py",
        "AgentConfig",
        1,
        SiteKind.NO_ALIAS,
        "the auth probe builds a throwaway config and does no LLM work",
    ),
]

# Design inventory number -> tests that assert the effort that path sends or records.
PATH_TESTS: dict[int, tuple[str, ...]] = {
    1: (
        "tests/pipeline/actions/test_dispatch_usage.py::test_session_success_stamps_the_session_effort",
    ),
    2: ("tests/pipeline/actions/test_summary.py::test_session_summary_records_the_session_effort",),
    3: ("tests/pipeline/actions/test_compact.py::test_capture_turn_records_usage",),
    4: (
        "tests/pipeline/actions/test_dispatch_usage.py::test_one_shot_success_stamps_the_alias_effort",
    ),
    5: (
        "tests/pipeline/actions/test_summary.py::test_one_shot_summary_records_usage_and_passes_budget",
    ),
    6: ("tests/pipeline/actions/test_review_action.py::test_review_result_stamps_the_effort_sent",),
    7: ("tests/pipeline/test_findings_addressed_judge.py::test_judge_sends_its_alias_effort",),
    8: ("tests/replay/test_judge_dispatch.py::test_judge_call_puts_the_alias_effort_on_its_config",),
    9: ("tests/cli/test_review_profile.py::test_alias_effort_reaches_the_review",),
    10: ("tests/pipeline/test_effort_plumbing.py::test_summary_run_cli_passes_effort",),
    11: (
        "tests/cli/commands/test_dispatch_run.py::test_dispatch_run_effort_flag_reaches_the_dispatch",
    ),
    12: (
        "tests/replay/test_outcome.py::"
        "test_a_failed_dispatch_with_no_usage_record_reads_the_stamped_effort",
    ),
}

_UNCLASSIFIED_HELP = """
{where} calls {constructor}(...) but is not in _SITES in {this_file}.

If it sends an alias's or the session's effort, add it as SENDS_ALIAS_EFFORT or
SENDS_SESSION_EFFORT with the test that proves it. If it has no alias to send, add it as
NO_ALIAS with the reason.
"""


def _call_sites() -> dict[tuple[str, str], list[int]]:
    """Source file and constructor -> the line of each call, found by walking the AST.

    The AST, not text: ``class AgentConfig(BaseModel)``, imports, comments and docstrings
    must not count.
    """
    found: dict[tuple[str, str], list[int]] = {}
    for py_file in _SRC_ROOT.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in _CONSTRUCTORS:
                key = (py_file.relative_to(_SRC_ROOT).as_posix(), str(name))
                found.setdefault(key, []).append(node.lineno)
    return found


def _classified() -> dict[tuple[str, str], Site]:
    return {(site.path, site.constructor): site for site in _SITES}


def test_every_construction_site_is_classified() -> None:
    classified = _classified()
    missing = [
        _UNCLASSIFIED_HELP.format(
            where=f"src/squadron/{path}:{lines[0]}",
            constructor=constructor,
            this_file=Path(__file__).name,
        )
        for (path, constructor), lines in sorted(_call_sites().items())
        if (path, constructor) not in classified
    ]
    assert not missing, "".join(missing)


def test_the_table_has_no_stale_entries() -> None:
    found = _call_sites()
    stale = [
        f"{site.path}: {site.constructor} called {len(found.get((site.path, site.constructor), []))}x, "
        f"table says {site.count}x"
        for site in _SITES
        if len(found.get((site.path, site.constructor), [])) != site.count
    ]
    assert not stale, "\n".join(stale)


def _function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def _assert_test_exists(reference: str) -> None:
    file_part, _, name = reference.partition("::")
    path = _TESTS_ROOT.parent / file_part
    assert path.is_file(), f"{reference}: {file_part} does not exist"
    assert name in _function_names(path), f"{reference}: no test named {name} in {file_part}"


@pytest.mark.parametrize(
    "site",
    [s for s in _SITES if s.kind is not SiteKind.NO_ALIAS],
    ids=lambda s: f"{s.path}:{s.constructor}",
)
def test_every_sending_site_names_a_test_that_exists(site: Site) -> None:
    _assert_test_exists(site.evidence)


def test_every_inventory_path_one_to_twelve_maps_to_an_existing_test() -> None:
    assert sorted(PATH_TESTS) == list(range(1, 13))
    for tests in PATH_TESTS.values():
        assert tests
        for reference in tests:
            _assert_test_exists(reference)
