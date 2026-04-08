"""Tests for the emit destination registry and types (T4, T5, T6)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.emit import (
    EmitDestination,
    EmitKind,
    EmitResult,
    get_emit,
    parse_emit_list,
    register_emit,
)

# ---------------------------------------------------------------------------
# T4 — Registry and types
# ---------------------------------------------------------------------------


def test_emit_kind_values_are_lowercase() -> None:
    assert EmitKind.STDOUT == "stdout"
    assert EmitKind.FILE == "file"
    assert EmitKind.CLIPBOARD == "clipboard"
    assert EmitKind.ROTATE == "rotate"


def test_emit_destination_display_file() -> None:
    dest = EmitDestination(kind=EmitKind.FILE, arg="/tmp/x")
    assert dest.display() == "file:/tmp/x"


def test_emit_destination_display_stdout() -> None:
    dest = EmitDestination(kind=EmitKind.STDOUT)
    assert dest.display() == "stdout"


def test_register_and_get_emit() -> None:
    async def fake_fn(text: str, dest: EmitDestination, ctx: object) -> EmitResult:
        return EmitResult(destination="stdout", ok=True, detail="")

    register_emit(EmitKind.STDOUT, fake_fn)  # type: ignore[arg-type]
    assert get_emit(EmitKind.STDOUT) is fake_fn


def test_get_emit_unregistered_raises_key_error() -> None:
    from squadron.pipeline.emit import _REGISTRY

    # Temporarily remove clipboard to test KeyError
    saved = _REGISTRY.pop(EmitKind.CLIPBOARD, None)
    try:
        with pytest.raises(KeyError):
            get_emit(EmitKind.CLIPBOARD)
    finally:
        if saved is not None:
            _REGISTRY[EmitKind.CLIPBOARD] = saved


# ---------------------------------------------------------------------------
# T6 — parse_emit_entry / parse_emit_list
# ---------------------------------------------------------------------------


def test_parse_emit_list_none_returns_stdout_default() -> None:
    result = parse_emit_list(None)
    assert result == [EmitDestination(kind=EmitKind.STDOUT)]


def test_parse_emit_list_stdout_and_clipboard() -> None:
    result = parse_emit_list(["stdout", "clipboard"])
    assert result == [
        EmitDestination(kind=EmitKind.STDOUT),
        EmitDestination(kind=EmitKind.CLIPBOARD),
    ]


def test_parse_emit_list_file_dict() -> None:
    result = parse_emit_list([{"file": "/tmp/x.md"}])
    assert result == [EmitDestination(kind=EmitKind.FILE, arg="/tmp/x.md")]


def test_parse_emit_list_rotate_and_file() -> None:
    result = parse_emit_list(["rotate", {"file": "/tmp/y"}])
    assert result == [
        EmitDestination(kind=EmitKind.ROTATE),
        EmitDestination(kind=EmitKind.FILE, arg="/tmp/y"),
    ]


def test_parse_emit_list_empty_raises() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        parse_emit_list([])


def test_parse_emit_list_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown emit destination"):
        parse_emit_list(["banana"])


def test_parse_emit_list_file_empty_path_raises() -> None:
    with pytest.raises(ValueError):
        parse_emit_list([{"file": ""}])


def test_parse_emit_list_file_non_string_path_raises() -> None:
    with pytest.raises(ValueError):
        parse_emit_list([{"file": 42}])


def test_parse_emit_list_string_not_list_raises() -> None:
    with pytest.raises(ValueError):
        parse_emit_list("stdout")


# ---------------------------------------------------------------------------
# T5 — Built-in emit destination implementations
# ---------------------------------------------------------------------------


def _make_ctx(cwd: str = "/tmp", sdk_session: object = None) -> MagicMock:
    ctx = MagicMock()
    ctx.cwd = cwd
    ctx.sdk_session = sdk_session
    return ctx


@pytest.mark.asyncio
async def test_emit_stdout_prints_and_returns_ok(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from squadron.pipeline.emit import _emit_stdout

    dest = EmitDestination(kind=EmitKind.STDOUT)
    result = await _emit_stdout("hello", dest, _make_ctx())
    captured = capsys.readouterr()
    assert "hello" in captured.out
    assert result.ok is True


@pytest.mark.asyncio
async def test_emit_file_writes_content(tmp_path: object) -> None:
    from pathlib import Path

    from squadron.pipeline.emit import _emit_file

    assert isinstance(tmp_path, Path)
    dest = EmitDestination(kind=EmitKind.FILE, arg=str(tmp_path / "sub" / "out.md"))
    ctx = _make_ctx(cwd=str(tmp_path))
    result = await _emit_file("payload", dest, ctx)

    assert result.ok is True
    assert "bytes" in result.detail
    assert (tmp_path / "sub" / "out.md").read_text() == "payload"


@pytest.mark.asyncio
async def test_emit_file_relative_path_resolves_to_cwd(tmp_path: object) -> None:
    from pathlib import Path

    from squadron.pipeline.emit import _emit_file

    assert isinstance(tmp_path, Path)
    dest = EmitDestination(kind=EmitKind.FILE, arg="relative/out.md")
    ctx = _make_ctx(cwd=str(tmp_path))
    result = await _emit_file("data", dest, ctx)

    assert result.ok is True
    assert (tmp_path / "relative" / "out.md").read_text() == "data"


@pytest.mark.asyncio
async def test_emit_file_readonly_dir_returns_ok_false(tmp_path: object) -> None:
    import sys
    from pathlib import Path

    from squadron.pipeline.emit import _emit_file

    if sys.platform == "win32":
        pytest.skip("chmod not reliable on Windows")

    assert isinstance(tmp_path, Path)
    ro = tmp_path / "readonly"
    ro.mkdir()
    ro.chmod(0o555)
    dest = EmitDestination(kind=EmitKind.FILE, arg=str(ro / "out.md"))
    ctx = _make_ctx(cwd=str(tmp_path))
    result = await _emit_file("x", dest, ctx)

    assert result.ok is False
    assert result.detail != ""


@pytest.mark.asyncio
async def test_emit_clipboard_success() -> None:
    from squadron.pipeline.emit import _emit_clipboard

    dest = EmitDestination(kind=EmitKind.CLIPBOARD)
    ctx = _make_ctx()

    with patch("pyperclip.copy") as mock_copy:
        result = await _emit_clipboard("clipboard text", dest, ctx)

    mock_copy.assert_called_once_with("clipboard text")
    assert result.ok is True


@pytest.mark.asyncio
async def test_emit_clipboard_failure_returns_ok_false() -> None:
    import pyperclip

    from squadron.pipeline.emit import _emit_clipboard

    dest = EmitDestination(kind=EmitKind.CLIPBOARD)
    ctx = _make_ctx()

    with patch(
        "pyperclip.copy", side_effect=pyperclip.PyperclipException("no clipboard")
    ):
        result = await _emit_clipboard("x", dest, ctx)

    assert result.ok is False
    assert "no clipboard" in result.detail


@pytest.mark.asyncio
async def test_emit_rotate_without_sdk_session_returns_ok_false() -> None:
    from squadron.pipeline.emit import _emit_rotate

    dest = EmitDestination(kind=EmitKind.ROTATE)
    ctx = _make_ctx(sdk_session=None)
    result = await _emit_rotate("summary", dest, ctx)

    assert result.ok is False
    assert "SDK" in result.detail


@pytest.mark.asyncio
async def test_emit_rotate_with_session_calls_compact() -> None:
    from squadron.pipeline.emit import _emit_rotate

    dest = EmitDestination(kind=EmitKind.ROTATE)
    session = AsyncMock()
    session.current_model = "sonnet-id"
    ctx = _make_ctx(sdk_session=session)

    result = await _emit_rotate("summary text", dest, ctx)

    session.compact.assert_called_once_with(
        instructions="",
        summary="summary text",
        restore_model="sonnet-id",
    )
    assert result.ok is True
    assert result.detail == "session rotated"


@pytest.mark.asyncio
async def test_emit_rotate_passes_summary_unchanged() -> None:
    from squadron.pipeline.emit import _emit_rotate

    dest = EmitDestination(kind=EmitKind.ROTATE)
    session = AsyncMock()
    session.current_model = "sonnet-id"
    ctx = _make_ctx(sdk_session=session)

    await _emit_rotate("exact text", dest, ctx)

    assert session.compact.call_args.kwargs["summary"] == "exact text"
