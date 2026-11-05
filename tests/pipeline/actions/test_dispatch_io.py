"""Prompt assembly, reply hand-off, JSON extraction and output files (slice 949 D2-D5)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from squadron.pipeline.actions import dispatch_io
from squadron.pipeline.actions.dispatch_io import (
    DispatchInputError,
    OutputWriteError,
    apply_reply_contract,
    assemble_prompt,
    assemble_step_prompt,
    extract_json_object,
    step_reply,
    write_step_files,
)
from squadron.pipeline.control_params import RUN_IO_DIR
from squadron.pipeline.models import ActionResult, prior_output_key

# --- extract_json_object (D4) ---


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('Here you go: {"a": 1} hope that helps', '{"a": 1}'),
        ('{"outer": {"inner": 2}}', '{"outer": {"inner": 2}}'),
        ('{ broken {"inner": 2}', '{"inner": 2}'),
        ('{"n":   1,  "s": "x"}', '{"n":   1,  "s": "x"}'),  # spacing kept: no re-serialization
        ('{"a": NaN} then {"b": 2}', '{"b": 2}'),
    ],
)
def test_extract_json_object(text: str, expected: str) -> None:
    assert extract_json_object(text) == expected


@pytest.mark.parametrize(
    "text",
    ["no braces at all", "{ not json }", '{"a": NaN}', '{"a": Infinity}', '{"a": -Infinity}', ""],
)
def test_extract_json_object_finds_nothing(text: str) -> None:
    assert extract_json_object(text) is None


# --- assemble_prompt (D2) ---


def _write(root: Path, name: str, content: bytes | str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if isinstance(content, bytes) else content.encode())


def test_prompt_then_files_then_reply_joined_by_a_blank_line(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "AAA")
    _write(tmp_path, "sub/b.md", "BBB")
    text = assemble_prompt(
        prompt="PROMPT", prompt_files=["a.md", "sub/b.md"], reply="REPLY", cwd=tmp_path
    )
    assert text == "PROMPT\n\nAAA\n\nBBB\n\nREPLY"


def test_a_prompt_only_step_is_returned_unchanged(tmp_path: Path) -> None:
    assert (
        assemble_prompt(prompt="just this\n", prompt_files=[], reply=None, cwd=tmp_path)
        == "just this\n"
    )


def test_placeholders_inside_a_file_arrive_unchanged(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "slice is {slice} and {nested.value}")
    text = assemble_prompt(prompt=None, prompt_files=["a.md"], reply=None, cwd=tmp_path)
    assert text == "slice is {slice} and {nested.value}"


def test_file_content_is_verbatim_including_line_endings(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", b"one\r\ntwo\r\n")
    assert (
        assemble_prompt(prompt=None, prompt_files=["a.md"], reply=None, cwd=tmp_path)
        == "one\r\ntwo\r\n"
    )


def _assemble_error(tmp_path: Path, relative: str) -> str:
    with pytest.raises(DispatchInputError) as raised:
        assemble_prompt(prompt="p", prompt_files=[relative], reply=None, cwd=tmp_path)
    return str(raised.value)


def test_a_missing_file_raises_naming_the_path(tmp_path: Path) -> None:
    assert "missing.md" in _assemble_error(tmp_path, "missing.md")


def test_a_directory_raises_naming_the_path(tmp_path: Path) -> None:
    (tmp_path / "adir").mkdir()
    assert "adir" in _assemble_error(tmp_path, "adir")


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs POSIX named pipes")
def test_a_fifo_raises_without_blocking(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "pipe")  # type: ignore[attr-defined]
    assert "pipe" in _assemble_error(tmp_path, "pipe")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")  # type: ignore[attr-defined]
def test_a_permission_denied_file_raises_naming_the_path(tmp_path: Path) -> None:
    _write(tmp_path, "secret.md", "x")
    (tmp_path / "secret.md").chmod(0o000)
    try:
        assert "secret.md" in _assemble_error(tmp_path, "secret.md")
    finally:
        (tmp_path / "secret.md").chmod(0o600)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")  # type: ignore[attr-defined]
def test_a_file_in_an_unsearchable_directory_raises_naming_the_path(tmp_path: Path) -> None:
    _write(tmp_path, "locked/a.md", "x")
    (tmp_path / "locked").chmod(0o000)
    try:
        assert "locked/a.md" in _assemble_error(tmp_path, "locked/a.md")
    finally:
        (tmp_path / "locked").chmod(0o700)


def test_invalid_utf8_raises_naming_the_path(tmp_path: Path) -> None:
    _write(tmp_path, "bad.md", b"\xff\xfe\x00bad")
    assert "bad.md" in _assemble_error(tmp_path, "bad.md")


@pytest.mark.parametrize("relative", ["/etc/hosts", "../outside.md", "a/../../b.md"])
def test_unsafe_run_time_paths_raise_naming_the_path(tmp_path: Path, relative: str) -> None:
    assert relative in _assemble_error(tmp_path, relative)


# --- step_reply (D3) ---


def _dispatch_result(*, success: bool = True, **outputs: object) -> ActionResult:
    return ActionResult(success=success, action_type="dispatch", outputs=dict(outputs))


def _prior(name: str, result: ActionResult) -> dict[str, ActionResult]:
    return {prior_output_key(name, "dispatch", 0): result}


def test_step_reply_returns_the_response() -> None:
    prior = _prior("extract", _dispatch_result(response="the reply"))
    assert step_reply(prior, "extract") == "the reply"


def test_step_reply_prefers_reply_json() -> None:
    prior = _prior("extract", _dispatch_result(response="prose {}", reply_json='{"a": 1}'))
    assert step_reply(prior, "extract") == '{"a": 1}'


def test_step_reply_takes_the_last_dispatch_result() -> None:
    prior = {
        prior_output_key("extract", "dispatch", 1): _dispatch_result(response="second"),
        prior_output_key("extract", "dispatch", 0): _dispatch_result(response="first"),
    }
    assert step_reply(prior, "extract") == "second"


@pytest.mark.parametrize(
    "prior",
    [
        _prior("extract", _dispatch_result(success=False, response="partial")),
        _prior("extract", _dispatch_result()),  # skipped: no response
        _prior("extract", _dispatch_result(response="")),
        _prior("other", _dispatch_result(response="x")),
        {},
    ],
    ids=["failed", "no-response", "empty", "other-step", "nothing"],
)
def test_step_reply_refuses_a_step_with_no_usable_reply(prior: dict[str, ActionResult]) -> None:
    with pytest.raises(DispatchInputError, match="extract"):
        step_reply(prior, "extract")


# --- write_step_files (D5) ---


def test_write_step_files_writes_exact_bytes_without_a_trailing_newline(tmp_path: Path) -> None:
    write_step_files(
        cwd=tmp_path,
        delivered_prompt_file="out/prompt.md",
        delivered_prompt="the prompt",
        reply_file="out/reply.json",
        reply='{"a": 1}',
    )
    assert (tmp_path / "out/prompt.md").read_bytes() == b"the prompt"
    assert (tmp_path / "out/reply.json").read_bytes() == b'{"a": 1}'


def test_write_step_files_writes_only_the_files_asked_for(tmp_path: Path) -> None:
    write_step_files(
        cwd=tmp_path, delivered_prompt_file=None, delivered_prompt="p", reply_file="r.txt", reply="R"
    )
    assert sorted(path.name for path in tmp_path.iterdir()) == ["r.txt"]


def _fail_writes_to(monkeypatch: pytest.MonkeyPatch, *targets: tuple[Path, int]) -> None:
    """Make the n-th write to each target path raise OSError; other writes are real."""
    real_write = dispatch_io.write_new_file
    seen: dict[Path, int] = {}

    def failing(path: Path, content: bytes, *, force: bool) -> Path:
        seen[path] = seen.get(path, 0) + 1
        if (path, seen[path]) in targets:
            raise OSError(f"injected failure writing {path.name}")
        return real_write(path, content, force=force)

    monkeypatch.setattr(dispatch_io, "write_new_file", failing)


def test_a_reply_write_failure_restores_an_existing_prompt_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "prompt.md").write_bytes(b"old prompt")
    (tmp_path / "reply.json").write_bytes(b"old reply")
    _fail_writes_to(monkeypatch, (tmp_path / "reply.json", 1))

    with pytest.raises(OutputWriteError, match=r"reply\.json"):
        write_step_files(
            cwd=tmp_path,
            delivered_prompt_file="prompt.md",
            delivered_prompt="new prompt",
            reply_file="reply.json",
            reply="new reply",
        )

    assert (tmp_path / "prompt.md").read_bytes() == b"old prompt"
    assert (tmp_path / "reply.json").read_bytes() == b"old reply"


def test_a_reply_write_failure_removes_a_prompt_file_that_was_new(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fail_writes_to(monkeypatch, (tmp_path / "reply.json", 1))

    with pytest.raises(OutputWriteError):
        write_step_files(
            cwd=tmp_path,
            delivered_prompt_file="prompt.md",
            delivered_prompt="new prompt",
            reply_file="reply.json",
            reply="new reply",
        )

    assert not (tmp_path / "prompt.md").exists()
    assert not (tmp_path / "reply.json").exists()


def test_a_failed_restore_logs_an_error_naming_the_prompt_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "prompt.md").write_bytes(b"old prompt")
    # The prompt file's first write is the new prompt; its second is the restore.
    _fail_writes_to(monkeypatch, (tmp_path / "reply.json", 1), (tmp_path / "prompt.md", 2))

    with caplog.at_level(logging.ERROR, logger=dispatch_io.__name__):
        with pytest.raises(OutputWriteError):
            write_step_files(
                cwd=tmp_path,
                delivered_prompt_file="prompt.md",
                delivered_prompt="new prompt",
                reply_file="reply.json",
                reply="new reply",
            )

    assert any("prompt.md" in record.getMessage() for record in caplog.records)


def test_a_prompt_write_failure_leaves_both_files_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "prompt.md").write_bytes(b"old prompt")
    _fail_writes_to(monkeypatch, (tmp_path / "prompt.md", 1))

    with pytest.raises(OutputWriteError, match=r"prompt\.md"):
        write_step_files(
            cwd=tmp_path,
            delivered_prompt_file="prompt.md",
            delivered_prompt="new prompt",
            reply_file="reply.json",
            reply="new reply",
        )

    assert (tmp_path / "prompt.md").read_bytes() == b"old prompt"
    assert not (tmp_path / "reply.json").exists()


@pytest.mark.parametrize("relative", ["/tmp/abs.json", "../up.json"])
def test_unsafe_output_paths_are_refused_before_any_write(tmp_path: Path, relative: str) -> None:
    with pytest.raises(OutputWriteError, match="reply_file"):
        write_step_files(
            cwd=tmp_path,
            delivered_prompt_file="prompt.md",
            delivered_prompt="p",
            reply_file=relative,
            reply="r",
        )
    assert not (tmp_path / "prompt.md").exists()


# --- apply_reply_contract (D4, D5) ---


def _ok(response: str) -> ActionResult:
    return ActionResult(success=True, action_type="dispatch", outputs={"response": response})


def test_a_json_step_records_reply_json_and_writes_it(tmp_path: Path) -> None:
    reply = 'Sure!\n```json\n{"a": 1}\n```\nDone.'
    params = {"reply_format": "json", "reply_file": "claims.json", "delivered_prompt_file": "p.md"}

    result = apply_reply_contract(_ok(reply), params, str(tmp_path), "DELIVERED")

    assert result.success is True
    assert result.outputs == {"response": reply, "reply_json": '{"a": 1}'}
    assert (tmp_path / "claims.json").read_bytes() == b'{"a": 1}'
    assert (tmp_path / "p.md").read_bytes() == b"DELIVERED"


def test_a_text_step_writes_the_full_response(tmp_path: Path) -> None:
    result = apply_reply_contract(_ok("plain reply"), {"reply_file": "r.txt"}, str(tmp_path), "D")

    assert result.outputs == {"response": "plain reply"}
    assert (tmp_path / "r.txt").read_bytes() == b"plain reply"


def test_a_json_step_with_no_object_fails_and_writes_nothing(tmp_path: Path) -> None:
    (tmp_path / "claims.json").write_bytes(b"previous")
    params = {"reply_format": "json", "reply_file": "claims.json", "delivered_prompt_file": "p.md"}

    result = apply_reply_contract(_ok("no json here"), params, str(tmp_path), "D")

    assert result.success is False
    assert result.error == "reply contains no JSON object"
    assert result.outputs == {"response": "no json here"}
    assert (tmp_path / "claims.json").read_bytes() == b"previous"
    assert not (tmp_path / "p.md").exists()


def test_a_bad_reply_format_is_refused() -> None:
    with pytest.raises(DispatchInputError, match="reply_format"):
        apply_reply_contract(_ok("x"), {"reply_format": "yaml"}, "/unused", "D")


# --- sq run --io-dir (#292) ---


def test_io_dir_moves_prompt_file_reads_out_of_the_working_directory(tmp_path: Path) -> None:
    workdir, io = tmp_path / "checkout", tmp_path / "io"
    workdir.mkdir()
    io.mkdir()
    (io / "request.md").write_text("FROM IO")
    params: dict[str, object] = {"prompt_files": ["request.md"], RUN_IO_DIR: str(io)}

    assert assemble_step_prompt(params, {}, str(workdir)) == "FROM IO"


def test_io_dir_moves_reply_and_prompt_writes_out_of_the_working_directory(
    tmp_path: Path,
) -> None:
    workdir, io = tmp_path / "checkout", tmp_path / "io"
    workdir.mkdir()
    io.mkdir()
    params: dict[str, object] = {
        "reply_file": "reply.txt",
        "delivered_prompt_file": "prompt.txt",
        RUN_IO_DIR: str(io),
    }

    apply_reply_contract(_ok("REPLY"), params, str(workdir), "DELIVERED")

    assert (io / "reply.txt").read_text() == "REPLY"
    assert (io / "prompt.txt").read_text() == "DELIVERED"
    assert list(workdir.iterdir()) == []


def test_without_io_dir_files_resolve_against_the_working_directory(tmp_path: Path) -> None:
    (tmp_path / "request.md").write_text("FROM CWD")

    assert assemble_step_prompt({"prompt_files": ["request.md"]}, {}, str(tmp_path)) == "FROM CWD"
