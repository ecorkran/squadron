"""Tests for SummaryAction (T7, T8, T9)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.actions.summary import SummaryAction
from squadron.pipeline.emit import EmitDestination, EmitKind, EmitResult
from squadron.pipeline.models import ActionContext


def _make_action() -> SummaryAction:
    return SummaryAction()


def _make_context(
    params: dict[str, object] | None = None,
    sdk_session: object = None,
    cwd: str = "/tmp",
    step_index: int = 0,
    step_name: str = "test-step",
    prior_outputs: dict | None = None,
) -> MagicMock:
    ctx = MagicMock(spec=ActionContext)
    ctx.params = params or {}
    ctx.sdk_session = sdk_session
    ctx.cwd = cwd
    ctx.step_index = step_index
    ctx.step_name = step_name
    ctx.prior_outputs = prior_outputs if prior_outputs is not None else {}
    ctx.resolver = MagicMock()
    ctx.resolver.resolve.return_value = ("resolved-model-id", None)
    return ctx


# ---------------------------------------------------------------------------
# T7 — SummaryAction class and validation
# ---------------------------------------------------------------------------


def test_summary_action_type() -> None:
    assert _make_action().action_type == "summary"


def test_validate_valid_template() -> None:
    errors = _make_action().validate({"template": "minimal-sdk"})
    assert errors == []


def test_validate_template_non_string() -> None:
    errors = _make_action().validate({"template": 42})
    assert len(errors) == 1
    assert errors[0].field == "template"


def test_validate_model_non_string() -> None:
    errors = _make_action().validate({"model": 42})
    assert len(errors) == 1
    assert errors[0].field == "model"


def test_validate_emit_unknown_kind() -> None:
    errors = _make_action().validate({"emit": ["banana"]})
    assert len(errors) == 1
    assert errors[0].field == "emit"
    assert "banana" in errors[0].message


def test_validate_emit_valid_file() -> None:
    errors = _make_action().validate({"emit": [{"file": "/tmp/x"}]})
    assert errors == []


# ---------------------------------------------------------------------------
# T8 — _execute_summary helper
# ---------------------------------------------------------------------------


def _make_emit_result(ok: bool = True, destination: str = "stdout") -> EmitResult:
    return EmitResult(destination=destination, ok=ok, detail="")


async def _fake_emit_ok(text: str, dest: EmitDestination, ctx: object) -> EmitResult:
    return EmitResult(destination=dest.display(), ok=True, detail="")


async def _fake_emit_fail(text: str, dest: EmitDestination, ctx: object) -> EmitResult:
    return EmitResult(destination=dest.display(), ok=False, detail="emit failed")


@pytest.mark.asyncio
async def test_execute_summary_stdout_emit_calls_capture_and_emit() -> None:
    from squadron.pipeline.actions.summary import _execute_summary

    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="SUMMARY TEXT")
    ctx = _make_context(sdk_session=session)

    dests = [EmitDestination(kind=EmitKind.STDOUT)]
    with patch(
        "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
    ):
        result = await _execute_summary(
            context=ctx,
            instructions="summarize",
            summary_model_alias=None,
            emit_destinations=dests,
            action_type="summary",
        )

    assert result.success is True
    assert isinstance(result.outputs.get("emit_results"), list)
    emit_results = result.outputs["emit_results"]
    assert isinstance(emit_results, list) and len(emit_results) == 1
    assert emit_results[0]["ok"] is True  # type: ignore[index]


@pytest.mark.asyncio
async def test_execute_summary_multiple_emits_in_order() -> None:
    from squadron.pipeline.actions.summary import _execute_summary

    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="SUMMARY")
    ctx = _make_context(sdk_session=session)

    call_order: list[str] = []

    async def ordered_emit(text: str, dest: EmitDestination, c: object) -> EmitResult:
        call_order.append(dest.display())
        return EmitResult(destination=dest.display(), ok=True, detail="")

    dests = [
        EmitDestination(kind=EmitKind.STDOUT),
        EmitDestination(kind=EmitKind.FILE, arg="/tmp/x"),
        EmitDestination(kind=EmitKind.CLIPBOARD),
    ]
    with patch("squadron.pipeline.actions.summary.get_emit", return_value=ordered_emit):
        result = await _execute_summary(
            context=ctx,
            instructions="summarize",
            summary_model_alias=None,
            emit_destinations=dests,
            action_type="summary",
        )

    assert result.success is True
    assert call_order == ["stdout", "file:/tmp/x", "clipboard"]
    emit_results = result.outputs["emit_results"]
    assert isinstance(emit_results, list) and len(emit_results) == 3


@pytest.mark.asyncio
async def test_execute_summary_sdk_profile_without_session_fails() -> None:
    """SDK profile (alias=None → profile=None) without a session fails."""
    from squadron.pipeline.actions.summary import _execute_summary

    ctx = _make_context(sdk_session=None)
    # alias=None means profile=None, which is_sdk_profile treats as SDK
    result = await _execute_summary(
        context=ctx,
        instructions="x",
        summary_model_alias=None,
        emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
        action_type="summary",
    )

    assert result.success is False
    assert result.error is not None
    assert "SDK" in result.error


@pytest.mark.asyncio
async def test_execute_summary_capture_exception_returns_failure() -> None:
    from squadron.pipeline.actions.summary import _execute_summary

    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(side_effect=RuntimeError("network fail"))
    ctx = _make_context(sdk_session=session)

    result = await _execute_summary(
        context=ctx,
        instructions="x",
        summary_model_alias=None,
        emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
        action_type="summary",
    )

    assert result.success is False
    assert "network fail" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_summary_non_rotate_emit_failure_still_succeeds() -> None:
    from squadron.pipeline.actions.summary import _execute_summary

    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="SUMMARY")
    ctx = _make_context(sdk_session=session)

    async def bad_emit(text: str, dest: EmitDestination, c: object) -> EmitResult:
        return EmitResult(destination=dest.display(), ok=False, detail="disk full")

    dests = [EmitDestination(kind=EmitKind.FILE, arg="/tmp/x")]
    with patch("squadron.pipeline.actions.summary.get_emit", return_value=bad_emit):
        result = await _execute_summary(
            context=ctx,
            instructions="x",
            summary_model_alias=None,
            emit_destinations=dests,
            action_type="summary",
        )

    assert result.success is True  # non-rotate failure doesn't fail the action
    emit_results = result.outputs["emit_results"]
    assert isinstance(emit_results, list)
    assert emit_results[0]["ok"] is False  # type: ignore[index]


@pytest.mark.asyncio
async def test_execute_summary_rotate_failure_fails_action() -> None:
    from squadron.pipeline.actions.summary import _execute_summary

    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="SUMMARY")
    ctx = _make_context(sdk_session=session)

    async def rotate_fail(text: str, dest: EmitDestination, c: object) -> EmitResult:
        return EmitResult(destination=dest.display(), ok=False, detail="rotate error")

    dests = [EmitDestination(kind=EmitKind.ROTATE)]
    with patch("squadron.pipeline.actions.summary.get_emit", return_value=rotate_fail):
        result = await _execute_summary(
            context=ctx,
            instructions="x",
            summary_model_alias=None,
            emit_destinations=dests,
            action_type="summary",
        )

    assert result.success is False
    assert "rotate error" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_summary_captures_once_for_stdout_and_rotate() -> None:
    """Summary is captured ONCE even when multiple emits are configured."""
    from squadron.pipeline.actions.summary import _execute_summary

    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="SHARED SUMMARY")
    ctx = _make_context(sdk_session=session)

    received_texts: list[str] = []

    async def recording_emit(text: str, dest: EmitDestination, c: object) -> EmitResult:
        received_texts.append(text)
        return EmitResult(destination=dest.display(), ok=True, detail="")

    dests = [
        EmitDestination(kind=EmitKind.STDOUT),
        EmitDestination(kind=EmitKind.ROTATE),
    ]
    with patch(
        "squadron.pipeline.actions.summary.get_emit", return_value=recording_emit
    ):
        await _execute_summary(
            context=ctx,
            instructions="x",
            summary_model_alias=None,
            emit_destinations=dests,
            action_type="summary",
        )

    session.capture_summary.assert_called_once()
    assert all(t == "SHARED SUMMARY" for t in received_texts)


@pytest.mark.asyncio
async def test_execute_summary_resolves_model_alias() -> None:
    from squadron.pipeline.actions.summary import _execute_summary

    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="SUMMARY")
    ctx = _make_context(sdk_session=session)
    ctx.resolver.resolve.return_value = ("haiku-resolved", None)

    with patch(
        "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
    ):
        await _execute_summary(
            context=ctx,
            instructions="x",
            summary_model_alias="haiku",
            emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
            action_type="summary",
        )

    ctx.resolver.resolve.assert_called_once_with(action_model="haiku", step_model=None)
    session.capture_summary.assert_called_once()
    call_kwargs = session.capture_summary.call_args.kwargs
    assert call_kwargs["summary_model"] == "haiku-resolved"


@pytest.mark.asyncio
async def test_execute_summary_outputs_include_step_info() -> None:
    from squadron.pipeline.actions.summary import _execute_summary

    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="SUMMARY")
    ctx = _make_context(sdk_session=session, step_index=3, step_name="my-step")

    with patch(
        "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
    ):
        result = await _execute_summary(
            context=ctx,
            instructions="x",
            summary_model_alias=None,
            emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
            action_type="summary",
        )

    assert result.outputs["source_step_index"] == 3
    assert result.outputs["source_step_name"] == "my-step"


@pytest.mark.asyncio
async def test_execute_summary_extensibility_custom_emit_fn() -> None:
    """Custom EmitFn registered via register_emit is called through _execute_summary."""
    from squadron.pipeline.actions.summary import _execute_summary
    from squadron.pipeline.emit import EmitKind, register_emit

    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="CUSTOM SUMMARY")
    ctx = _make_context(sdk_session=session)

    captured_text: list[str] = []
    captured_dest: list[EmitDestination] = []

    async def custom_emit_fn(text: str, dest: EmitDestination, c: object) -> EmitResult:
        captured_text.append(text)
        captured_dest.append(dest)
        return EmitResult(destination=dest.display(), ok=True, detail="custom ok")

    register_emit(EmitKind.STDOUT, custom_emit_fn)  # type: ignore[arg-type]
    try:
        dests = [EmitDestination(kind=EmitKind.STDOUT)]
        result = await _execute_summary(
            context=ctx,
            instructions="x",
            summary_model_alias=None,
            emit_destinations=dests,
            action_type="summary",
        )

        assert captured_text == ["CUSTOM SUMMARY"]
        assert captured_dest == [EmitDestination(kind=EmitKind.STDOUT)]
        assert result.success is True
    finally:
        # Restore built-in stdout emit
        from squadron.pipeline.emit import _emit_stdout

        register_emit(EmitKind.STDOUT, _emit_stdout)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T9 — SummaryAction.execute() wired to _execute_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_loads_template_and_passes_instructions() -> None:
    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="SUMMARY")
    ctx = _make_context(params={"template": "minimal-sdk"}, sdk_session=session)

    with patch(
        "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
    ):
        result = await _make_action().execute(ctx)

    assert result.success is True
    session.capture_summary.assert_called_once()
    instructions = session.capture_summary.call_args.kwargs["instructions"]
    assert isinstance(instructions, str) and len(instructions) > 0


@pytest.mark.asyncio
async def test_execute_missing_template_returns_failure() -> None:
    session = AsyncMock()
    session.current_model = "sonnet-id"
    ctx = _make_context(params={"template": "does-not-exist"}, sdk_session=session)

    result = await _make_action().execute(ctx)

    assert result.success is False
    assert result.error is not None
    assert "does-not-exist" in result.error


@pytest.mark.asyncio
async def test_execute_default_emit_is_stdout() -> None:
    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="SUMMARY")
    ctx = _make_context(params={}, sdk_session=session)

    emitted_to: list[str] = []

    async def capturing_emit(text: str, dest: EmitDestination, c: object) -> EmitResult:
        emitted_to.append(dest.display())
        return EmitResult(destination=dest.display(), ok=True, detail="")

    with patch(
        "squadron.pipeline.actions.summary.get_emit", return_value=capturing_emit
    ):
        result = await _make_action().execute(ctx)

    assert result.success is True
    assert emitted_to == ["stdout"]


@pytest.mark.asyncio
async def test_execute_invalid_emit_param_returns_failure() -> None:
    session = AsyncMock()
    ctx = _make_context(params={"emit": ["banana"]}, sdk_session=session)

    result = await _make_action().execute(ctx)

    assert result.success is False
    assert result.error is not None
    assert "banana" in result.error


# ---------------------------------------------------------------------------
# T7 (slice 164) — profile branching tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_summary_routes_non_sdk_profile_via_oneshot() -> None:
    """Non-SDK profile routes through capture_summary_via_profile, not sdk_session."""
    from unittest.mock import patch

    from squadron.pipeline.actions.summary import _execute_summary

    ctx = _make_context(sdk_session=None)
    ctx.resolver.resolve.return_value = ("minimax-01", "openrouter")

    with patch(
        "squadron.pipeline.actions.summary.capture_summary_via_profile",
        new=AsyncMock(return_value="ONESHOT SUMMARY"),
    ) as mock_oneshot:
        with patch(
            "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
        ):
            result = await _execute_summary(
                context=ctx,
                instructions="summarize",
                summary_model_alias="minimax",
                emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
                action_type="summary",
            )

    assert result.success is True
    assert result.outputs.get("summary") == "ONESHOT SUMMARY"
    mock_oneshot.assert_called_once_with(
        instructions="summarize",
        model_id="minimax-01",
        profile="openrouter",
    )


@pytest.mark.asyncio
async def test_execute_summary_non_sdk_profile_with_rotate_fails() -> None:
    """Rotate emit + non-SDK profile fails before any provider call."""
    from unittest.mock import patch

    from squadron.pipeline.actions.summary import _execute_summary

    ctx = _make_context(sdk_session=None)
    ctx.resolver.resolve.return_value = ("minimax-01", "openrouter")

    with patch(
        "squadron.pipeline.actions.summary.capture_summary_via_profile",
        new=AsyncMock(return_value="SHOULD NOT REACH"),
    ) as mock_oneshot:
        result = await _execute_summary(
            context=ctx,
            instructions="summarize",
            summary_model_alias="minimax",
            emit_destinations=[EmitDestination(kind=EmitKind.ROTATE)],
            action_type="summary",
        )

    assert result.success is False
    assert result.error is not None
    assert "rotate" in result.error.lower()
    assert "non-SDK" in result.error or "openrouter" in result.error
    mock_oneshot.assert_not_called()


@pytest.mark.asyncio
async def test_execute_summary_sdk_profile_path_unchanged() -> None:
    """SDK profile still calls sdk_session.capture_summary as before."""
    from squadron.pipeline.actions.summary import _execute_summary

    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="SDK SUMMARY")
    ctx = _make_context(sdk_session=session)
    ctx.resolver.resolve.return_value = ("haiku-resolved", "sdk")

    with patch(
        "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
    ):
        result = await _execute_summary(
            context=ctx,
            instructions="summarize",
            summary_model_alias="haiku",
            emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
            action_type="summary",
        )

    assert result.success is True
    session.capture_summary.assert_called_once()
    assert session.capture_summary.call_args.kwargs["summary_model"] == "haiku-resolved"


@pytest.mark.asyncio
async def test_execute_summary_unannotated_alias_uses_sdk_path() -> None:
    """Resolver returning profile=None (unannotated alias) uses the SDK path."""
    from squadron.pipeline.actions.summary import _execute_summary

    session = AsyncMock()
    session.current_model = "sonnet-id"
    session.capture_summary = AsyncMock(return_value="SDK SUMMARY")
    ctx = _make_context(sdk_session=session)
    ctx.resolver.resolve.return_value = ("some-resolved-id", None)

    with patch(
        "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
    ):
        result = await _execute_summary(
            context=ctx,
            instructions="summarize",
            summary_model_alias="some-alias",
            emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
            action_type="summary",
        )

    assert result.success is True
    session.capture_summary.assert_called_once()
    assert (
        session.capture_summary.call_args.kwargs["summary_model"] == "some-resolved-id"
    )


# ---------------------------------------------------------------------------
# T4 (slice 191) — context injection integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_sdk_summary_injects_prior_context() -> None:
    """Non-SDK summary prepends assembled pipeline context to instructions."""
    from squadron.pipeline.actions.summary import _execute_summary
    from squadron.pipeline.models import ActionResult

    dispatch_result = ActionResult(
        success=True,
        action_type="dispatch",
        outputs={"response": "The web server uses a layered architecture."},
    )
    ctx = _make_context(
        sdk_session=None,
        prior_outputs={"design": dispatch_result},
    )
    ctx.resolver.resolve.return_value = ("minimax-01", "openrouter")

    with patch(
        "squadron.pipeline.actions.summary.capture_summary_via_profile",
        new=AsyncMock(return_value="SUMMARY WITH CONTEXT"),
    ) as mock_oneshot:
        with patch(
            "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
        ):
            result = await _execute_summary(
                context=ctx,
                instructions="Please summarize.",
                summary_model_alias="minimax",
                emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
                action_type="summary",
            )

    assert result.success is True
    mock_oneshot.assert_called_once()
    injected_instructions = mock_oneshot.call_args.kwargs["instructions"]
    assert "--- Pipeline Context" in injected_instructions
    assert "The web server uses a layered architecture." in injected_instructions
    assert "Please summarize." in injected_instructions


@pytest.mark.asyncio
async def test_sdk_summary_does_not_inject_context() -> None:
    """SDK path does not prepend pipeline context — sdk_session has full history."""
    from squadron.pipeline.actions.summary import _execute_summary
    from squadron.pipeline.models import ActionResult

    dispatch_result = ActionResult(
        success=True,
        action_type="dispatch",
        outputs={"response": "Should not appear in SDK instructions."},
    )
    session = AsyncMock()
    session.current_model = "haiku-id"
    session.capture_summary = AsyncMock(return_value="SDK SUMMARY")

    ctx = _make_context(
        sdk_session=session,
        prior_outputs={"design": dispatch_result},
    )
    ctx.resolver.resolve.return_value = ("haiku-resolved", None)

    with patch(
        "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
    ):
        result = await _execute_summary(
            context=ctx,
            instructions="Please summarize.",
            summary_model_alias="haiku",
            emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
            action_type="summary",
        )

    assert result.success is True
    session.capture_summary.assert_called_once()
    sdk_instructions = session.capture_summary.call_args.kwargs["instructions"]
    assert "--- Pipeline Context" not in sdk_instructions


# ---------------------------------------------------------------------------
# T8 — restore mode
# ---------------------------------------------------------------------------


def _make_prior_summary_result() -> object:
    from squadron.pipeline.models import ActionResult

    return ActionResult(
        success=True,
        action_type="summary",
        outputs={
            "summary": "the prior session summary text",
            "instructions": "compact",
        },
    )


@pytest.mark.asyncio
async def test_restore_injects_prior_summary_via_sdk_session() -> None:

    prior = _make_prior_summary_result()
    session = MagicMock()
    session.seed_context = AsyncMock()

    ctx = _make_context(
        params={"restore": True},
        sdk_session=session,
        prior_outputs={"summary-0": prior},
    )

    result = await _make_action().execute(ctx)

    assert result.success is True
    assert result.outputs.get("restored") is True
    assert result.outputs.get("summary") == "the prior session summary text"
    session.seed_context.assert_awaited_once()
    # Confirm framed text was passed to seed_context
    seeded = session.seed_context.call_args.args[0]
    assert "the prior session summary text" in seeded


@pytest.mark.asyncio
async def test_restore_no_prior_summary_returns_error() -> None:
    ctx = _make_context(params={"restore": True}, prior_outputs={})

    result = await _make_action().execute(ctx)

    assert result.success is False
    assert "no prior summary" in (result.error or "")


@pytest.mark.asyncio
async def test_restore_prompt_only_no_sdk_session_returns_success() -> None:
    """In prompt-only mode (no sdk_session), restore succeeds with summary in outputs."""
    prior = _make_prior_summary_result()
    ctx = _make_context(
        params={"restore": True},
        sdk_session=None,
        prior_outputs={"summary-0": prior},
    )

    result = await _make_action().execute(ctx)

    assert result.success is True
    assert result.outputs.get("restored") is True
    assert result.outputs.get("summary") == "the prior session summary text"


@pytest.mark.asyncio
async def test_restore_uses_most_recent_prior_summary() -> None:
    """When multiple prior summary results exist, the most recent wins."""
    from squadron.pipeline.models import ActionResult

    old = ActionResult(
        success=True,
        action_type="summary",
        outputs={"summary": "old summary"},
    )
    new = ActionResult(
        success=True,
        action_type="summary",
        outputs={"summary": "new summary"},
    )
    session = MagicMock()
    session.seed_context = AsyncMock()
    ctx = _make_context(
        params={"restore": True},
        sdk_session=session,
        prior_outputs={"summary-0": old, "summary-1": new},
    )

    result = await _make_action().execute(ctx)

    assert result.outputs["summary"] == "new summary"


@pytest.mark.asyncio
async def test_normal_summarize_does_not_enter_restore_path() -> None:
    """Without restore:true, seed_context is never called."""
    prior = _make_prior_summary_result()
    session = MagicMock()
    session.seed_context = AsyncMock()

    ctx = _make_context(
        params={},  # no restore param
        sdk_session=session,
        prior_outputs={"summary-0": prior},
    )

    # We don't care if the normal summarize path succeeds or fails in this test;
    # we only care that seed_context (restore path) was NOT called.
    with patch(
        "squadron.pipeline.actions.summary._execute_summary", new_callable=AsyncMock
    ):
        await _make_action().execute(ctx)

    session.seed_context.assert_not_awaited()


def test_validate_restore_bool() -> None:
    errors = _make_action().validate({"restore": True})
    assert errors == []


def test_validate_restore_non_bool() -> None:
    errors = _make_action().validate({"restore": "yes"})
    assert len(errors) == 1
    assert errors[0].field == "restore"
