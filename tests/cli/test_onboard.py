"""Tests for the ``sq onboard`` report command (slice 440 T18/T19)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.integrations.cf_adoption import ContextForgeReportError
from squadron.integrations.context_forge import ContextForgeError, ContextForgeNotAvailable
from squadron.onboard.comprehension import ANALYSIS_DIR, COMPREHENSION_SUFFIX
from tests.onboard.fakes import FakeAdoptionClient

runner = CliRunner()


def _invoke(fake: FakeAdoptionClient, *args: str):  # noqa: ANN202 - click Result type
    return runner.invoke(app, ["onboard", *args], obj=fake)


def test_json_output_parses_and_matches_the_contract(tmp_path: Path) -> None:
    result = _invoke(FakeAdoptionClient(), "--path", str(tmp_path), "--json")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["root"] == str(tmp_path.resolve())
    assert data["outcome"] == "brownfield"
    assert data["next"]["step"] == "build-graph"
    assert set(data) == {
        "root",
        "outcome",
        "registered",
        "graph",
        "comprehension",
        "comprehension_older_than_graph",
        "concept",
        "surfaces",
        "notices",
        "next",
    }


def test_text_output_names_the_next_step(tmp_path: Path) -> None:
    result = _invoke(FakeAdoptionClient(), "--path", str(tmp_path))
    assert result.exit_code == 0
    assert "Next: build-graph" in result.stdout
    assert "Outcome: brownfield" in result.stdout


def test_a_handoff_names_where_to_go(tmp_path: Path) -> None:
    result = _invoke(FakeAdoptionClient("detect-greenfield"), "--path", str(tmp_path))
    assert result.exit_code == 0
    assert "Next: handoff" in result.stdout
    assert "cf-onboard" in result.stdout


@pytest.mark.parametrize(
    "error",
    [
        ContextForgeReportError("detect", "path-not-found", "no such directory"),
        ContextForgeError("cf detect: unsupported reportVersion 2"),
        ContextForgeError("cf detect: unknown outcome 'half-adopted'"),
        ContextForgeError("cf detect: timed out after 300s"),
        ContextForgeNotAvailable("'cf' (Context-Forge CLI) is not installed or not on PATH."),
    ],
    ids=["envelope", "version", "outcome", "timeout", "not-installed"],
)
def test_cf_errors_exit_1_with_one_stderr_line(tmp_path: Path, error: Exception) -> None:
    result = _invoke(FakeAdoptionClient(raises=error), "--path", str(tmp_path))
    assert result.exit_code == 1
    assert result.stderr.strip() == str(error)
    assert result.stdout == ""


def test_path_that_is_not_a_directory_exits_1_before_any_cf_call(tmp_path: Path) -> None:
    fake = FakeAdoptionClient()
    result = _invoke(fake, "--path", str(tmp_path / "missing"))
    assert result.exit_code == 1
    assert "not an existing directory" in result.stderr
    assert fake.calls == []


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {
        str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
    }


def test_report_writes_nothing(tmp_path: Path) -> None:
    (tmp_path / "src.py").write_text("print(1)\n")
    before = _snapshot(tmp_path)
    fake = FakeAdoptionClient(registered=False)

    result = _invoke(fake, "--path", str(tmp_path))

    assert result.exit_code == 0
    assert _snapshot(tmp_path) == before
    assert not (tmp_path / ".context-forge.toml").exists()
    assert set(fake.call_names) <= {"detect", "is_registered"}


def test_a_monorepo_subdirectory_is_the_root_for_every_call(tmp_path: Path) -> None:
    (tmp_path / ".context-forge.toml").write_text("")
    sub = tmp_path / "packages" / "app"
    doc = sub / ANALYSIS_DIR / f"940{COMPREHENSION_SUFFIX}"
    doc.parent.mkdir(parents=True)
    doc.write_text("doc")
    fake = FakeAdoptionClient()

    result = _invoke(fake, "--path", str(sub), "--json")

    assert result.exit_code == 0
    assert {args[0] for _, args in fake.calls} == {sub.resolve()}
    assert json.loads(result.stdout)["comprehension"] == f"{ANALYSIS_DIR}/940{COMPREHENSION_SUFFIX}"


def test_path_defaults_to_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    fake = FakeAdoptionClient()
    result = _invoke(fake, "--json")
    assert result.exit_code == 0
    assert json.loads(result.stdout)["root"] == os.path.realpath(tmp_path)
