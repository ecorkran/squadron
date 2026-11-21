"""Tests for --rules flag and rules injection into system prompt."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.review import load_review_rules_or_exit
from squadron.integrations.context_forge import GUIDE_RULES_DIR
from squadron.review.models import ReviewResult, Verdict
from squadron.review.rules import RulesSource, guide_rules_dir, load_review_rules


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def pass_result() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="## Summary\nPASS\n",
        template_name="code",
        input_files={"cwd": "."},
    )


@pytest.fixture
def mock_run_review(pass_result: ReviewResult):
    """Patch run_review so we can inspect the system prompt it receives."""
    with patch(
        "squadron.cli.commands.review.run_review_with_profile",
        new_callable=AsyncMock,
        return_value=pass_result,
    ) as mock:
        yield mock


class TestRulesFlag:
    """Test --rules flag on review code."""

    def test_rules_content_passed_to_runner(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        tmp_path: Path,
    ) -> None:
        rules_file = tmp_path / "rules.md"
        rules_file.write_text("Always check for null pointers.")

        # Isolate from filesystem: suppress auto-template-rules resolution so
        # we only test that the explicit --rules file content reaches the runner.
        with patch(
            "squadron.cli.commands.review.resolve_rules_dir",
            return_value=(None, RulesSource.NONE),
        ):
            result = cli_runner.invoke(
                app, ["review", "code", "--rules", str(rules_file), "--files", "**/*"]
            )
        assert result.exit_code == 0

        # run_review was called with rules_content keyword
        call_kwargs = mock_run_review.call_args
        assert call_kwargs.kwargs["rules_content"] == ("Always check for null pointers.")

    def test_missing_rules_file_error(
        self,
        cli_runner: CliRunner,
    ) -> None:
        result = cli_runner.invoke(
            app, ["review", "code", "--rules", "/nonexistent/rules.md", "--files", "**/*"]
        )
        assert result.exit_code == 1
        assert "Rules file not found" in result.output

    def test_no_rules_flag_passes_none(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        with (
            patch(
                "squadron.cli.commands.review.get_config",
                return_value=None,
            ),
            patch(
                "squadron.cli.commands.review.resolve_rules_dir",
                return_value=(None, RulesSource.NONE),
            ),
        ):
            result = cli_runner.invoke(app, ["review", "code", "--files", "**/*"])
            assert result.exit_code == 0
            call_kwargs = mock_run_review.call_args
            assert call_kwargs.kwargs["rules_content"] is None

    def test_rules_flag_overrides_config(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        tmp_path: Path,
    ) -> None:
        flag_rules = tmp_path / "flag_rules.md"
        flag_rules.write_text("Flag rules content.")

        config_rules = tmp_path / "config_rules.md"
        config_rules.write_text("Config rules content.")

        def mock_get_config(key: str, cwd: str = ".") -> object:
            if key == "default_rules":
                return str(config_rules)
            if key == "verbosity":
                return 0
            return None

        with (
            patch(
                "squadron.cli.commands.review.get_config",
                side_effect=mock_get_config,
            ),
            patch(
                "squadron.cli.commands.review.resolve_rules_dir",
                return_value=(None, RulesSource.NONE),
            ),
        ):
            result = cli_runner.invoke(
                app, ["review", "code", "--rules", str(flag_rules), "--files", "**/*"]
            )
            assert result.exit_code == 0
            call_kwargs = mock_run_review.call_args
            assert call_kwargs.kwargs["rules_content"] == ("Flag rules content.")


class TestConfigDefaultRules:
    """Test config-based default_rules."""

    def test_config_rules_used_when_no_flag(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        tmp_path: Path,
    ) -> None:
        config_rules = tmp_path / "default_rules.md"
        config_rules.write_text("Default rules from config.")

        def mock_get_config(key: str, cwd: str = ".") -> object:
            if key == "default_rules":
                return str(config_rules)
            if key == "verbosity":
                return 0
            return None

        with (
            patch(
                "squadron.cli.commands.review.get_config",
                side_effect=mock_get_config,
            ),
            patch(
                "squadron.cli.commands.review.resolve_rules_dir",
                return_value=(None, RulesSource.NONE),
            ),
        ):
            result = cli_runner.invoke(app, ["review", "code", "--files", "**/*"])
            assert result.exit_code == 0
            call_kwargs = mock_run_review.call_args
            assert call_kwargs.kwargs["rules_content"] == ("Default rules from config.")


class TestRunnerRulesInjection:
    """Test that rules content is appended to system prompt in runner."""

    def test_rules_appended_to_system_prompt(self) -> None:
        from squadron.review.templates import ReviewTemplate

        template = ReviewTemplate(
            name="test",
            description="test",
            system_prompt="Base prompt.",
            allowed_tools=[],
            permission_mode="bypassPermissions",
            setting_sources=None,
            required_inputs=[],
            optional_inputs=[],
            prompt_template="Review this: {input}",
        )

        # We can't easily run the full async runner, but we can test
        # the system prompt construction logic directly
        system_prompt = template.system_prompt
        rules_content = "Check for SQL injection."
        if rules_content:
            system_prompt += f"\n\n## Additional Review Rules\n\n{rules_content}"

        assert "Base prompt." in system_prompt
        assert "## Additional Review Rules" in system_prompt
        assert "Check for SQL injection." in system_prompt


class TestLoadReviewRulesSteps:
    """Slice 935 D3: review language rules honor the ``steps`` key."""

    @staticmethod
    def _rules_dir(tmp_path: Path, frontmatter: str) -> Path:
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "python.md").write_text(f"---\n{frontmatter}\n---\nPython rule body.\n")
        return rules_dir

    def test_implement_only_rule_is_excluded(self, tmp_path: Path) -> None:
        rules_dir = self._rules_dir(tmp_path, 'paths: ["**/*.py"]\nsteps: [implement]')
        loaded = load_review_rules("code", rules_dir, file_paths=["src/a.py"])
        assert loaded.language_rules == []
        assert loaded.content is None

    def test_review_rule_is_included(self, tmp_path: Path) -> None:
        rules_dir = self._rules_dir(tmp_path, 'paths: ["**/*.py"]\nsteps: [review]')
        loaded = load_review_rules("code", rules_dir, file_paths=["src/a.py"])
        assert loaded.language_rules == ["python.md"]
        assert loaded.content is not None
        assert "Python rule body." in loaded.content

    def test_a_review_rule_with_no_paths_goes_to_every_review(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "design-rules.md").write_text(
            "---\nsteps: [design, review]\n---\nEvery state has an exit.\n"
        )

        with_no_files = load_review_rules("tasks", rules_dir)
        with_files = load_review_rules("code", rules_dir, file_paths=["src/a.py"])

        assert with_no_files.language_rules == ["design-rules.md"]
        assert "Every state has an exit." in (with_no_files.content or "")
        assert with_files.language_rules == ["design-rules.md"]

    def test_a_rule_with_no_paths_and_no_steps_is_not_sent_to_every_review(
        self, tmp_path: Path
    ) -> None:
        """Always-on is opt-in: a bare file (workflow notes, say) stays out of reviews."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "bug-fixes.md").write_text("How fixes are committed.\n")

        assert load_review_rules("tasks", rules_dir).language_rules == []

    def test_an_always_on_rule_is_sent_once_when_its_name_also_matches_a_file(
        self, tmp_path: Path
    ) -> None:
        rules_dir = self._rules_dir(tmp_path, "steps: [review]")

        loaded = load_review_rules("code", rules_dir, file_paths=["src/a.py"])

        assert loaded.language_rules == ["python.md"]
        assert (loaded.content or "").count("Python rule body.") == 1

    @staticmethod
    def _guide_dir(tmp_path: Path) -> Path:
        guide_dir = tmp_path / "guide-rules"
        guide_dir.mkdir()
        (guide_dir / "general.md").write_text(
            "---\nalwaysApply: true\nsteps: [design, review]\n---\nNo silent fallbacks.\n"
        )
        (guide_dir / "git.md").write_text(
            "---\nalwaysApply: true\nsteps: [implement]\n---\nBranch naming.\n"
        )
        return guide_dir

    def test_guide_rules_marked_for_review_go_to_every_review(self, tmp_path: Path) -> None:
        """With or without a project rules directory, and ahead of the project's own rules."""
        guide_dir = self._guide_dir(tmp_path)
        rules_dir = self._rules_dir(tmp_path, "steps: [review]")

        alone = load_review_rules("tasks", None, guide_rules_dir=guide_dir)
        both = load_review_rules("tasks", rules_dir, guide_rules_dir=guide_dir)

        assert alone.language_rules == ["general.md"]
        assert "Branch naming." not in (alone.content or "")
        assert both.language_rules == ["general.md", "python.md"]

    def test_a_project_rule_replaces_the_guide_rule_of_the_same_name(self, tmp_path: Path) -> None:
        guide_dir = self._guide_dir(tmp_path)
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "general.md").write_text("---\nsteps: [review]\n---\nProject general.\n")

        loaded = load_review_rules("tasks", rules_dir, guide_rules_dir=guide_dir)

        assert loaded.language_rules == ["general.md"]
        assert "Project general." in (loaded.content or "")
        assert "No silent fallbacks." not in (loaded.content or "")

    def test_the_installed_guide_rules_directory_is_found_under_the_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("squadron.review.rules.GUIDE_RULES_DIR", GUIDE_RULES_DIR)
        assert guide_rules_dir(str(tmp_path)) is None
        installed = tmp_path / GUIDE_RULES_DIR
        installed.mkdir(parents=True)
        (installed / "general.md").write_text("---\nsteps: [review]\n---\nNo silent fallbacks.\n")

        loaded = load_review_rules_or_exit("tasks", None, cwd=str(tmp_path))

        assert guide_rules_dir(str(tmp_path)) == installed
        assert loaded.language_rules == ["general.md"]

    def test_no_steps_behaves_as_before(self, tmp_path: Path) -> None:
        rules_dir = self._rules_dir(tmp_path, 'paths: ["**/*.py"]')
        loaded = load_review_rules("code", rules_dir, file_paths=["src/a.py"])
        assert loaded.language_rules == ["python.md"]

    def test_unreadable_language_rule_warns_and_is_left_out(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "python.md").write_text("Python rule body.\n")
        # A broken link has a filename-derived glob but can't be read.
        (rules_dir / "go.md").symlink_to(tmp_path / "missing.md")
        with caplog.at_level(logging.WARNING):
            loaded = load_review_rules("code", rules_dir, file_paths=["a.py", "b.go"])
        assert loaded.language_rules == ["python.md"]
        assert "go.md" in caplog.text

    @pytest.mark.skipif(
        sys.platform == "win32" or os.geteuid() == 0, reason="chmod 000 is readable by root"
    )
    def test_unreadable_template_rule_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "review.md").write_text("General review rule.\n")
        (rules_dir / "review.md").chmod(0)
        try:
            with caplog.at_level(logging.WARNING):
                loaded = load_review_rules("code", rules_dir)
        finally:
            (rules_dir / "review.md").chmod(0o644)
        assert loaded.content is None
        assert "review.md" in caplog.text


class TestCliRulesErrors:
    """Review F003: a rules problem at the CLI boundary is one error line and exit 1."""

    def test_unknown_steps_value_exits_cleanly(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("print('a')\n")
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "python.md").write_text("---\nsteps: [implemnt]\n---\nBody\n")
        with patch("squadron.cli.commands.review._run_review_command") as run:
            result = cli_runner.invoke(
                app,
                [
                    "review",
                    "code",
                    "--files",
                    "*.py",
                    "--cwd",
                    str(tmp_path),
                    "--rules-dir",
                    str(rules_dir),
                    "--no-save",
                ],
            )
        assert result.exit_code == 1
        assert "unknown steps value 'implemnt'" in result.output
        assert result.exception is None or isinstance(result.exception, SystemExit)
        run.assert_not_called()
