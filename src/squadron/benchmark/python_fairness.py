"""The Python fix-case adapter (slice 422 D3, D4, D6, D7, D11).

This file holds the pieces that run pytest with the trace plugin; the boundary resolver
and the diff overlay live beside it as they arrive. Every harness-side failure is logged at
ERROR and raised as ``HarnessFailure``: a check that could not run is never a verdict.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from squadron.benchmark.adapter import SandboxContext
from squadron.benchmark.fairness import (
    AllowedBoundary,
    CollectedTests,
    CollectionFailed,
    FairnessVerdict,
    HarnessFailure,
)
from squadron.benchmark.python_adapter import LOCKFILE_NAME
from squadron.benchmark.python_boundary import resolve_boundary
from squadron.benchmark.python_failure import venv_bin
from squadron.benchmark.python_tree_files import (
    PYPROJECT_NAME,
    copy_trace_plugin,
    grader_commands_for,
    overlay_files,
)
from squadron.benchmark.trace_verdict import TraceFacts, judge_trace
from squadron.core.process_runner import ProcessNotFoundError, ProcessTimedOutError
from squadron.metrology.benchmark_models import ConftestFixture, GraderCommand
from squadron.metrology.snapshot_models import SourceLanguage

_logger = logging.getLogger(__name__)

TRACE_MODULE = "squadron_fixcase_trace"
TRACE_CONFIG_ENV = "SQUADRON_FIXCASE_TRACE_CONFIG"
MODE_COLLECT = "collect"
MODE_TRACE = "trace"
CONFIG_FILE = "fixcase_trace_config.json"
OUTPUT_FILE = "fixcase_trace_output.json"
GIT_QUERY_TIMEOUT_S = 60
#: pytest exit codes a collect-only run may end with: 0 collected, 2 collection errors,
#: 5 nothing collected. Anything else (3 internal error, 4 usage) is a harness failure.
_COLLECT_EXIT_CODES = (0, 2, 5)
#: A trace run executes the tests: 0 all passed, 1 some failed (a hidden test may fail at the
#: reference; it is still traced). Anything else, a usage error for one, is a harness failure.
_TRACE_EXIT_CODES = (0, 1)
_DEFAULT_TEST_DIRS = ("tests", "test")
_DEFAULT_TEST_FILE_PATTERNS = ("test_*.py", "*_test.py", "conftest.py")


def _harness_failure(detail: str) -> HarnessFailure:
    _logger.error("fix-case harness failure: %s", detail)
    return HarnessFailure(detail)


def _configured_testpaths(pyproject_text: str | None) -> tuple[str, ...] | None:
    """``[tool.pytest.ini_options] testpaths`` from the project's config text, if set."""
    if pyproject_text is None:
        return None
    try:
        data = tomllib.loads(pyproject_text)
    except tomllib.TOMLDecodeError as exc:
        # An unparsable pyproject also fails the environment install, which reports it; here
        # the default test-side rules are the only answer left.
        _logger.warning("pyproject.toml does not parse (%s); using default test-side rules", exc)
        return None
    testpaths: Any = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("testpaths")
    if isinstance(testpaths, str):
        return tuple(testpaths.split())
    if isinstance(testpaths, list):
        return tuple(str(entry) for entry in testpaths)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return None


def _under(path: str, directory: str) -> bool:
    base = directory.strip().rstrip("/").removeprefix("./")
    return path == base or path.startswith(f"{base}/") or fnmatch.fnmatch(path, base)


def _default_test_side(path: str) -> bool:
    pure = PurePosixPath(path)
    if any(fnmatch.fnmatch(pure.name, pattern) for pattern in _DEFAULT_TEST_FILE_PATTERNS):
        return True
    return any(part in _DEFAULT_TEST_DIRS for part in pure.parts[:-1])


class PythonFixCaseAdapter:
    language = SourceLanguage.PYTHON

    def is_test_side(self, pyproject_text: str | None, path: str) -> bool:
        """Under the parent's ``testpaths`` when set, else by the default patterns and dirs."""
        testpaths = _configured_testpaths(pyproject_text)
        if testpaths is None:
            return _default_test_side(path)
        return any(_under(path, testpath) for testpath in testpaths)

    def is_test_source(self, path: str) -> bool:
        return path.endswith(".py")

    def lockfile_names(self) -> tuple[str, ...]:
        return (LOCKFILE_NAME,)

    def overlay(self, ctx: SandboxContext, files: Mapping[str, bytes | None]) -> None:
        """Write each ``path -> bytes`` and remove each ``path -> None`` inside the tree."""
        overlay_files(ctx.tree, files)

    def grader_commands(self, tree: Path) -> tuple[GraderCommand, ...]:
        return grader_commands_for(tree)

    def boundary(self, ctx: SandboxContext) -> AllowedBoundary:
        """The packaging boundary at the tree's current state (raises ``BoundaryUndecidable``)."""
        return resolve_boundary(ctx)

    def collect(self, ctx: SandboxContext) -> CollectedTests:
        """Node ids, closure digests and conftest fixtures at the tree's current file state.

        Raises ``CollectionFailed`` naming the first test-side file that failed to import,
        and ``HarnessFailure`` when the run itself could not produce a result.
        """
        output = self._run_plugin(ctx, MODE_COLLECT, ["--collect-only", "-q"])
        errors: list[dict[str, str]] = output["collection_errors"]
        if errors:
            files = ", ".join(error["file"] for error in errors)
            raise CollectionFailed(errors[0]["file"], f"{errors[0]['message']} (failed: {files})")
        digests: dict[str, str] = {}
        reached: dict[str, tuple[ConftestFixture, ...]] = {}
        for item in output["items"]:
            digests[item["node_id"]] = item["digest"]
            reached[item["node_id"]] = tuple(_fixture(entry) for entry in item["fixtures"])
        defined = tuple(_fixture(entry) for entry in output["conftest_fixtures"])
        return CollectedTests(digests=digests, fixtures_reached=reached, conftest_fixtures=defined)

    def _test_side_files(self, ctx: SandboxContext) -> list[str]:
        """Test-side files in the tree, uncommitted ones included (an overlay adds files)."""
        argv = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
        try:
            result = ctx.runner.run(argv, cwd=str(ctx.tree), timeout=GIT_QUERY_TIMEOUT_S)
        except (ProcessTimedOutError, ProcessNotFoundError) as exc:
            _logger.exception("git ls-files failed in %s", ctx.tree)
            raise HarnessFailure(f"git ls-files failed: {exc}") from exc
        if result.returncode != 0:
            raise _harness_failure(f"git ls-files exited {result.returncode}: {result.stderr.strip()}")
        pyproject = ctx.tree / PYPROJECT_NAME
        text = pyproject.read_text(encoding="utf-8") if pyproject.is_file() else None
        return [line for line in result.stdout.splitlines() if line and self.is_test_side(text, line)]

    def trace(
        self, ctx: SandboxContext, node_ids: Sequence[str], allowed: AllowedBoundary
    ) -> Mapping[str, FairnessVerdict]:
        """Run ``node_ids`` once with the trace plugin and judge each node's recorded facts.

        Meant for the reference file state, where the hidden tests pass and their whole path
        executes. A node the run did not report is a harness failure, not a verdict.
        """
        output = self._run_plugin(ctx, MODE_TRACE, list(node_ids), _TRACE_EXIT_CODES)
        has_co_qualname = bool(output["has_co_qualname"])
        nodes: dict[str, Any] = output["nodes"]
        verdicts: dict[str, FairnessVerdict] = {}
        for node_id in node_ids:
            if node_id not in nodes:
                raise _harness_failure(f"the trace run did not report {node_id}")
            facts = TraceFacts.from_plugin(nodes[node_id], has_co_qualname=has_co_qualname)
            verdicts[node_id] = judge_trace(facts, allowed)
        return verdicts

    def _run_plugin(
        self,
        ctx: SandboxContext,
        mode: str,
        pytest_args: Sequence[str],
        exit_codes: tuple[int, ...] = _COLLECT_EXIT_CODES,
    ) -> dict[str, Any]:
        """Run pytest in the sandbox with the trace plugin and return its parsed output."""
        plugin_dir = copy_trace_plugin(ctx)
        config = ctx.output_dir / CONFIG_FILE
        output = ctx.output_dir / OUTPUT_FILE
        config.write_text(
            json.dumps(
                {
                    "mode": mode,
                    "tree": str(ctx.tree),
                    "test_side_files": self._test_side_files(ctx),
                    "output": str(output),
                }
            ),
            encoding="utf-8",
        )
        env = {
            **ctx.env.variables((venv_bin(ctx.tree),)),
            "PYTHONPATH": str(plugin_dir),
            TRACE_CONFIG_ENV: str(config),
        }
        argv = [
            str(venv_bin(ctx.tree) / "python"),
            "-m",
            "pytest",
            "-p",
            TRACE_MODULE,
            "-p",
            "no:cacheprovider",
            *pytest_args,
        ]
        try:
            result = ctx.runner.run(
                argv, cwd=str(ctx.tree), timeout=ctx.suite_timeout_s, env=env, replace_env=True
            )
        except (ProcessTimedOutError, ProcessNotFoundError) as exc:
            _logger.exception("trace plugin run failed in %s", ctx.tree)
            raise HarnessFailure(f"pytest with the trace plugin failed: {exc}") from exc
        if not output.is_file():
            raise _harness_failure(
                "the trace plugin never loaded (no output file); "
                f"pytest stderr: {result.stderr.strip()}"
            )
        if result.returncode not in exit_codes:
            raise _harness_failure(
                f"pytest exited {result.returncode}; stderr: {result.stderr.strip()}"
            )
        return _read_output(output, result.stderr)


def _fixture(entry: Sequence[str]) -> ConftestFixture:
    return ConftestFixture(conftest_path=entry[0], fixture_name=entry[1])


def _read_output(output: Path, stderr: str) -> dict[str, Any]:
    try:
        parsed: dict[str, Any] = json.loads(output.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _harness_failure(
            f"the trace plugin's output does not parse ({exc}); pytest stderr: {stderr.strip()}"
        ) from exc
    return parsed
