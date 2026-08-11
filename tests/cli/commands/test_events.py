"""Tests for the sq events CLI (design D8)."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from squadron.cli.commands.events import events_app
from squadron.events.dispatcher import EventOutcome, OutcomeErrorKind
from squadron.events.manifest import DEFAULT_BINDINGS, Binding, EventManifest
from squadron.pipeline.models import ActionResult

runner = CliRunner()


def _outcome(name: str, *, success: bool) -> EventOutcome:
    return EventOutcome(
        action_name=name,
        result=ActionResult(
            success=success, action_type=name, outputs={}, error=None if success else "boom"
        ),
        error_kind=OutcomeErrorKind.NONE,
    )


class TestFireExitCodes:
    def test_all_success_exits_0(self) -> None:
        with patch(
            "squadron.cli.commands.events.run_event",
            return_value=[_outcome("squadron.frontmatter-gate", success=True)],
        ):
            result = runner.invoke(events_app, ["fire", "commit"])

        assert result.exit_code == 0

    def test_any_fail_exits_1(self) -> None:
        with patch(
            "squadron.cli.commands.events.run_event",
            return_value=[_outcome("squadron.frontmatter-gate", success=False)],
        ):
            result = runner.invoke(events_app, ["fire", "commit"])

        assert result.exit_code == 1

    def test_plugin_load_error_exits_2(self) -> None:
        from squadron.events.discovery import PluginLoadError

        with patch(
            "squadron.cli.commands.events.run_event",
            side_effect=PluginLoadError("broken_plugin", "events.yaml"),
        ):
            result = runner.invoke(events_app, ["fire", "commit"])

        assert result.exit_code == 2

    def test_manifest_error_exits_2(self) -> None:
        from squadron.events.manifest import ManifestError

        with patch(
            "squadron.cli.commands.events.run_event",
            side_effect=ManifestError("bad manifest"),
        ):
            result = runner.invoke(events_app, ["fire", "commit"])

        assert result.exit_code == 2

    def test_timeout_outcome_exits_1(self) -> None:
        timeout_outcome = EventOutcome(
            action_name="squadron.frontmatter-gate", result=None, error_kind=OutcomeErrorKind.TIMEOUT
        )
        with patch("squadron.cli.commands.events.run_event", return_value=[timeout_outcome]):
            result = runner.invoke(events_app, ["fire", "commit"])

        assert result.exit_code == 1


class TestFirePostActionUsageError:
    def test_fire_post_action_is_usage_error(self) -> None:
        result = runner.invoke(events_app, ["fire", "post-action"])

        assert result.exit_code == 2
        assert "cannot be fired" in result.output.replace("\n", " ")

    def test_unknown_event_is_usage_error(self) -> None:
        result = runner.invoke(events_app, ["fire", "bogus-event"])

        assert result.exit_code == 2
        assert "unknown event" in result.output


class TestList:
    def test_list_shows_manifest_binding_and_disabled_builtin(self) -> None:
        from squadron.events import EventType

        manifest = EventManifest(
            plugins=(),
            bindings=(
                *[b for b in DEFAULT_BINDINGS if b.action != "squadron.frontmatter-gate"],
                Binding(
                    event=EventType.COMMIT,
                    action="demo.rule-check",
                    params={},
                    source="project-documents/user/events.yaml",
                ),
            ),
            disabled=frozenset({"squadron.frontmatter-gate"}),
            manifest_path=None,
        )
        with patch("squadron.cli.commands.events.load_manifest", return_value=manifest):
            result = runner.invoke(events_app, ["list"])

        assert result.exit_code == 0
        assert "demo.rule-check" in result.output
        assert "squadron.frontmatter-gate" in result.output
        assert "disabled" in result.output
