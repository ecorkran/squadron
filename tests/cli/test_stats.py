"""Tests for ``sq stats run`` and ``sq stats reviews`` (slice 175 D8, criterion 8)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.models.aliases import ModelAlias
from squadron.pipeline.state import StateManager
from squadron.providers.base import USAGE_KEY

runner = CliRunner()
_RUN = "run-20261014-p4-ab12cd34"
_ALIASES: dict[str, ModelAlias] = {
    "opus": {"profile": "sdk", "model": "claude-opus", "cost_tier": "subscription"},
    "glm": {"profile": "openrouter", "model": "z/glm"},
}


def _record(
    alias: str, basis: CostBasis | None, *, cost: float | None, partial: bool = False
) -> dict[str, object]:
    return UsageRecord(
        model="m",
        alias=alias,
        profile="sdk",
        effort="high",
        turns=41,
        duration_seconds=580.0,
        usage=TokenUsage(prompt=3_120_000, cached=2_980_000, cache_write=96_100, completion=18_400),
        cost_usd=cost,
        cost_basis=basis,
        partial=partial,
    ).to_dict()


def _action(action_type: str, usage: dict[str, object] | None = None) -> dict[str, object]:
    metadata: dict[str, object] = {} if usage is None else {USAGE_KEY: usage}
    return {"success": True, "action_type": action_type, "outputs": {}, "metadata": metadata}


@pytest.fixture
def runs_dir(tmp_path: Path):  # noqa: ANN201
    runs = tmp_path / "runs"
    runs.mkdir()
    steps = [
        (
            "design",
            [_action("cf-op"), _action("dispatch", _record("opus", CostBasis.PROVIDER, cost=2.07))],
        ),
        (
            "design-rev",
            [_action("review", _record("glm", CostBasis.ALIAS_PRICING, cost=0.03, partial=True))],
        ),
        ("tasks", [_action("dispatch")]),
    ]
    state = {
        "schema_version": 5,
        "run_id": _RUN,
        "pipeline": "p456",
        "params": {"slice": "175"},
        "started_at": "2026-10-14T10:00:00+00:00",
        "updated_at": "2026-10-14T10:38:12+00:00",
        "status": "completed",
        "completed_steps": [
            {
                "step_name": name,
                "step_type": "phase",
                "status": "completed",
                "completed_at": "2026-10-14T10:10:00+00:00",
                "action_results": actions,
            }
            for name, actions in steps
        ],
    }
    (runs / f"{_RUN}.json").write_text(json.dumps(state))
    with (
        patch("squadron.cli.commands.stats.StateManager", lambda: StateManager(runs_dir=runs)),
        patch("squadron.cli.stats_views.get_all_aliases", return_value=_ALIASES),
    ):
        yield runs


def test_run_table(runs_dir: Path) -> None:
    result = runner.invoke(app, ["stats", "run", _RUN])

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0] == f"Run {_RUN}  p456  slice=175  completed  38m12s"
    design = next(line for line in lines if "dispatch" in line and "opus" in line)
    for cell in (
        "opus / high",
        "41",
        "3.12M",
        "2.98M",
        "96.1k",
        "18.4k",
        "$2.07 api-rate equiv.",
        "9m40s",
    ):
        assert cell in design
    review = next(line for line in lines if "design-rev*" in line)
    assert "$0.03 alias" in review
    total = next(line for line in lines if line.strip().startswith("Total"))
    assert "$2.10 (2 of 3 priced)" in total
    assert "1 LLM action(s) have no usage recorded." in lines
    assert "* partial: an interrupted turn's spend is not recorded" in lines


def test_run_json_matches_table_rows(runs_dir: Path) -> None:
    result = runner.invoke(app, ["stats", "run", _RUN, "--json"])

    payload = json.loads(result.output)
    assert [(row["step"], row["action"]) for row in payload["rows"]] == [
        ("design", "cf-op"),
        ("design", "dispatch"),
        ("design-rev", "review"),
        ("tasks", "dispatch"),
    ]
    assert payload["rows"][1]["usage"]["cost_usd"] == 2.07
    assert payload["totals"]["priced"] == 2
    assert payload["totals"]["cost_usd"] == pytest.approx(2.10)
    assert (payload["llm_actions"], payload["unrecorded"]) == (3, 1)


def test_pre_slice_run_shows_dashes_and_unrecorded_line(runs_dir: Path) -> None:
    state = json.loads((runs_dir / f"{_RUN}.json").read_text())
    state["run_id"] = "run-old"
    state["completed_steps"] = [state["completed_steps"][2]]
    (runs_dir / "run-old.json").write_text(json.dumps(state))

    result = runner.invoke(app, ["stats", "run", "run-old"])

    assert result.exit_code == 0
    row = next(line for line in result.output.splitlines() if line.strip().startswith("tasks"))
    assert "—" in row
    assert "1 LLM action(s) have no usage recorded." in result.output


def test_loop_run_shows_rounds_and_partial_loop_note(runs_dir: Path) -> None:
    state = json.loads((runs_dir / f"{_RUN}.json").read_text())
    loop_step = {
        "step_name": "rounds",
        "step_type": "loop",
        "status": "failed",
        "completed_at": "2026-10-14T10:20:00+00:00",
        "iteration": 2,
        "prior_round_results": [
            [_action("review", _record("glm", CostBasis.ALIAS_PRICING, cost=0.03))]
        ],
        "action_results": [_action("review", _record("glm", CostBasis.ALIAS_PRICING, cost=0.04))],
    }
    state.update(run_id="run-loop", status="failed", current_step="rounds")
    state["completed_steps"] = [loop_step]
    (runs_dir / "run-loop.json").write_text(json.dumps(state))

    table = runner.invoke(app, ["stats", "run", "run-loop"])
    payload = json.loads(runner.invoke(app, ["stats", "run", "run-loop", "--json"]).output)

    assert table.exit_code == 0
    assert "rounds r1" in table.output and "rounds r2" in table.output
    assert "partial loop not recorded" in table.output
    assert [row["round"] for row in payload["rows"]] == [1, 2]
    assert payload["partial_loop"] is True


def test_unknown_run_exits_1_naming_id_and_dir(runs_dir: Path) -> None:
    result = runner.invoke(app, ["stats", "run", "run-nope"])

    assert result.exit_code == 1
    assert "run-nope" in result.output and str(runs_dir) in result.output


def test_corrupt_run_exits_1_naming_file(runs_dir: Path) -> None:
    (runs_dir / "run-bad.json").write_text("{truncated")

    result = runner.invoke(app, ["stats", "run", "run-bad"])

    assert result.exit_code == 1
    assert "run-bad.json" in result.output


def _review(directory: Path, name: str, **front: object) -> None:
    lines = ["---", "docType: review", "reviewType: slice", "verdict: PASS", "dateCreated: 20261014"]
    lines += [f"{key}: {value}" for key, value in front.items()]
    (directory / name).write_text("\n".join([*lines, "---", "", "body", ""]))


def test_reviews_table_and_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviews = tmp_path / "project-documents/user/reviews"
    reviews.mkdir(parents=True)
    _review(
        reviews,
        "175-review.slice.a.md",
        slice="a",
        aiModel="opus",
        promptTokens=412_800,
        costUsd=0.41,
        costBasis="provider",
    )
    _review(reviews, "175-review.tasks.a.md", slice="a", runId=_RUN)
    monkeypatch.chdir(tmp_path)

    table = runner.invoke(app, ["stats", "reviews", "--slice", "175"])
    payload = json.loads(runner.invoke(app, ["stats", "reviews", "--slice", "175", "--json"]).output)

    assert table.exit_code == 0, table.output
    row = next(line for line in table.output.splitlines() if "20261014" in line)
    assert "412.8k" in row and "$0.41 prov" in row
    assert f"1 pipeline review(s) excluded; see sq stats run {_RUN}" in table.output
    assert [r["file"] for r in payload["rows"]] == ["175-review.slice.a.md"]
    assert payload["excluded_run_ids"] == [_RUN]


def test_reviews_missing_dir_exits_0_with_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stats", "reviews"])

    assert result.exit_code == 0
    assert "No review directory at" in result.output


def test_reviews_missing_dir_json_is_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stats", "reviews", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["missing_dir"] is True and payload["rows"] == []
