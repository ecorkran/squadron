---
docType: slice-design
slice: conditional-persistent-session-construction
project: squadron
parent: user/architecture/240-slices.pipeline-auth-boundary-flexibility.md
dependencies: [242, 243]
interfaces: [245, 247, 248]
dateCreated: 20260504
dateUpdated: 20260504
reviewResponse: 20260504
status: not_started
reviewFindings: [F003, F004, F005]
---

# Slice Design: Conditional Persistent Session Construction

## Overview

Gate `SDKExecutionSession` construction on the pipeline classification from
slice 243. Today `_run_pipeline_sdk` always constructs and connects a
persistent session before calling `execute_pipeline`. After this slice, the
session is constructed only when `PipelineClassification.needs_persistent_session`
is `True`. Pipelines whose dispatch/summary/compact steps all resolve to
non-SDK profiles start and finish without ever spawning a Claude CLI process.

## Value

- **Users:** Pure-non-SDK pipelines (e.g. pipelines that only dispatch to
  Minimax or other non-Claude providers) no longer require Claude auth to run.
  `sq run my-non-claude-pipeline` works even without a Claude CLI login.
- **Architectural:** Establishes the three observable pipeline shapes
  (`claude_required_persistent`, `claude_required_one_shot`, `claude_free`)
  that subsequent slices (245, 246, 248) build on.
- **Developer:** Single clear gate for session construction; the lifecycle
  invariant "session is non-None iff persistent session was warranted" becomes
  auditable.

## Technical Scope

**In scope:**
- Call `classify_pipeline` inside `_run_pipeline_sdk` after `definition` is
  loaded and `resolver` is constructed.
- Skip session construction when `classification.needs_persistent_session` is
  `False`; pass `sdk_session=None` to `execute_pipeline` in that case.
- Log the classification result (shape + step count) at INFO before execution.
- Run-state schema: unchanged. Classification is derived at start time from
  the current pipeline YAML and alias mappings; it is not persisted.
- Resume path: re-classifies on resume (same logic, same code path).
- Pool-uncertain steps: conservative-pessimistic — treated as
  `SDK_REQUIRED` (the `POOL_UNCERTAIN` value already triggers
  `needs_persistent_session` per `PipelineClassification.needs_persistent_session`).

**Out of scope:**
- Lazy / mid-run session construction (slice 245).
- `sq run --explain` diagnostics surface (slice 246).
- Any change to review-step routing (reviews already use one-shot path,
  unchanged by this slice).
- Any UI or CLI flag changes.
- Auth pre-flight for `claude_required_one_shot` pipelines (see §Known Gap below).

### Known gap: deferred auth failure for `claude_required_one_shot` shape

Pipelines whose only Claude-touching steps are reviews (e.g., a review-only
pipeline where every review resolves to an SDK profile) have shape
`claude_required_one_shot`. Today these pipelines fail at startup when
`session.connect()` is called unconditionally. After this slice, the persistent
session is not constructed, so auth failure is deferred to the first review's
one-shot `ClaudeSDKAgent` call — a regression in fail-fast behavior.

This is a known and accepted gap for this slice. The mitigation is:
1. The shape is logged at INFO before execution, so the user can see
   `shape: claude_required_one_shot` and anticipate that Claude auth will
   be needed at review time.
2. The architecture's auth pre-flight check (`needs_one_shot_claude` feeds
   the diagnostic surface) is delivered in slice 246. Until then, auth
   failure for this shape surfaces as a provider-level error mid-run, not
   at startup.

No code change is needed here; this section exists to document the gap so
it is not mistaken for a bug introduced by this slice.

## Architecture

### Component Structure

```
run.py:_run_pipeline_sdk
  → (1) load_pipeline + validate
  → (2) build resolver (ModelResolver)  [already exists]
  → (3) classify_pipeline(definition, resolver, pool_backend)  [NEW]
  → (4a) if needs_persistent_session: construct + connect SDKExecutionSession
  → (4b) else: session = None
  → (5) _run_pipeline(..., sdk_session=session)
  → (6) if session: disconnect
```

The pool_backend used in step (3) must be the same `DefaultPoolBackend`
instance used by the resolver in step (2). Currently `_run_pipeline` creates
the pool_backend internally; this must be lifted to `_run_pipeline_sdk` so
it can be shared with the classifier.

### Data Flow

```
_run_pipeline_sdk
  ├─ load_pipeline → PipelineDefinition
  ├─ DefaultPoolBackend()      ← shared between resolver and classifier
  ├─ ModelResolver(cli_override, pipeline_model, pool_backend)
  ├─ classify_pipeline(definition, resolver, pool_backend)
  │     → PipelineClassification.needs_persistent_session  [bool]
  │     → PipelineClassification.shape                     [logged]
  │
  ├─ if needs_persistent_session:
  │     ClaudeAgentOptions → ClaudeSDKClient → SDKExecutionSession.connect()
  │
  └─ _run_pipeline(..., sdk_session=session_or_None)
```

### Refactoring: pool_backend construction site

Currently `_run_pipeline` (the async core) creates the `DefaultPoolBackend`
and `ModelResolver` internally. For classification to use the same
`pool_backend` as the resolver, `_run_pipeline_sdk` must supply them.

**Option A — thread the objects as parameters into `_run_pipeline`.**  
`_run_pipeline` already accepts `sdk_session` from outside; it can similarly
accept `resolver` and `pool_backend`. `_run_pipeline_sdk` constructs them,
classifies, decides on a session, then calls `_run_pipeline(resolver=...,
pool_backend=...)`. The internal construction in `_run_pipeline` becomes
optional (falls back to constructing its own when not provided), preserving
the existing integration test surface.

**Option B — inline the classification into `_run_pipeline_sdk` using a
second (temporary) resolver that matches what `_run_pipeline` will build.**  
Would work but creates two resolver instances with the same config — fragile.
Rejected.

**Decision: Option A.** `_run_pipeline` accepts optional `resolver:
ModelResolver | None = None` and `pool_backend: PoolBackend | None = None`
parameters. When non-None, it skips internal construction and uses the
provided instances. Callers that don't supply them (existing tests, prompt-only
path) are unaffected.

## Implementation Details

### Key change in `_run_pipeline_sdk` (`run.py`)

```python
# After load + validate:
pool_backend = DefaultPoolBackend()
resolver = ModelResolver(
    cli_override=model_override,
    pipeline_model=definition.model,
    pool_backend=pool_backend,
)

classification = classify_pipeline(definition, resolver, pool_backend)
_logger.info(
    "pipeline '%s' shape: %s (%d classified steps)",
    pipeline_name,
    classification.shape,
    len(classification.steps),
)

if classification.needs_persistent_session:
    options = claude_agent_sdk.ClaudeAgentOptions(...)
    client = claude_agent_sdk.ClaudeSDKClient(options=options)
    session: SDKExecutionSession | None = SDKExecutionSession(client=client, options=options)
    await session.connect()
else:
    session = None

try:
    result = await _run_pipeline(
        pipeline_name, params,
        resolver=resolver,
        pool_backend=pool_backend,
        sdk_session=session,
        ...
    )
finally:
    if session is not None:
        await session.disconnect()
```

### Resume path

`_run_pipeline_sdk` is called for both fresh and resumed SDK runs (line 793,
847, 878 in `run.py`). The classification runs every time. On resume, the
classification reflects the *current* pipeline YAML and alias state, which is
correct: if an alias was remapped between runs, the new classification wins.
Run-state remains unchanged (no new fields added).

### ClassificationError handling

`classify_pipeline` raises `ClassificationError` when a step has an empty
cascade or a pool reference without a backend. This propagates up through
`_run_pipeline_sdk` and surfaces as an unhandled `ValueError`-family error.
Add a `try/except ClassificationError` in `_run_pipeline_sdk` that prints
a clear message and raises `typer.Exit(1)`. This is a pipeline
misconfiguration; the user needs to fix the pipeline definition.

### Conditional `connect()` failure modes

`session.connect()` is now only called when `needs_persistent_session` is
`True`. The call is placed **before** the `try/finally` block:

```python
if classification.needs_persistent_session:
    session = SDKExecutionSession(client=client, options=options)
    await session.connect()   # ← may raise
else:
    session = None

try:
    result = await _run_pipeline(..., sdk_session=session)
finally:
    if session is not None:
        await session.disconnect()
```

If `session.connect()` raises, `session` is already assigned (the
`SDKExecutionSession` object exists) but the underlying client is not
fully connected. The `try/finally` is not yet entered, so `disconnect()`
is not called. This is intentional and safe: `SDKExecutionSession.disconnect()`
calls `self.client.disconnect()` with a best-effort catch-all; calling it on
a session whose `connect()` failed would be a no-op at best and a double-fault
at worst. The partially-constructed session is simply dropped.

Specific failure modes and their handling:

| Exception | Source | Handling |
|-----------|--------|----------|
| `CLINotFoundError` | `connect()` → `ProviderAuthError` | Propagates; caller prints error and exits |
| `ProcessError` | `connect()` → `ProviderAPIError` | Propagates; caller prints error and exits |
| `CLIConnectionError` / `CLIJSONDecodeError` | `connect()` → `ProviderError` | Propagates; caller prints error and exits |
| Auth unavailable (Claude not logged in) | `connect()` → `CLINotFoundError` or `ProcessError` | Same as above |
| `TimeoutError` | `connect()` blocks indefinitely | Not guarded — SDK's internal process management handles it; no change from current behavior |

All of these are existing failure modes for the `_run_pipeline_sdk` path;
conditionality changes *when* they occur (only for `claude_required_persistent`
pipelines), not how they propagate. The `try/except` for `ClassificationError`
wraps only the `classify_pipeline` call and is separate from this flow.

### Logging

At INFO level, before constructing the session, log:
```
pipeline 'my-pipeline' shape: claude_free (0 classified steps)
pipeline 'my-pipeline' shape: claude_required_persistent (3 classified steps)
```

At DEBUG level, log each step's classification:
```
  step 'write-code' [dispatch]: sdk_required (alias 'sonnet' → profile 'sdk')
  step 'review' [review]: non_sdk (alias 'minimax-text' → profile 'minimax')
```

## Integration Points

### Provides to Other Slices
- **245 (Pool-Resolution Policy):** The gate established here (session
  constructed iff `needs_persistent_session`) is the entry point for lazy
  mode — 245 will change the gate logic for `POOL_UNCERTAIN` steps.
- **246 (Diagnostics CLI):** The `classify_pipeline` call and its result
  are the data source for `sq run --explain`. 246 calls the same function
  independently; no coupling to the private gate logic here.
- **248 (Adversarial Test Matrix):** Asserts that no Claude CLI subprocess
  is spawned for `claude_free` pipelines; the gate introduced here is what
  makes that assertion possible.

### Consumes from Other Slices
- **243:** `classify_pipeline`, `PipelineClassification`, `ClassificationError`
  from `squadron.pipeline.classification`.
- **242:** `DispatchAction` routing unchanged — this slice does not touch
  per-step routing logic.
- **241:** `is_sdk_profile` (used inside `classify_pipeline`).

### `sdk_session=None` correctness for summary and compact steps

When this slice passes `sdk_session=None` to the executor, summary and compact
steps that appear in a `claude_free` pipeline must handle the absent session
without crashing. All three step handlers already do so correctly:

**CompactAction** (`compact.py:62–64`): branches on `context.sdk_session is not None`.
When `None`, routes to `_execute_prompt_only`, which issues `/compact` via a
one-shot `claude_agent_sdk.query()` call. This is the existing prompt-only path
and works without a persistent session.

**SummaryAction — non-SDK profile** (`summary.py:245–254`): routes to
`capture_summary_via_profile()` via the provider registry. Does not touch
`context.sdk_session`. Works with `None`.

**SummaryAction — SDK profile with `sdk_session=None`** (`summary.py:218–224`):
guarded by an explicit check that returns `ActionResult(success=False, ...)` with
`"summary action requires SDK execution mode for SDK-profile models"`. This is a
belt-and-suspenders guard: the classification gate in this slice ensures that
any step resolving to an SDK profile triggers `needs_persistent_session=True`,
so the session will be non-None when that step runs. The guard fires only on
misconfiguration (e.g., alias table changed between classification and execution).

**SummaryAction — restore variant** (`summary.py:149`): checks
`context.sdk_session is not None` before calling `seed_context`; if None,
logs a debug warning and completes without seeding. Graceful degradation.

In summary: classification ensures the gate is correct by construction. The
step handlers' existing `None` guards are belt-and-suspenders for the
misconfiguration edge case. No changes to step handlers are required by this
slice.

## Success Criteria

### Functional Requirements
1. A pipeline whose all model-dispatching steps resolve to non-SDK profiles
   runs successfully with `sdk_session=None` passed to `execute_pipeline`.
2. No `ClaudeSDKClient` or `SDKExecutionSession` is constructed for such
   a pipeline (including pipelines with summary or compact steps on non-SDK
   profiles — see §`sdk_session=None` correctness).
3. A pipeline with at least one SDK-resolved dispatch/summary/compact step
   constructs and connects the session as before.
4. A pipeline with `POOL_UNCERTAIN` steps constructs the session
   (conservative path).
5. `ClassificationError` from `classify_pipeline` produces a clear error
   message and `typer.Exit(1)` — not an unhandled exception traceback.
6. Resume re-classifies and applies the same gate logic; session lifecycle
   (connect before, disconnect in finally) is identical to fresh runs.
7. `connect()` failure (e.g., `CLINotFoundError`) propagates cleanly without
   leaving a partially-connected session in memory; `disconnect()` is not
   called in this case (session never entered the `try` block).
8. `claude_required_one_shot` pipelines (review-only, SDK profiles) run
   without a persistent session; auth failure is deferred to one-shot review
   time and is logged at INFO via the shape annotation (known gap; full
   pre-flight check is slice 246).

### Technical Requirements
- `ruff format` / `ruff check` clean.
- `pyright` zero errors.
- Full test suite passes (no regressions).
- New tests (see below) cover the three shapes and the error path.

### Test Coverage

New tests in `tests/pipeline/test_conditional_session.py` (or alongside
existing `test_classification.py`):

| # | Scenario | Assert |
|---|----------|--------|
| T1 | All steps non-SDK (dispatch only) | `_run_pipeline` called with `sdk_session=None` |
| T2 | Non-SDK pipeline with summary + compact steps | summary/compact execute without crash; `sdk_session=None` throughout |
| T3 | At least one dispatch step SDK | session constructed + `connect()` called |
| T4 | Pool-uncertain step | session constructed (conservative) |
| T5 | `ClassificationError` (empty cascade) | `typer.Exit(1)` raised, no session |
| T6 | Resume with non-SDK pipeline | session not constructed |
| T7 | Resume with SDK pipeline | session constructed + seeded |
| T8 | `connect()` failure (mock `CLINotFoundError`) | exception propagates; `disconnect()` not called; no session leak |

Tests use mock `classify_pipeline` return values so they don't depend on alias
config; the classifier's own correctness is covered by `test_classification.py`.

T2 exercises the summary and compact step handlers directly with `sdk_session=None`
(non-SDK profile) to confirm the existing guards hold and no session is leaked.

The existing `_run_pipeline` integration tests are unaffected (they don't
supply a resolver or pool_backend, so the fallback internal-construction path
is exercised).

## Risk Assessment

### Lifecycle correctness on resume

Resume with `start_from` seeds the SDK session from a prior compact summary
(executor.py:575–596). That code path only runs `if sdk_session is not None`.
If classification says `claude_free` but a prior run had an SDK session that
produced compact summaries, the seeding is skipped. This is correct: if the
pipeline was re-classified as non-SDK (e.g., alias remapped), the prior compact
summary is irrelevant.

If the pipeline is still SDK-required on resume, seeding works as before.

### `_run_pipeline` signature change

Adding optional `resolver` and `pool_backend` parameters to `_run_pipeline`
is backward-compatible. Callers that omit them (prompt-only path, most
integration tests) are unaffected. The fallback internal-construction branch
must remain correct — cover with an explicit test asserting that omitting the
parameters still produces a valid run.

## Verification Walkthrough

### 1. Non-SDK pipeline: no session

```bash
# Create a minimal pipeline whose dispatch step uses a non-SDK model.
# (Assumes 'minimax-text' or equivalent non-SDK alias exists in alias config.)
# Run it — should complete without spawning Claude CLI.

sq run my-non-sdk-pipeline
```

Expected log output includes:
```
pipeline 'my-non-sdk-pipeline' shape: claude_free (1 classified steps)
```

No Claude CLI authentication prompt appears. Run completes.

### 2. SDK pipeline: session constructed

```bash
sq run my-sdk-pipeline
```

Expected log output includes:
```
pipeline 'my-sdk-pipeline' shape: claude_required_persistent (2 classified steps)
```

Behavior identical to pre-slice.

### 3. Unit test gate

```bash
cd /Users/manta/source/repos/manta/squadron
uv run pytest tests/pipeline/test_conditional_session.py -v
```

All T1–T6 scenarios pass.

### 4. Full suite

```bash
uv run pytest --tb=short -q
```

No regressions (1795+ passing, 0 new failures).

### 5. Pyright and ruff

```bash
uv run pyright
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

All clean.
