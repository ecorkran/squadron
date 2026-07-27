"""Audit harness behavior — the failure modes are the point.

Every test here runs against a **stubbed agent**: no provider is contacted
and no tokens are spent. That is deliberate and worth preserving. The
expensive part of this slice is the real variance campaign; the harness's
correctness must be establishable without it.

The load-bearing assertions are about what does *not* happen. A timeout, a
mid-stream exception, and an absent or malformed findings block must each
persist **zero** records, because a partially-recorded run would enter a
noise floor as a spuriously low finding count and bias the floor downward.
And pre-flight failures must not construct an agent at all, which is what
makes a misconfigured campaign cost nothing.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from squadron.core.models import Message
from squadron.metrology.audit import (
    AuditRunFailure,
    run_audit,
)
from squadron.metrology.store import MetrologyStore

# --------------------------------------------------------------------------
# Stub agent / provider plumbing
# --------------------------------------------------------------------------


@dataclass
class _StubResponse:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


class _StubAgent:
    """An agent that replays a scripted outcome instead of calling a provider."""

    def __init__(self, *, output: str | None, raises: Exception | None, hang: bool) -> None:
        self._output = output
        self._raises = raises
        self._hang = hang
        self.shutdown_called = False

    async def handle_message(self, message: Message) -> AsyncIterator[_StubResponse]:
        if self._raises is not None:
            # Yield some prose first so the failure is genuinely mid-stream.
            yield _StubResponse(content="## Phase 1: Orient\n")
            raise self._raises
        if self._hang:
            import asyncio

            await asyncio.sleep(3600)
        yield _StubResponse(content=self._output or "")

    async def shutdown(self) -> None:
        self.shutdown_called = True


@dataclass
class _StubProvider:
    """Records every agent it creates so a test can assert none were."""

    agent: _StubAgent | None = None
    created: list[_StubAgent] = field(default_factory=list[_StubAgent])

    async def create_agent(self, config: object) -> _StubAgent:
        agent = self.agent if self.agent is not None else _StubAgent(output="", raises=None, hang=False)
        self.created.append(agent)
        return agent


@dataclass
class _StubProfile:
    provider: str = "stub"
    base_url: str | None = None
    api_key_env: str | None = None
    default_headers: dict[str, str] = field(default_factory=dict[str, str])


@pytest.fixture
def stub_provider() -> Iterator[_StubProvider]:
    """Patch the provider plumbing run_audit resolves at call time."""
    provider = _StubProvider()
    with (
        patch("squadron.providers.profiles.get_profile", return_value=_StubProfile()),
        patch("squadron.providers.loader.ensure_provider_loaded"),
        patch("squadron.providers.registry.get_provider", return_value=provider),
        patch("squadron.metrology.audit.resolve_audit_profile", return_value="stub"),
    ):
        yield provider


_FINDINGS_BLOCK = """
<!-- squadron:findings:begin v1 -->
```yaml
findings:
  - id: F001
    category: architectural-decay
    location: src/x.py:12
    severity: Critical
    effort: L
    summary: God module
  - id: F002
    category: test-debt
    location: src/y.py:4
    severity: Medium
    effort: S
    summary: No coverage on the refund path
```
<!-- squadron:findings:end -->
"""


def _audit_output(block: str = _FINDINGS_BLOCK) -> str:
    """A realistic agent response: prose, a table, then the block."""
    return (
        "# Tech Debt Audit\n\n## Executive summary\n\n- 2 findings\n\n"
        "| ID | Category | Severity |\n|----|----------|----------|\n"
        "| F001 | architectural-decay | Critical |\n\n" + block
    )


# --------------------------------------------------------------------------
# Happy path
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_run_persists_exactly_one_record(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    stub_provider.agent = _StubAgent(output=_audit_output(), raises=None, hang=False)

    result = await run_audit(audited_repo, store=audit_store, cwd=str(audited_repo))

    assert result.succeeded
    assert result.failure is None
    persisted = audit_store.list_audit_runs()
    assert len(persisted) == 1

    run = persisted[0]
    assert len(run.findings) == 2
    assert run.unnormalized_count == 0
    assert len(run.commit_sha) == 40
    assert len(run.audit_prompt_hash) == 64
    assert run.project_id.value == "github.com/manta/example-repo"


@pytest.mark.asyncio
async def test_unnormalized_findings_are_counted_on_the_run(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    """A run with an unusable severity still persists, carrying the count."""
    block = _FINDINGS_BLOCK.replace("severity: Medium", "severity: Catastrophic")
    stub_provider.agent = _StubAgent(output=_audit_output(block), raises=None, hang=False)

    result = await run_audit(audited_repo, store=audit_store, cwd=str(audited_repo))

    assert result.succeeded
    assert result.run is not None
    assert len(result.run.findings) == 1
    assert result.run.unnormalized_count == 1


# --------------------------------------------------------------------------
# Failure modes: each persists nothing and emits a WARNING
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_persists_nothing_and_warns(
    audited_repo: Path,
    audit_store: MetrologyStore,
    stub_provider: _StubProvider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A hung stream is bounded, discarded, and observable.

    Without the cap this run would hang forever; without the
    persist-nothing rule it would land as a zero-finding sample and drag the
    floor down.
    """
    stub_provider.agent = _StubAgent(output=None, raises=None, hang=True)

    with (
        patch("squadron.metrology.audit.get_typed_config", return_value=1),
        caplog.at_level(logging.WARNING),
    ):
        result = await run_audit(audited_repo, store=audit_store, cwd=str(audited_repo))

    assert result.failure is AuditRunFailure.TIMEOUT
    assert not result.succeeded
    assert audit_store.list_audit_runs() == []
    assert "timed out" in caplog.text.lower()
    assert stub_provider.created[0].shutdown_called


@pytest.mark.asyncio
async def test_mid_stream_exception_persists_nothing_and_shuts_down(
    audited_repo: Path,
    audit_store: MetrologyStore,
    stub_provider: _StubProvider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A peer disconnect mid-generation discards the partial output."""
    stub_provider.agent = _StubAgent(output=None, raises=ConnectionError("peer went away"), hang=False)

    with caplog.at_level(logging.WARNING):
        result = await run_audit(audited_repo, store=audit_store, cwd=str(audited_repo))

    assert result.failure is AuditRunFailure.STREAM_ERROR
    assert audit_store.list_audit_runs() == []
    assert "ConnectionError" in caplog.text
    assert stub_provider.created[0].shutdown_called, "agent must be shut down in finally"


@pytest.mark.asyncio
async def test_absent_block_persists_nothing_and_warns(
    audited_repo: Path,
    audit_store: MetrologyStore,
    stub_provider: _StubProvider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A run with no block is a failed run, not a zero-finding run."""
    stub_provider.agent = _StubAgent(
        output="# Audit\n\nProse only, no machine-readable block.\n", raises=None, hang=False
    )

    with caplog.at_level(logging.WARNING):
        result = await run_audit(audited_repo, store=audit_store, cwd=str(audited_repo))

    assert result.failure is AuditRunFailure.BLOCK_MISSING
    assert audit_store.list_audit_runs() == []
    assert "no findings block" in caplog.text.lower()


@pytest.mark.asyncio
async def test_malformed_block_is_logged_distinctly_from_absent(
    audited_repo: Path,
    audit_store: MetrologyStore,
    stub_provider: _StubProvider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Malformed and absent are different failures with different messages.

    A model that never emitted the block and one that emitted damaged YAML
    call for different responses, so the log must not collapse them.
    """
    broken = (
        "\n<!-- squadron:findings:begin v1 -->\n```yaml\n"
        "findings:\n  - id: F001\n   category: [unclosed\n```\n"
        "<!-- squadron:findings:end -->\n"
    )
    stub_provider.agent = _StubAgent(output=_audit_output(broken), raises=None, hang=False)

    with caplog.at_level(logging.WARNING):
        result = await run_audit(audited_repo, store=audit_store, cwd=str(audited_repo))

    assert result.failure is AuditRunFailure.BLOCK_MALFORMED
    assert audit_store.list_audit_runs() == []
    assert "malformed" in caplog.text.lower()
    assert "no findings block" not in caplog.text.lower()


# --------------------------------------------------------------------------
# Pre-flight short-circuits: no agent, therefore no tokens
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nonexistent_path_creates_no_agent(
    tmp_path: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    from squadron.metrology.audit import AuditPreflightError

    with pytest.raises(AuditPreflightError):
        await run_audit(tmp_path / "not-here", store=audit_store, cwd=str(tmp_path))

    assert stub_provider.created == [], "pre-flight must precede agent creation"
    assert audit_store.list_audit_runs() == []


@pytest.mark.asyncio
async def test_non_git_directory_creates_no_agent(
    non_repo_dir: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    from squadron.metrology.audit import AuditPreflightError

    with pytest.raises(AuditPreflightError):
        await run_audit(non_repo_dir, store=audit_store, cwd=str(non_repo_dir))

    assert stub_provider.created == []


@pytest.mark.asyncio
async def test_dirty_worktree_refuses_variance_run_with_no_agent(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    """The variance refusal costs zero tokens — it is checked pre-flight."""
    from squadron.metrology.audit import AuditPreflightError

    (audited_repo / "scratch.tmp").write_text("uncommitted", encoding="utf-8")

    with pytest.raises(AuditPreflightError, match="dirty"):
        await run_audit(
            audited_repo,
            store=audit_store,
            require_clean=True,
            cwd=str(audited_repo),
        )

    assert stub_provider.created == []
    assert audit_store.list_audit_runs() == []


@pytest.mark.asyncio
async def test_progress_is_reported_while_the_run_works(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    """A long run must show it is alive, not just report when it finishes.

    An audit takes 5-20 minutes and emits no prose until the end, so without
    a liveness signal a working run is indistinguishable from a hang — and
    an operator watching a 12-audit campaign has no way to tell.
    """
    from squadron.metrology.audit import AuditProgress

    class _ToolNarratingAgent(_StubAgent):
        async def handle_message(self, message: Message) -> AsyncIterator[_StubResponse]:
            for _ in range(25):
                yield _StubResponse(content="", metadata={"sdk_type": "tool_use"})
            yield _StubResponse(content=_audit_output())

    stub_provider.agent = _ToolNarratingAgent(output=None, raises=None, hang=False)
    seen: list[AuditProgress] = []

    result = await run_audit(
        audited_repo,
        store=audit_store,
        on_progress=seen.append,
        cwd=str(audited_repo),
    )

    assert result.succeeded
    assert seen, "a run doing tool work must emit at least one progress event"
    assert seen[-1].tool_events >= 20
    # Narration is still filtered out of the parsed text.
    assert result.run is not None
    assert len(result.run.findings) == 2


@pytest.mark.asyncio
async def test_progress_callback_is_optional(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    """A programmatic caller passing no callback still works."""
    stub_provider.agent = _StubAgent(output=_audit_output(), raises=None, hang=False)

    result = await run_audit(audited_repo, store=audit_store, cwd=str(audited_repo))

    assert result.succeeded


@pytest.mark.asyncio
async def test_the_audits_own_output_file_does_not_refuse_the_next_run(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    """A variance series must not refuse itself.

    The skill writes ``analysis/nnn-analysis.{project}.md`` into every repo
    it audits. Counting that as a dirty worktree would refuse runs 2 and 3
    of every series, so no floor would ever be written — the slice's central
    deliverable, lost to its own artifact.
    """
    analysis_dir = audited_repo / "analysis"
    analysis_dir.mkdir()
    (analysis_dir / "940-analysis.example-repo.md").write_text("# prior run\n", encoding="utf-8")

    stub_provider.agent = _StubAgent(output=_audit_output(), raises=None, hang=False)

    result = await run_audit(audited_repo, store=audit_store, require_clean=True, cwd=str(audited_repo))

    assert result.succeeded, "the audit's own output must not refuse the next run"


@pytest.mark.asyncio
async def test_a_real_source_change_still_refuses_a_variance_run(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    """The exemption is narrow: actual code changes still refuse.

    Guards against the artifact exemption being over-broad — a floor
    measured across a source edit is exactly what the check exists to
    prevent.
    """
    from squadron.metrology.audit import AuditPreflightError

    (audited_repo / "src_change.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(AuditPreflightError, match="dirty"):
        await run_audit(audited_repo, store=audit_store, require_clean=True, cwd=str(audited_repo))

    assert stub_provider.created == []


@pytest.mark.asyncio
async def test_a_modified_tracked_analysis_file_still_refuses(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    """Only *untracked* audit output is exempt, not a tracked-file edit."""
    import subprocess

    from squadron.metrology.audit import AuditPreflightError

    analysis_dir = audited_repo / "analysis"
    analysis_dir.mkdir()
    tracked = analysis_dir / "940-analysis.example-repo.md"
    tracked.write_text("# committed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=audited_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add analysis"], cwd=audited_repo, check=True, capture_output=True
    )
    tracked.write_text("# edited after commit\n", encoding="utf-8")

    with pytest.raises(AuditPreflightError, match="dirty"):
        await run_audit(audited_repo, store=audit_store, require_clean=True, cwd=str(audited_repo))

    assert stub_provider.created == []


@pytest.mark.asyncio
async def test_untracked_source_outside_analysis_still_refuses(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    """The exemption is scoped to ``analysis/`` and nothing else."""
    from squadron.metrology.audit import AuditPreflightError

    (audited_repo / "src").mkdir()
    (audited_repo / "src" / "new_module.py").write_text("y = 2\n", encoding="utf-8")

    with pytest.raises(AuditPreflightError, match="dirty"):
        await run_audit(audited_repo, store=audit_store, require_clean=True, cwd=str(audited_repo))

    assert stub_provider.created == []


@pytest.mark.asyncio
async def test_head_moving_mid_series_is_refused(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    """A pinned series refuses to continue across a commit."""
    from squadron.metrology.audit import AuditPreflightError

    stub_provider.agent = _StubAgent(output=_audit_output(), raises=None, hang=False)

    with pytest.raises(AuditPreflightError, match="HEAD moved"):
        await run_audit(
            audited_repo,
            store=audit_store,
            require_clean=True,
            expected_sha="0" * 40,
            cwd=str(audited_repo),
        )

    assert stub_provider.created == []
    assert audit_store.list_audit_runs() == []


@pytest.mark.asyncio
async def test_dirty_worktree_is_allowed_for_a_plain_baseline_run(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    """Cleanliness is required only where it changes the measurement.

    A one-off baseline audit of a dirty tree is a legitimate thing to want;
    only a variance *series* needs the commit pinned.
    """
    (audited_repo / "scratch.tmp").write_text("uncommitted", encoding="utf-8")
    stub_provider.agent = _StubAgent(output=_audit_output(), raises=None, hang=False)

    result = await run_audit(
        audited_repo, store=audit_store, require_clean=False, cwd=str(audited_repo)
    )

    assert result.succeeded


# --------------------------------------------------------------------------
# Campaign behavior and parity
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_series_continues_when_one_project_fails(
    audited_repo: Path,
    second_audited_repo: Path,
    non_repo_dir: Path,
    audit_store: MetrologyStore,
    stub_provider: _StubProvider,
) -> None:
    """One failed project must not cost the campaign the others.

    Project 2 here fails pre-flight; projects 1 and 3 still persist, which
    is what makes a 12-audit campaign resumable rather than all-or-nothing.
    """
    from squadron.metrology.audit import AuditPreflightError

    stub_provider.agent = _StubAgent(output=_audit_output(), raises=None, hang=False)
    projects = [audited_repo, non_repo_dir, second_audited_repo]

    persisted = 0
    failed = 0
    for project in projects:
        try:
            outcome = await run_audit(project, store=audit_store, cwd=str(project))
        except AuditPreflightError:
            failed += 1
            continue
        if outcome.succeeded:
            persisted += 1

    assert persisted == 2
    assert failed == 1
    assert len(audit_store.list_audit_runs()) == 2


@pytest.mark.asyncio
async def test_independent_run_prepends_the_marker(
    audited_repo: Path, audit_store: MetrologyStore, stub_provider: _StubProvider
) -> None:
    """A variance run must actually send the marker that decorrelates it."""
    from squadron.metrology.audit import INDEPENDENT_RUN_MARKER

    sent: list[str] = []

    class _CapturingAgent(_StubAgent):
        async def handle_message(self, message: Message) -> AsyncIterator[_StubResponse]:
            sent.append(message.content)
            yield _StubResponse(content=_audit_output())

    stub_provider.agent = _CapturingAgent(output=None, raises=None, hang=False)

    await run_audit(
        audited_repo,
        store=audit_store,
        independent_run=True,
        cwd=str(audited_repo),
    )

    assert sent and sent[0].startswith(INDEPENDENT_RUN_MARKER)


def test_audit_modules_are_surface_agnostic() -> None:
    """No audit core module may import Typer — the 320/321/322 parity rule."""
    import ast

    for module in ("audit", "audit_parse", "audit_variance", "audit_report"):
        path = Path("src/squadron/metrology") / f"{module}.py"
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert "typer" not in imported, f"{module}.py must not import typer"
        assert "rich" not in imported, f"{module}.py must not import rich"
