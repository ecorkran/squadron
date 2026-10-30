"""Adapters resolve tools from ``environment_root`` and read the tree from ``repo_root`` (403 D5).

Each test sets the two roots to different directories, as a commit export does, and checks
three things: the tool path is under the environment, the tool runs with ``cwd=repo_root``,
and the rule-set source is read from the measured tree.
"""

from __future__ import annotations

import stat
from collections.abc import Sequence
from pathlib import Path

import pytest

from squadron.metrology.snapshot.contract import ToolResult
from squadron.metrology.snapshot.python_lint import measure_ruff_lint
from squadron.metrology.snapshot.python_types import measure_pyright_types
from squadron.metrology.snapshot.typescript_lint import measure_eslint_lint
from tests.metrology.snapshot.builders import make_context, read_fixture
from tests.metrology.snapshot.conftest import FakeToolRunner

LOCK_BYTES = b"version = 1\n"


class CwdRecordingRunner(FakeToolRunner):
    """A scripted runner that also records the working directory of every call."""

    def __init__(self) -> None:
        super().__init__()
        self.cwds: list[Path] = []

    def run(self, argv: Sequence[str], *, cwd: Path, timeout_s: int) -> ToolResult:
        self.cwds.append(cwd)
        return super().run(argv, cwd=cwd, timeout_s=timeout_s)

    def cwd_of(self, prefix: tuple[str, ...]) -> Path:
        index = next(i for i, call in enumerate(self.calls) if call[: len(prefix)] == prefix)
        return self.cwds[index]


def executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@pytest.fixture
def roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """``(repo_root, environment_root)``: two distinct directories, with only fake tools on PATH."""
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    repo_root = tmp_path / "tree"
    environment_root = tmp_path / "live"
    repo_root.mkdir()
    environment_root.mkdir()
    return repo_root, environment_root


def test_ruff_comes_from_the_environment_and_runs_in_the_tree(roots: tuple[Path, Path]) -> None:
    repo_root, environment_root = roots
    (repo_root / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")
    ruff = executable(environment_root / ".venv" / "bin" / "ruff")
    runner = CwdRecordingRunner()
    runner.script(
        (str(ruff), "--version"),
        ToolResult(0, read_fixture("version_ruff.stdout", repo_root), "", False),
    )
    runner.script(
        (str(ruff), "check"),
        ToolResult(0, read_fixture("ruff_scratch_findings.stdout", repo_root), "", False),
    )
    ctx = make_context(repo_root, runner, environment_root=environment_root)

    measurement = measure_ruff_lint(ctx, ["bad.py"])

    assert measurement.absent is None
    assert runner.calls[-1][0] == str(ruff)
    assert runner.cwd_of((str(ruff), "check")) == repo_root
    assert measurement.rule_set is not None
    assert measurement.rule_set.source == "pyproject.toml[tool.ruff]"


def test_pyright_comes_from_the_environment_and_runs_in_the_tree(roots: tuple[Path, Path]) -> None:
    repo_root, environment_root = roots
    (repo_root / "uv.lock").write_bytes(LOCK_BYTES)
    (environment_root / "uv.lock").write_bytes(LOCK_BYTES)
    (repo_root / "pyrightconfig.json").write_text("{}\n", encoding="utf-8")
    python = executable(environment_root / ".venv" / "bin" / "python")
    pyright = executable(environment_root / ".venv" / "bin" / "pyright")
    uv = executable(roots[0].parent / "bin" / "uv")
    runner = CwdRecordingRunner()
    runner.script((str(uv), "sync"), ToolResult(0, "", "", False))
    runner.script((str(python), "--version"), ToolResult(0, "Python 3.12.4\n", "", False))
    runner.script(
        (str(pyright), "--version"),
        ToolResult(0, read_fixture("version_pyright.stdout", repo_root), "", False),
    )
    runner.script(
        (str(pyright), "--outputjson"),
        ToolResult(1, read_fixture("pyright_scratch_findings.stdout", repo_root), "", False),
    )
    ctx = make_context(repo_root, runner, environment_root=environment_root)

    measurement = measure_pyright_types(ctx, ["mod.py"])

    assert measurement.absent is None
    run = next(call for call in runner.calls if "--outputjson" in call)
    assert run[0] == str(pyright)
    assert run[run.index("--pythonpath") + 1] == str(python)
    assert runner.cwd_of((str(pyright), "--outputjson")) == repo_root
    assert runner.cwd_of((str(uv), "sync")) == environment_root
    assert measurement.rule_set is not None
    assert measurement.rule_set.source == "pyrightconfig.json"


def test_eslint_comes_from_the_environment_and_runs_in_the_tree(roots: tuple[Path, Path]) -> None:
    repo_root, environment_root = roots
    (repo_root / "eslint.config.mjs").write_bytes(b"export default [];\n")
    eslint = executable(environment_root / "node_modules" / ".bin" / "eslint")
    runner = CwdRecordingRunner()
    runner.script(
        (str(eslint), "--version"),
        ToolResult(0, read_fixture("version_eslint.stdout", repo_root), "", False),
    )
    runner.script(
        (str(eslint), "--format"),
        ToolResult(1, read_fixture("eslint_context_forge_findings.stdout", repo_root), "", False),
    )
    ctx = make_context(repo_root, runner, environment_root=environment_root)

    measurement = measure_eslint_lint(ctx, ["packages/core/src/project-defaults.ts"])

    assert measurement.absent is None
    assert runner.calls[-1][0] == str(eslint)
    assert runner.cwd_of((str(eslint), "--format")) == repo_root
    assert measurement.rule_set is not None
    assert measurement.rule_set.source == "eslint.config.mjs"
