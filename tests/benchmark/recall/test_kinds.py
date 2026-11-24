"""The case-kind registry (slice 430 D14)."""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

import pytest

from squadron.benchmark.recall.kinds import (
    CodeKind,
    KindContext,
    UnknownKindError,
    get_kind,
    registered_kind,
)
from squadron.metrology.recall_case_models import RealBugCase, RecallCaseKind
from tests.benchmark.recall.support import case_fields


class StubKind:
    def validate(self, case_file: Path, context: KindContext) -> RealBugCase:
        return RealBugCase.build(**case_fields())

    def open_sandbox(
        self, case: RealBugCase, context: KindContext, root: Path, sandbox_id: str
    ) -> AbstractContextManager[Path]:
        return nullcontext(root)

    def review_argv(
        self,
        case: RealBugCase,
        alias: str,
        sq_path: Path,
        out_path: Path,
        *,
        no_tools: bool = False,
        rules_path: Path | None = None,
    ) -> list[str]:
        return ["stub", alias, str(out_path)]


def test_code_kind_registered() -> None:
    assert isinstance(get_kind("code"), CodeKind)


def test_unknown_kind_raises() -> None:
    with pytest.raises(UnknownKindError, match="document"):
        get_kind("document")


def test_stub_kind_registers_and_restores() -> None:
    stub = StubKind()
    with registered_kind(RecallCaseKind.CODE, stub):
        assert get_kind(RecallCaseKind.CODE) is stub
    assert isinstance(get_kind(RecallCaseKind.CODE), CodeKind)


def test_code_review_argv() -> None:
    case = RealBugCase.build(**case_fields())
    argv = CodeKind().review_argv(case, "luna", Path("/bin/sq"), Path("/o/x.json"))
    assert argv == [
        "/bin/sq", "review", "code", "--diff", case.base, "--model", "luna",
        "--no-save", "--output", "file", "--output-path", "/o/x.json", "--cwd", ".",
    ]  # fmt: skip


def test_code_review_argv_with_reviewer_options() -> None:
    case = RealBugCase.build(**case_fields())
    plain = CodeKind().review_argv(case, "luna", Path("/bin/sq"), Path("/o/x.json"))
    argv = CodeKind().review_argv(
        case, "luna", Path("/bin/sq"), Path("/o/x.json"), no_tools=True, rules_path=Path("/h/r.md")
    )
    assert argv == [*plain, "--no-tools", "--rules", "/h/r.md"]
