"""The case-kind seam (D14): a protocol, a registry keyed by ``kind``, and ``CodeKind``.

``cases add``, the stage runner and the import look a kind up here and never branch on it.
432 adds ``DocumentKind`` and a registry entry without changing them.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

from squadron.benchmark.recall.case_models import (
    CaseFileError,
    build_case,
    derive_locations,
    load_case_file,
)
from squadron.benchmark.recall.review_sandbox import review_sandbox
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.project_id import ProjectId
from squadron.metrology.recall_case_models import RealBugCase, RecallCaseKind


class UnknownKindError(Exception):
    """No kind is registered under the case's ``kind``."""


@dataclass(frozen=True)
class KindContext:
    """What a kind needs to validate a file or open a sandbox."""

    runner: ProcessRunner
    fetch_timeout: float
    project_id: ProjectId


class RecallKind(Protocol):
    def validate(self, case_file: Path, context: KindContext) -> RealBugCase:
        """Kind-specific schema and checks; raises ``CaseFileError``."""
        ...

    def open_sandbox(
        self, case: RealBugCase, context: KindContext, root: Path, sandbox_id: str
    ) -> AbstractContextManager[Path]:
        """The tree a review reads; raises ``SandboxError`` on enter."""
        ...

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
        """The review command, run with cwd = the sandbox tree.

        *no_tools* and *rules_path* are the reviewer's recipe options: a review without
        tools, and a rules file to add to the review's rules.
        """
        ...


class CodeKind:
    """A merged code diff, reviewed with the production ``sq review code`` (D1, D6, D7)."""

    def validate(self, case_file: Path, context: KindContext) -> RealBugCase:
        spec = load_case_file(case_file)
        bugs = derive_locations(case_file, spec, context.runner, context.fetch_timeout)
        return build_case(spec, bugs, context.project_id)

    def open_sandbox(
        self, case: RealBugCase, context: KindContext, root: Path, sandbox_id: str
    ) -> AbstractContextManager[Path]:
        return review_sandbox(
            repo=Path(case.repo).expanduser(),
            base=case.base,
            head=case.head,
            runner=context.runner,
            root=root,
            sandbox_id=sandbox_id,
            fetch_timeout=context.fetch_timeout,
        )

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
        argv = [
            str(sq_path),
            "review",
            "code",
            "--diff",
            case.base,
            "--model",
            alias,
            "--no-save",
            "--output",
            "file",
            "--output-path",
            str(out_path),
            # The call runs with cwd = the sandbox; without this a seeded config `cwd` key
            # (the user's config.toml is copied into the scrubbed home) points elsewhere.
            "--cwd",
            ".",
        ]
        if no_tools:
            argv.append("--no-tools")
        if rules_path is not None:
            argv.extend(["--rules", str(rules_path)])
        return argv


_REGISTRY: dict[RecallCaseKind, RecallKind] = {RecallCaseKind.CODE: CodeKind()}


def get_kind(kind: RecallCaseKind | str) -> RecallKind:
    """The registered kind; an unknown value raises ``UnknownKindError``."""
    try:
        return _REGISTRY[RecallCaseKind(kind)]
    except (ValueError, KeyError) as exc:
        raise UnknownKindError(f"no recall case kind registered for {kind!r}") from exc


def register_kind(kind: RecallCaseKind, implementation: RecallKind) -> None:
    _REGISTRY[kind] = implementation


@contextmanager
def registered_kind(kind: RecallCaseKind, implementation: RecallKind) -> Iterator[None]:
    """Register *implementation* for the block, then restore the previous entry."""
    previous = _REGISTRY.get(kind)
    _REGISTRY[kind] = implementation
    try:
        yield
    finally:
        if previous is None:
            del _REGISTRY[kind]
        else:
            _REGISTRY[kind] = previous


def read_case_kind(case_file: Path) -> str:
    """The ``kind`` field of a case file, read before kind-specific validation."""
    try:
        raw: Any = yaml.safe_load(case_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CaseFileError(case_file, f"unreadable: {exc}") from exc
    if not isinstance(raw, dict) or "kind" not in raw:
        raise CaseFileError(case_file, "kind: Field required")
    return str(raw["kind"])  # pyright: ignore[reportUnknownArgumentType]
