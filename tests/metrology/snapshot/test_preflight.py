"""Config keys, preflight and integrity-check tests (slice 400, D9/D10)."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from squadron.config.keys import CONFIG_KEYS
from squadron.metrology.errors import SnapshotIntegrityError, SnapshotPreflightError
from squadron.metrology.snapshot import preflight as preflight_module
from squadron.metrology.snapshot.preflight import check_integrity, preflight
from tests.conftest import run_test_git
from tests.metrology.snapshot.conftest import SnapshotRepoFactory

ConfigWriter = Callable[[Path, dict[str, object]], Path]


@pytest.fixture
def repo(snapshot_git_repo: SnapshotRepoFactory) -> Path:
    return snapshot_git_repo({"src/a.py": "x = 1\n", ".gitignore": "ignored/\n"})


class TestPreflight:
    def test_clean_repo_passes_and_returns_head_sha(self, repo: Path) -> None:
        result = preflight(repo)

        assert result.head_sha == run_test_git(repo, "rev-parse", "HEAD").strip()
        assert result.limits.limits_declared is False
        assert result.project_exclusions == ()

    def test_non_repo_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(SnapshotPreflightError, match="not a git repository"):
            preflight(tmp_path)

    def test_a_subdirectory_of_a_repo_is_refused(self, repo: Path) -> None:
        with pytest.raises(SnapshotPreflightError, match="not its root"):
            preflight(repo / "src")

    def test_repo_without_commits_raises(self, tmp_path: Path) -> None:
        run_test_git(tmp_path, "init", "-q", "-b", "main")

        with pytest.raises(SnapshotPreflightError, match="no commits"):
            preflight(tmp_path)

    def test_modified_tracked_file_raises_naming_the_path(self, repo: Path) -> None:
        (repo / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")

        with pytest.raises(SnapshotPreflightError, match=r"src/a\.py"):
            preflight(repo)

    def test_untracked_file_raises_naming_the_path(self, repo: Path) -> None:
        (repo / "scratch.txt").write_text("x\n", encoding="utf-8")

        with pytest.raises(SnapshotPreflightError, match=r"scratch\.txt"):
            preflight(repo)

    def test_untracked_files_inside_a_new_directory_are_named(self, repo: Path) -> None:
        (repo / "newdir").mkdir()
        (repo / "newdir" / "b.py").write_text("y = 1\n", encoding="utf-8")

        with pytest.raises(SnapshotPreflightError, match=r"newdir/b\.py"):
            preflight(repo)

    def test_untracked_project_config_is_exempt(
        self, repo: Path, write_project_config: ConfigWriter
    ) -> None:
        write_project_config(repo, {"metrology.max_file_lines": 300})

        assert preflight(repo).limits.max_file_lines == 300

    def test_untracked_tool_config_still_fails(self, repo: Path) -> None:
        (repo / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")

        with pytest.raises(SnapshotPreflightError, match=r"ruff\.toml"):
            preflight(repo)

    def test_rename_does_not_hide_the_second_path(self, repo: Path) -> None:
        run_test_git(repo, "mv", "src/a.py", "src/b.py")

        with pytest.raises(SnapshotPreflightError, match=r"src/b\.py"):
            preflight(repo)


class TestLimitsAndConfig:
    def test_valid_limits_are_recorded(self, repo: Path, write_project_config: ConfigWriter) -> None:
        write_project_config(
            repo, {"metrology.max_file_lines": 300, "metrology.max_function_lines": 50}
        )

        limits = preflight(repo).limits

        assert (limits.max_file_lines, limits.max_function_lines) == (300, 50)
        assert limits.limits_declared is True

    def test_one_limit_declared_leaves_the_other_none(
        self, repo: Path, write_project_config: ConfigWriter
    ) -> None:
        write_project_config(repo, {"metrology.max_function_lines": 50})

        limits = preflight(repo).limits

        assert limits.max_file_lines is None
        assert limits.max_function_lines == 50
        assert limits.limits_declared is True

    @pytest.mark.parametrize("bad", [0, -1, "many", 3.5, True])
    def test_bad_limit_raises(
        self, repo: Path, write_project_config: ConfigWriter, bad: object
    ) -> None:
        write_project_config(repo, {"metrology.max_file_lines": bad})

        with pytest.raises(SnapshotPreflightError, match=r"metrology\.max_file_lines"):
            preflight(repo)

    def test_exclusions_are_split_stripped_and_empties_skipped(
        self, repo: Path, write_project_config: ConfigWriter
    ) -> None:
        write_project_config(repo, {"metrology.snapshot_exclude": "a/**, ,b/**"})

        assert preflight(repo).project_exclusions == ("a/**", "b/**")

    def test_bad_timeout_raises(self, repo: Path, write_project_config: ConfigWriter) -> None:
        write_project_config(repo, {"metrology.snapshot_tool_timeout_s": 0})

        with pytest.raises(SnapshotPreflightError, match="snapshot_tool_timeout_s"):
            preflight(repo)

    def test_config_comes_from_the_measured_repo_not_the_process_cwd(
        self,
        repo: Path,
        tmp_path: Path,
        write_project_config: ConfigWriter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        write_project_config(repo, {"metrology.max_file_lines": 123})
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        write_project_config(elsewhere, {"metrology.max_file_lines": 999})
        monkeypatch.chdir(elsewhere)

        assert preflight(repo).limits.max_file_lines == 123

    def test_new_config_keys_have_declared_types_and_defaults(self) -> None:
        expected = {
            "metrology.max_file_lines": (int, None),
            "metrology.max_function_lines": (int, None),
            "metrology.snapshot_exclude": (str, None),
            "metrology.snapshot_tool_timeout_s": (int, 600),
        }
        for name, (type_, default) in expected.items():
            assert CONFIG_KEYS[name].type_ is type_
            assert CONFIG_KEYS[name].default == default


class TestIntegrity:
    def test_clean_tree_passes(self, repo: Path) -> None:
        check_integrity(repo)

    def test_modified_tracked_file_raises(self, repo: Path) -> None:
        (repo / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")

        with pytest.raises(SnapshotIntegrityError, match=r"src/a\.py"):
            check_integrity(repo)

    def test_new_untracked_file_raises(self, repo: Path) -> None:
        (repo / "created_by_tool.txt").write_text("x\n", encoding="utf-8")

        with pytest.raises(SnapshotIntegrityError, match=r"created_by_tool\.txt"):
            check_integrity(repo)

    def test_ignored_path_passes(self, repo: Path) -> None:
        (repo / "ignored").mkdir()
        (repo / "ignored" / "cache.bin").write_text("x\n", encoding="utf-8")

        check_integrity(repo)

    def test_exempt_project_config_passes(self, repo: Path, write_project_config: ConfigWriter) -> None:
        write_project_config(repo, {"metrology.max_file_lines": 300})

        check_integrity(repo)


class TestGitCannotAnswer:
    @staticmethod
    def _unanswerable(monkeypatch: pytest.MonkeyPatch) -> None:
        def run_git(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
            return None

        monkeypatch.setattr(preflight_module, "run_git", run_git)

    @staticmethod
    def _refusing(monkeypatch: pytest.MonkeyPatch) -> None:
        refused = subprocess.CompletedProcess(args=["git"], returncode=128, stdout="", stderr="")
        real_run_git = preflight_module.run_git

        def run_git(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
            if args[0] == "status":
                return refused
            return real_run_git(args, cwd=cwd)

        monkeypatch.setattr(preflight_module, "run_git", run_git)

    def test_preflight_raises_and_logs_error_when_git_returns_none(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        self._unanswerable(monkeypatch)

        with caplog.at_level(logging.ERROR), pytest.raises(SnapshotPreflightError):
            preflight(repo)

        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_integrity_raises_and_logs_error_when_git_returns_none(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        self._unanswerable(monkeypatch)

        with caplog.at_level(logging.ERROR), pytest.raises(SnapshotIntegrityError):
            check_integrity(repo)

        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_failing_status_is_never_a_clean_tree(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        self._refusing(monkeypatch)

        with caplog.at_level(logging.ERROR), pytest.raises(SnapshotPreflightError, match="status"):
            preflight(repo)
        with pytest.raises(SnapshotIntegrityError, match="status"):
            check_integrity(repo)

        assert any(r.levelno == logging.ERROR for r in caplog.records)
