---
docType: slice-design
slice: compact-action-sdk-capability-dispatch
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [149-pipeline-executor-and-loops, 161-summary-step-with-emit-destinations, 164-profile-aware-summary-model-routing, 166-compact-and-summary-unification]
interfaces: [CompactStepType, CompactAction, SessionCapabilities, SDKExecutionSession, PromptOnlyExecutor]
dateCreated: 20260418
dateUpdated: 20260422
status: in-progress
---

# Slice Design: Compact Action — SDK Capability Dispatch

## Overview

The Claude Agent SDK now supports `/compact` as a prompt dispatched through `query()`, emitting a `SystemMessage(subtype="compact_boundary")` carrying `pre_tokens` and `trigger` metadata. Previously `/compact` was user-initiated only, so prompt-only pipelines (IDE extension, Claude Code CLI) could not rotate context at all — only `sq run` (true CLI) could, via the existing SDK session rotate flow.

This slice restructures pipeline context-management actions so authors get the best available behavior in every environment from a single portable pipeline, without guessing what a given environment can and cannot do.

Three actions, each with one responsibility:

- **`summarize`** — produce a summary artifact via a model. Works in all environments. No rotation side effects.
- **`compact`** — reduce the current session's context. In true CLI, keeps today's session-rotate flow (summarize → session end → new session → summary restore). In prompt-only environments, dispatches `/compact` via `query()` and listens for the `compact_boundary` boundary message. Same action, environment-appropriate mechanism.
- **`summarize` with `restore: true`** — inject a previously captured summary back into the current session context. (Named "restore mode" on the `summarize` action rather than a separate action, to mirror the existing `sq:summary --restore` slash command.)

Rotation is no longer an implicit side effect of a compound action. Pipeline authors compose explicitly: `summarize` creates, `compact` reduces, `summarize restore` injects.

## Value

**For pipeline authors:** one pipeline YAML now produces the best possible context-management behavior in every environment. Previously, `compact:` stalled in prompt-only mode (pre-slice 166) and, even after 166's unification, prompt-only lifecycle was bounded to what the user could type. Post-193, a pipeline ending with `compact:` actually reduces context in the IDE and Claude CLI.

**For long-running pipelines:** session lifetime management is now automatable in all three environments. Fan-out parents that aggregate across many branches, multi-step dispatch chains, and convergence loops can reach past their prior token walls without requiring the user to step in.

**For the mental model:** separates "make a summary artifact" from "reduce my context" from "inject a summary into context." Each is independently useful; previously they were entangled.

## Technical Scope

### Included

- `compact` action: dispatches on execution environment and available slash-command capabilities. True-CLI path preserves today's `SDKExecutionSession` rotate flow. Prompt-only path issues `/compact` via `query()` and consumes the `compact_boundary` boundary message, logging `pre_tokens` and `trigger`.
- **Capability discovery** component: on session start (or first action requiring a slash command), inspects the SDK init message (`SystemMessage(subtype="init")`, field `slash_commands`) and caches the available set on the session/execution context. Subsequent dispatches branch on capability presence, not environment heuristic.
- Separation of concerns: `compact` stops acting as "summarize + rotate" shorthand. Authors who want a summary captured around a compact add an explicit `summarize` step before or after.
- `summarize` remains the canonical summary-production action. Confirm/extend existing `restore: true` option (or add if not currently supported) so summaries can be re-injected into a later session.
- `/model` automation investigation: probe the init message in each environment to determine whether `/model` is dispatchable via `query()`. If yes, adjust compact's model-switch rendering in prompt-only mode accordingly. If no, keep today's "suggested model" printout.
- Documentation updates: pipeline-authoring guide (slice 190 will reference this), execution-environment matrix note.

### Excluded

- **No `clear` action.** `/clear` is not dispatchable via `query()`. A prompt-only "clear" would require session termination, which the IDE extension and Claude Code CLI do not expose to the pipeline executor. True-CLI-only rotation remains available as the existing `compact` behavior, not as a separate action.
- **No `rotate_strategy` field.** Discarded after design discussion — action name is the strategy. Adding an enum would create a second, parallel naming surface.
- **No token-threshold triggers, no `auto` mode.** Token count is an explicit non-goal. Rotation fires only when an author places the action in their pipeline.
- **No mitigation for compact instruction-following reliability beyond documentation.** `/compact` is known to not always follow instructions tightly; the authoring guide will note this. A post-compact verification step is deferred to future work.
- **No cross-step conversation persistence.** That lives in slice 188.
- **No changes to `summarize`'s SDK vs. non-SDK profile routing** (slice 164 is respected as-is).

## Dependencies

### Prerequisites

- **166 (Compact and Summary Unification)** — established that compact is a thin step-type expanding to summary in some form. This slice builds on that by narrowing `compact` into its own identity again: a context-reduction action, not a summary-and-rotate shorthand.
- **149 (Pipeline Executor and Loops)** — the executor's step dispatch loop is where capability discovery hooks in.
- **161 (Summary Step with Emit Destinations)** — the `summarize` surface that 193 keeps intact.
- **164 (Profile-Aware Summary Model Routing)** — SDK vs. non-SDK branching already exists in `summary.py`; the `compact` action will follow the same pattern for its own branching.

### Interfaces Required

- `ClaudeSDKClient.query()` — dispatches `/compact` as a prompt.
- `SystemMessage(subtype="init")` with `data["slash_commands"]` — for capability discovery.
- `SystemMessage(subtype="compact_boundary")` with `data["compact_metadata"]["pre_tokens"]` and `data["compact_metadata"]["trigger"]` — for compact completion detection.
- Existing `SDKExecutionSession.compact()` path (src/squadron/pipeline/sdk_session.py:197-242) — true-CLI flow retained.
- Existing `is_sdk_profile()` predicate (src/squadron/pipeline/summary_oneshot.py:19-24).

## Architecture

### Component Structure

New / restructured components:

1. **`CompactAction`** (new or restored) — dedicated action class with its own dispatch logic. Not a thin wrapper over summary. Registered as `ActionType.COMPACT` in the action registry.
2. **`SessionCapabilities`** (new) — dataclass on the execution context holding `slash_commands: frozenset[str]`, populated by the capability discovery probe. Read by `CompactAction` and any future action that dispatches a slash command.
3. **`CompactStepType`** (existing, behavior-changed) — no longer expands to `summary(emit=[rotate])`. Expands to `compact:` action directly. YAML `compact:` remains valid; what it does is changed.
4. **`SummaryAction`** (existing, minor) — unchanged primary behavior; ensure `restore: true` mode is present and documented.
5. **Capability probe hook** — called once per session in the executor (true CLI on `ClaudeSDKClient` start; prompt-only on first init-message receipt).

### Data Flow

#### True CLI (`sq run`)

```
pipeline step: compact
  → CompactAction.execute(context)
  → capabilities = context.session.capabilities  (cached; probed at session start)
  → dispatch on environment: SDK-session present → SDKExecutionSession.compact()
      → capture_summary() on current client
      → disconnect client
      → new ClaudeSDKClient
      → seed new session with framed summary
  → return StepResult(ok=True)
```

Behavior identical to today's compact step. The distinction is that `CompactAction` now owns this flow directly rather than delegating through the summary action with `emit=[rotate]`.

#### Prompt-only (IDE extension, Claude Code CLI)

```
pipeline step: compact
  → CompactAction.execute(context)
  → capabilities = context.session.capabilities  (probed from SystemMessage init)
  → "/compact" in capabilities?
      yes → dispatch "/compact <optional_instructions>" via the same ClaudeSDKClient
            wait for SystemMessage(subtype="compact_boundary")
            log pre_tokens, trigger
            return StepResult(ok=True)
      no  → render informational "compact not available in this environment" notice
            return StepResult(ok=True, note=...)
```

The executor dispatches `/compact` as a prompt inside the current session. The boundary message arrives as a normal SDK message; the action awaits it before returning.

#### Authoring pattern (explicit composition)

```yaml
steps:
  - action: dispatch
    # ... some work that grows context

  - action: summarize
    model: sonnet
    template: pipeline-progress
    emit: [file]              # capture artifact but don't rotate

  - action: compact
    # reduces in place; summary artifact from prior step is independent

  - action: summarize
    restore: true             # re-inject the earlier captured summary
```

`compact` no longer implicitly summarizes; authors opt in to summary capture/restore around it.

### State Management

- `SessionCapabilities` is cached per-session; no persistence beyond the run.
- `compact_boundary` events are logged into existing pipeline run state alongside other per-step metadata (`pre_tokens`, `trigger`, timestamp). Useful for post-hoc debugging of when compaction fired and what triggered it.

## Technical Decisions

### Action-name-is-the-strategy

Considered `rotate_strategy: compact | summarize_new_session | auto`. Rejected: creates a parallel naming surface, "summarize_new_session" isn't a meaningful name outside of the internals, and `auto` invites token-threshold design that the project has explicitly ruled out. YAML pipelines read more clearly with `action: compact` than with `action: rotate, strategy: compact`.

### Re-separate `compact` from `summary`

Slice 166 unified them to delete code. Slice 193 re-splits them — but on a different axis. The unification's driver was "compact's prompt-only branch rendered a dead slash command." Now that `/compact` actually works in prompt-only via `query()`, `compact` has meaningful independent behavior. Keeping it as a summary alias would force every compact to also produce a summary artifact, which is wrong semantically and conflates two concerns.

Code deletion from 166 is not undone wholesale. The `summarize` path remains the summary-production canonical; `compact` gets a small dedicated action that dispatches on capabilities.

### Capability discovery over environment heuristics

Hardcoding "prompt-only means use `/compact`, true-CLI means rotate" is fragile. Reading `slash_commands` from the SDK init message is authoritative and future-proofs against the SDK exposing new commands (e.g., if `/clear` becomes dispatchable later). The probe cost is one message parse per session.

### `/compact` rotate path even in true CLI? No.

Considered using `/compact` via `query()` in true CLI instead of the existing session-rotate flow. Rejected: the rotate flow gives better control (explicit summary capture, deterministic new session, controlled restore), and the project has validated it as production-ready in slice 158. `/compact` is a fallback for environments where session rotation is not available to the pipeline executor. The existing rotate flow is strictly better where it works.

### `restore` as a mode on `summarize`, not a separate action

The existing `sq:summary --restore` slash command establishes the shape. A separate `restore-summary` action would fragment the surface. Documented in the authoring guide so scanners don't mis-read `summarize` with `restore: true` as "summarize again."

### Investigation: `/model`

Not a blocking decision but worth confirming during implementation. If `slash_commands` in the init message contains `/model`, the compact action can dispatch a model switch via `query()` in prompt-only mode, matching true-CLI's optional model-switch behavior. If not, the existing "suggested model" printout path stays.

## Implementation Details

### Migration Plan

This is a **behavior-migration slice**. No storage migration. YAML does not change — existing pipelines with `compact:` continue to load.

**Source → destination of behavior:**

| YAML today | Today's behavior | Post-193 behavior |
|---|---|---|
| `compact:` (true CLI) | Summary captured, session rotated, summary restored | Same (no change) |
| `compact:` (prompt-only) | Broken (pre-166) / summary-only (post-166, no rotation possible) | `/compact` dispatched via `query()`, session context reduced in place |
| `summarize:` | Summary artifact produced per `emit:` destinations | Same (no change) |

**Consumer updates:**

- Pipeline YAML files using `compact:` in true CLI: no change required.
- Pipeline YAML files relying on `compact:` to also produce a summary artifact: must add an explicit `summarize:` step. Audit `src/squadron/data/pipelines/*.yaml` during implementation; update any that relied on the compound behavior. Document the migration in the authoring guide.

**Behavior verification:**

- Existing true-CLI compact tests must continue to pass unchanged.
- New tests: prompt-only `/compact` dispatch produces `compact_boundary` message; action awaits it and logs metadata.
- Integration test: a `compact:` step placed in a prompt-only pipeline no longer prints a dead slash command (regression guard for pre-166 behavior) and correctly consumes the boundary message.

### API / Configuration

**YAML (unchanged for existing pipelines):**

```yaml
- action: compact
  instructions: >      # optional, passed to /compact in prompt-only mode;
                       # in true CLI, used as the summary prompt body
    Keep recent fan-out branch results verbatim; drop tool-use details.
```

**`instructions` field:** in true CLI, feeds into the summary capture step of the rotate flow (same as today's compact). In prompt-only, appended to `/compact` as the prompt body. Optional in both modes.

**Runtime capability check (pseudocode):**

```python
# Executor, once per session start
init_msg = await read_init_message(client)
capabilities = SessionCapabilities(
    slash_commands=frozenset(init_msg.data.get("slash_commands", [])),
)
context.session.capabilities = capabilities
```

## Integration Points

### Provides to Other Slices

- **`SessionCapabilities`** on the execution context — reusable by any future action that needs to dispatch a slash command. Future slices wanting to automate other SDK-dispatchable commands inherit the probe/cache.
- **Portable compact behavior** — slice 188 (conversation persistence in convergence loop) and slice 182 (fan-out) both benefit: their inner steps can now include `compact:` and run correctly in every environment.

### Consumes from Other Slices

- `SDKExecutionSession.compact()` from slice 158 (true-CLI rotate path).
- `is_sdk_profile()` and the summary dispatch surface from slices 161 and 164.
- Pipeline executor's step dispatch loop from slice 149 — capability probe hooks in at session start.

## Success Criteria

### Functional Requirements

- `compact:` action works in all three execution environments (IDE, Claude Code CLI, `sq run`), producing the best behavior available in each.
- True CLI compact behavior is **bit-for-bit identical** to today: summary captured, session rotated, summary restored. No regression.
- Prompt-only compact dispatches `/compact` via `query()` and awaits `SystemMessage(subtype="compact_boundary")` before returning. Pipeline does not stall or emit dead slash-command text.
- `pre_tokens` and `trigger` from the compact boundary are logged into pipeline run state.
- `summarize:` action behavior is unchanged for existing uses. `restore: true` mode is documented and tested.
- A test pipeline exercising `summarize` → `compact` → `summarize restore:true` runs to completion in at least one prompt-only environment and in true CLI.

### Technical Requirements

- `SessionCapabilities` probe fires once per session; value cached; no re-probing.
- `CompactAction` is a dedicated class, registered in the action registry, not a delegation to `SummaryAction`.
- `CompactStepType.expand()` emits `compact:` action, not `summary:` with `emit=[rotate]`.
- Unit tests for each environment branch of `CompactAction`.
- Integration test for prompt-only `/compact` dispatch using a mocked SDK client emitting `compact_boundary`.
- pyright clean, ruff clean, no new warnings.
- Code deletion from slice 166 is not reverted wholesale; only the compact-specific paths are restored as needed.

### Verification Walkthrough

Each step is runnable against the implemented slice. Caveat: the capability-probe step originally specified here was **dropped during implementation** — `/compact` is assumed available going forward; the `CompactAction` branches on `sdk_session` presence instead of probing `slash_commands`. `SessionCapabilities` and `ActionContext.capabilities` are not present in the final code.

**1. Unit + integration test suite — confirm implementation is wired end-to-end.**

```bash
uv run pytest tests/pipeline/actions/test_compact.py -q
# Expected: 16 passed (validate, true-CLI rotate, prompt-only /compact dispatch,
# boundary await, timeout)

uv run pytest tests/pipeline/steps/test_compact.py -q
# Expected: 12 passed (CompactStepType emits compact action, not summary+rotate)

uv run pytest tests/pipeline/test_compact_compose_integration.py -q
# Expected: 3 passed (prompt-only + true-CLI compose pipelines, dead-slash regression)

uv run pytest tests/pipeline/actions/test_summary.py -q
# Expected: 33 passed (including 6 new restore-mode tests)

uv run pytest -q
# Expected: 1665 passed
```

**2. Static checks.**

```bash
uv run pyright src/       # 0 errors, 0 warnings, 0 informations
uv run ruff check src/    # All checks passed!
uv run ruff format src/   # 124 files left unchanged
```

**3. True CLI compact — confirm no regression.**

Use any existing compact-using pipeline (e.g. `tasks`, `slice`, `P6`).

```bash
sq run P6 --slice 169
# Expected: compact steps execute via the session-rotate flow (summary
# captured, client disconnected/reconnected, summary re-injected). The
# ActionResult.success=True, outputs={}. Behavior is bit-for-bit identical to
# pre-169 main for these pipelines because the rotate flow in sdk_session.compact()
# is unchanged — only the dispatch surface (CompactAction) is new.
```

**4. Prompt-only compact — automatable for the first time.**

In the IDE extension or Claude Code CLI:

```
/sq:run test-compact-compose
```

The pipeline steps are rendered as JSON instructions. The `compact-2` step's instruction carries `action_type: "compact"` with `trigger: "/compact"`. The agent invokes `/compact`, Claude reduces context, and subsequent steps proceed. Before slice 169 this trigger was either absent (pre-166) or rendered as a dead slash-command string; post-169 it is real capability.

**5. Explicit summary composition — separation of concerns.**

The `test-compact-compose.yaml` pipeline (added in T10) exercises:

```yaml
steps:
  - dispatch: {prompt: "Describe three key facts about async Python programming."}
  - summary: {emit: [file]}            # capture artifact
  - compact: {}                        # reduce in place
  - summary: {restore: true}           # re-inject captured summary
  - dispatch: {prompt: "What were the key facts from the earlier step?"}
```

The prompt-only compose integration test asserts all five steps complete in order. The true-CLI compose integration test asserts `sdk_session.compact()` is called exactly once (rotate flow) and all five steps complete.

**6. Action registry.**

```bash
uv run python -c "from squadron.pipeline.actions import list_actions; print(list_actions())"
# Expected output includes 'compact': ['dispatch', 'review', 'summary', 'compact',
# 'checkpoint', 'cf-op', 'commit', 'devlog']
```

**7. Documentation.**

- `docs/PIPELINES.md` — `compact` step section documents the new environment matrix; `summary` section documents `restore: true` mode; actions table updated.
- `CHANGELOG.md` — `[Unreleased]` section documents the added `compact` portability, added `restore: true`, and the migration note for pipelines that relied on implicit summary capture.

## Risk Assessment

### Technical Risks

- **Compact instruction-following reliability.** `/compact` does not always obey its prompt body tightly. Pipelines that pass detailed preservation instructions to compact in prompt-only mode may see drift. **Mitigation:** document the limitation in the authoring guide. Pipelines needing tight artifact preservation should use true-CLI mode or structure their work to tolerate compact drift (e.g., capture a summary artifact via `summarize` before compacting, then restore it).
- **Capability probe timing.** The init message arrives once at session start; if the executor's step loop begins before the probe completes, the first `compact:` step could see an empty capabilities set. **Mitigation:** probe synchronously during session initialization; block step dispatch until capabilities are populated.
- **`/compact` blocking semantics.** The `compact_boundary` message arrives asynchronously. If the action returns too early, subsequent dispatches may see a half-reduced context. **Mitigation:** the action awaits the boundary message explicitly before returning; test with a mock client that delays the boundary to confirm the await behavior.

### Mitigation Strategies

Summarized inline above. No separate mitigation-tracking mechanism needed.

## Implementation Notes

### Development Approach

Suggested implementation order within the slice:

1. Capability discovery probe + `SessionCapabilities` dataclass + executor integration.
2. `/model` availability investigation (read-only probe, no code changes yet). Record outcome.
3. `CompactAction` class — start with true-CLI branch (lift-and-shift from today's summary-with-emit-rotate path).
4. Prompt-only branch of `CompactAction`: `/compact` dispatch + `compact_boundary` await + metadata logging.
5. `CompactStepType.expand()` update — emit `compact:` instead of `summary: emit=[rotate]`.
6. Audit and update any pipeline YAML that relied on compact's implicit summary.
7. Tests: unit per branch, integration for prompt-only `/compact` with mocked SDK client, end-to-end for the compose example.
8. Documentation: authoring guide updates, execution-environment matrix note, migration note.
9. If `/model` probe showed it's dispatchable: add model-switch branch to prompt-only compact.

### Special Considerations

- **Do not revert slice 166's deletions wholesale.** The summary action remains the canonical summary-production surface. Only reintroduce the compact-specific paths that 193 actually needs.
- **Keep `compact:` YAML loadable without changes.** The only YAML-visible change is semantic (compact no longer summarizes), not syntactic.
- **Audit test pipelines before implementation begins.** `src/squadron/data/pipelines/app.yaml` and `example.yaml` (and any others found) may rely on today's compound behavior. Identify them first so the migration is focused.
- **Branch name for implementation:** `193-slice.rotation-strategy-control-compact-vs-summarize-new-session` per project git rules.
