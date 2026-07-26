"""CLI tests: recommend/graduate/offers, --json, refusal, idempotence,
no-mutation, and surface-agnostic-core parity (T16/T17)."""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.calibration_models import RecommendationReport
from squadron.metrology.store import MetrologyStore
from squadron.review.templates import ReviewTemplate, clear_registry, register_template

runner = CliRunner()

_TEMPLATE_NAME = "judge.slice-vs-arch"
_MODEL = "minimax/minimax-m2.7"
_LEVEL = "slice_design_vs_arch"


def _normalized(output: str) -> str:
    return " ".join(output.split())


@pytest.fixture
def cli_store(tmp_path: Path) -> Iterator[Path]:
    store_dir = tmp_path / "cli-store"
    with patch("squadron.cli.commands.metrology.resolve_store_dir", return_value=store_dir):
        yield store_dir


@pytest.fixture(autouse=True)
def _clear_template_registry() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    # These tests fully control the template registry via register_template
    # below, and use "judge.slice-vs-arch" — a name that collides with a
    # real built-in template. The CLI commands under test call
    # load_all_templates() (so real invocations resolve templates without
    # a prior `sq review` call in the same process); patch it to a no-op
    # here so that call doesn't clobber this test's own fake registration
    # with the real built-in's different system_prompt/judge block.
    clear_registry()
    with patch("squadron.cli.commands.metrology.load_all_templates"):
        yield
    clear_registry()


def _register_judge_template(*, system_prompt: str = "You are a judge.") -> None:
    register_template(
        ReviewTemplate(
            name=_TEMPLATE_NAME,
            description="Example",
            system_prompt=system_prompt,
            allowed_tools=[],
            permission_mode="default",
            setting_sources=None,
            required_inputs=[],
            optional_inputs=[],
            model=_MODEL,
            prompt_template="Judge this: {input}",
            judge={"pass_floor": 78, "concerns_floor": 55},
        )
    )


@pytest.fixture
def project_repo(
    repo_no_remote: Path,
    write_project_config: Callable[[Path, dict[str, object]], Path],
) -> Path:
    write_project_config(repo_no_remote, {"metrology.project_id": "acme/widget"})
    return repo_no_remote


def _write_judge_review(write_review_file: Callable[..., Path], reviews_dir: Path, index: int) -> Path:
    return write_review_file(
        reviews_dir,
        filename=f"{index}-review.judge.slice-vs-arch.example.md",
        review_type=_TEMPLATE_NAME,
    )


def _capture(project_repo: Path, review_index: int, verdict: str = "PASS") -> None:
    with patch("squadron.cli.commands.metrology._sample_budget", return_value=100):
        result = runner.invoke(
            app,
            [
                "metrology",
                "sample",
                str(review_index),
                "--type",
                _TEMPLATE_NAME,
                "--verdict",
                verdict,
                "--cwd",
                str(project_repo),
            ],
        )
    assert result.exit_code == 0, result.output


def _capture_evidence(
    project_repo: Path,
    write_review_file: Callable[..., Path],
    cli_store: Path,
    *,
    n: int,
    verdict: str = "PASS",
) -> None:
    """Write n judge reviews and blind-capture a matching verdict for each."""
    reviews_dir = project_repo / "project-documents/user/reviews"
    for i in range(n):
        _write_judge_review(write_review_file, reviews_dir, 500 + i)
        _capture(project_repo, 500 + i, verdict=verdict)


class TestRecommend:
    def test_prints_rows_with_n_floor_and_model_dimension_note(
        self, project_repo: Path, write_review_file: Callable[..., Path], cli_store: Path
    ) -> None:
        _register_judge_template()
        _capture_evidence(project_repo, write_review_file, cli_store, n=6, verdict="PASS")

        result = runner.invoke(app, ["metrology", "recommend", "--cwd", str(project_repo)])
        assert result.exit_code == 0, result.output
        normalized = _normalized(result.output)
        assert "n=6" in normalized
        assert "floor=" in normalized
        assert "paired with" in normalized  # model_dimension_note text

    def test_json_parses_back_to_recommendation_report(
        self, project_repo: Path, write_review_file: Callable[..., Path], cli_store: Path
    ) -> None:
        _register_judge_template()
        _capture_evidence(project_repo, write_review_file, cli_store, n=6, verdict="PASS")

        result = runner.invoke(app, ["metrology", "recommend", "--cwd", str(project_repo), "--json"])
        assert result.exit_code == 0, result.output
        parsed = RecommendationReport.model_validate(json.loads(result.output))
        assert len(parsed.cells) == 1
        assert parsed.cells[0].evidence.n == 6


class TestGraduateRefusal:
    def test_below_floor_pairing_refuses_and_writes_nothing(
        self, project_repo: Path, write_review_file: Callable[..., Path], cli_store: Path
    ) -> None:
        _register_judge_template()
        # n=1 is below the default floor (5) — cannot GRADUATE.
        _capture_evidence(project_repo, write_review_file, cli_store, n=1, verdict="PASS")
        record_count_before = len(list(cli_store.glob("*.json")))

        result = runner.invoke(
            app,
            [
                "metrology",
                "graduate",
                "--template",
                _TEMPLATE_NAME,
                "--model",
                _MODEL,
                "--level",
                _LEVEL,
                "--cwd",
                str(project_repo),
            ],
        )
        assert result.exit_code != 0
        assert "n=" in result.output and "floor=" in result.output
        assert len(list(cli_store.glob("*.json"))) == record_count_before


class TestGraduateCellDisambiguation:
    def test_stale_prompt_evidence_is_not_graduated_over_current_evidence(
        self, project_repo: Path, write_review_file: Callable[..., Path], cli_store: Path
    ) -> None:
        # Two cells can share (template_name, model, level) while differing
        # in template_content_hash: evidence from before a prompt edit,
        # alongside fresh evidence captured after. graduate must act on the
        # template as currently configured, never on stale evidence — even
        # if the stale cell happens to qualify for GRADUATE too.
        _register_judge_template(system_prompt="Original prompt.")
        _capture_evidence(project_repo, write_review_file, cli_store, n=6, verdict="PASS")

        clear_registry()
        _register_judge_template(system_prompt="Rewritten prompt.")
        reviews_dir = project_repo / "project-documents/user/reviews"
        for i in range(6):
            _write_judge_review(write_review_file, reviews_dir, 700 + i)
            _capture(project_repo, 700 + i, verdict="PASS")

        result = runner.invoke(
            app,
            [
                "metrology",
                "graduate",
                "--template",
                _TEMPLATE_NAME,
                "--model",
                _MODEL,
                "--level",
                _LEVEL,
                "--cwd",
                str(project_repo),
            ],
        )
        assert result.exit_code == 0, result.output

        store = MetrologyStore(store_dir=cli_store)
        graduations = store.list_graduations()
        assert len(graduations) == 1
        graduated_hash = graduations[0][1].judge_config.template_content_hash

        # The graduated identity must be the *current* (rewritten-prompt)
        # instrument's hash, not the stale original.
        from squadron.metrology.calibration import read_current_template_content_hash

        assert graduated_hash == read_current_template_content_hash(_TEMPLATE_NAME)


class TestGraduateSuccessAndIdempotence:
    def test_graduate_meeting_threshold_writes_exactly_one_record(
        self, project_repo: Path, write_review_file: Callable[..., Path], cli_store: Path
    ) -> None:
        _register_judge_template()
        _capture_evidence(project_repo, write_review_file, cli_store, n=6, verdict="PASS")

        result = runner.invoke(
            app,
            [
                "metrology",
                "graduate",
                "--template",
                _TEMPLATE_NAME,
                "--model",
                _MODEL,
                "--level",
                _LEVEL,
                "--cwd",
                str(project_repo),
            ],
        )
        assert result.exit_code == 0, result.output

        store = MetrologyStore(store_dir=cli_store)
        graduations = store.list_graduations()
        assert len(graduations) == 1

    def test_re_graduate_updates_in_place_not_duplicate(
        self, project_repo: Path, write_review_file: Callable[..., Path], cli_store: Path
    ) -> None:
        _register_judge_template()
        _capture_evidence(project_repo, write_review_file, cli_store, n=6, verdict="PASS")

        graduate_args = [
            "metrology",
            "graduate",
            "--template",
            _TEMPLATE_NAME,
            "--model",
            _MODEL,
            "--level",
            _LEVEL,
            "--cwd",
            str(project_repo),
        ]
        first = runner.invoke(app, graduate_args)
        assert first.exit_code == 0, first.output
        second = runner.invoke(app, graduate_args)
        assert second.exit_code == 0, second.output

        store = MetrologyStore(store_dir=cli_store)
        assert len(store.list_graduations()) == 1


class TestOffers:
    def test_graduated_config_with_unsampled_match_lists_an_offer(
        self,
        project_repo: Path,
        write_review_file: Callable[..., Path],
        cli_store: Path,
        write_project_config: Callable[[Path, dict[str, object]], Path],
    ) -> None:
        _register_judge_template()
        _capture_evidence(project_repo, write_review_file, cli_store, n=6, verdict="PASS")
        runner.invoke(
            app,
            [
                "metrology",
                "graduate",
                "--template",
                _TEMPLATE_NAME,
                "--model",
                _MODEL,
                "--level",
                _LEVEL,
                "--cwd",
                str(project_repo),
            ],
        )

        # rate=1.0 so a single unsampled match reliably yields an offer
        # (the default 0.1 rate rounds a single match down to zero).
        write_project_config(project_repo, {"metrology.residual_sample_rate": 1.0})

        # Add one more unsampled judge review after graduation.
        reviews_dir = project_repo / "project-documents/user/reviews"
        _write_judge_review(write_review_file, reviews_dir, 999)

        result = runner.invoke(app, ["metrology", "offers", "--cwd", str(project_repo)])
        assert result.exit_code == 0, result.output
        assert "offer:" in result.output

    def test_lapsed_graduation_prints_explanatory_line_and_zero_offers(
        self, project_repo: Path, write_review_file: Callable[..., Path], cli_store: Path
    ) -> None:
        _register_judge_template(system_prompt="Original prompt.")
        _capture_evidence(project_repo, write_review_file, cli_store, n=6, verdict="PASS")
        runner.invoke(
            app,
            [
                "metrology",
                "graduate",
                "--template",
                _TEMPLATE_NAME,
                "--model",
                _MODEL,
                "--level",
                _LEVEL,
                "--cwd",
                str(project_repo),
            ],
        )

        # Edit the template (a real instrument change) — the graduation lapses.
        clear_registry()
        _register_judge_template(system_prompt="Rewritten prompt.")

        result = runner.invoke(app, ["metrology", "offers", "--cwd", str(project_repo)])
        assert result.exit_code == 0, result.output
        assert "lapsed" in result.output.lower()
        assert "offer:" not in result.output


class TestNoMutationAtCliLayer:
    def test_recommend_leaves_template_config_and_store_byte_identical(
        self, project_repo: Path, write_review_file: Callable[..., Path], cli_store: Path
    ) -> None:
        _register_judge_template()
        _capture_evidence(project_repo, write_review_file, cli_store, n=6, verdict="PASS")

        template_yaml = project_repo / "template.yaml"
        template_yaml.write_text("name: judge.slice-vs-arch\npass_floor: 78\n", encoding="utf-8")
        squadron_toml = project_repo / ".squadron.toml"

        def _hashes() -> dict[str, str]:
            paths = [template_yaml, squadron_toml, *sorted(cli_store.glob("*.json"))]
            return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}

        before = _hashes()
        result = runner.invoke(app, ["metrology", "recommend", "--cwd", str(project_repo)])
        assert result.exit_code == 0, result.output
        after = _hashes()
        assert before == after


class TestSurfaceAgnosticCore:
    def test_calibration_core_modules_import_no_typer(self) -> None:
        for module_path in (
            "src/squadron/metrology/calibration.py",
            "src/squadron/metrology/graduation.py",
            "src/squadron/metrology/calibration_models.py",
        ):
            source = Path(module_path).read_text(encoding="utf-8")
            tree = ast.parse(source)
            imported_modules: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module)
            assert not any("typer" in module for module in imported_modules), module_path
