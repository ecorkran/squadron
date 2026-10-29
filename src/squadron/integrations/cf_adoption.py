"""Typed access to cf's brownfield-adoption reports (slice 440 D5–D8).

Parses the reports cf 271 defines: ``cf detect --json`` (D3), the shared error
envelope (D5) and ``cf init --json`` (D8). Every report is read through
``_checked_report`` so an unknown version or an error envelope fails the same
way for both commands, and an unknown outcome never falls back to a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, Self, cast

from squadron.config.keys import CF_CLI_TIMEOUT_KEY
from squadron.config.manager import get_positive_int_config
from squadron.integrations.context_forge import ContextForgeClient, ContextForgeError

#: ``reportVersion`` of ``cf detect --json`` this module understands (cf 271 D3).
DETECT_REPORT_VERSION = 1
#: ``reportVersion`` of ``cf init --json`` this module understands (cf 271 D8).
INIT_REPORT_VERSION = 1
#: cf's prompt key for the brownfield adoption prompt.
ADOPTION_PROMPT_KEY = "brownfield-adoption"
#: The cf config key holding the opt-out state, and the value that opts out.
ADOPTION_STATE_KEY = "adoption.state"
ADOPTION_STATE_DECLINED = "declined"
#: ``cf init --json``'s error code for a worktree of a registered project (cf 271 D8).
WORKTREE_ERROR_CODE = "worktree-of-registered-project"
#: ``InitStep.status`` of a step that failed (the others are ``ok`` and ``skipped``).
STEP_STATUS_FAILED = "failed"


class AdoptionOutcome(StrEnum):
    """cf's five adoption outcomes, exactly as ``cf detect`` reports them."""

    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"
    ADOPTION_INCOMPLETE = "adoption-incomplete"
    ALREADY_PLANNED = "already-planned"
    OPTED_OUT = "opted-out"


class ContextForgeReportError(ContextForgeError):
    """cf answered with its error envelope (``{"error": {"code", "message"}}``)."""

    def __init__(self, command: str, code: str, message: str) -> None:
        self.command = command
        self.code = code
        self.message = message
        super().__init__(f"cf {command}: {code}: {message}")


@dataclass(frozen=True)
class DetectionArtifacts:
    """Planning artifacts cf found; paths are relative to the project root."""

    concept: str | None
    derived_architectures: tuple[str, ...]
    existing_state_plan: str | None


@dataclass(frozen=True)
class DetectionReport:
    """``cf detect --json`` result."""

    outcome: AdoptionOutcome
    artifacts: DetectionArtifacts
    notices: tuple[str, ...]


@dataclass(frozen=True)
class InitStep:
    """One step of ``cf init``: ``status`` is cf's ``ok``, ``skipped`` or ``failed``."""

    step: str
    status: str
    message: str | None


@dataclass(frozen=True)
class InitReport:
    """``cf init --json`` result; ``ok`` is false when any step failed."""

    project_name: str
    registration: str
    steps: tuple[InitStep, ...]
    notices: tuple[str, ...]
    ok: bool


def _checked_report(data: dict[str, Any], expected_version: int, command: str) -> dict[str, Any]:
    """Return *data* if it is a current-version report, else raise.

    The version is checked before the envelope: an unknown version may carry a
    different envelope (D7).

    Raises:
        ContextForgeError: ``reportVersion`` is missing or not *expected_version*.
        ContextForgeReportError: *data* is cf's error envelope.
    """
    version = data.get("reportVersion")
    if version != expected_version:
        shown = "missing" if version is None else repr(version)
        raise ContextForgeError(
            f"cf {command}: unsupported reportVersion {shown} "
            f"(this sq reads version {expected_version}); sq and cf are out of step"
        )
    if "error" in data:
        error = data["error"]
        if not isinstance(error, dict) or not {"code", "message"} <= error.keys():
            raise ContextForgeError(f"cf {command}: malformed error object: {error!r}")
        envelope = cast("dict[str, object]", error)
        raise ContextForgeReportError(command, str(envelope["code"]), str(envelope["message"]))
    return data


def _field(data: dict[str, Any], key: str, command: str) -> Any:
    """``data[key]``, or a ``ContextForgeError`` naming the missing field."""
    if key not in data:
        raise ContextForgeError(f"cf {command}: report has no '{key}' field")
    return data[key]


def _strings(raw: object, key: str, command: str) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ContextForgeError(f"cf {command}: '{key}' is not a list")
    return tuple(str(item) for item in cast("list[object]", raw))


def _optional_path(raw: object) -> str | None:
    return None if raw is None else str(raw)


def parse_detect_report(data: dict[str, Any]) -> DetectionReport:
    """Parse a ``cf detect --json`` payload.

    Raises:
        ContextForgeError: unknown version or outcome, or a missing field.
        ContextForgeReportError: the payload is an error envelope.
    """
    command = "detect"
    report = _checked_report(data, DETECT_REPORT_VERSION, command)
    outcome_raw = str(_field(report, "outcome", command))
    try:
        outcome = AdoptionOutcome(outcome_raw)
    except ValueError as exc:
        raise ContextForgeError(f"cf {command}: unknown outcome '{outcome_raw}'") from exc
    artifacts = _field(report, "artifacts", command)
    if not isinstance(artifacts, dict):
        raise ContextForgeError(f"cf {command}: 'artifacts' is not an object")
    found = cast("dict[str, Any]", artifacts)
    return DetectionReport(
        outcome=outcome,
        artifacts=DetectionArtifacts(
            concept=_optional_path(_field(found, "concept", command)),
            derived_architectures=_strings(
                _field(found, "derivedArchitectures", command), "derivedArchitectures", command
            ),
            existing_state_plan=_optional_path(_field(found, "existingStatePlan", command)),
        ),
        notices=_strings(_field(report, "notices", command), "notices", command),
    )


def parse_init_report(data: dict[str, Any]) -> InitReport:
    """Parse a ``cf init --json`` payload (``ok: false`` is a report, not an error).

    Raises:
        ContextForgeError: unknown version, or a missing or malformed field.
        ContextForgeReportError: the payload is an error envelope.
    """
    command = "init"
    report = _checked_report(data, INIT_REPORT_VERSION, command)
    steps_raw = _field(report, "steps", command)
    if not isinstance(steps_raw, list):
        raise ContextForgeError(f"cf {command}: 'steps' is not a list")
    steps: list[InitStep] = []
    for item in cast("list[object]", steps_raw):
        if not isinstance(item, dict):
            raise ContextForgeError(f"cf {command}: a 'steps' entry is not an object")
        raw = cast("dict[str, Any]", item)
        message = raw.get("message")
        steps.append(
            InitStep(
                step=str(_field(raw, "step", command)),
                status=str(_field(raw, "status", command)),
                message=None if message is None else str(message),
            )
        )
    return InitReport(
        project_name=str(_field(report, "projectName", command)),
        registration=str(_field(report, "registration", command)),
        steps=tuple(steps),
        notices=_strings(_field(report, "notices", command), "notices", command),
        ok=bool(_field(report, "ok", command)),
    )


class AdoptionClient(Protocol):
    """What ``build_onboard_report`` and the ``sq onboard`` commands need from cf."""

    def detect(self, root: Path) -> DetectionReport: ...

    def is_registered(self, root: Path) -> bool: ...

    def init_project(self, root: Path, ide: str | None) -> InitReport: ...

    def decline(self, root: Path) -> None: ...

    def adoption_prompt(self, root: Path, comprehension: Path) -> str: ...

    def register_comprehension(self, root: Path, comprehension: Path) -> None: ...


class CfAdoptionClient:
    """``AdoptionClient`` over the cf CLI; every call is bounded by *timeout_s*."""

    def __init__(self, timeout_s: int) -> None:
        self._timeout_s = timeout_s

    @classmethod
    def from_config(cls, cwd: str = ".") -> Self:
        """Build with the timeout from ``cf.cli_timeout_s``."""
        return cls(get_positive_int_config(CF_CLI_TIMEOUT_KEY, cwd=cwd))

    def _cf(self, cwd: Path | None = None) -> ContextForgeClient:
        return ContextForgeClient(cwd=cwd, timeout_s=self._timeout_s)

    def detect(self, root: Path) -> DetectionReport:
        """``cf detect --path <root> --json`` (D4: *root* is judged as given)."""
        data = self._cf().run_report(["detect", "--path", str(root), "--json"])
        return parse_detect_report(data)

    def is_registered(self, root: Path) -> bool:
        """True when a cf project's ``projectPath`` is exactly *root* (D5).

        cf resolves a directory to the nearest registered ancestor, so its own
        resolution would call a monorepo subdirectory registered.
        """
        entries = self._cf().run_json(["project", "list", "--json"])
        if not isinstance(entries, list):
            raise ContextForgeError("cf project list --json: output is not a list")
        wanted = root.resolve()
        for entry in cast("list[object]", entries):
            if not isinstance(entry, dict):
                raise ContextForgeError("cf project list --json: an entry is not an object")
            path = cast("dict[str, Any]", entry).get("projectPath")
            if path is not None and Path(str(path)).resolve() == wanted:
                return True
        return False

    def init_project(self, root: Path, ide: str | None) -> InitReport:
        """``cf init --json [--ide <ide>]`` run in *root*; ``ok: false`` is returned."""
        args = ["init", "--json", *(["--ide", ide] if ide is not None else [])]
        return parse_init_report(self._cf(root).run_report(args))

    def decline(self, root: Path) -> None:
        """Record the opt-out in cf (D6)."""
        self._cf(root).run(
            ["config", "set", ADOPTION_STATE_KEY, ADOPTION_STATE_DECLINED, "--project", str(root)]
        )

    def adoption_prompt(self, root: Path, comprehension: Path) -> str:
        """cf's adoption prompt for *root*, with the comprehension doc's absolute path."""
        return self._cf().run(
            [
                "prompt",
                "get",
                ADOPTION_PROMPT_KEY,
                "--path",
                str(root),
                "--comprehension",
                str(comprehension.resolve()),
            ]
        )

    def register_comprehension(self, root: Path, comprehension: Path) -> None:
        """``cf set comprehension <doc>`` in *root*; cf stores the path root-relative."""
        self._cf(root).run(["set", "comprehension", str(comprehension.resolve())])
