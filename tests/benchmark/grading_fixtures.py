"""Start and reference fixture trees for the grading tests (slice 425 Tasks 12-13).

Source commit: 50648563 "fix: rank FAIL above UNKNOWN in split-review verdict fold" (#176).
Files: ``tests/review/test_parts.py`` (start = ``50648563~1``, reference = ``50648563``) and
the ``tests/review/conftest.py`` that sits beside it. The test file has a class
(``TestWorstVerdict``) with a parametrized method (``test_every_ordered_pair``). Both files
import only pytest, the standard library and ``squadron``, so the trees run under the repo's
own interpreter.

Added by this slice, because the commit changed no conftest: the reference conftest gains
imports (``Sequence`` on the existing ``collections.abc`` line, and ``Verdict``) and one fixture
(``verdict_order``), and the reference test file gains one test that uses it
(``test_fold_matches_the_fixture_order``). That is the shape 422 D3 permits and 425 D3 must
inject.

The trees under ``fixtures/grading/`` are plain files. ``start/`` is the whole start tree;
``reference/`` and each ``producer_*/`` hold only the files they change over it. The producer
variants: (a) edits an existing assertion, (b) adds ``# type: ignore`` and ``# noqa: E501`` in a
new source file, (c) loosens ``[tool.pyright]`` and ``[tool.ruff]`` while adding a dependency and
a ``[tool.uv]`` change, (d) adds a test and a fixture named like the hidden ones, (e) adds a
``test_sqhidden_<stem>.py``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.tree_reader import GitTreeReader
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CaseKind,
    CaseProvenance,
    ConftestFixture,
    GraderCommand,
    GraderCommandKind,
)
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from tests.conftest import run_test_git

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "grading"
START_FIXTURE = FIXTURE_ROOT / "start"
REFERENCE_FIXTURE = FIXTURE_ROOT / "reference"

HIDDEN_FILE = "tests/review/test_parts.py"
CONFTEST_PATH = "tests/review/conftest.py"
PARAMETRIZED_HIDDEN_ID = f"{HIDDEN_FILE}::TestWorstVerdict::test_every_ordered_pair[FAIL-UNKNOWN]"
FIXTURE_USING_HIDDEN_ID = f"{HIDDEN_FILE}::TestWorstVerdict::test_fold_matches_the_fixture_order"
HIDDEN_IDS = (
    f"{HIDDEN_FILE}::TestWorstVerdict::test_fail_outranks_unknown",
    FIXTURE_USING_HIDDEN_ID,
    PARAMETRIZED_HIDDEN_ID,
)
HIDDEN_FIXTURE = ConftestFixture(conftest_path=CONFTEST_PATH, fixture_name="verdict_order")
PYTEST_TIMEOUT_S = 120
#: Each variant and the files it changes over the start tree, sorted.
PRODUCER_VARIANT_FILES: dict[str, tuple[str, ...]] = {
    "producer_a": ("tests/review/test_parts.py",),
    "producer_b": ("src/fixture_pkg/helpers.py",),
    "producer_c": ("pyproject.toml",),
    "producer_d": ("tests/review/conftest.py", "tests/review/test_parts.py"),
    "producer_e": ("tests/review/test_sqhidden_test_parts.py",),
}


@dataclass(frozen=True)
class GradingRepo:
    """A git repo with the start commit and the reference commit on top of it."""

    root: Path
    start_sha: str
    reference_sha: str

    @property
    def start(self) -> GitTreeReader:
        return GitTreeReader(SubprocessRunner(), self.root, self.start_sha)

    @property
    def reference(self) -> GitTreeReader:
        return GitTreeReader(SubprocessRunner(), self.root, self.reference_sha)


def copy_tree(source: Path, destination: Path) -> None:
    """Copy *source* over *destination*, creating directories and overwriting files."""
    shutil.copytree(source, destination, dirs_exist_ok=True)


def build_grading_repo(root: Path) -> GradingRepo:
    """Create a repo at *root*: the start fixture committed, then the reference's files."""
    root.mkdir(parents=True)
    run_test_git(root, "init", "-q", "-b", "main")
    copy_tree(START_FIXTURE, root)
    run_test_git(root, "add", "-A")
    run_test_git(root, "commit", "-q", "-m", "start")
    start_sha = run_test_git(root, "rev-parse", "HEAD").strip()
    copy_tree(REFERENCE_FIXTURE, root)
    run_test_git(root, "add", "-A")
    run_test_git(root, "commit", "-q", "-m", "reference")
    reference_sha = run_test_git(root, "rev-parse", "HEAD").strip()
    return GradingRepo(root=root, start_sha=start_sha, reference_sha=reference_sha)


def checkout_tree(repo: GradingRepo, sha: str, destination: Path) -> Path:
    """Export the files of commit *sha* into a new directory and return it."""
    destination.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "archive", sha], cwd=repo.root, capture_output=True, check=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(destination)], input=archive, check=True)
    return destination


def _pytest(tree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=tree,
        capture_output=True,
        text=True,
        timeout=PYTEST_TIMEOUT_S,
    )


def collect_ids(tree: Path, ids: tuple[str, ...]) -> tuple[str, ...]:
    """The node ids pytest collects in *tree* for the given ids (``--collect-only -q``)."""
    done = _pytest(tree, "--collect-only", "-q", *ids)
    if done.returncode not in (0, 5):
        raise RuntimeError(f"pytest collection failed:\n{done.stdout}\n{done.stderr}")
    return tuple(line for line in done.stdout.splitlines() if "::" in line)


def run_pytest_ids(tree: Path, ids: tuple[str, ...]) -> dict[str, str]:
    """Run the given node ids in *tree*; map each reported id to its outcome.

    Outcomes are ``passed``, ``failed``, ``skipped`` or ``error``, read from pytest's junit
    XML (``xunit1``, which records each test's file).
    """
    report = tree.parent / f"{tree.name}.junit.xml"
    _pytest(tree, "-o", "junit_family=xunit1", f"--junitxml={report}", *ids)
    return _read_junit(report)


def _read_junit(report: Path) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    for case in ElementTree.parse(report).iter("testcase"):
        file_path = case.attrib["file"]
        module = file_path.removesuffix(".py").replace("/", ".")
        classname = case.attrib["classname"].removeprefix(module).strip(".")
        parts = [file_path, *([part for part in classname.split(".") if part]), case.attrib["name"]]
        children = {child.tag for child in case}
        outcome = "passed"
        if "error" in children:
            outcome = "error"
        elif "failure" in children:
            outcome = "failed"
        elif "skipped" in children:
            outcome = "skipped"
        outcomes["::".join(parts)] = outcome
    return outcomes


@dataclass(frozen=True)
class VariantTree:
    """A producer's tree: a clone checked out at the start commit with the variant committed."""

    root: Path
    start_sha: str
    commit_sha: str

    def diff(self) -> bytes:
        """``git diff --binary`` from the start commit to the producer's commit."""
        return subprocess.run(
            ["git", "diff", "--binary", self.start_sha, self.commit_sha],
            cwd=self.root,
            capture_output=True,
            check=True,
        ).stdout

    def changed_files(self) -> tuple[str, ...]:
        names = run_test_git(self.root, "diff", "--name-only", self.start_sha, self.commit_sha)
        return tuple(sorted(names.split()))


def build_variant(repo: GradingRepo, variant: str, destination: Path) -> VariantTree:
    """Clone *repo* to *destination*, apply the ``producer_*`` variant over the start tree, commit."""
    run_test_git(repo.root.parent, "clone", "-q", "--no-hardlinks", str(repo.root), str(destination))
    run_test_git(destination, "checkout", "-q", "--detach", repo.start_sha)
    copy_tree(FIXTURE_ROOT / variant, destination)
    run_test_git(destination, "add", "-A")
    run_test_git(destination, "commit", "-q", "-m", variant)
    commit_sha = run_test_git(destination, "rev-parse", "HEAD").strip()
    return VariantTree(root=destination, start_sha=repo.start_sha, commit_sha=commit_sha)


def make_grading_case(
    repo: GradingRepo, grader_commands: tuple[GraderCommand, ...] | None = None
) -> BenchmarkCase:
    """A fix case over the fixture commits, hidden set and hidden fixture as designed above."""
    return BenchmarkCase.build(
        project_id=ProjectId(value="grading-fixture", source=ProjectIdSource.RECORDED),
        kind=CaseKind.FIX,
        start_sha=repo.start_sha,
        reference_sha=repo.reference_sha,
        task_text="fix the verdict fold",
        hidden_tests=HIDDEN_IDS,
        hidden_fixtures=(HIDDEN_FIXTURE,),
        superseded_tests=(),
        excluded_tests=(),
        grader_commands=grader_commands
        or (GraderCommand(kind=GraderCommandKind.SUITE, argv=("pytest",)),),
        provenance=CaseProvenance(
            source_ref="fixture", created_at=datetime(2026, 11, 14, tzinfo=UTC), built_by="test"
        ),
    )


def build_tree_with(
    repo: GradingRepo, name: str, files: Mapping[str, str | None], destination: Path
) -> VariantTree:
    """Like ``build_variant`` for files given inline: ``path -> text``, ``None`` deletes."""
    run_test_git(repo.root.parent, "clone", "-q", "--no-hardlinks", str(repo.root), str(destination))
    run_test_git(destination, "checkout", "-q", "--detach", repo.start_sha)
    for path, content in files.items():
        target = destination / path
        if content is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    run_test_git(destination, "add", "-A")
    run_test_git(destination, "commit", "-q", "-m", name)
    commit_sha = run_test_git(destination, "rev-parse", "HEAD").strip()
    return VariantTree(root=destination, start_sha=repo.start_sha, commit_sha=commit_sha)
