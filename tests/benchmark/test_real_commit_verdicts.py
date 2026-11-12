"""Fairness verdicts on squadron's own fix commits (slice 422 design step 6).

These pin the real history: a commit absent from the clone fails the test (CI checks out with
``fetch-depth: 0``), and so does a commit whose outcome changed. ``network``: the sandboxes
install squadron's locked environment at each parent commit, which is slow.

Every hidden test in the three commits below is rejected for patching project code, as the
design expected. The deciding target is the first patch in sorted order, and
``squadron.cli.app._load_env_file`` never decides it: ``tests/conftest.py`` patches that in an
autouse fixture (since 3ea67555, 2026-09-26), and D7 exempts it as environment isolation.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from squadron.benchmark.diff_classify import DiffClassification, classify_diff, parse_name_status
from squadron.benchmark.fix_discovery import FixCandidate, discover
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.python_fairness import PythonFixCaseAdapter
from squadron.benchmark.qualify_sandbox import qualify_in_sandbox
from squadron.benchmark.qualify_types import QualifyDeps, QualifyResult
from squadron.benchmark.sandbox import BenchmarkSandbox
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import (
    CandidateRejection,
    QualificationOutcome,
    TestRejection,
)
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.store import MetrologyStore

# ``real_history`` keeps this file out of the default run (about 42 minutes: it builds and
# traces squadron's own suite at real commits). Run it with ``pytest -m real_history``.
pytestmark = [pytest.mark.network, pytest.mark.real_history]

REPO = Path(__file__).resolve().parents[2]
RUNNER = SubprocessRunner()
GIT_TIMEOUT = 120
MARKERS = "squadron.events.builtin.blocked_tasks.BlockedTasksAction._read_markers"
APPLY_OVERRIDES = "squadron.cli.commands.run._apply_param_overrides"
LOAD_PIPELINE = "squadron.cli.commands.run.load_pipeline"
CLI = "tests/cli/test_param_parsing.py::"
SUMMARY = "tests/pipeline/test_summary_artifacts.py::"

#: commit prefix -> {hidden node id: deciding patch target}. All are ``patches_project_code``.
PATCHING_COMMITS: dict[str, dict[str, str]] = {
    "ebd45f3f": {f"{SUMMARY}test_each_loop_slice_record_resolves_by_its_index": MARKERS},
    "9fc4fc1c": {
        f"{CLI}test_interior_empty_pair_still_fails": MARKERS,
        f"{CLI}test_run_command_receives_both_params_after_space_comma": APPLY_OVERRIDES,
        f"{CLI}test_run_command_rejects_stray_non_pair": MARKERS,
        f"{CLI}test_stray_non_pair_is_an_error": MARKERS,
        f"{CLI}test_stray_pair_is_folded_into_params": MARKERS,
        f"{CLI}test_trailing_comma_is_dropped": MARKERS,
    },
    "d6535d62": {
        f"{CLI}test_no_stray_arguments_leaves_params_unchanged": MARKERS,
        f"{CLI}test_review_commands_use_stray_param_handling[arch]": MARKERS,
        f"{CLI}test_review_commands_use_stray_param_handling[code]": MARKERS,
        f"{CLI}test_review_commands_use_stray_param_handling[slice]": MARKERS,
        f"{CLI}test_review_commands_use_stray_param_handling[tasks]": MARKERS,
        f"{CLI}test_run_dry_run_shows_both_params_after_space_comma": LOAD_PIPELINE,
        f"{CLI}test_run_dry_run_without_p_is_unchanged": LOAD_PIPELINE,
        f"{CLI}test_run_rejects_bare_pair_without_trailing_comma": LOAD_PIPELINE,
        f"{CLI}test_stray_non_pair_is_an_error": MARKERS,
        f"{CLI}test_stray_pair_after_trailing_comma_is_folded_into_params": MARKERS,
        f"{CLI}test_stray_pair_without_trailing_comma_is_an_error": MARKERS,
    },
}


def git(*args: str) -> str:
    result = RUNNER.run(["git", "-C", str(REPO), *args], cwd=None, timeout=GIT_TIMEOUT)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def require_commit(prefix: str) -> str:
    """The full sha, or a failure that says full history is required (there is no skip)."""
    result = RUNNER.run(
        ["git", "-C", str(REPO), "rev-parse", "--verify", f"{prefix}^{{commit}}"],
        cwd=None,
        timeout=GIT_TIMEOUT,
    )
    if result.returncode != 0:
        pytest.fail(
            f"commit {prefix} is not in this clone; these pins need full history "
            "(CI checks out with fetch-depth: 0)"
        )
    return result.stdout.strip()


# --- Discovery pins --------------------------------------------------------------------------


def test_the_two_291_commits_are_multiple_closing_commits_and_ebd45f3f_is_not_a_candidate() -> None:
    first, second, no_keyword = (require_commit(p) for p in ("9fc4fc1c", "d6535d62", "ebd45f3f"))
    result = discover(RUNNER, REPO, timeout_seconds=GIT_TIMEOUT)
    rejections = {r.sha: r.rejection for r in result.rejections}
    candidates = {c.sha for c in result.candidates}
    assert rejections.get(first) is CandidateRejection.MULTIPLE_CLOSING_COMMITS
    assert rejections.get(second) is CandidateRejection.MULTIPLE_CLOSING_COMMITS
    assert no_keyword not in candidates and no_keyword not in rejections


# --- Fairness pins ---------------------------------------------------------------------------


def hand_built_candidate(sha: str) -> FixCandidate:
    parent = git("rev-parse", f"{sha}^")
    committed = datetime.fromisoformat(git("log", "-1", "--format=%cI", sha))
    return FixCandidate(sha, parent, committed, "#0", None, 0)


def read_at(sha: str, path: str) -> str | None:
    result = RUNNER.run(
        ["git", "-C", str(REPO), "show", f"{sha}:{path}"], cwd=None, timeout=GIT_TIMEOUT
    )
    return result.stdout if result.returncode == 0 else None


def classification(candidate: FixCandidate) -> DiffClassification:
    raw = git("diff", "--name-status", "--no-renames", f"{candidate.parent_sha}..{candidate.sha}")
    classified = classify_diff(
        parse_name_status(raw),
        PythonFixCaseAdapter(),
        read_at(candidate.parent_sha, "pyproject.toml"),
        lambda path: read_at(candidate.parent_sha, path),
        lambda path: read_at(candidate.sha, path),
    )
    assert isinstance(classified, DiffClassification), classified
    return classified


def qualify_directly(sha: str, tmp_path: Path) -> QualifyResult:
    """The sandbox stages on a hand-built candidate: no ``gh`` call and no local store."""
    candidate = hand_built_candidate(sha)
    sandboxes = 0

    def factory(start_sha: str) -> BenchmarkSandbox:
        nonlocal sandboxes
        sandboxes += 1
        return BenchmarkSandbox(
            start_sha=start_sha,
            sandbox_id=f"real-{sha[:8]}-{sandboxes}",
            repo_root=REPO,
            runner=RUNNER,
            adapter=PythonBenchmarkAdapter(),
            harness_env=dict(os.environ),
            install_timeout_s=1800,
            suite_timeout_s=1800,
            root=tmp_path / "sandboxes",
        )

    deps = QualifyDeps(
        repo_root=REPO,
        project_id=ProjectId(value="squadron-real-commits", source=ProjectIdSource.RECORDED),
        host=None,  # type: ignore[arg-type]  # the sandbox stages never call the host
        store=BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store")),
        runner=RUNNER,
        adapter=PythonFixCaseAdapter(),
        sandbox_stages=qualify_in_sandbox,
        sandbox_factory=factory,
        suite_runner=PythonBenchmarkAdapter(),
        repeats=3,
        git_timeout_seconds=GIT_TIMEOUT,
    )
    return qualify_in_sandbox(candidate, classification(candidate), "placeholder task text", deps)


@pytest.mark.parametrize("prefix", sorted(PATCHING_COMMITS))
def test_each_hidden_test_is_rejected_for_patching_project_code(prefix: str, tmp_path: Path) -> None:
    sha = require_commit(prefix)
    result = qualify_directly(sha, tmp_path)
    record = result.record
    assert record.outcome is QualificationOutcome.REJECTED, record.detail
    assert record.rejection is CandidateRejection.NO_QUALIFYING_HIDDEN_TEST
    verdicts = {v.node_id: (v.rejection, v.detail) for v in record.hidden_verdicts}
    assert verdicts == {
        node: (TestRejection.PATCHES_PROJECT_CODE, target)
        for node, target in PATCHING_COMMITS[prefix].items()
    }


# --- Examples taken from the 2026-11-08 full run (94 records, 1 qualified) ---------------------
# Categories with no instance in that history: a crash fix (no qualified case records
# ``project_exception``), test-first by unknown symbol (no ``uses_symbol_added_by_fix``) and a
# qualified CLI test (the one qualified case has no ``CliRunner``). Fixture projects cover them.

QUALIFIED_COMMIT = "21013615"
QUALIFIED_HIDDEN_TEST = (
    "tests/providers/test_capabilities.py::TestAppliesEffort::test_codex_applies_effort"
)
BOUNDARY_COMMIT = "c45d28e9"
BOUNDARY_TEST = (
    "tests/providers/sdk/test_tool_less_live.py::"
    "test_tool_less_sdk_step_runs_no_tools_and_loads_no_project_text"
)
BOUNDARY_SYMBOL = "squadron.pipeline.actions.dispatch.one_shot_dispatch_with_telemetry"


def test_the_effort_fix_qualifies_with_its_test_failing_by_assertion_at_the_parent(
    tmp_path: Path,
) -> None:
    record = qualify_directly(require_commit(QUALIFIED_COMMIT), tmp_path).record
    assert record.outcome is QualificationOutcome.QUALIFIED, record.detail
    verdicts = {v.node_id: v for v in record.hidden_verdicts}
    qualified = verdicts[QUALIFIED_HIDDEN_TEST]
    assert qualified.rejection is None
    assert "assertion_failure" in qualified.detail
    assert [v.node_id for v in record.hidden_verdicts if v.rejection is None] == [QUALIFIED_HIDDEN_TEST]


def test_a_test_reaching_an_internal_symbol_is_rejected_past_the_boundary(tmp_path: Path) -> None:
    record = qualify_directly(require_commit(BOUNDARY_COMMIT), tmp_path).record
    assert record.outcome is QualificationOutcome.REJECTED, record.detail
    verdicts = {v.node_id: (v.rejection, v.detail) for v in record.hidden_verdicts}
    assert verdicts[BOUNDARY_TEST] == (TestRejection.REACHES_PAST_BOUNDARY, BOUNDARY_SYMBOL)
