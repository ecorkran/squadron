"""A fixture-backed ``AdoptionClient`` for onboard and CLI tests."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from squadron.integrations.cf_adoption import (
    DetectionReport,
    InitReport,
    parse_detect_report,
    parse_init_report,
)
from tests.fixtures.cf_adoption import load_fixture


class FakeAdoptionClient:
    """Returns recorded cf reports and records every call as ``(name, args)``.

    ``raises`` is raised from every method after the call is recorded. Error
    fixtures (envelopes) raise through the real parsers, as cf's would.
    """

    def __init__(
        self,
        detect_fixture: str = "detect-brownfield",
        registered: bool = True,
        init_fixture: str = "init-ok",
        prompt_text: str = "ADOPTION PROMPT",
        raises: Exception | None = None,
    ) -> None:
        self._detect_fixture = detect_fixture
        self._registered = registered
        self._init_fixture = init_fixture
        self._prompt_text = prompt_text
        self._raises = raises
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    @property
    def call_names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def _record(self, name: str, *args: object) -> None:
        self.calls.append((name, args))
        if self._raises is not None:
            raise self._raises

    def detect(self, root: Path) -> DetectionReport:
        self._record("detect", root)
        return parse_detect_report(cast("dict[str, object]", load_fixture(self._detect_fixture)))

    def is_registered(self, root: Path) -> bool:
        self._record("is_registered", root)
        return self._registered

    def init_project(self, root: Path, ide: str | None) -> InitReport:
        self._record("init_project", root, ide)
        return parse_init_report(cast("dict[str, object]", load_fixture(self._init_fixture)))

    def decline(self, root: Path) -> None:
        self._record("decline", root)

    def adoption_prompt(self, root: Path, comprehension: Path) -> str:
        self._record("adoption_prompt", root, comprehension)
        return self._prompt_text

    def register_comprehension(self, root: Path, comprehension: Path) -> None:
        self._record("register_comprehension", root, comprehension)
