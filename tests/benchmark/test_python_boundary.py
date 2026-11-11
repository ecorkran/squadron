"""The packaging boundary resolver and ``PythonFixCaseAdapter.boundary`` (slice 422 D6).

``network`` tests install a fixture project into a real sandbox.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from types import ModuleType

import pytest

from squadron.benchmark.adapter import SandboxContext
from squadron.benchmark.fairness import AllowedBoundary, BoundaryUndecidable, HarnessFailure
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.python_boundary import IMPORT_FAILURE_EXIT, RESOLVER_CONFIG_FILE
from squadron.benchmark.python_fairness import PythonFixCaseAdapter
from squadron.benchmark.python_tree_files import trace_plugin_dir
from squadron.benchmark.sandbox import BenchmarkSandbox
from squadron.benchmark.scrubbed_env import CredentialGrant, ScrubbedEnvironment
from squadron.core.process_runner import (
    ProcessNotFoundError,
    ProcessResult,
    ProcessTimedOutError,
    SubprocessRunner,
)
from tests.benchmark.support import RunnerCall, bare_context, git_tree

ADAPTER = PythonFixCaseAdapter()
RESOLVER_PATH = trace_plugin_dir() / "boundary_resolver.py"


def head(tree: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(tree), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def sandbox_context(fixture: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[SandboxContext]:
    tree = git_tree(fixture, tmp_path_factory.mktemp(f"{fixture}_src"))
    sandbox = BenchmarkSandbox(
        start_sha=head(tree),
        sandbox_id=f"boundary-{fixture}",
        repo_root=tree,
        runner=SubprocessRunner(),
        adapter=PythonBenchmarkAdapter(),
        harness_env=dict(os.environ),
        install_timeout_s=900,
        suite_timeout_s=300,
        root=tmp_path_factory.mktemp(f"{fixture}_root"),
    )
    with sandbox:
        yield sandbox.context()


@pytest.fixture(scope="module")
def project_context(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SandboxContext]:
    yield from sandbox_context("fixfair_project", tmp_path_factory)


@pytest.fixture(scope="module")
def no_boundary_context(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SandboxContext]:
    yield from sandbox_context("fixfair_no_boundary", tmp_path_factory)


@pytest.fixture(scope="module")
def bad_import_context(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SandboxContext]:
    yield from sandbox_context("fixfair_bad_import", tmp_path_factory)


@pytest.mark.network
def test_the_allowed_set_is_the_exports_and_the_script_target(project_context: SandboxContext) -> None:
    allowed = ADAPTER.boundary(project_context)
    assert allowed.entries == {("fixpkg.api", "exported_function"), ("fixpkg.cli", "main")}
    assert allowed.allows("fixpkg.api", "exported_function")
    assert not allowed.allows("fixpkg.internal", "internal_function")


@pytest.mark.network
def test_a_project_with_no_all_and_no_scripts_has_an_empty_boundary(
    no_boundary_context: SandboxContext,
) -> None:
    assert ADAPTER.boundary(no_boundary_context) == AllowedBoundary()


@pytest.mark.network
def test_a_package_that_will_not_import_is_undecidable(
    bad_import_context: SandboxContext, caplog: pytest.LogCaptureFixture
) -> None:
    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(BoundaryUndecidable, match="badimport cannot be imported"),
    ):
        ADAPTER.boundary(bad_import_context)


# --- Scripted failure modes: each is an ERROR log plus HarnessFailure ---------------------


def scripted(tmp_path: Path, behaviour: ProcessResult | Exception) -> SandboxContext:
    ctx = bare_context(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "p"\n[project.scripts]\nrun = "p.cli:main"\n', encoding="utf-8"
    )
    return SandboxContext(
        tree=ctx.tree,
        output_dir=ctx.output_dir,
        env=ScrubbedEnvironment(tmp_path, "scripted", CredentialGrant.none(), {}),
        runner=_Runner(behaviour),
        install_timeout_s=1,
        suite_timeout_s=1,
    )


class _Runner:
    """A ``ProcessRunner`` that raises or returns one scripted behaviour for every call."""

    def __init__(self, behaviour: ProcessResult | Exception) -> None:
        self._behaviour = behaviour
        self.calls: list[RunnerCall] = []

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
        stdin: str | None = None,
        replace_env: bool = False,
    ) -> ProcessResult:
        self.calls.append(RunnerCall(tuple(argv), cwd, timeout, env, replace_env))
        if isinstance(self._behaviour, Exception):
            raise self._behaviour
        return self._behaviour


def result(code: int, stdout: str = "", stderr: str = "") -> ProcessResult:
    return ProcessResult(("python",), code, stdout, stderr)


def test_a_resolver_bug_exit_is_a_harness_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = scripted(tmp_path, result(1, stderr="Traceback ... KeyError"))
    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="exited 1"):
        ADAPTER.boundary(ctx)
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_resolver_timeout_is_a_harness_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = scripted(tmp_path, ProcessTimedOutError(["python"], 1))
    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="exceeded"):
        ADAPTER.boundary(ctx)
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_missing_interpreter_is_a_harness_failure(tmp_path: Path) -> None:
    ctx = scripted(tmp_path, ProcessNotFoundError("python"))
    with pytest.raises(HarnessFailure, match="not found"):
        ADAPTER.boundary(ctx)


@pytest.mark.parametrize("stdout", ["not json at all", '{"wrong": []}', '{"allowed": [["only-one"]]}'])
def test_exit_zero_with_garbage_output_is_a_harness_failure(
    tmp_path: Path, stdout: str, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = scripted(tmp_path, result(0, stdout=stdout))
    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="does not parse"):
        ADAPTER.boundary(ctx)
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_the_import_failure_exit_code_is_undecidable_not_a_harness_failure(tmp_path: Path) -> None:
    ctx = scripted(tmp_path, result(IMPORT_FAILURE_EXIT, stderr="ImportError: nope"))
    with pytest.raises(BoundaryUndecidable, match="nope"):
        ADAPTER.boundary(ctx)


def test_the_resolver_is_given_the_projects_name_and_script_targets(tmp_path: Path) -> None:
    ctx = scripted(tmp_path, result(0, stdout='{"allowed": [["p.cli", "main"]]}'))
    allowed = ADAPTER.boundary(ctx)
    assert allowed.entries == {("p.cli", "main")}
    config = (ctx.output_dir / RESOLVER_CONFIG_FILE).read_text(encoding="utf-8")
    assert '"name": "p"' in config and "p.cli:main" in config


# --- The resolver script itself --------------------------------------------------------


def load_resolver() -> ModuleType:
    spec = importlib.util.spec_from_file_location("boundary_resolver_under_test", RESOLVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_harness_and_resolver_agree_on_the_import_failure_exit_code() -> None:
    assert load_resolver().IMPORT_FAILURE_EXIT == IMPORT_FAILURE_EXIT


def test_top_level_packages_come_from_a_regular_installs_files_and_an_editable_pth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = tmp_path / "site"
    (site / "regpkg").mkdir(parents=True)
    (site / "regpkg" / "__init__.py").write_text("", encoding="utf-8")
    (site / "single.py").write_text("", encoding="utf-8")
    dist_info = site / "regdist-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: regdist\nVersion: 1.0\n", encoding="utf-8"
    )
    (dist_info / "RECORD").write_text(
        "regpkg/__init__.py,,\nsingle.py,,\nregdist-1.0.dist-info/METADATA,,\n", encoding="utf-8"
    )
    src = tmp_path / "src"
    (src / "editpkg").mkdir(parents=True)
    (src / "editpkg" / "__init__.py").write_text("", encoding="utf-8")
    (src / "loose.py").write_text("", encoding="utf-8")
    edit_info = site / "editdist-1.0.dist-info"
    edit_info.mkdir()
    (edit_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: editdist\nVersion: 1.0\n", encoding="utf-8"
    )
    (site / "_editable_impl_editdist.pth").write_text(
        f"{src}\n# comment\nimport os\n", encoding="utf-8"
    )
    (edit_info / "RECORD").write_text(
        "_editable_impl_editdist.pth,,\neditdist-1.0.dist-info/METADATA,,\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(site))
    import importlib.metadata as metadata

    resolver = load_resolver()
    assert resolver.top_level_packages(metadata.distribution("regdist")) == ["regpkg", "single"]
    assert resolver.top_level_packages(metadata.distribution("editdist")) == ["editpkg", "loose"]
    assert sys.modules.get("boundary_resolver_under_test") is None
