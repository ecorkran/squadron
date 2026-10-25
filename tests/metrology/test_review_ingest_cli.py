"""``sq metrology ingest-reviews`` CLI tests (slice 402)."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.store import MetrologyStore

runner = CliRunner()

ConfigWriter = Callable[[Path, dict[str, object]], Path]
FIXTURES = Path(__file__).parent / "fixtures" / "review_ingest"
PROJECT = "github.com/manta/example-repo"
BAD_FILES = (
    "synthetic-malformed-frontmatter.code.md",
    "synthetic-missing-verdict.code.md",
    "synthetic-new-format-bad-category.code.md",
)


@pytest.fixture
def store_dir(tmp_path: Path) -> Iterator[Path]:
    directory = tmp_path / "cli-store"
    with patch(
        "squadron.cli.commands.metrology_review_ingest.resolve_store_dir", return_value=directory
    ):
        yield directory


@pytest.fixture
def project(tmp_path: Path, write_project_config: ConfigWriter) -> Path:
    """A project directory with a recorded identity and no git remote."""
    root = tmp_path / "project"
    root.mkdir()
    write_project_config(root, {"metrology.project_id": PROJECT})
    return root


@pytest.fixture
def reviews(tmp_path: Path) -> Path:
    target = tmp_path / "reviews"
    shutil.copytree(FIXTURES, target)
    return target


def invoke(project: Path, *paths: Path) -> tuple[int, str]:
    result = runner.invoke(
        app, ["metrology", "ingest-reviews", *map(str, paths), "--cwd", str(project)]
    )
    return result.exit_code, result.output


def record_files(store_dir: Path) -> list[Path]:
    return sorted(store_dir.glob("*.json")) if store_dir.exists() else []


def test_fixture_directory_prints_counts_and_exits_one_for_the_failed_files(
    project: Path, reviews: Path, store_dir: Path
) -> None:
    code, output = invoke(project, reviews)

    assert code == 1, output
    assert f"Ingested 5 code reviews into {store_dir} (0 replaced)" in output
    assert "Skipped: 1 not code reviews, 2 unknown verdict" in output
    assert "Failed: 3" in output
    for name in BAD_FILES:
        assert name in output
    assert len(record_files(store_dir)) == 5


def test_only_good_files_exit_zero_and_a_second_run_replaces(
    project: Path, reviews: Path, store_dir: Path
) -> None:
    for name in BAD_FILES:
        (reviews / name).unlink()

    first_code, _ = invoke(project, reviews)
    second_code, second_output = invoke(project, reviews)

    assert (first_code, second_code) == (0, 0)
    assert "(5 replaced)" in second_output
    assert len(record_files(store_dir)) == 5


def test_nonexistent_path_exits_one_and_writes_nothing(
    project: Path, tmp_path: Path, store_dir: Path
) -> None:
    code, output = invoke(project, tmp_path / "nope")

    assert code == 1
    assert "nope" in output
    assert record_files(store_dir) == []


def test_missing_default_reviews_directory_exits_one_naming_it(project: Path, store_dir: Path) -> None:
    code, output = invoke(project)

    assert code == 1
    assert "reviews directory" in output
    assert "doesn't exist" in output
    assert record_files(store_dir) == []


def test_empty_directory_ingests_zero_with_a_warning_and_exits_zero(
    project: Path, tmp_path: Path, store_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    with caplog.at_level(logging.WARNING):
        code, output = invoke(project, empty)

    assert code == 0
    assert "Ingested 0 code reviews" in output
    assert str(empty) in caplog.text


def test_store_write_error_prints_the_partial_count_and_exits_one(
    project: Path, reviews: Path, store_dir: Path
) -> None:
    real_write = MetrologyStore.write_code_review
    calls: list[str] = []

    def failing_second(self: MetrologyStore, record: object) -> str:
        calls.append("write")
        if len(calls) == 2:
            raise MetrologyStoreError("disk full")
        return real_write(self, record)  # pyright: ignore[reportArgumentType]

    with patch.object(MetrologyStore, "write_code_review", failing_second):
        code, output = invoke(project, reviews)

    assert code == 1
    assert "Ingested 1 code reviews" in output
    assert "disk full" in output


def test_identity_failure_exits_one_and_writes_nothing(
    tmp_path: Path, reviews: Path, store_dir: Path
) -> None:
    no_identity = tmp_path / "anonymous"
    no_identity.mkdir()

    code, output = invoke(no_identity, reviews)

    assert code == 1
    assert "project identity" in output
    assert record_files(store_dir) == []
