"""Tests for the sq pools CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline.intelligence.pools.loader import load_pool_state


def _invoke(runner: CliRunner, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["pools", *args])


@pytest.fixture
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch loader._config_dir so all state writes go to tmp_path."""
    config_dir = tmp_path / "squadron"
    config_dir.mkdir()
    import squadron.pipeline.intelligence.pools.loader as loader_mod

    monkeypatch.setattr(loader_mod, "_config_dir", lambda: config_dir)


# ---------------------------------------------------------------------------
# sq pools list (and sq pools with no subcommand)
# ---------------------------------------------------------------------------


class TestPoolsList:
    def test_list_exits_zero(self, cli_runner: CliRunner) -> None:
        result = _invoke(cli_runner, "list")
        assert result.exit_code == 0

    def test_list_contains_builtin_pools(self, cli_runner: CliRunner) -> None:
        result = _invoke(cli_runner, "list")
        assert "review" in result.output
        assert "high" in result.output
        assert "cheap" in result.output

    def test_no_subcommand_behaves_like_list(self, cli_runner: CliRunner) -> None:
        result_list = _invoke(cli_runner, "list")
        result_default = _invoke(cli_runner)
        assert result_list.exit_code == 0
        assert result_default.exit_code == 0
        # Both should show the same pool names
        assert "review" in result_default.output
        assert "high" in result_default.output


# ---------------------------------------------------------------------------
# sq pools show
# ---------------------------------------------------------------------------


class TestPoolsShow:
    def test_show_known_pool_exits_zero(self, cli_runner: CliRunner) -> None:
        result = _invoke(cli_runner, "show", "review")
        assert result.exit_code == 0

    def test_show_contains_strategy(self, cli_runner: CliRunner) -> None:
        result = _invoke(cli_runner, "show", "review")
        assert "round-robin" in result.output

    def test_show_contains_at_least_one_member(self, cli_runner: CliRunner) -> None:
        result = _invoke(cli_runner, "show", "review")
        # At least one of the known review pool members must appear
        assert any(
            m in result.output for m in ["minimax", "glm5", "kimi25", "grok-fast"]
        )

    def test_show_unknown_pool_exits_nonzero(self, cli_runner: CliRunner) -> None:
        result = _invoke(cli_runner, "show", "nonexistent")
        assert result.exit_code != 0

    def test_show_unknown_pool_prints_error(self, cli_runner: CliRunner) -> None:
        result = _invoke(cli_runner, "show", "nonexistent")
        assert "nonexistent" in result.output or "nonexistent" in (result.stdout or "")


# ---------------------------------------------------------------------------
# sq pools reset
# ---------------------------------------------------------------------------


class TestPoolsReset:
    def test_reset_known_pool_exits_zero(
        self, cli_runner: CliRunner, isolated_state: None
    ) -> None:
        result = _invoke(cli_runner, "reset", "review")
        assert result.exit_code == 0

    def test_reset_prints_confirmation(
        self, cli_runner: CliRunner, isolated_state: None
    ) -> None:
        result = _invoke(cli_runner, "reset", "review")
        assert "review" in result.output

    def test_reset_clears_state(
        self, cli_runner: CliRunner, isolated_state: None
    ) -> None:
        from squadron.pipeline.intelligence.pools.loader import save_pool_state
        from squadron.pipeline.intelligence.pools.models import PoolState

        save_pool_state("review", PoolState(last_index=5))
        _invoke(cli_runner, "reset", "review")
        assert load_pool_state("review").last_index == 0

    def test_reset_unknown_pool_exits_nonzero(
        self, cli_runner: CliRunner, isolated_state: None
    ) -> None:
        result = _invoke(cli_runner, "reset", "nonexistent")
        assert result.exit_code != 0
