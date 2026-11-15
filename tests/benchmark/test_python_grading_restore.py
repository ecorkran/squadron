"""Tool-config restoration and dependency-change detection (slice 425 Task 14, D4, D5)."""

from __future__ import annotations

import logging
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest

from squadron.benchmark.grading_adapter import ProducerConfigError
from squadron.benchmark.python_grading import (
    PACKAGING_TOOL_TABLES,
    deps_changed,
    restore_tool_config,
)
from squadron.benchmark.tree_reader import GitTreeReader
from squadron.core.process_runner import SubprocessRunner
from tests.benchmark.grading_fixtures import GradingRepo, build_variant, checkout_tree
from tests.conftest import run_test_git

START_PYPROJECT = """\
[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[tool.ruff]
line-length = 100

[tool.pyright]
typeCheckingMode = "strict"
"""


def load(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def make_case(tmp_path: Path, start_files: dict[str, str]) -> tuple[GitTreeReader, Path]:
    """A repo committed with *start_files*, and a producer tree that starts as a copy of them."""
    repo = tmp_path / "start-repo"
    tree = tmp_path / "producer-tree"
    for root in (repo, tree):
        for name, content in start_files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(content, encoding="utf-8")
    run_test_git(repo, "init", "-q", "-b", "main")
    run_test_git(repo, "add", "-A")
    run_test_git(repo, "commit", "-q", "-m", "start")
    sha = run_test_git(repo, "rev-parse", "HEAD").strip()
    return GitTreeReader(SubprocessRunner(), repo, sha), tree


@pytest.fixture
def variant_c(grading_repo: GradingRepo, tmp_path: Path) -> Path:
    return build_variant(grading_repo, "producer_c", tmp_path / "variant-c").root


class TestRestoreOnTheFixtureTrees:
    def test_variant_c_restores_ruff_and_pyright_and_keeps_packaging_and_deps(
        self, grading_repo: GradingRepo, variant_c: Path
    ) -> None:
        result = restore_tool_config(variant_c, grading_repo.start)
        assert result.config_edits == ("tool.pyright", "tool.ruff")
        restored = load(variant_c / "pyproject.toml")
        start = tomllib.loads(grading_repo.start.read("pyproject.toml").decode())
        assert restored["tool"]["ruff"] == start["tool"]["ruff"]
        assert restored["tool"]["pyright"] == start["tool"]["pyright"]
        assert restored["project"]["dependencies"] == ["tomli-w>=1.0"]
        assert restored["tool"]["uv"] == {"managed": True, "package": False}

    def test_an_unchanged_table_is_not_reported(
        self, grading_repo: GradingRepo, variant_c: Path
    ) -> None:
        result = restore_tool_config(variant_c, grading_repo.start)
        assert "tool.pytest" not in result.config_edits
        assert "tool.uv" not in result.config_edits

    def test_a_tree_identical_to_the_start_reports_nothing(
        self, grading_repo: GradingRepo, tmp_path: Path
    ) -> None:
        tree = checkout_tree(grading_repo, grading_repo.start_sha, tmp_path / "same")
        before = (tree / "pyproject.toml").read_bytes()
        assert restore_tool_config(tree, grading_repo.start).config_edits == ()
        assert (tree / "pyproject.toml").read_bytes() == before


class TestRestoreRules:
    def test_a_producer_added_ruff_toml_is_deleted_and_reported(self, tmp_path: Path) -> None:
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        (tree / "ruff.toml").write_text("line-length = 300\n", encoding="utf-8")
        result = restore_tool_config(tree, start)
        assert result.config_edits == ("ruff.toml",)
        assert not (tree / "ruff.toml").exists()

    def test_a_start_pyrightconfig_the_producer_edited_is_restored(self, tmp_path: Path) -> None:
        original = '{"typeCheckingMode": "strict"}\n'
        start, tree = make_case(
            tmp_path, {"pyproject.toml": START_PYPROJECT, "pyrightconfig.json": original}
        )
        (tree / "pyrightconfig.json").write_text('{"typeCheckingMode": "off"}\n', encoding="utf-8")
        result = restore_tool_config(tree, start)
        assert result.config_edits == ("pyrightconfig.json",)
        assert (tree / "pyrightconfig.json").read_text(encoding="utf-8") == original

    @pytest.mark.parametrize("name", ["setup.cfg", "tox.ini"])
    def test_a_pytest_config_the_producer_added_is_deleted_and_reported(
        self, tmp_path: Path, name: str
    ) -> None:
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        (tree / name).write_text("[pytest]\naddopts = -k nothing\n", encoding="utf-8")
        assert restore_tool_config(tree, start).config_edits == (name,)
        assert not (tree / name).exists()

    def test_a_squadron_config_the_producer_added_is_deleted_and_reported(self, tmp_path: Path) -> None:
        """The snapshot reads its exclusions from .squadron.toml; a producer must not set them."""
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        (tree / ".squadron.toml").write_text(
            '[metrology]\nsnapshot_exclusions = ["src/**"]\n', encoding="utf-8"
        )
        assert restore_tool_config(tree, start).config_edits == (".squadron.toml",)
        assert not (tree / ".squadron.toml").exists()

    def test_a_start_file_the_producer_deleted_is_restored_and_reported(self, tmp_path: Path) -> None:
        start, tree = make_case(
            tmp_path, {"pyproject.toml": START_PYPROJECT, "mypy.ini": "[mypy]\nstrict = True\n"}
        )
        (tree / "mypy.ini").unlink()
        assert restore_tool_config(tree, start).config_edits == ("mypy.ini",)
        assert (tree / "mypy.ini").read_text(encoding="utf-8") == "[mypy]\nstrict = True\n"

    def test_a_producer_deleted_pyproject_is_not_recreated_as_a_partial_file(
        self, tmp_path: Path
    ) -> None:
        reader, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        (tree / "pyproject.toml").unlink()
        result = restore_tool_config(tree, reader)
        assert result.config_edits == ()
        assert not (tree / "pyproject.toml").exists()
        assert deps_changed(tree, reader)

    def test_a_pyproject_with_no_tool_section_is_untouched(self, tmp_path: Path) -> None:
        text = '[project]\nname = "demo"\nversion = "0.1.0"\n# a comment\n'
        start, tree = make_case(tmp_path, {"pyproject.toml": text})
        assert restore_tool_config(tree, start).config_edits == ()
        assert (tree / "pyproject.toml").read_text(encoding="utf-8") == text

    def test_a_tool_table_the_producer_added_is_removed_and_reported(self, tmp_path: Path) -> None:
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        with (tree / "pyproject.toml").open("a", encoding="utf-8") as handle:
            handle.write("\n[tool.black]\nline-length = 300\n")
        assert restore_tool_config(tree, start).config_edits == ("tool.black",)
        assert "black" not in load(tree / "pyproject.toml")["tool"]

    def test_a_start_table_the_producer_deleted_is_restored_and_reported(self, tmp_path: Path) -> None:
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        (tree / "pyproject.toml").write_text(
            START_PYPROJECT.split("[tool.ruff]")[0] + '[tool.pyright]\ntypeCheckingMode = "strict"\n',
            encoding="utf-8",
        )
        assert restore_tool_config(tree, start).config_edits == ("tool.ruff",)
        assert load(tree / "pyproject.toml")["tool"]["ruff"] == {"line-length": 100}

    @pytest.mark.parametrize("table", PACKAGING_TOOL_TABLES)
    def test_every_packaging_table_follows_the_producer(self, tmp_path: Path, table: str) -> None:
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        with (tree / "pyproject.toml").open("a", encoding="utf-8") as handle:
            handle.write(f"\n[tool.{table}]\nproducer-key = true\n")
        result = restore_tool_config(tree, start)
        assert f"tool.{table}" not in result.config_edits
        assert load(tree / "pyproject.toml")["tool"][table] == {"producer-key": True}

    def test_the_rewritten_tree_still_passes_uv_lock_check(self, tmp_path: Path) -> None:
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        subprocess.run(["uv", "lock"], cwd=tree, check=True, capture_output=True)
        text = (tree / "pyproject.toml").read_text(encoding="utf-8")
        (tree / "pyproject.toml").write_text(
            text.replace("line-length = 100", "line-length = 300"), encoding="utf-8"
        )
        assert restore_tool_config(tree, start).config_edits == ("tool.ruff",)
        check = subprocess.run(["uv", "lock", "--check"], cwd=tree, capture_output=True, text=True)
        assert check.returncode == 0, check.stderr

    def test_a_producer_pyproject_that_is_not_utf8_raises_and_logs_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        reader, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        (tree / "pyproject.toml").write_bytes(b"[project]\nname = '\xff\xfe'\n")
        with caplog.at_level(logging.ERROR), pytest.raises(ProducerConfigError, match="UTF-8"):
            restore_tool_config(tree, reader)
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_a_malformed_producer_pyproject_raises_and_logs_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        (tree / "pyproject.toml").write_text("[project\nname = \n", encoding="utf-8")
        with caplog.at_level(logging.ERROR), pytest.raises(ProducerConfigError, match="pyproject.toml"):
            restore_tool_config(tree, start)
        assert any(r.levelno == logging.ERROR for r in caplog.records)


class TestDepsChanged:
    def test_variant_c_changed_dependencies(self, grading_repo: GradingRepo, variant_c: Path) -> None:
        assert deps_changed(variant_c, grading_repo.start)

    def test_an_unchanged_tree_is_not_changed(self, grading_repo: GradingRepo, tmp_path: Path) -> None:
        tree = checkout_tree(grading_repo, grading_repo.start_sha, tmp_path / "same")
        assert not deps_changed(tree, grading_repo.start)

    def test_a_change_only_in_a_tool_table_is_not_a_dependency_change(self, tmp_path: Path) -> None:
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        text = (tree / "pyproject.toml").read_text(encoding="utf-8")
        (tree / "pyproject.toml").write_text(
            text.replace("line-length = 100", "line-length = 300"), encoding="utf-8"
        )
        assert not deps_changed(tree, start)

    def test_a_comment_only_or_reformat_only_change_is_not_a_dependency_change(
        self, tmp_path: Path
    ) -> None:
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        reformatted = START_PYPROJECT.replace('name = "demo"', '# renamed? no\nname   =   "demo"')
        (tree / "pyproject.toml").write_text(reformatted + "\n\n", encoding="utf-8")
        assert not deps_changed(tree, start)

    def test_a_changed_lockfile_alone_is_a_dependency_change(self, tmp_path: Path) -> None:
        start, tree = make_case(
            tmp_path, {"pyproject.toml": START_PYPROJECT, "uv.lock": "version = 1\n"}
        )
        (tree / "uv.lock").write_text("version = 1\n# producer re-locked\n", encoding="utf-8")
        assert deps_changed(tree, start)

    def test_a_lockfile_the_producer_added_or_removed_is_a_dependency_change(
        self, tmp_path: Path
    ) -> None:
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        (tree / "uv.lock").write_text("version = 1\n", encoding="utf-8")
        assert deps_changed(tree, start)

    def test_a_malformed_producer_pyproject_raises_and_logs_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        start, tree = make_case(tmp_path, {"pyproject.toml": START_PYPROJECT})
        (tree / "pyproject.toml").write_text("[project\n", encoding="utf-8")
        with caplog.at_level(logging.ERROR), pytest.raises(ProducerConfigError):
            deps_changed(tree, start)
        assert any(r.levelno == logging.ERROR for r in caplog.records)
