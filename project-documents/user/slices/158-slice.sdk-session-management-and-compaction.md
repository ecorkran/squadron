---
docType: slice-design
slice: sdk-session-management-and-compaction
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [155-sdk-pipeline-executor, 156-pipeline-executor-hardening]
interfaces: [152-pipeline-documentation]
dateCreated: 20260406
dateUpdated: 20260407
status: complete
---

# Slice Design: SDK Session Management and Compaction

## Overview

Replace the unconnected `configure_compaction()` stub from slice 155 with working context compaction via session rotation. When a compact step executes in SDK mode, the current session's model is switched to a cheap summarizer, the compact template instructions are sent as a query, the summary response is captured, the session is disconnected, and a fresh session continues with the summary as its opening context.

Scope is strictly SDK mode. Interactive Claude Code compaction (VS Code extension, CLI Claude Code) is handled by a separate `PreCompact` settings hook in a follow-up slice — squadron does not register hooks programmatically here.

## Value

- **Deterministic compaction at step boundaries**: Compaction happens exactly where the pipeline author placed the compact step — not at arbitrary token thresholds. This prevents context loss mid-phase (e.g., losing design context during task breakdown).
- **Cost savings via summarization model**: The compact YAML can specify a cheap model (haiku) for summarization, avoiding the cost of using opus/sonnet to compress context.

## Technical Scope

### In Scope

1. **Session rotate compaction** — Replace the `configure_compaction()` stub with a working implementation that: switches model, queries with compact instructions, captures summary, disconnects, reconnects fresh with summary context.
2. **Persisted compact summaries** — A keyed `compact_summaries: dict[str, CompactSummary]` field on `RunState` that records every compact step's output. Schema bumped to v3. Forward-compat: missing field defaults to empty dict on v2 load.
3. **Executor-owned summary injection on resume** — When `execute_pipeline` resumes from a non-zero start position with an active SDK session, it asks state for the active compact summary (most recent compact preceding the resume point) and seeds the new session with it before running the next action.
4. **Session ID capture** — Extract `session_id` from `ResultMessage` during dispatch so the session can be identified for logging and diagnostics.
5. **Compact YAML `model` field** — Optional model alias for the summarization query. Validated at load time like other model aliases.
6. **Cleanup of `configure_compaction()` stub** — Remove the unused `_compaction_config` field and `configure_compaction()` method from `SDKExecutionSession`.

### Out of Scope

- Controlling Claude Code's internal compaction threshold (no API exposed).
- Server-side `context_management` API integration (Agent SDK doesn't expose it).
- Manual compaction triggering from SDK mode (no `compact()` method on `ClaudeSDKClient`).
- `PreCompact` / `PostCompact` hooks for interactive Claude Code (VS Code extension, CLI Claude Code) — covered by a separate slice that ships a `.claude/settings.json` hook script.
- Pipeline artifact summary action (separate future work).

## Architecture

### Session Rotate Flow

```
Compact step executes:
  |
  1. Resolve compact template → render instructions with pipeline params
  2. Resolve summarization model (compact YAML `model` field, or fallback)
  |
  3. session.set_model(summarization_model)   ← cheap model (e.g. haiku)
  4. session.dispatch(compact_instructions)    ← ask current session to summarize
  5. Capture summary text from response
  |
  6. session.disconnect()                      ← done with old conversation
  |
  7. Create new ClaudeSDKClient + SDKExecutionSession
  8. new_session.connect()
  9. new_session.set_model(next_step_model)    ← restore to pipeline model
  10. new_session.dispatch(summary_as_context)  ← seed new conversation
  |
  Continue pipeline with new session
```

Key insight from PM: we summarize in the **current** session (step 3-5) rather than disconnecting first and resuming. The model that did the work has the best understanding of what happened. No need to resume the old conversation in a new process just to read it — we already have it live.

### SDKExecutionSession Changes

The session gains two capabilities:

```python
@dataclass
class SDKExecutionSession:
    client: ClaudeSDKClient
    current_model: str | None = None
    session_id: str | None = None       # captured from ResultMessage

    async def compact(
        self,
        instructions: str,
        summary_model: str | None = None,
        restore_model: str | None = None,
    ) -> str:
        """Perform session-rotate compaction.

        1. Switch to summary_model (if specified).
        2. Query with compact instructions.
        3. Capture summary from response.
        4. Disconnect current session.
        5. Create and connect a new session.
        6. Seed new session with summary.
        7. Restore model to restore_model (if specified).

        Returns the summary text for logging/diagnostics.
        """
        ...
```

The `compact()` method owns the full rotate lifecycle. It replaces `configure_compaction()` which is deleted.

The `session_id` field is populated from `ResultMessage.session_id` during `dispatch()`. This is captured for logging and diagnostics — not used for resume (we don't resume the old session, we start fresh).

### Compact Action Changes

The compact action's SDK path changes from configuring a stub to actually performing compaction:

```python
# Current (stub — does nothing):
if context.sdk_session is not None:
    context.sdk_session.configure_compaction(...)
    return ActionResult(success=True, ...)

# New (performs session rotate):
if context.sdk_session is not None:
    summary_model = str(context.params.get("model", "")) or None
    summary = await context.sdk_session.compact(
        instructions=instructions,
        summary_model=summary_model_id,
        restore_model=current_pipeline_model,
    )
    return ActionResult(
        success=True,
        outputs={"summary": summary, "instructions": instructions},
    )
```

The `model` param in compact config is the summarization model. It goes through the same model alias resolution as dispatch and review model params.

### Compact YAML `model` Field

Pipeline authors can specify a model for summarization:

```yaml
steps:
  - compact:
      template: minimal
      model: haiku          # ← new: use haiku for cheaper summarization
```

When omitted, the summarization query uses whatever model the session currently has active (typically the dispatch model from the previous step).

Validation: the `model` field is validated by `_validate_model_alias` in `validate_pipeline`, same as step-level and action-level model aliases. The compact step's `validate()` method checks the field type.

### Data Flow

```
Pipeline YAML compact step:
  template: "minimal"
  model: "haiku"
       |
       v
CompactAction.execute()
  → load_compaction_template("minimal")
  → render_instructions(template, pipeline_params)
  → resolve_model_alias("haiku") → model_id
       |
       v
SDKExecutionSession.compact(instructions, summary_model=model_id)
  → set_model(model_id)              # switch to haiku
  → dispatch(instructions)           # haiku summarizes the conversation
  → capture summary text
  → disconnect()                     # end old conversation
  → create new ClaudeSDKClient       # fresh conversation
  → connect()
  → dispatch(summary)                # seed new conversation with summary
  → set_model(restore_model)         # restore for next dispatch step
       |
       v
ActionResult(success=True, outputs={"summary": ..., "instructions": ...})
```

### State Management

The session rotate creates a new `ClaudeSDKClient` internally. The executor's reference to `sdk_session` must remain valid. Two approaches:

**Option A — Session replaces its own client**: `SDKExecutionSession.compact()` creates a new client, replaces `self.client`, and updates `self.session_id`. The executor's reference to the session object is unchanged. This is the simpler path.

**Option B — Executor provides a session factory**: The `compact()` method receives a factory callable to create new clients. More flexible but more complex.

**Decision**: Option A. The session owns its client lifecycle. The executor doesn't need to know that the underlying client changed. `compact()` is the only method that replaces the client, and it handles the full connect/disconnect/reconnect cycle internally.

The `ClaudeAgentOptions` used to create the replacement client must match the original (same `cwd`, `hooks`, etc.). The session stores the options at construction time for reuse.

### Persisted Compact Summaries (Schema v3)

The summary produced by a compact step must survive checkpoint and resume. The previous process's session is gone after resume, so the new session has nothing to inject unless the summary lives in the persisted state file.

**Data model:**

```python
@dataclass
class CompactSummary:
    key: str                              # deterministic, unique per occurrence
    text: str                             # the summary content
    summary_model: str | None             # model used to generate it
    source_step_index: int                # the compact step's index
    source_step_name: str                 # the compact step's name
    created_at: datetime

class RunState:
    ...
    compact_summaries: dict[str, CompactSummary] = {}
```

**Keying scheme:** `f"{step_index}:{step_name}"` for top-level compact steps. This is deterministic, unique per pipeline run, and obvious in the state file. When fan-out branches (slice 158) introduce branch-internal compaction, branches will extend the key with a branch suffix (e.g., `f"{step_index}:{step_name}#branch{n}"`). The keying scheme is intentionally extensible — future cases (loops, nested branches) add suffixes without changing the storage shape.

**Schema bump:** `_SCHEMA_VERSION` goes from 2 → 3. The `compact_summaries` field defaults to `{}` so v2 files (which have no summaries) load cleanly as having an empty dict. v1 files continue to raise `SchemaVersionError` as before.

**Persistence point:** The compact action, after `session.compact()` returns the summary, builds a `CompactSummary` record and stores it directly on the `ActionContext`'s state. This happens via the existing `on_step_complete` callback that the state manager already wires through `execute_pipeline`. The state manager gains a new method `record_compact_summary(run_id, summary)` that updates and persists state.

**Helper for retrieval:**

```python
def active_compact_summary_for_resume(
    self, resume_step_index: int
) -> CompactSummary | None:
    """Return the compact summary that should seed a session resuming
    at *resume_step_index*. The active summary is the one with the
    highest source_step_index < resume_step_index.
    """
```

For slice 157 the helper handles the linear case. Slice 158 will extend the lookup logic to consider branch context when applicable.

### Executor-Owned Resume Injection

When `execute_pipeline` is invoked with `start_from` set (resume path) and an `sdk_session` is present, it asks state for the active compact summary and seeds the session before the first step runs:

```python
# Pseudocode inside execute_pipeline, at resume entry:
if start_from is not None and sdk_session is not None:
    active = state.active_compact_summary_for_resume(start_step_index)
    if active is not None:
        await sdk_session.seed_context(active.text)
```

The session method `seed_context(text)` is a thin wrapper around `dispatch(text)` that marks intent and logs distinctly (so verbose output shows "context seeded from compact summary <key>" rather than a generic dispatch line). It returns nothing — the model's response to seeding is discarded.

**Why the executor and not `_run_pipeline_sdk`:** The executor already owns the resume machinery (`start_from`, prior outputs loading) and is mode-agnostic. Putting the seeding here means any future execution mode that supports session-style operation gets the same behavior automatically. `_run_pipeline_sdk` stays focused on session lifecycle.

**Why not in `compact()` itself:** The `compact()` method already seeds the new session with the freshly generated summary as part of the rotate flow. Resume injection is a *separate* event — it's the executor reconstituting session state from persisted summaries when the original session is gone.

## Technical Decisions

### Summarize in Current Session, Not via Resume

Resuming the old conversation in a new process would load the entire context just to summarize it — defeating the purpose. Instead, we query the current live session with the compact instructions. The model has full context and produces the best summary. Then we disconnect and start clean.

### Session Owns Client Replacement

The `SDKExecutionSession` replaces its own `ClaudeSDKClient` during compact. This keeps the executor unaware of the rotation — it just sees the same session object. The alternative (executor managing sessions) would spread lifecycle logic across two layers.

### Compact Model Is Optional

If no `model` is specified in the compact YAML, the session uses whatever model is currently active. This is fine for pipelines where the dispatch model is already cheap. For expensive models (opus dispatching design work), authors should specify `model: haiku` on the compact step to save tokens.

## Implementation Details

### Changes to `src/squadron/pipeline/sdk_session.py`

- Remove `_compaction_config` field and `configure_compaction()` method.
- Add `session_id: str | None` field, populated from `ResultMessage` during `dispatch()`.
- Add `options: ClaudeAgentOptions` field, stored at construction for reuse during rotation.
- Add `compact()` method implementing the full session rotate flow.
- Add `seed_context(text)` method — thin wrapper around `dispatch()` for resume re-injection, with distinct logging.
- Update `dispatch()` to capture `session_id` from `ResultMessage`.

### Changes to `src/squadron/pipeline/state.py`

- Add `CompactSummary` dataclass.
- Bump `_SCHEMA_VERSION` from 2 → 3.
- Add `compact_summaries: dict[str, CompactSummary] = {}` field on `RunState`.
- Add `StateManager.record_compact_summary(run_id, summary)` method that updates and persists state.
- Add `RunState.active_compact_summary_for_resume(resume_step_index)` helper.

### Changes to `src/squadron/pipeline/executor.py`

- At resume entry (when `start_from is not None`), if `sdk_session is not None`, look up the active compact summary from state and call `await sdk_session.seed_context(summary.text)` before running the first step.

### Changes to `src/squadron/pipeline/actions/compact.py`

- Replace the `configure_compaction()` stub call with `await context.sdk_session.compact(...)`.
- After successful compact, build a `CompactSummary` record and persist via `state_manager.record_compact_summary(...)`. The state manager reference reaches the action via the existing `on_step_complete` callback wiring — confirm during implementation whether the action calls the manager directly or returns the summary in `ActionResult.outputs` for the executor to persist. Prefer the executor doing the persistence to keep actions free of state-manager coupling.
- Add model resolution for the compact step's `model` param.
- Add `model` to `validate()` checks.

### Changes to `src/squadron/pipeline/steps/compact.py`

- Pass through the `model` config field when expanding to the compact action.
- ~5 lines changed.

### Changes to `src/squadron/cli/commands/run.py`

- Pass `ClaudeAgentOptions` to `SDKExecutionSession` constructor (needed for client recreation during rotate).

### Changes to `src/squadron/providers/sdk/translation.py`

- Capture `session_id` from `ResultMessage` in the translated message metadata.

## Success Criteria

1. `sq run test-pipeline 154 -vv` with a compact step shows: model switch to summarization model, compact query, summary captured, session disconnected, new session connected, summary injected, model restored.
2. The summary text is visible in `-vv` output and stored in the step's `ActionResult.outputs` AND persisted in `RunState.compact_summaries` keyed by `{step_index}:{step_name}`.
3. Compact step with `model: haiku` uses haiku for summarization, not the dispatch model.
4. Compact step without `model` uses the current session model.
5. Pipeline execution continues normally after compact — subsequent dispatch steps work with the new session.
6. Resume after checkpoint following a compact step correctly seeds the new session: the executor reads `compact_summaries` from state, picks the most recent summary preceding the resume step, and calls `session.seed_context(summary.text)` before running. Verbose output shows "context seeded from compact summary <key>".
7. `RunState` schema bumps to v3; v2 files load with `compact_summaries={}`; v1 files raise `SchemaVersionError`.
8. `--validate` catches invalid model aliases in compact step `model` field.
9. `configure_compaction()` stub and `_compaction_config` field are removed.
10. All existing tests pass; new tests cover compact flow with mock SDK client, state persistence of summaries, resume injection lookup, and the `seed_context` call path.

## Verification Walkthrough

### 1. Session rotate compaction

```bash
sq run test-pipeline 154 -vv
```

**Expected output** at compact step:
```
action 5/7: compact template=minimal
  SDKExecutionSession: switched model to claude-haiku-4-5-20251001
  SDKExecutionSession: compact query sent (instructions: 42 chars)
  SDKExecutionSession: summary captured (387 chars)
  SDKExecutionSession: old session disconnected
  SDKExecutionSession: new session connected
  SDKExecutionSession: summary injected as context
    -> ok
    outputs={'summary': '...', 'instructions': '...'}
```

### 2. Compact with explicit model

```yaml
# test-pipeline.yaml
steps:
  - compact:
      template: minimal
      model: haiku
```

```bash
sq run test-pipeline 154 -vv
```

**Expected**: Compact step uses haiku for summarization regardless of what the previous dispatch used.

### 3. Pipeline continues after compact

```bash
sq run test-pipeline 154 -v
```

**Expected**: Steps after compact execute normally. The dispatch action uses the new session. The model is restored to whatever the next step specifies.

### 4. Resume after compact (manual)

Construct a pipeline with: dispatch → compact → checkpoint(always) → dispatch.

```bash
sq run test-pipeline 154 -vv
# Runs dispatch, compact (summary persisted), checkpoint fires, exits.
```

Inspect the state file:

```bash
cat ~/.config/squadron/runs/<run-id>.json | jq .compact_summaries
```

**Expected**: The compact summary appears keyed by `{step_index}:{step_name}` with the summary text, summary_model, source_step_index, and created_at.

```bash
sq run --resume <run-id> -vv
```

**Expected output**: Verbose log includes:
```
executor: resuming at step <next>; seeding session from compact summary "<key>"
SDKExecutionSession: seed_context (587 chars)
```

Subsequent dispatch executes with the seeded summary as conversation context, not just the cf build output.

### 5. Validation

```bash
sq run test-pipeline --validate
```

**Expected**: Invalid model alias in compact `model` field is caught:
```
Validation errors for 'test-pipeline':
  steps[compact-4].model: Model alias 'bogus' did not resolve to a known alias
```

## Risk Assessment

### Technical Risks

- **New session context quality**: The summary injected into the fresh session may not preserve enough context for subsequent steps. Mitigation: compact templates are pipeline-author-controlled and can be tuned per pipeline. The `default` and `minimal` templates already exist with sensible defaults.
- **Client recreation in `compact()`**: Creating a new `ClaudeSDKClient` mid-pipeline means re-establishing the subprocess connection. If connect fails, the pipeline fails mid-run. Mitigation: the same connect/disconnect pattern is used at pipeline start — if it works there, it works here. Error handling in `compact()` should fail the step explicitly.

## Implementation Notes

### Development Approach

1. **Capture session_id in dispatch** — Update `dispatch()` to extract from `ResultMessage`. Small, testable change.
2. **Add `CompactSummary` and bump RunState schema to v3** — Add the dataclass, the field, the helper, and the state manager method. Tests for serialization, defaults, and active-summary lookup.
3. **Implement `compact()` and `seed_context()` methods** — Core session rotate logic with mock tests. Store `options` for client recreation.
4. **Wire compact action** — Replace stub with `compact()` call. Add model resolution. Persist the resulting summary via the executor's `on_step_complete` hook (executor reads `ActionResult.outputs["summary"]` and calls `state_manager.record_compact_summary`).
5. **Executor resume injection** — In `execute_pipeline`, on resume entry with an active SDK session, look up active summary and call `session.seed_context(...)`.
6. **Add compact `model` field** — Step expansion, validation, YAML support.
7. **PreCompact hook** — Wire into `ClaudeAgentOptions` in `_run_pipeline_sdk`.
8. **Remove `configure_compaction()` stub** — Cleanup.
9. **Automated integration test** — In `tests/pipeline/test_sdk_wiring.py`, exercise dispatch → compact → dispatch with a mock session, asserting `compact()` is called between dispatches and the second dispatch sees the new client.
10. **Resume-after-compact integration test** — Build a state file with a recorded compact summary, invoke the resume path with a mocked session, assert `seed_context` is called with the summary text before any subsequent action.
11. **End-to-end manual smoke test** — Run `test-pipeline` with compact step and checkpoint to verify the full real-SDK flow.

### Keying Alignment with Slice 158

Slice 158 (Pipeline Fan-Out / Fan-In) will introduce parallel branches whose internal compactions need their own keys. The keying scheme defined here (`{step_index}:{step_name}`) is intentionally extensible:

- Top-level compact: `"3:compact-midpoint"`
- Branch-internal compact (158): `"3:compact-midpoint#branch1"`, `"3:compact-midpoint#branch2"`
- Loop iteration compact (future): `"3:compact-midpoint@iter4"`

Slice 157 implements only the top-level form. The `active_compact_summary_for_resume` helper uses simple "highest source_step_index < resume_step_index" logic that works for the linear case. Slice 158 will extend the lookup to consider branch context. The storage shape (`dict[str, CompactSummary]`) does not change.
