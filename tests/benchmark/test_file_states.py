"""File states, overlay and grader commands (slice 422 D4, D11). ``network`` tests install."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from squadron.benchmark.adapter import SandboxContext
from squadron.benchmark.diff_classify import DiffClassification, classify_diff, parse_name_status
from squadron.benchmark.fairness import HarnessFailure
from squadron.benchmark.file_states import FileState, FileStates
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.python_fairness import CONFIG_FILE, PythonFixCaseAdapter
from squadron.benchmark.sandbox import BenchmarkSandbox
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import GraderCommandKind
from tests.benchmark.support import FixHistory, fix_history, hermetic_git

ADAPTER = PythonFixCaseAdapter()
RUNNER = SubprocessRunner()
TIMEOUT = 60.0
TOUCHED = {
    "tests/conftest.py",
    "tests/test_reach.py",
    "tests/test_new_feature.py",
    "tests/test_other.py",
}


def classify(history: FixHistory) -> DiffClassification:
    raw = hermetic_git(
        history.repo, "diff", "--name-status", "--no-renames", history.parent_sha, history.fix_sha
    )

    def read(sha: str, path: str) -> str | None:
        shown = hermetic_git(history.repo, "show", f"{sha}:{path}")
        return shown

    result = classify_diff(
        parse_name_status(raw),
        ADAPTER,
        None,
        lambda path: read(history.parent_sha, path),
        lambda path: read(history.fix_sha, path),
    )
    assert isinstance(result, DiffClassification)
    return result


def file_states(history: FixHistory) -> FileStates:
    return FileStates.build(
        RUNNER, history.repo, classify(history), history.parent_sha, history.fix_sha, TIMEOUT
    )


def snapshot(tree: Path) -> dict[str, str]:
    """Path -> sha256 of every file outside ``.git`` and ``.venv``."""
    found: dict[str, str] = {}
    for current, dirs, names in os.walk(tree):
        dirs[:] = [name for name in dirs if name not in (".git", ".venv")]
        for name in names:
            path = Path(current) / name
            found[path.relative_to(tree).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


@pytest.fixture(scope="module")
def history(tmp_path_factory: pytest.TempPathFactory) -> FixHistory:
    return fix_history("fixfair_project", "sort_sets", tmp_path_factory.mktemp("states"))


@pytest.fixture(scope="module")
def parent_sandbox(
    history: FixHistory, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[BenchmarkSandbox]:
    sandbox = BenchmarkSandbox(
        start_sha=history.parent_sha,
        sandbox_id="states-parent",
        repo_root=history.repo,
        runner=RUNNER,
        adapter=PythonBenchmarkAdapter(),
        harness_env=dict(os.environ),
        install_timeout_s=900,
        suite_timeout_s=300,
        root=tmp_path_factory.mktemp("states_root"),
    )
    with sandbox:
        yield sandbox


@pytest.fixture
def ctx(parent_sandbox: BenchmarkSandbox, history: FixHistory) -> Iterator[SandboxContext]:
    """The shared sandbox, restored to the parent state after each test."""
    context = parent_sandbox.context()
    yield context
    file_states(history).switch_to(context, ADAPTER, FileState.PARENT)


def status_paths(tree: Path) -> set[str]:
    out = hermetic_git(tree, "status", "--porcelain")
    # hermetic_git strips the output, which eats the first line's leading status space.
    return {line.split(maxsplit=1)[1] for line in out.splitlines() if line.strip()}


# --- Pure content (no sandbox) -------------------------------------------------------


def test_file_states_hold_whole_files_per_state(history: FixHistory) -> None:
    states = file_states(history)
    assert set(states.reference_files) == TOUCHED
    assert states.reference_files["tests/test_other.py"] is None
    assert states.parent_files["tests/test_new_feature.py"] is None
    assert states.parent_files["tests/test_other.py"] is not None
    assert b"extra_value" in (states.reference_files["tests/conftest.py"] or b"")
    assert b"extra_value" not in (states.parent_files["tests/conftest.py"] or b"")
    assert set(states.overlay_files) == TOUCHED  # every touched path here is test-side


def test_parent_plus_overlay_takes_test_side_files_from_the_reference(history: FixHistory) -> None:
    states = file_states(history)
    plus = states.files_for(FileState.PARENT_PLUS_OVERLAY)
    assert plus == states.files_for(FileState.REFERENCE)
    assert states.files_for(FileState.PARENT) == dict(states.parent_files)


def test_a_path_absent_at_the_sha_is_a_harness_failure(
    history: FixHistory, caplog: pytest.LogCaptureFixture
) -> None:
    classification = DiffClassification(
        added=(), changed=("tests/no_such_file.py",), deleted=(), test_side=()
    )
    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="no_such_file"):
        FileStates.build(
            RUNNER, history.repo, classification, history.parent_sha, history.fix_sha, TIMEOUT
        )
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_non_utf8_file_is_refused_rather_than_altered(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    hermetic_git(repo, "init", "-q", "-b", "main")
    (repo / "blob.py").write_bytes(b"x = '\xff\xfe'\n")
    hermetic_git(repo, "add", "-A")
    hermetic_git(repo, "commit", "-q", "-m", "binary")
    sha = hermetic_git(repo, "rev-parse", "HEAD")
    classification = DiffClassification(added=("blob.py",), changed=(), deleted=(), test_side=())
    with pytest.raises(HarnessFailure, match="not valid UTF-8"):
        FileStates.build(RUNNER, repo, classification, sha, sha, TIMEOUT)


# --- A real sandbox ------------------------------------------------------------------


@pytest.mark.network
def test_overlay_shows_exactly_the_overlaid_paths_in_git_status(
    ctx: SandboxContext, history: FixHistory
) -> None:
    assert status_paths(ctx.tree) == set()
    file_states(history).switch_to(ctx, ADAPTER, FileState.REFERENCE)
    assert status_paths(ctx.tree) == TOUCHED


@pytest.mark.network
def test_switching_parent_reference_parent_leaves_the_tree_byte_identical(
    ctx: SandboxContext, history: FixHistory
) -> None:
    states = file_states(history)
    before = snapshot(ctx.tree)
    states.switch_to(ctx, ADAPTER, FileState.REFERENCE)
    assert snapshot(ctx.tree) != before
    states.switch_to(ctx, ADAPTER, FileState.PARENT)
    assert snapshot(ctx.tree) == before


@pytest.mark.network
def test_collect_after_switching_to_reference_includes_the_added_test_file(
    ctx: SandboxContext, history: FixHistory
) -> None:
    file_states(history).switch_to(ctx, ADAPTER, FileState.REFERENCE)
    collected = ADAPTER.collect(ctx)
    assert "tests/test_new_feature.py::test_new_behavior" in collected.digests
    config = json.loads((ctx.output_dir / CONFIG_FILE).read_text(encoding="utf-8"))
    assert "tests/test_new_feature.py" in config["test_side_files"]


@pytest.mark.network
def test_the_environment_identity_is_unchanged_across_the_switches(
    ctx: SandboxContext, parent_sandbox: BenchmarkSandbox, history: FixHistory
) -> None:
    states = file_states(history)
    states.switch_to(ctx, ADAPTER, FileState.REFERENCE)
    states.switch_to(ctx, ADAPTER, FileState.PARENT_PLUS_OVERLAY)
    resolved = PythonBenchmarkAdapter().resolve_environment(ctx)
    assert resolved.identity_digest == parent_sandbox.identity.identity_digest


@pytest.mark.network
@pytest.mark.parametrize("path", ["../escape.txt", "/etc/escape.txt", "tests/../../escape.txt", ""])
def test_a_path_escaping_the_tree_raises_and_writes_nothing(
    ctx: SandboxContext, path: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure):
        ADAPTER.overlay(ctx, {"tests/ok.py": b"x = 1\n", path: b"nope"})
    assert not (ctx.tree / "tests" / "ok.py").exists(), "validation precedes any write"
    assert not (ctx.tree.parent / "escape.txt").exists()
    assert any(record.levelno == logging.ERROR for record in caplog.records)


@pytest.mark.network
def test_an_overlay_into_a_read_only_directory_is_a_harness_failure(
    ctx: SandboxContext, caplog: pytest.LogCaptureFixture
) -> None:
    locked = ctx.tree / "tests"
    original = locked.stat().st_mode
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="overlay of"):
            ADAPTER.overlay(ctx, {"tests/new_file.py": b"x = 1\n"})
    finally:
        locked.chmod(original)
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_removing_a_file_prunes_the_directories_it_alone_created(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    ADAPTER.overlay(SandboxContextStub.at(tree), {"deep/er/file.py": b"x = 1\n"})
    assert (tree / "deep" / "er" / "file.py").is_file()
    ADAPTER.overlay(SandboxContextStub.at(tree), {"deep/er/file.py": None})
    assert not (tree / "deep").exists()


class SandboxContextStub:
    """Only ``tree`` is read by ``overlay``."""

    @staticmethod
    def at(tree: Path) -> SandboxContext:
        return SandboxContext(
            tree=tree,
            output_dir=tree,
            env=None,  # type: ignore[arg-type]
            runner=RUNNER,
            install_timeout_s=1,
            suite_timeout_s=1,
        )


# --- grader_commands (D11) -------------------------------------------------------------


def tree_with(tmp_path: Path, name: str, pyproject: str, extra: tuple[str, ...] = ()) -> Path:
    tree = tmp_path / name
    tree.mkdir()
    (tree / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    for filename in extra:
        (tree / filename).write_text("", encoding="utf-8")
    return tree


@pytest.mark.parametrize(
    ("pyproject", "extra", "expected"),
    [
        ("[project]\nname = 'p'\n", (), [GraderCommandKind.SUITE]),
        ("[tool.ruff]\nline-length = 100\n", (), [GraderCommandKind.SUITE, GraderCommandKind.LINT]),
        (
            "[tool.pyright]\ninclude = ['src']\n",
            (),
            [GraderCommandKind.SUITE, GraderCommandKind.TYPECHECK],
        ),
        (
            "[tool.ruff]\n\n[tool.pyright]\n",
            (),
            [GraderCommandKind.SUITE, GraderCommandKind.LINT, GraderCommandKind.TYPECHECK],
        ),
        ("[project]\nname = 'p'\n", ("ruff.toml",), [GraderCommandKind.SUITE, GraderCommandKind.LINT]),
        (
            "[project]\nname = 'p'\n",
            ("pyrightconfig.json",),
            [GraderCommandKind.SUITE, GraderCommandKind.TYPECHECK],
        ),
    ],
    ids=["neither", "ruff only", "pyright only", "both", "ruff.toml", "pyrightconfig.json"],
)
def test_grader_commands_follow_the_parents_configured_tools(
    tmp_path: Path, pyproject: str, extra: tuple[str, ...], expected: list[GraderCommandKind]
) -> None:
    commands = ADAPTER.grader_commands(tree_with(tmp_path, "t", pyproject, extra))
    assert [command.kind for command in commands] == expected


def test_a_tree_without_a_pyproject_still_gets_the_suite(tmp_path: Path) -> None:
    tree = tmp_path / "bare"
    tree.mkdir()
    assert [c.kind for c in ADAPTER.grader_commands(tree)] == [GraderCommandKind.SUITE]
