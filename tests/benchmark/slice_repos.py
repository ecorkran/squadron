"""Throwaway-repo builders for slice-case tests, one per history shape (slice 426, Task 6).

Each builder makes a repo on ``main`` under *tmp_path* and returns a ``SliceRepo`` holding
the shas tests assert on. The fork commit holds the slice's design, task file and slice plan
(unless the shape leaves one out), a source file and its tests. Landing shapes reuse the
slice-range builders' history helpers (slice 403).
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from squadron.metrology.slice_range_models import LandingMethod, SliceLanding, SliceRanges
from tests.conftest import run_test_git
from tests.metrology.slice_range_repos import LandingShas

DOCS = "project-documents"
SOURCE_FILE = "src/app.py"
TEST_FILE = "tests/test_app.py"
NEW_TEST_FILE = "tests/test_feature.py"
DEVLOG = "DEVLOG.md"
INITIATIVE = 500
SLICE_NAME = "demo"
MAIN_BRANCH = "main"
REAL_LANDINGS_FILE = Path(__file__).parent / "fixtures" / "real_landings.json"
#: Squadron's own landings saved in ``real_landings.json``: slice index -> landing method.
REAL_LANDING_SLICES = {402: "merge_commit", 420: "fast_forward"}


class SliceRepo(NamedTuple):
    """A built repo, the slice index in it, and its landing (``second`` for a follow-up)."""

    repo: Path
    index: int
    landing: LandingShas
    second: LandingShas | None = None


RESOLVED_AT = datetime(2026, 11, 1, tzinfo=UTC)


def landing_to_record(shas: LandingShas) -> SliceLanding:
    """The ``slice_ranges`` landing for a fixture's shas."""
    return SliceLanding(
        method=LandingMethod.FAST_FORWARD if shas.merge is None else LandingMethod.MERGE_COMMIT,
        target_ref="main",
        before_sha=shas.before,
        after_sha=shas.after,
        fork_sha=shas.fork,
        tip_sha=shas.tip,
        merge_sha=shas.merge,
        resolved_at=RESOLVED_AT,
    )


def landing_of(built: SliceRepo) -> SliceLanding:
    """The first landing of a built repo as a ``SliceLanding``."""
    return landing_to_record(built.landing)


def load_real_landings() -> SliceRanges:
    """Squadron's real merge and fast-forward landings, as the store record held them."""
    return SliceRanges.model_validate_json(REAL_LANDINGS_FILE.read_text())


def design_path(index: int) -> str:
    return f"{DOCS}/user/slices/{index}-slice.{SLICE_NAME}.md"


def tasks_path(index: int, suffix: str = "") -> str:
    return f"{DOCS}/user/tasks/{index}-tasks.{SLICE_NAME}{suffix}.md"


def plan_path() -> str:
    return f"{DOCS}/user/architecture/{INITIATIVE}-slices.{SLICE_NAME}-initiative.md"


def _plan_text(index: int) -> str:
    return f"# Plan\n\n1. [ ] **({index}) Demo Slice** — text. Effort: 2/5\n"


def _head(repo: Path, ref: str = "HEAD") -> str:
    return run_test_git(repo, "rev-parse", ref).strip()


def _write(repo: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)


def _commit(repo: Path, message: str, files: dict[str, str]) -> str:
    _write(repo, files)
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", message)
    return _head(repo)


def _start_files(
    index: int,
    *,
    design: bool = True,
    tasks: bool | Sequence[str] = True,
    plan: bool = True,
) -> dict[str, str]:
    """The fork commit's files; ``tasks`` may list split-file suffixes such as ``-1``."""
    files = {
        SOURCE_FILE: "def run() -> int:\n    return 1\n",
        TEST_FILE: "from src.app import run\n\n\ndef test_run() -> None:\n    assert run() == 1\n",
        DEVLOG: "# DEVLOG\n",
    }
    if design:
        files[design_path(index)] = f"---\nslice: {SLICE_NAME}\n---\n# Design {index}\n"
    if tasks:
        suffixes = [""] if tasks is True else list(tasks)
        for suffix in suffixes:
            files[tasks_path(index, suffix)] = f"---\nslice: {SLICE_NAME}\n---\n- [ ] task{suffix}\n"
    if plan:
        files[plan_path()] = _plan_text(index)
    return files


def _init(tmp_path: Path, start_files: dict[str, str]) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    run_test_git(repo, "init", "-q", "-b", MAIN_BRANCH)
    return repo, _commit(repo, "start", start_files)


def _slice_work(repo: Path, index: int, label: str = "") -> str:
    """Code, a new test file, then DEVLOG and task-file bookkeeping; returns the tip."""
    _commit(
        repo,
        f"feat: slice {index} code{label}",
        {
            SOURCE_FILE: f"def run() -> int:\n    return 2{label and 1}\n",
            NEW_TEST_FILE: f"def test_feature{label.replace('-', '_')}() -> None:\n    assert True\n",
        },
    )
    return _commit(
        repo,
        f"docs: slice {index} bookkeeping{label}",
        {DEVLOG: f"# DEVLOG\n\nslice {index} done{label}\n"},
    )


def _branch(index: int) -> str:
    return f"{index}-slice.{SLICE_NAME}"


def _merge_no_ff(repo: Path, branch: str) -> str:
    run_test_git(repo, "merge", "-q", "--no-ff", "-m", f"Merge {branch}", branch)
    return _head(repo)


def _landing_via_merge(tmp_path: Path, index: int, start_files: dict[str, str]) -> SliceRepo:
    repo, fork = _init(tmp_path, start_files)
    run_test_git(repo, "checkout", "-q", "-b", _branch(index))
    tip = _slice_work(repo, index)
    run_test_git(repo, "checkout", "-q", MAIN_BRANCH)
    before = _commit(repo, "main moves", {"other.txt": "other\n"})
    merge = _merge_no_ff(repo, _branch(index))
    return SliceRepo(repo, index, LandingShas(fork, before, tip, merge, merge))


def two_parent_landing(tmp_path: Path) -> SliceRepo:
    """Slice 501 lands with a ``--no-ff`` merge commit while main has moved on."""
    return _landing_via_merge(tmp_path, 501, _start_files(501))


def fast_forward_landing(tmp_path: Path) -> SliceRepo:
    """Slice 502 fast-forwards into main: no landing commit, ``after`` is the tip."""
    repo, fork = _init(tmp_path, _start_files(502))
    run_test_git(repo, "checkout", "-q", "-b", _branch(502))
    tip = _slice_work(repo, 502)
    run_test_git(repo, "checkout", "-q", MAIN_BRANCH)
    run_test_git(repo, "merge", "-q", "--ff-only", _branch(502))
    return SliceRepo(repo, 502, LandingShas(fork, fork, tip, tip, None))


def two_landings_of_one_slice(tmp_path: Path) -> SliceRepo:
    """Slice 503 is merged, gets a follow-up commit on its branch, and is merged again."""
    first = _landing_via_merge(tmp_path, 503, _start_files(503))
    repo = first.repo
    run_test_git(repo, "checkout", "-q", _branch(503))
    second_tip = _slice_work(repo, 503, "-2")
    run_test_git(repo, "checkout", "-q", MAIN_BRANCH)
    second_before = _commit(repo, "main moves again", {"other2.txt": "other2\n"})
    second_merge = _merge_no_ff(repo, _branch(503))
    second = LandingShas(first.landing.tip, second_before, second_tip, second_merge, second_merge)
    return SliceRepo(repo, 503, first.landing, second)


def branch_with_target_merge(tmp_path: Path) -> SliceRepo:
    """Slice 504's branch carries a two-parent commit that merged main into it."""
    repo, fork = _init(tmp_path, _start_files(504))
    run_test_git(repo, "checkout", "-q", "-b", _branch(504))
    _commit(repo, "feat: slice 504 first", {SOURCE_FILE: "def run() -> int:\n    return 3\n"})
    run_test_git(repo, "checkout", "-q", MAIN_BRANCH)
    _commit(repo, "main moves", {"other.txt": "other\n"})
    run_test_git(repo, "checkout", "-q", _branch(504))
    run_test_git(repo, "merge", "-q", "--no-ff", "-m", "Merge branch 'main' into branch", MAIN_BRANCH)
    tip = _slice_work(repo, 504)
    run_test_git(repo, "checkout", "-q", MAIN_BRANCH)
    before = _head(repo)
    merge = _merge_no_ff(repo, _branch(504))
    return SliceRepo(repo, 504, LandingShas(fork, before, tip, merge, merge))


def no_task_file_at_fork(tmp_path: Path) -> SliceRepo:
    """Slice 505's fork has a design and a plan but no task file."""
    return _landing_via_merge(tmp_path, 505, _start_files(505, tasks=False))


def no_design_at_fork(tmp_path: Path) -> SliceRepo:
    """Slice 506's fork has a task file and a plan but no design."""
    return _landing_via_merge(tmp_path, 506, _start_files(506, design=False))


def no_slice_plan_at_fork(tmp_path: Path) -> SliceRepo:
    """Slice 507's fork has a design and a task file but no slice plan."""
    return _landing_via_merge(tmp_path, 507, _start_files(507, plan=False))


def split_task_files_at_fork(tmp_path: Path) -> SliceRepo:
    """Slice 508's fork has task files ``-1``, ``-2`` and ``-10``."""
    return _landing_via_merge(tmp_path, 508, _start_files(508, tasks=("-1", "-2", "-10")))


def docs_only_slice(tmp_path: Path) -> SliceRepo:
    """Slice 509 changes only DEVLOG, its task file and a review file."""
    index = 509
    repo, fork = _init(tmp_path, _start_files(index))
    run_test_git(repo, "checkout", "-q", "-b", _branch(index))
    _commit(repo, "docs: devlog", {DEVLOG: "# DEVLOG\n\nplanning only\n"})
    tip = _commit(
        repo,
        "docs: tasks and review",
        {
            tasks_path(index): f"---\nslice: {SLICE_NAME}\n---\n- [x] task\n",
            f"{DOCS}/user/reviews/{index}-review.tasks.{SLICE_NAME}.md": "# Review\n",
        },
    )
    run_test_git(repo, "checkout", "-q", MAIN_BRANCH)
    before = _commit(repo, "main moves", {"other.txt": "other\n"})
    merge = _merge_no_ff(repo, _branch(index))
    return SliceRepo(repo, index, LandingShas(fork, before, tip, merge, merge))


def all_tests_rewritten(tmp_path: Path) -> SliceRepo:
    """Slice 510 rewrites every test file the fork has, so no fork test node survives
    unchanged: the regression selection would be empty."""
    index = 510
    repo, fork = _init(tmp_path, _start_files(index))
    run_test_git(repo, "checkout", "-q", "-b", _branch(index))
    tip = _commit(
        repo,
        "feat: rewrite tests",
        {
            SOURCE_FILE: "def run() -> int:\n    return 4\n",
            TEST_FILE: "from src.app import run\n\n\ndef test_run() -> None:\n    assert run() == 4\n",
        },
    )
    run_test_git(repo, "checkout", "-q", MAIN_BRANCH)
    before = _commit(repo, "main moves", {"other.txt": "other\n"})
    merge = _merge_no_ff(repo, _branch(index))
    return SliceRepo(repo, index, LandingShas(fork, before, tip, merge, merge))


SLICE_PROJECT_FIXTURE = Path(__file__).parent / "fixtures" / "slice_project"
CODE_SLICE_INDEX = 511
DOCS_SLICE_INDEX = 512
#: What the code slice adds to the fixture project; tests assert on the new node.
NEW_FUNCTION_FILE = "src/calc.py"
NEW_FUNCTION_TEST = "tests/test_mul.py"


class SliceProjectRepos(NamedTuple):
    """The fixture project's history: a code slice and a docs-only slice, both landed."""

    repo: Path
    code: SliceRepo
    docs: SliceRepo


def _slice_project_plan() -> str:
    return (
        "# Plan\n\n"
        f"1. [ ] **({CODE_SLICE_INDEX}) Multiply** — add mul. Effort: 1/5\n"
        f"2. [ ] **({DOCS_SLICE_INDEX}) Notes** — planning only. Effort: 1/5\n"
    )


def _slice_project_docs() -> dict[str, str]:
    """Design and task file for both slices, the plan listing them and the initiative's
    architecture file (cf resolves ``cf set arch <initiative>`` against it)."""
    files = {
        plan_path(): _slice_project_plan(),
        f"{DOCS}/user/architecture/{INITIATIVE}-arch.{SLICE_NAME}-initiative.md": (
            f"---\ndocType: architecture\n---\n# Architecture {INITIATIVE}\n"
        ),
    }
    for index in (CODE_SLICE_INDEX, DOCS_SLICE_INDEX):
        files[design_path(index)] = f"---\nslice: {SLICE_NAME}\n---\n# Design {index}\n"
        files[tasks_path(index)] = f"---\nslice: {SLICE_NAME}\n---\n- [ ] task {index}\n"
    return files


def slice_project_history(tmp_path: Path) -> SliceProjectRepos:
    """Copy the ``slice_project`` fixture into *tmp_path* and commit a two-slice history.

    The first commit is the fixture plus both slices' design, task file and plan. Slice 511
    adds ``mul`` and its test and lands with a merge commit; slice 512 forks from that
    landing, changes only docs, and lands the same way.
    """
    repo = tmp_path / "repo"
    shutil.copytree(SLICE_PROJECT_FIXTURE, repo)
    run_test_git(repo, "init", "-q", "-b", MAIN_BRANCH)
    _write(repo, _slice_project_docs())
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "start")
    code = _land_code_slice(repo)
    docs = _land_docs_slice(repo, code.landing.after)
    return SliceProjectRepos(repo, code, docs)


def _land_code_slice(repo: Path) -> SliceRepo:
    index = CODE_SLICE_INDEX
    fork = _head(repo)
    run_test_git(repo, "checkout", "-q", "-b", _branch(index))
    original = (repo / NEW_FUNCTION_FILE).read_text()
    _commit(
        repo,
        "feat: add mul",
        {
            NEW_FUNCTION_FILE: original
            + "\n\ndef mul(left: int, right: int) -> int:\n    return left * right\n",
            NEW_FUNCTION_TEST: (
                "from calc import mul\n\n\ndef test_mul() -> None:\n    assert mul(2, 3) == 6\n"
            ),
        },
    )
    tip = _commit(repo, "docs: bookkeeping", {DEVLOG: f"# DEVLOG\n\nslice {index} done\n"})
    run_test_git(repo, "checkout", "-q", MAIN_BRANCH)
    before = _commit(repo, "main moves", {"other.txt": "other\n"})
    merge = _merge_no_ff(repo, _branch(index))
    return SliceRepo(repo, index, LandingShas(fork, before, tip, merge, merge))


def _land_docs_slice(repo: Path, fork: str) -> SliceRepo:
    index = DOCS_SLICE_INDEX
    run_test_git(repo, "checkout", "-q", "-b", _branch(index), fork)
    tip = _commit(
        repo,
        "docs: notes",
        {
            DEVLOG: "# DEVLOG\n\nplanning notes\n",
            tasks_path(index): f"---\nslice: {SLICE_NAME}\n---\n- [x] task {index}\n",
        },
    )
    run_test_git(repo, "checkout", "-q", MAIN_BRANCH)
    before = _commit(repo, "main moves again", {"other2.txt": "other2\n"})
    merge = _merge_no_ff(repo, _branch(index))
    return SliceRepo(repo, index, LandingShas(fork, before, tip, merge, merge))
