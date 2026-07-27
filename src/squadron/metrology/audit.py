"""The audit harness: run the tech-debt-audit skill against a project.

Surface-agnostic — no Typer imports — matching the 320/321/322 core/CLI
split. The CLI shells in ``cli/commands/metrology.py`` are thin wrappers
over this module.

The instrument's identity travels with every run. ``audit_prompt_hash`` is
taken from the vendored skill file **actually used for that run**, not from
the canonical fork, so a fork/squadron divergence lands in the data even if
it escapes the CI sync guard. Audits taken under differing hashes are never
pooled — the same comparability discipline 322 canonized for judge
templates.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from squadron.config.manager import get_config, get_typed_config
from squadron.metrology.audit_parse import parse_audit_findings
from squadron.metrology.errors import (
    AuditBlockMalformedError,
    AuditBlockMissingError,
    MetrologyError,
)
from squadron.metrology.identity import derive_project_id
from squadron.metrology.models import AuditRun, ProjectId
from squadron.metrology.store import MetrologyStore, generate_audit_run_id
from squadron.providers.errors import ProviderRateLimitError
from squadron.skills.models import SkillSourceError
from squadron.skills.resolver import _resolve_bundled  # pyright: ignore[reportPrivateUsage]

_logger = logging.getLogger(__name__)

#: The pack and file the audit instrument lives in, resolved through the
#: skills resolver so the harness works whether or not ``sq skills install``
#: has been run.
_AUDIT_PACK = "analysis"
_AUDIT_SKILL_FILENAME = "tech-debt-audit.md"

#: Where the skill writes its audit file. It specifies
#: ``analysis/nnn-analysis.{project}.md`` but also cites
#: ``file-naming-conventions``, so in a cf-managed project the model
#: resolves that to ``project-documents/user/analysis/``. Both are real
#: locations and both are searched — observed in practice, not assumed.
_AUDIT_FILE_GLOBS = (
    "project-documents/user/analysis/*-analysis.*.md",
    "analysis/*-analysis.*.md",
)

#: Untracked paths that are the audit's own output rather than a change to
#: the code under measurement. Recognized so a variance series does not
#: refuse itself on the second run.
#:
#: Git collapses a wholly-untracked directory to a single ``?? dir/`` entry
#: instead of listing its files, and it collapses to the *shallowest*
#: untracked ancestor — so a repo where ``project-documents/`` itself is new
#: reports ``?? project-documents/``, not the analysis path beneath it.
#: Every prefix of both output locations is therefore matched.
_AUDIT_ARTIFACT_PATTERN = re.compile(
    r"^(?:"
    r"project-documents/(?:user/(?:analysis/(?:\d+-analysis\..+\.md)?)?)?"
    r"|analysis/(?:\d+-analysis\..+\.md)?"
    r")$"
)

#: Prefixed to the audit prompt to suppress the skill's repeat-run mode.
#:
#: The skill is a living document by default: on a repeat run it reads the
#: previous audit file and emits a RESOLVED/NEW diff. That behavior is
#: correct for interactive use and fatal for variance measurement — run 2
#: of a series would be anchored to run 1 rather than an independent
#: sample, biasing the measured floor toward zero.
#:
#: Defined once here and asserted against the skill file by
#: ``tests/metrology/test_audit_skill_sync.py``, so the string the harness
#: sends and the string the skill documents cannot drift apart.
INDEPENDENT_RUN_MARKER = "INDEPENDENT RUN: do not read or update any existing audit file"


class AuditSkillError(MetrologyError):
    """The tech-debt-audit skill file could not be resolved or read.

    Names the pack and the expected filename, since the fix is either
    installing the pack or repairing a damaged install — not something the
    caller can infer from a bare path.
    """


class AuditPreflightError(MetrologyError):
    """A project failed validation before any audit was attempted.

    Raised for a missing path, a non-git directory, an unresolvable HEAD, or
    (on a variance series) a dirty worktree. Distinct from run-time failures
    because it is detected at zero token cost and fails only that project —
    the rest of a campaign continues.
    """


def resolve_audit_skill() -> Path:
    """Return the path to the vendored tech-debt-audit skill file.

    Resolves through ``_resolve_bundled`` rather than a relative path, so it
    works from an editable checkout and an installed wheel alike, and so the
    harness and the sync guard exercise the same lookup.
    """
    try:
        pack_dir = _resolve_bundled(_AUDIT_PACK)
    except SkillSourceError as exc:
        raise AuditSkillError(
            f"Could not resolve the '{_AUDIT_PACK}' skill pack: {exc}. "
            f"Install it with 'sq skills install {_AUDIT_PACK}'."
        ) from exc

    skill_path = pack_dir / _AUDIT_SKILL_FILENAME
    if not skill_path.is_file():
        raise AuditSkillError(
            f"The '{_AUDIT_PACK}' pack has no {_AUDIT_SKILL_FILENAME} at {skill_path}. "
            f"Reinstall it with 'sq skills install {_AUDIT_PACK}'."
        )
    return skill_path


def audit_prompt_hash(skill_path: Path) -> str:
    """Return the SHA-256 of the skill file — the instrument's identity.

    Hashed from raw bytes, so any edit at all produces a different hash. An
    edit to the instrument invalidates comparison across the edit, and the
    baseline report groups on this rather than blending runs taken under
    different prompts.
    """
    try:
        return hashlib.sha256(skill_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise AuditSkillError(f"Could not read the audit skill at {skill_path}: {exc}") from exc


#: Tools the audit agent needs in the target repo. The skill runs `rg`,
#: `git log`, and language-native tooling (`ruff`, `npm audit`, ...), so Bash
#: is required — this is a strictly larger tool surface than a judge review.
_AUDIT_ALLOWED_TOOLS = ["Read", "Glob", "Grep", "Bash", "Task", "TodoWrite"]

#: The audit runs unattended against an external repo; the skill's protocol
#: is the authority on what it may do, so permission prompts are bypassed
#: exactly as the code-review template does.
_AUDIT_PERMISSION_MODE = "bypassPermissions"


#: How often to emit a liveness update while an audit runs. The audit does
#: tens to hundreds of tool calls, so reporting every one would be noise;
#: reporting none at all makes a 20-minute run look hung.
_PROGRESS_EVERY_N_TOOL_EVENTS = 10


@dataclass(frozen=True)
class AuditProgress:
    """Liveness signal emitted while an audit is still working.

    Carries only what a surface needs to show the run is alive. The core
    emits these; rendering them is the CLI's job, so this module stays
    surface-agnostic.
    """

    tool_events: int
    bytes_received: int


#: Called with an ``AuditProgress`` as the run proceeds. Optional — an
#: unattended or programmatic caller passes nothing and sees no output.
ProgressCallback = Callable[[AuditProgress], None]


class AuditRunFailure(StrEnum):
    """Why a run failed, for logging and honest campaign summaries.

    Every value means the same thing for persistence — **nothing was
    written** — and differs only in what the operator should do about it.
    """

    TIMEOUT = "timeout"
    STREAM_ERROR = "stream_error"
    BLOCK_MISSING = "block_missing"
    BLOCK_MALFORMED = "block_malformed"
    #: The provider rate-limited the run and retries were exhausted.
    #: Distinct because it says nothing about the audit or the project —
    #: every remaining run in a campaign will fail the same way until the
    #: limit resets, so the caller should stop rather than continue.
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class AuditRunResult:
    """The outcome of one attempted audit.

    Exactly one of ``run`` / ``failure`` is set. A failed run persists
    nothing, so the caller reports it and continues the campaign rather than
    treating it as a zero-finding data point.
    """

    project_path: Path
    run: AuditRun | None = None
    failure: AuditRunFailure | None = None
    detail: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.run is not None


@dataclass(frozen=True)
class PreflightResult:
    """A project that passed pre-flight: its identity and pinned commit."""

    project_path: Path
    project_id: ProjectId
    commit_sha: str


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command in ``cwd``, capturing output. Never raises on exit code."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def find_audit_file(project_path: Path, *, newer_than: float | None = None) -> Path | None:
    """Return the audit file the skill just wrote, or ``None``.

    The skill writes its findings to a **file**, not to the response stream
    — the stream carries tool narration and a brief closing remark. Reading
    the file is therefore the only way to obtain the audit; a harness that
    parsed the response would see a few dozen bytes of pleasantries.

    ``newer_than`` (a Unix mtime) restricts the search to files written by
    *this* run, so a stale audit from a previous session can never be
    mistaken for a fresh result — which would silently persist old findings
    under a new run id.
    """
    candidates: list[Path] = []
    for pattern in _AUDIT_FILE_GLOBS:
        candidates.extend(project_path.glob(pattern))

    fresh = [
        path
        for path in candidates
        if path.is_file() and (newer_than is None or path.stat().st_mtime >= newer_than)
    ]
    if not fresh:
        return None
    return max(fresh, key=lambda path: path.stat().st_mtime)


def _is_audit_artifact(status_line: str) -> bool:
    """Whether a ``git status --porcelain`` line is the audit's own output.

    The skill writes ``analysis/nnn-analysis.{project}.md`` into the repo it
    audits. That file is a *product* of the measurement, not a change to the
    code being measured, so it must not make the next run in a series look
    like it is auditing changed code.

    Matched narrowly — only untracked (``??``) paths under ``analysis/``. A
    modification to a tracked file, even under ``analysis/``, is a real
    change and still refuses.
    """
    stripped = status_line.strip()
    if not stripped.startswith("??"):
        return False
    path = stripped[2:].strip().strip('"')
    return bool(_AUDIT_ARTIFACT_PATTERN.match(path))


def preflight_project(
    project_path: Path,
    *,
    require_clean: bool,
    expected_sha: str | None = None,
    cwd: str = ".",
) -> PreflightResult:
    """Validate a project before any token is spent on it.

    Every check here runs **before** an agent is created, so a campaign
    misconfigured across four projects fails in seconds rather than after
    hours of audits. Each failure raises, and the caller is expected to fail
    that project only and continue the campaign.

    ``require_clean`` is set for variance runs: a floor measured across a
    code change is not a floor. The check deliberately **ignores the audit's
    own output file**, because the skill writes one into every repo it
    audits — without that exemption, run 1 of a series would dirty the tree
    and every later run would be refused, leaving the floor unmeasurable.

    ``expected_sha`` pins the series after its first run: later runs assert
    HEAD has not moved rather than re-deriving it. Together these make the
    precondition precise — unchanged *source* at one commit, not an
    untouched directory.

    Raises:
        AuditPreflightError: path, git-repo, worktree-cleanliness, or a
            HEAD that moved mid-series.
        MetrologyIdentityError: identity is underivable (message carries its
            own ``sq config set`` remediation, which is left intact).
    """
    if not project_path.exists():
        raise AuditPreflightError(f"Project path does not exist: {project_path}")
    if not project_path.is_dir():
        raise AuditPreflightError(f"Project path is not a directory: {project_path}")

    inside = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=project_path)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise AuditPreflightError(
            f"Project path is not a git repository: {project_path}. "
            "The audit pins a commit SHA, so an unversioned directory cannot be measured."
        )

    head = _run_git(["rev-parse", "HEAD"], cwd=project_path)
    if head.returncode != 0 or not head.stdout.strip():
        raise AuditPreflightError(
            f"Could not resolve HEAD in {project_path}: {head.stderr.strip() or 'no commits?'}"
        )
    commit_sha = head.stdout.strip()

    if expected_sha is not None and commit_sha != expected_sha:
        raise AuditPreflightError(
            f"Refusing to continue the variance series in {project_path}: HEAD moved "
            f"from {expected_sha[:8]} to {commit_sha[:8]} mid-series. A floor measured "
            "across a commit is not a floor."
        )

    # Propagates with its own remediation text intact — do not wrap it.
    project_id = derive_project_id(cwd=str(project_path))

    if require_clean:
        status = _run_git(["status", "--porcelain"], cwd=project_path)
        if status.returncode != 0:
            raise AuditPreflightError(
                f"Could not read git status in {project_path}: {status.stderr.strip()}"
            )
        offending = [
            line for line in status.stdout.splitlines() if line.strip() and not _is_audit_artifact(line)
        ]
        if offending:
            shown = ", ".join(line.strip() for line in offending[:5])
            raise AuditPreflightError(
                f"Refusing a variance series in {project_path}: the worktree is dirty "
                f"({shown}{', ...' if len(offending) > 5 else ''}). A noise floor measures "
                "repeated audits of unchanged code, so the commit must be pinned. "
                "Commit or stash your changes first."
            )

    return PreflightResult(
        project_path=project_path,
        project_id=project_id,
        commit_sha=commit_sha,
    )


def extract_audit_protocol(body: str) -> str:
    """Return just the executable protocol from the skill file.

    The file is a *skill definition*, not a prompt. It opens with YAML
    frontmatter (including ``disable-model-invocation: true``) and closes
    with a "Project documentation" half addressed to humans installing or
    contributing to the skill. The file states the boundary itself:
    everything through the ``---`` divider is the protocol Claude executes;
    the rest is documentation.

    Sending the whole file reads as "here is a document" rather than "do
    this now" — which produced a ~2KB acknowledgement instead of an audit.
    So the frontmatter and the human half are stripped, and only the
    protocol is sent.

    Falls back to the full body if the expected structure is absent, since a
    reworded skill should degrade to the old behavior rather than send an
    empty prompt.
    """
    remainder = body
    if remainder.lstrip().startswith("<!--"):
        _, _, remainder = remainder.partition("-->")

    stripped = remainder.lstrip()
    if stripped.startswith("---"):
        # Drop the YAML frontmatter block.
        after_open = stripped[3:]
        _, sep, after_close = after_open.partition("\n---")
        if sep:
            remainder = after_close

    # The protocol runs until the divider that introduces the human docs.
    # If that divider is absent the whole remainder is protocol — the
    # frontmatter strip above still stands, since a skill with no human
    # half is not a reason to send its YAML header to the model.
    marker = "\n# Project documentation"
    protocol, sep, _ = remainder.partition(marker)
    if not sep:
        return remainder.strip() or body.strip()

    # That divider is preceded by a bare '---' rule; trim it.
    protocol = protocol.rstrip()
    if protocol.endswith("---"):
        protocol = protocol[: -len("---")].rstrip()
    return protocol.strip()


#: Framing that turns the protocol document into an instruction to execute.
#: Without it the model treats a pasted protocol as reference material.
_EXECUTE_INSTRUCTION = (
    "Perform a tech debt audit of the repository in your current working "
    "directory, following the protocol below exactly. Execute it now — the "
    "protocol is your instruction, not a document to summarize. Complete "
    "every phase, including the machine-readable findings block, which is "
    "mandatory and must be the last thing in the audit file you write."
)


def build_audit_prompt(skill_path: Path, *, independent_run: bool) -> str:
    """Return the audit prompt: an execute instruction plus the protocol.

    When ``independent_run`` is True the prompt is prefixed with
    ``INDEPENDENT_RUN_MARKER``, which the skill documents as the condition
    under which its repeat-run clause does not apply. Variance runs set it so
    each run is an independent sample; a plain baseline run does not, leaving
    the living-document behavior interactive users get.
    """
    try:
        body = skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AuditSkillError(f"Could not read the audit skill at {skill_path}: {exc}") from exc

    protocol = extract_audit_protocol(body)
    prompt = f"{_EXECUTE_INSTRUCTION}\n\n---\n\n{protocol}"

    if not independent_run:
        return prompt
    return f"{INDEPENDENT_RUN_MARKER}\n\n{prompt}"


def resolve_audit_profile(profile: str | None, *, cwd: str = ".") -> str:
    """Resolve the provider profile for an audit run.

    Explicit argument wins, then ``metrology.audit_profile``, then the
    review default. No hard-coded provider name at the call site.
    """
    if profile is not None:
        return profile
    configured = get_config("metrology.audit_profile", cwd=cwd)
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    review_default = get_config("default_review_profile", cwd=cwd)
    if isinstance(review_default, str) and review_default.strip():
        return review_default.strip()
    raise AuditSkillError(
        "No provider profile for the audit run. Set one with "
        "'sq config set metrology.audit_profile <profile>' or pass --profile."
    )


async def _collect_audit_output(
    agent: object,
    prompt: str,
    agent_name: str,
    on_progress: ProgressCallback | None = None,
) -> str:
    """Drive the agent stream and return its prose, tool narration filtered.

    Mirrors the review client's narration filter: SDK providers emit a
    duplicate ResultMessage plus tool_use/tool_result messages that narrate
    the agent's work. The audit's findings block sits in the prose, and
    mixing narration into it would corrupt the parse.

    Those filtered narration events are, however, the only evidence the
    agent is alive — a full audit takes 5-20 minutes and emits no prose
    until it finishes. So they are *counted* and reported through
    ``on_progress`` rather than simply discarded: an unattended run that
    prints nothing for twenty minutes is indistinguishable from a hang.
    """
    from squadron.core.models import SDK_RESULT_TYPE, Message, MessageType

    message = Message(
        sender="metrology-audit",
        recipients=[agent_name],
        content=prompt,
        message_type=MessageType.chat,
    )
    parts: list[str] = []
    tool_events = 0
    async for response in agent.handle_message(message):  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        sdk_type = response.metadata.get("sdk_type")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if sdk_type in ("tool_use", "tool_result"):
            tool_events += 1
            if on_progress is not None and tool_events % _PROGRESS_EVERY_N_TOOL_EVENTS == 0:
                on_progress(
                    AuditProgress(tool_events=tool_events, bytes_received=sum(len(p) for p in parts))
                )
            continue
        if sdk_type == SDK_RESULT_TYPE:
            continue
        parts.append(response.content)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    return "\n".join(parts)


async def run_audit(
    project_path: Path,
    *,
    store: MetrologyStore,
    profile: str | None = None,
    model: str | None = None,
    independent_run: bool = False,
    require_clean: bool = False,
    expected_sha: str | None = None,
    on_progress: ProgressCallback | None = None,
    cwd: str = ".",
) -> AuditRunResult:
    """Run one audit against ``project_path`` and persist it, or persist nothing.

    The governing rule is one run = one persisted unit. Every failure path
    below persists **nothing** and returns a typed failure, so a hung or
    truncated run can never enter a noise floor as a spuriously low finding
    count — which would bias the floor downward, the same direction the
    skill's repeat-run mode would have.

    Pre-flight runs first, before an agent exists, so a bad project costs
    zero tokens. The caller is expected to continue the campaign on failure.
    """
    from squadron.core.models import AgentConfig
    from squadron.providers.loader import ensure_provider_loaded
    from squadron.providers.profiles import get_profile
    from squadron.providers.registry import get_provider

    # --- Pre-flight: everything here precedes token spend --------------
    preflight = preflight_project(
        project_path,
        require_clean=require_clean,
        expected_sha=expected_sha,
        cwd=cwd,
    )
    skill_path = resolve_audit_skill()
    prompt_hash = audit_prompt_hash(skill_path)
    prompt = build_audit_prompt(skill_path, independent_run=independent_run)
    resolved_profile = resolve_audit_profile(profile, cwd=cwd)
    timeout_s = int(get_typed_config("metrology.audit_timeout_s", int, cwd=cwd))

    provider_profile = get_profile(resolved_profile)
    ensure_provider_loaded(provider_profile.provider)
    provider = get_provider(provider_profile.provider)

    agent_name = f"metrology-audit-{preflight.project_id.value.replace('/', '-')}"
    config = AgentConfig(
        name=agent_name,
        agent_type=provider_profile.provider,
        provider=provider_profile.provider,
        model=model,
        instructions="",
        api_key=None,
        base_url=provider_profile.base_url,
        cwd=str(project_path),
        allowed_tools=_AUDIT_ALLOWED_TOOLS,
        permission_mode=_AUDIT_PERMISSION_MODE,
        setting_sources=["project"],
        credentials={
            "api_key_env": provider_profile.api_key_env,
            "default_headers": provider_profile.default_headers,
            "mode": "client",
        },
    )

    _logger.info(
        "Audit %s (profile=%s, provider=%s, sha=%s, independent=%s, timeout=%ds)",
        preflight.project_id.value,
        resolved_profile,
        provider_profile.provider,
        preflight.commit_sha[:8],
        independent_run,
        timeout_s,
    )

    # --- Execution: bounded, and failing closed -------------------------
    # Stamped before the agent starts so only a file this run wrote counts;
    # a stale audit from a previous session must never be persisted under a
    # fresh run id. One second of slack absorbs filesystem mtime coarseness.
    started_at = time.time() - 1.0
    agent = await provider.create_agent(config)
    try:
        raw_output = await asyncio.wait_for(
            _collect_audit_output(agent, prompt, agent_name, on_progress),
            timeout=timeout_s,
        )
    except TimeoutError:
        _logger.warning(
            "Audit timed out after %ds for %s (sha %s); persisting nothing.",
            timeout_s,
            preflight.project_id.value,
            preflight.commit_sha[:8],
        )
        return AuditRunResult(
            project_path=project_path,
            failure=AuditRunFailure.TIMEOUT,
            detail=f"exceeded metrology.audit_timeout_s ({timeout_s}s)",
        )
    except ProviderRateLimitError as exc:
        # Says nothing about this project or this audit — the provider is
        # throttling. Reported distinctly so a campaign can stop instead of
        # burning its remaining projects on runs that will fail identically.
        _logger.warning(
            "Audit rate limited for %s after provider retries; persisting nothing. %s",
            preflight.project_id.value,
            exc,
        )
        return AuditRunResult(
            project_path=project_path,
            failure=AuditRunFailure.RATE_LIMITED,
            detail=str(exc),
        )
    except Exception as exc:
        # Any stream failure — peer disconnect, API error, provider fault.
        # Logged with its type so a systematic provider problem is
        # distinguishable from a one-off, then swallowed so the campaign
        # continues; nothing is persisted either way.
        _logger.warning(
            "Audit stream failed for %s: %s: %s; persisting nothing.",
            preflight.project_id.value,
            type(exc).__name__,
            exc,
        )
        return AuditRunResult(
            project_path=project_path,
            failure=AuditRunFailure.STREAM_ERROR,
            detail=f"{type(exc).__name__}: {exc}",
        )
    finally:
        await agent.shutdown()

    # --- Locate the audit file: the findings live there, not in the stream
    audit_file = find_audit_file(project_path, newer_than=started_at)
    if audit_file is None:
        _logger.warning(
            "Audit for %s wrote no audit file (%d bytes of narration received); "
            "persisting nothing. Expected one of: %s",
            preflight.project_id.value,
            len(raw_output),
            ", ".join(_AUDIT_FILE_GLOBS),
        )
        return AuditRunResult(
            project_path=project_path,
            failure=AuditRunFailure.BLOCK_MISSING,
            detail=f"no audit file written under {' or '.join(_AUDIT_FILE_GLOBS)}",
        )

    try:
        raw_output = audit_file.read_text(encoding="utf-8")
    except OSError as exc:
        _logger.warning("Could not read audit file %s: %s; persisting nothing.", audit_file, exc)
        return AuditRunResult(
            project_path=project_path,
            failure=AuditRunFailure.BLOCK_MISSING,
            detail=f"audit file unreadable: {exc}",
        )

    # --- Parse: absent and malformed are different failures -------------
    try:
        findings, unnormalized = parse_audit_findings(raw_output)
    except AuditBlockMissingError as exc:
        _logger.warning(
            "Audit for %s emitted no findings block (%d bytes received); persisting nothing. %s",
            preflight.project_id.value,
            len(raw_output),
            exc,
        )
        return AuditRunResult(
            project_path=project_path,
            failure=AuditRunFailure.BLOCK_MISSING,
            detail=str(exc),
        )
    except AuditBlockMalformedError as exc:
        _logger.warning(
            "Audit for %s emitted a malformed findings block; persisting nothing. %s",
            preflight.project_id.value,
            exc,
        )
        return AuditRunResult(
            project_path=project_path,
            failure=AuditRunFailure.BLOCK_MALFORMED,
            detail=str(exc),
        )

    # --- Persist: a complete run, or nothing ----------------------------
    run = AuditRun(
        run_id=generate_audit_run_id(),
        project_id=preflight.project_id,
        commit_sha=preflight.commit_sha,
        audit_prompt_hash=prompt_hash,
        model=model or provider_profile.provider,
        measured_at=datetime.now(UTC),
        findings=findings,
        unnormalized_count=unnormalized,
    )
    store.write_audit_run(run)
    _logger.info(
        "Audit persisted %s: %d findings (%d unnormalized) for %s at %s",
        run.run_id,
        len(findings),
        unnormalized,
        run.project_id.value,
        run.commit_sha[:8],
    )
    return AuditRunResult(project_path=project_path, run=run)
