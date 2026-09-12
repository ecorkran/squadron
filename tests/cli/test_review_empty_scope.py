"""Empty-scope refusal at both entry points (slice 916 Part B, issue #62).

A review whose filtered scope contains no files produces findings *about the
missing diff*, which are then persisted as a genuine verdict and clear review
gates. Both the CLI and the pipeline must refuse pre-flight, before any model
call, with the two empty cases distinguishable by structured field.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.models import ActionContext
from squadron.review.git_utils import EmptyScopeCase, EmptyScopeError
from squadron.review.models import ReviewResult, Verdict

_PIPELINE = "squadron.pipeline.actions.review"


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", message],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def md_only_repo(tmp_path: Path) -> Path:
    """A feature branch whose only change is markdown — the all-excluded case."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text("x = 1\n")
    _commit(repo, "init")
    subprocess.run(["git", "checkout", "-qb", "feature"], cwd=repo, check=True, capture_output=True)
    (repo / "notes.md").write_text("# notes\n")
    _commit(repo, "docs only")
    return repo


@pytest.fixture
def unchanged_repo(tmp_path: Path) -> Path:
    """A branch identical to its base — the no-changes case."""
    repo = tmp_path / "unchanged-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text("x = 1\n")
    _commit(repo, "init")
    return repo


@pytest.fixture
def healthy_repo(tmp_path: Path) -> Path:
    """A feature branch with a real code change — a scope the guard permits."""
    repo = tmp_path / "healthy-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text("x = 1\n")
    _commit(repo, "init")
    subprocess.run(["git", "checkout", "-qb", "feature"], cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text("x = 2\n")
    _commit(repo, "feature work")
    return repo


@pytest.fixture
def mock_run_review():
    result = ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="PASS",
        template_name="code",
        input_files={"cwd": "."},
    )
    with patch(
        "squadron.cli.commands.review.run_review_with_profile",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock:
        yield mock


def _config_reader(cwd_value: str):
    def mock_get_config(key: str, cwd: str = ".") -> object:
        if key == "cwd":
            return cwd_value
        if key == "verbosity":
            return 0
        return None

    return mock_get_config


class TestCLIRefusesEmptyScope:
    def test_all_excluded_exits_nonzero_and_writes_nothing(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        md_only_repo: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        reviews_dir = md_only_repo / "project-documents" / "user" / "reviews"
        reviews_dir.mkdir(parents=True)

        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=_config_reader(str(md_only_repo)),
        ):
            with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
                result = cli_runner.invoke(app, ["review", "code", "--diff", "main"])

        assert result.exit_code != 0
        mock_run_review.assert_not_called()
        assert list(reviews_dir.iterdir()) == []
        assert [r for r in caplog.records if r.levelname == "WARNING"]

    def test_no_changes_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        unchanged_repo: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=_config_reader(str(unchanged_repo)),
        ):
            with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
                result = cli_runner.invoke(app, ["review", "code", "--diff", "main"])

        assert result.exit_code != 0
        mock_run_review.assert_not_called()
        assert [r for r in caplog.records if r.levelname == "WARNING"]

    def test_two_cases_are_distinguishable_by_field(
        self, md_only_repo: Path, unchanged_repo: Path
    ) -> None:
        """Not by message text — conflating them is how #71 stayed unexplained."""
        from squadron.review.git_utils import assert_reviewable_scope

        with pytest.raises(EmptyScopeError) as excluded:
            assert_reviewable_scope("main...HEAD", str(md_only_repo), ["*.md"])
        with pytest.raises(EmptyScopeError) as empty:
            assert_reviewable_scope("main...HEAD", str(unchanged_repo), ["*.md"])

        assert excluded.value.case == EmptyScopeCase.ALL_EXCLUDED
        assert empty.value.case == EmptyScopeCase.NO_CHANGES
        assert excluded.value.case != empty.value.case

    def test_refusal_fires_with_no_rules_directory(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        md_only_repo: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The most important test in this part.

        Both existing ``extract_diff_paths`` call sites are nested under a
        rules-directory check. A guard hung off either would silently not run
        whenever no rules directory resolves — shipping the exact defect the
        guard exists to remove.
        """
        with (
            patch(
                "squadron.cli.commands.review.get_config",
                side_effect=_config_reader(str(md_only_repo)),
            ),
            patch("squadron.cli.commands.review.resolve_rules_dir", return_value=None),
        ):
            with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
                result = cli_runner.invoke(app, ["review", "code", "--diff", "main"])

        assert result.exit_code != 0
        mock_run_review.assert_not_called()
        assert [r for r in caplog.records if r.levelname == "WARNING"]


def _pipeline_context(cwd: str) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-4-20250514", None)
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-12345678",
        params={"template": "code", "diff": "main...HEAD", "diff_exclude_patterns": "*.md"},
        step_name="code-review",
        step_index=1,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd=cwd,
    )


class TestPipelineRefusesEmptyScope:
    """`sq run` is the path that clears review gates — the harm B exists to fix."""

    @pytest.mark.asyncio
    async def test_all_excluded_fails_the_step(
        self, md_only_repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with patch(f"{_PIPELINE}.run_review_with_profile") as mock_review:
            with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
                result = await ReviewAction().execute(_pipeline_context(str(md_only_repo)))

        assert result.success is False
        mock_review.assert_not_called()
        assert [r for r in caplog.records if r.levelname == "WARNING"]

    @pytest.mark.asyncio
    async def test_no_changes_fails_the_step(
        self, unchanged_repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with patch(f"{_PIPELINE}.run_review_with_profile") as mock_review:
            with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
                result = await ReviewAction().execute(_pipeline_context(str(unchanged_repo)))

        assert result.success is False
        mock_review.assert_not_called()
        assert [r for r in caplog.records if r.levelname == "WARNING"]

    @pytest.mark.asyncio
    async def test_refusal_fires_with_no_rules_directory(
        self, md_only_repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with (
            patch(f"{_PIPELINE}.resolve_rules_dir", return_value=None),
            patch(f"{_PIPELINE}.run_review_with_profile") as mock_review,
        ):
            with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
                result = await ReviewAction().execute(_pipeline_context(str(md_only_repo)))

        assert result.success is False
        mock_review.assert_not_called()
        assert [r for r in caplog.records if r.levelname == "WARNING"]


class TestPipelineNormalizesDiff:
    """The pipeline normalizes a step-supplied bare ref, exactly as the CLI does.

    Interface parity: `sq run` is the less-watched entry point, so an
    un-normalized range here is the harder bug to notice (issue #89).
    """

    @pytest.mark.asyncio
    async def test_bare_ref_is_normalized(self, healthy_repo: Path) -> None:
        repo = healthy_repo
        resolver = MagicMock()
        resolver.resolve.return_value = ("claude-sonnet-4-20250514", None)
        ctx = ActionContext(
            pipeline_name="p",
            run_id="run-1",
            params={"template": "code", "diff": "main"},
            step_name="code-review",
            step_index=1,
            prior_outputs={},
            resolver=resolver,
            cf_client=MagicMock(),
            cwd=str(repo),
        )

        with (
            patch(f"{_PIPELINE}.run_review_with_profile") as mock_review,
            patch(f"{_PIPELINE}.save_review_file", return_value=None),
            patch(f"{_PIPELINE}.format_review_markdown", return_value="# Review"),
        ):
            mock_review.return_value = ReviewResult(
                verdict=Verdict.PASS,
                findings=[],
                raw_output="PASS",
                template_name="code",
                input_files={"cwd": str(repo)},
            )
            await ReviewAction().execute(ctx)

        assert mock_review.called, "the review should have run on a healthy scope"
        call_inputs = mock_review.call_args[0][1]
        assert call_inputs["diff"] == "main...HEAD"


class TestPipelineExplicitDiffWins:
    """A step-supplied `diff` survives slice resolution, as the CLI's --diff does.

    `sq review code 118 --diff main` keeps the explicit range; a pipeline step
    carrying both `slice` and `diff` must mean the same thing (issue #89 parity).
    """

    @pytest.mark.asyncio
    async def test_step_diff_is_not_overwritten_by_slice_range(self, healthy_repo: Path) -> None:
        resolver = MagicMock()
        resolver.resolve.return_value = ("claude-sonnet-4-20250514", None)
        ctx = ActionContext(
            pipeline_name="p",
            run_id="run-1",
            params={"template": "code", "slice": 916, "diff": "main"},
            step_name="code-review",
            step_index=1,
            prior_outputs={},
            resolver=resolver,
            cf_client=MagicMock(),
            cwd=str(healthy_repo),
        )

        slice_info = {
            "index": 916,
            "name": "probe",
            "slice_name": "probe",
            "design_file": None,
            "task_files": [],
            "arch_file": None,
            "project": "squadron",
        }

        with (
            patch(f"{_PIPELINE}.run_review_with_profile") as mock_review,
            patch(f"{_PIPELINE}.save_review_file", return_value=None),
            patch(f"{_PIPELINE}.format_review_markdown", return_value="# Review"),
            patch(f"{_PIPELINE}.resolve_slice_info", return_value=slice_info),
            # Would otherwise replace the step's value with a slice-derived range.
            patch(
                "squadron.review.template_inputs.resolve_slice_diff_range",
                return_value="deadbeef...HEAD",
            ),
        ):
            mock_review.return_value = ReviewResult(
                verdict=Verdict.PASS,
                findings=[],
                raw_output="PASS",
                template_name="code",
                input_files={"cwd": str(healthy_repo)},
            )
            await ReviewAction().execute(ctx)

        assert mock_review.called
        call_inputs = mock_review.call_args[0][1]
        assert call_inputs["diff"] == "main...HEAD"
