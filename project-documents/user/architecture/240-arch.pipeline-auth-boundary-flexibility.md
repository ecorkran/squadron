---
docType: architecture
layer: project
project: squadron
archIndex: 240
component: pipeline-auth-boundary-flexibility
dateCreated: 20260428
dateUpdated: 20260428
reviewIteration: 2
status: draft
---

# Architecture: Pipeline Auth-Boundary Flexibility

## Overview

Squadron's pipeline executor today couples *running a pipeline* with
*holding an authenticated Claude SDK session* — the persistent
`SDKExecutionSession` is constructed and connected at the top of
`_run_pipeline_sdk` in `cli/commands/run.py`, before any step is
inspected. Any `sq run …` invocation in pure-CLI mode therefore
requires Claude CLI auth, even when no step in the pipeline will
actually use it. A second, less obvious dependency exists at the
review path: review actions route through the provider registry,
and when a review's resolved profile is `sdk`, the registry spawns a
short-lived `ClaudeSDKAgent` that opens its own Claude CLI subprocess.
Squadron has *two distinct paths to the Claude CLI* with different
lifecycles, and the auth requirement of a pipeline is the union of
the two.

This initiative decouples those paths from the pipeline executor
itself. Authentication becomes a property of the **steps that are
actually going to run**, derived from the resolved model on each
step, not a property of the executor. Pipelines composed entirely
of non-SDK profiles run end-to-end without Claude auth, login, or
account. Mixed pipelines pay Claude cost only on the steps that
need it. The persistent-session lifetime guarantee that makes
slice-lifecycle work today — single Claude session across design,
tasks, and implementation, terminated only by compact/rotate — is
preserved exactly when the pipeline contains SDK-profile dispatch
chains.

### Scope

This component owns:

- The **per-step auth classification** of resolved pipelines (does
  this step need a Claude subprocess? if so, of which kind?).
- **Conditional construction** of the persistent `SDKExecutionSession`
  — connect iff at least one step's resolved profile is SDK.
- **Profile-aware dispatch routing** in pure-CLI executor mode so
  non-SDK dispatches fall through to the existing one-shot agent
  path even when an `SDKExecutionSession` exists in context.
- **Error semantics and classification** when a `pool:`-resolved
  step's runtime selection conflicts with the upfront classification.
- Documentation and CLI affordances that make a pipeline's auth
  classification inspectable before it runs.

### Motivation

Three forces:

1. **Concrete defect.** `sq run p5 X --param model=minimax` from a
   pure CLI today silently fails the user's intent: the SDK executor
   constructs a Claude session, calls `set_model("minimax-…")` on a
   `ClaudeSDKClient`, and the dispatch is broken. The user has been
   confused about whether this works for hours at a time. Slice 170
   addresses the IDE / `/sq:run` axis of this problem; the pure-CLI
   axis is unaddressed.

2. **Capability the architecture wants.** Squadron is meant to be a
   pipeline runtime, not "a Claude Code companion that requires
   Claude auth." Pipelines composed entirely of OpenRouter, OpenAI-
   compatible, or local models are a legitimate and useful use case
   — particularly for users who do not have Claude accounts, for
   cost-sensitive workflows, and for review-only pipelines that
   already have nothing to do with Claude beyond an accidental
   coupling.

3. **Architectural property worth naming.** The two-paths-to-the-CLI
   structure (persistent session vs. one-shot agent) is real and
   load-bearing — the persistent session is *better* for chained
   dispatch (design → tasks → implement), the one-shot is *better*
   for reviews (template-driven prompt, no conversation pollution).
   These are not bugs to merge; they are intentional. But they are
   not currently documented and have caused planning errors. The
   initiative documents the property as a contract.

### Relationship to Other Components

**100-band (Orchestration v2):** stable. This initiative consumes
the agent registry, provider profiles, model alias registry, and the
existing `ClaudeSDKAgent` one-shot path unchanged.

**140-band (Pipeline Foundation):** this initiative directly extends
140. The `SDKExecutionSession` lifecycle, the `DispatchAction`
router, the model resolver cascade, and the pipeline state machine
all originate in 140. This initiative changes when and whether
the session is constructed and how the dispatch router branches; it
does not change the action protocol, step types, or pipeline grammar.

**180-band (Pipeline Intelligence):** coordinates with, does not
depend on. Pool resolution is a 180 mechanism; this initiative needs
a *minimal* contract from pools ("does this pool potentially yield
an SDK alias?") and otherwise stays out of pool selection logic.
The auth-classification ↔ pool-resolution boundary is named
explicitly in the design but the pool side is not touched.

**Slice 170 (Profile-Aware Dispatch Model Routing):** complementary,
narrowly scoped to the IDE / `/sq:run` axis. Slice 170 fixes the
prompt-only renderer; this initiative fixes the SDK executor. Both
are necessary; neither subsumes the other.

---

## Design Goals

- **Auth as a per-step property.** A pipeline's auth requirement is
  the union of its steps' auth requirements, derived from each step's
  resolved model and profile. The executor does not assume auth on
  the user's behalf.

- **Persistent-session lifetime preserved.** When a pipeline contains
  any SDK-profile dispatch step, the persistent `SDKExecutionSession`
  is constructed exactly as today and lives until pipeline end or
  intentional compact/rotate. Cross-step memory across design /
  tasks / implement chains is unchanged.

- **Claude-free pipelines run Claude-free.** A pipeline whose every
  step resolves to a non-SDK profile runs end-to-end without
  invoking the Claude CLI in any path — neither persistent session
  nor one-shot review subprocess. No auth check, no subprocess spawn,
  no Claude account requirement.

- **Fail fast at classification time.** When a pipeline's resolved
  models are statically determinable, classify before the run starts.
  If Claude auth is required and unavailable, the user learns at
  startup, not 90 seconds in. When models are not statically
  determinable (pool resolution), the design states explicitly when
  classification is conservative-pessimistic vs. lazy.

- **Two SDK-touching paths, named and documented.** The persistent
  `SDKExecutionSession` and the one-shot `ClaudeSDKAgent` spawned by
  the provider registry are documented as distinct paths with
  distinct lifecycles and distinct prompt environments. Neither is
  a special case of the other. The documentation lives at the arch
  level so future planning does not re-litigate the structure.

---

## Architectural Principles

- **Classification is a function of the resolved pipeline, not the
  executor mode.** SDK / prompt-only is an execution-mode concern;
  auth-boundary is a per-step concern derived from resolver output.
  These two axes are orthogonal and the design preserves their
  orthogonality.

- **Don't merge the two SDK paths.** The persistent session and the
  one-shot agent serve different purposes (chained dispatch with
  cross-step memory vs. isolated template-driven invocation with
  fresh context). Merging them would either pollute reviews with
  prior conversation context or strip cross-step memory from
  dispatch. Both are worse than the status quo.

- **Conservative on uncertainty.** When pool resolution makes the
  classification uncertain, the default behavior is to treat the
  pipeline as Claude-required (so the persistent session is connected
  upfront and fail-fast applies). A user can opt into lazy connection
  only with explicit acknowledgment of the trade-off (mid-run
  failure surface).

- **No new lifetime semantics.** This initiative does not introduce
  new lifecycle hooks, new session-rotation triggers, or new
  conversation-persistence mechanisms. It only makes existing
  lifetimes conditional on need.

- **Boundary discipline with 180-band.** The authoring of fan-out /
  fan-in semantics, until-loop convergence, intra-loop compaction,
  and the policy of where review findings flow (conversation turn
  vs. override-instruction vs. external artifact) are all 180
  concerns. This initiative neither prescribes nor changes them.
  Where they touch the auth-boundary surface, the design *names*
  the boundary and stops.

---

## Current State

Today, in pure-CLI executor mode (`sq run …` from a real terminal):

- `_run_pipeline_sdk` (`cli/commands/run.py`) constructs a
  `ClaudeSDKClient`, wraps it in `SDKExecutionSession`, and calls
  `session.connect()` **before** inspecting any step. The Claude CLI
  subprocess is spawned at this point. Any pipeline — including
  review-only pipelines that do not dispatch through the session
  at all — pays this cost and requires this auth.

- `DispatchAction._dispatch` routes to `_dispatch_via_session`
  whenever `context.sdk_session is not None`, regardless of the
  resolved model's profile. A non-SDK profile resolved on a
  dispatch step still hits `session.set_model(non_claude_id)`,
  which is broken. There is no profile branch at the router.

- Reviews route via `run_review_with_profile()` through the provider
  registry. When the resolved profile is `sdk`, the registry returns
  the `sdk` provider, which constructs a `ClaudeSDKAgent` per call.
  Each one-shot review with a Claude profile spawns its own Claude
  CLI subprocess (separate from the persistent session) with its own
  template-driven system prompt. This path is correct but
  undocumented as a distinct auth surface.

- Slice 170 (in design) addresses the prompt-only renderer for the
  IDE / `/sq:run` consumer. It branches `_render_dispatch` on resolved
  profile and emits a runnable command for non-SDK profiles. It does
  not change the SDK executor or the persistent-session construction.

The user-visible consequences of this state:

- A pure-CLI run of a non-Claude pipeline still requires Claude auth.
- A pure-CLI run with `--param model=<non-sdk-alias>` for a dispatch
  step silently fails (broken `set_model` call).
- A review-only pipeline with all non-SDK reviews still pays the
  persistent-session connect cost.
- A pipeline whose review template defaults to `sonnet` (an SDK
  alias) requires Claude auth even when no other step does.

---

## Envisioned State

After this initiative ships, the executor's behavior is:

1. At `sq run <pipeline>` invocation, after pipeline load and
   validation, the executor performs a **resolution pre-scan**:
   for each step that will dispatch a model (dispatch, review,
   summary, compact), ask the model resolver for `(model_id,
   profile)` using the same cascade that the action would use at
   runtime. The result is a per-step classification: SDK-required,
   non-SDK, or pool-uncertain.

2. The executor computes **two distinct pipeline-level properties**
   from the per-step classifications, because the two SDK-touching
   paths have different lifecycles and must be classified separately:

   - **`needs_persistent_session`** — true iff at least one
     dispatch / summary / compact step resolves to an SDK profile
     (or pool-uncertain under conservative default). These are the
     only steps that consume `context.sdk_session`. Reviews and
     `_dispatch_via_agent` invocations never use the persistent
     session, so review-only pipelines with SDK-profile reviews
     are *not* `needs_persistent_session`.
   - **`needs_one_shot_claude`** — true iff at least one step
     (review or non-SDK-mode dispatch) resolves to an SDK profile
     and will route through the provider registry's
     `ClaudeSDKAgent` path. This property is informational —
     one-shot subprocesses always spawn lazily at the moment the
     action runs, so this property does not gate any startup
     decision. It feeds the diagnostic surface and the auth
     pre-flight check.

   These yield three observable pipeline shapes for users:

   - **Claude-required (persistent)** — `needs_persistent_session`
     is true. Persistent session is connected at startup.
   - **Claude-required (one-shot only)** — `needs_persistent_session`
     is false but `needs_one_shot_claude` is true. No persistent
     session is constructed. Claude CLI subprocesses spawn per
     review/agent-dispatch as today, lazily.
   - **Claude-free** — both are false. No Claude path is touched.

3. The persistent `SDKExecutionSession` is constructed and connected
   **iff** `needs_persistent_session` is true. The "Claude-required
   (one-shot only)" shape — the canonical example is a review-only
   pipeline whose reviews resolve to `sonnet` — gets no persistent
   session even though Claude auth is required (lazily, at review
   time). For pipelines where neither property is true, no
   `SDKExecutionSession` is constructed; `ActionContext` carries
   `sdk_session=None` for every action.

4. `DispatchAction._dispatch` branches on the resolved profile *in
   addition to* the existing `sdk_session is not None` check. Non-SDK
   profiles route to `_dispatch_via_agent` even when an
   `SDKExecutionSession` exists. SDK profiles continue to use the
   persistent session as today.

5. The provider registry's one-shot `ClaudeSDKAgent` path is
   unchanged in this initiative. Reviews / one-shot dispatches with
   resolved Claude profile continue to spawn short-lived Claude CLI
   subprocesses with their template-driven system prompts. The arch
   doc (this document) names this path as a distinct auth surface
   so it is not confused with the persistent session.

5a. **Mid-run session construction** (Claude-optional case under
    lazy mode). The `ActionContext` is already constructed
    *per-action*, not per-run (`pipeline/executor.py` builds a fresh
    `ActionContext` immediately before each `action_impl.execute(ctx)`
    call). This means `ActionContext` remains immutable after
    construction; the executor itself owns the mutable session
    reference. The mechanism for mid-run construction is therefore:
    the executor holds an `Optional[SDKExecutionSession]` field on
    its run loop; before each action's `ActionContext` is built, if
    the action's resolved profile is SDK and the field is `None`,
    the executor constructs and connects a session, stores it on
    the field, and the new `ActionContext` carries that reference.
    Connect blocks the action that triggered it (one-time cost on
    first SDK-resolved step). No retroactive mutation of prior
    `ActionContext`s occurs — they were correctly `None` at the
    time. From this point forward the session lives until pipeline
    end or compact/rotate, identical to the eager-connect case.

6. A diagnostic CLI surface (`sq run --explain` or equivalent —
   exact name deferred to slice design) shows the classification of
   a pipeline and per-step rationale before running. The user can
   confirm "this pipeline does / does not need Claude auth" without
   running it.

The persistent-session lifetime guarantee is unchanged in shape:
when constructed, the session lives across all SDK-profile dispatch
steps in the run, reused via `set_model` for in-place model switches,
and terminated only by intentional compact/rotate or pipeline end.
What changes is **whether** it is constructed.

---

## Technical Considerations

- **Two SDK-touching paths with different lifecycles and different
  prompt environments.** The persistent `SDKExecutionSession` carries
  the `claude_code` system-prompt preset and accumulates conversation
  across steps (design → tasks → implement); the one-shot
  `ClaudeSDKAgent` (review path, also the existing
  `_dispatch_via_agent` path) carries a per-call system prompt
  (review template, action-supplied) and has no cross-call memory.
  This is intentional and correct; the architecture must document
  the distinction so future planning treats them as separate
  surfaces.

- **Pre-scan correctness under pool resolution.** Pools (180-band)
  defer alias selection to runtime. A pre-scan can ask "could this
  pool yield an SDK alias?" — a static query against pool
  definitions — but cannot know which alias *will* be selected. The
  design must specify how the executor handles the gap: conservative
  (treat any pool that can yield SDK as SDK-required, connect
  upfront), lazy (defer connect until a runtime selection forces it),
  or user-opt-in. The conservative default preserves fail-fast; the
  lazy mode provides flexibility at the cost of mid-run auth surprise.

- **Auth-failure UX at the boundary.** When a Claude-required
  pipeline runs without Claude auth, the failure today is the
  Claude CLI's own error from `client.connect()`. This is informative
  enough but happens before any pipeline output. With conditional
  connect, the same failure mode applies; with lazy connect for
  pool-optional pipelines, the failure happens mid-run and the
  pipeline state shows partial completion. The design must specify
  the error message, run-state shape, and resume implications for
  this case.

- **Resolver determinism for pre-scan.** Verified by inspection of
  `models/aliases.py:resolve_model_alias` and
  `pipeline/resolver.py:ModelResolver.resolve`: for non-pool aliases
  the resolution path is a pure dict lookup over merged built-in +
  user aliases (no logging, no telemetry, no cache mutation, no
  state writes). Calling `resolve(alias)` in pre-scan returns the
  same `(model_id, profile)` it returns at runtime, repeatable, no
  side effects. This is a contract this initiative *relies on* and
  documents in the pre-scan slice; if a future change adds side
  effects to alias resolution, the pre-scan must be updated to
  isolate the read path.

- **Pool steps in pre-scan — static query, not selection.** Pool
  resolution selects an alias *at runtime* via 180-band selection
  strategies. The pre-scan must classify a `pool:` step *without*
  invoking selection (which would alter selection state, telemetry,
  and weighted-decay counters in 180). The classification question
  the pre-scan asks is purely structural: "does this pool's alias
  list contain any SDK-profile aliases?" — answerable by walking the
  pool definition's static alias set and applying `is_sdk_profile`
  to each. No selection, no strategy invocation, no 180 API surface
  required. If the pool contains *only* non-SDK aliases, the step
  is classified non-SDK. If it contains *any* SDK alias, the step
  is `pool-uncertain` and falls under the conservative-vs-lazy
  policy. This stays inside the alias / pool-definition layer,
  which is structural data, not 180's selection logic.

- **Pre-scan resolver instance must match runtime.** The pre-scan
  must construct (or reuse) the *same* `ModelResolver` instance the
  executor will use at runtime — same `cli_override` (including
  `--param model=…` overrides from the CLI), same `pipeline_model`
  default, same `config_default`. A pre-scan that ignored CLI
  overrides would classify against the pipeline's default model
  and miss the case the initiative was promoted to fix
  (`sq run … --param model=minimax`). This is a constraint on slice
  design: the executor builds the resolver once, the pre-scan and
  every step's `ActionContext` share that instance.

- **Run-state schema and resume.** Existing run-state files have no
  classification field. Resume must not require it (older runs
  predate the field) and must compute classification from the
  resumed pipeline's *current* resolved models, not from cached
  state. Pipeline-level classification is a derived property, not
  durable state.

  **Policy when classification differs between original run and
  resume**: re-classification on resume uses current YAML and current
  alias mappings; the new classification wins. If a pipeline
  originally ran Claude-free and a model alias has since been
  remapped to an SDK profile, resume will detect the new
  classification, connect the persistent session if needed, and
  proceed. The reverse (originally SDK, now non-SDK) is also
  honored — resume will skip the persistent session. This
  preserves user intent: an alias remap is an explicit user action
  whose effect should apply on next run (including resume). The
  alternative (pin classification to the original run) would
  silently ignore user changes and is rejected.

  Mid-run resume on a Claude-required pipeline with no Claude auth
  available follows the same fail-fast path as a fresh run: the
  user gets a clear error at resume time, before any step executes.

- **One-shot Claude subprocess cost.** Each one-shot Claude review
  in a pipeline pays a Claude CLI cold start. For pipelines with
  many SDK-profile reviews, this can be material. This initiative
  *documents* the cost but does not optimise it; pooling/reusing
  one-shot subprocesses is explicitly out of scope. The documented
  workaround is "use a non-SDK profile for reviews when cold-start
  cost dominates."

- **Persona / system-prompt asymmetry across providers.** The
  persistent session carries the `claude_code` preset; non-SDK
  one-shot dispatches carry a minimal or template-supplied system
  prompt. This is already true today and is not changed by this
  initiative, but the conditional-session work makes the asymmetry
  more visible. Documentation must call out that switching a
  dispatch step from SDK to non-SDK (intentionally, via
  `--param model=…`) also switches the system-prompt environment.

- **Coordination with slice 170.** Slice 170 fixes the prompt-only
  renderer's dispatch leg; this initiative fixes the SDK executor's
  dispatch leg. The two changes share the `is_sdk_profile()`
  predicate and must agree on profile semantics, but they live in
  different files and ship independently. Sequencing: slice 170 may
  ship first, in or out; this initiative does not block on it.

- **`is_sdk_profile()` predicate — ownership and contract.** Today
  the predicate lives in `pipeline/summary_oneshot.py` (slice 164's
  introduction site), which is the wrong home for a predicate now
  shared by dispatch (slice 170), summary (slice 164), and the
  classification pre-scan (this initiative). This initiative
  promotes the predicate to a canonical home in
  `providers/profiles.py` (alongside `get_profile`, where profile
  semantics already live). The contract is documented here so all
  callers agree:
  > `is_sdk_profile(profile_name: str | None) -> bool` returns
  > `True` iff the profile name routes through the `ClaudeSDKAgent`
  > provider — i.e., the provider whose `provider` field is `"sdk"`
  > in the profiles registry. Returns `False` for any other
  > registered provider (`openai-compatible`, `openrouter`, etc.)
  > and for `None` (which means "no profile resolved yet — treat
  > as non-SDK for routing decisions"). The predicate does not
  > probe the Claude CLI, does not check auth, does not read config.
  > It is a pure function of the profiles registry.

  Existing callers (`summary_oneshot.py`, the slice-170 dispatch
  renderer, and the new pre-scan) import from the canonical home;
  the old definition is removed. Re-homing is mechanical and lands
  in the first slice that needs it (likely the pre-scan slice;
  slice 170 can also adopt the new home if it ships afterward).

- **Boundary with 180-band loop / fan-out semantics.** Until-loops
  and fan-out branches will interact with classification — a loop
  containing an SDK dispatch is Claude-required; a fan-out
  dispatching to N non-SDK reviewers is not. The classification
  rule (per-step union) handles the simple cases. Edge cases
  (e.g., a loop whose body's resolved profile depends on a pool
  selection that varies per iteration) are pool-uncertain and
  fall under the conservative-vs-lazy decision above. The design
  *names* this boundary; it does not solve loop-finding-routing
  or fan-in aggregation.

---

## Anticipated Slices

These are exploratory boundaries to inform slice planning; not
commitments. Final slice plan will be drafted in `240-slices.…`.

- **Profile-Aware Dispatch Router (pure CLI).** The minimal fix:
  `DispatchAction._dispatch` checks `is_sdk_profile(profile)` on the
  resolved model and routes non-SDK profiles to `_dispatch_via_agent`
  even when `sdk_session` is non-None. Closes the immediate
  `sq run --param model=<non-sdk>` defect. No session-construction
  changes; the persistent session still connects at startup. Small,
  high-value, ships first.

- **Resolution Pre-Scan.** A pipeline-walking pass that produces a
  per-step classification report. Reusable by both the conditional-
  connect slice and the diagnostic CLI surface. Includes a
  "classify, don't select" resolver entrypoint to avoid pool
  selection side effects.

- **Conditional Persistent Session.** Apply the pre-scan: only
  construct + connect `SDKExecutionSession` when classification is
  Claude-required. `ActionContext` carries `sdk_session=None` for
  Claude-free runs. State persistence and resume tested under both
  shapes.

- **Pool-Resolution Classification Policy.** Define and implement
  conservative-vs-lazy handling for pool-uncertain steps. CLI flag
  or config key to opt into lazy. Error messaging and run-state
  shape for mid-run auth failure.

- **Auth-Classification Diagnostics.** `sq run --explain` (or
  equivalent) prints a pipeline's classification and per-step
  rationale without executing. Useful for users debugging
  auth-failure surprises and for documentation examples.

- **Error Semantics and Mid-Run Auth Failure.** Tighten the
  failure path: when classification expected non-SDK and pool
  selection forces SDK mid-run, produce a clear error, persist
  run state with a recoverable shape, and document resume.

- **Documentation and Pipeline Authoring Guide Updates.** Arch-doc
  cross-references in the pipeline authoring guide, examples of
  Claude-free pipelines, examples of mixed pipelines, and a
  troubleshooting section for the common auth surprises.

- **Test Matrix Slice.** Adversarial pipelines exercising the
  classification matrix (Claude-required, Claude-free, mixed,
  pool-conservative, pool-lazy). Asserts the persistent session is
  constructed iff expected, no Claude subprocess is spawned for
  Claude-free runs (process-level assertion), and resume preserves
  classification correctness.

The split is open to revision — likely 6–10 slices once design
proceeds. Conservative estimate is in the 8-slice range based on
the surface area surveyed.

---

## Related Work

- **Slice 170 — Profile-Aware Dispatch Model Routing** (in design,
  140-band): IDE / `/sq:run` axis of the same routing problem.
  Complementary; ships independently. See
  `user/slices/170-slice.profile-aware-dispatch-model-routing.md`.
- **Slice 145 — Dispatch Action** (140-band, complete): the
  router this initiative extends.
- **Slice 155 — SDK Pipeline Executor** (140-band, complete):
  where the persistent `SDKExecutionSession` is constructed and
  connected today (`cli/commands/run.py:_run_pipeline_sdk`).
- **Slice 158 — SDK Session Management and Compaction** (140-band,
  complete): defines compact/rotate semantics that this initiative
  preserves.
- **Slice 164 — Profile-Aware Summary Model Routing** (140-band,
  complete): precedent pattern for `is_sdk_profile()` branching;
  this initiative reuses the predicate at the dispatch router.
- **Initiative 180 — Pipeline Intelligence** (draft):
  pool-resolution mechanics that this initiative coordinates with
  but does not depend on. The classification ↔ pool boundary is
  named here; pool internals stay there.
- **`140-arch.pipeline-foundation.md`**: the foundation this
  initiative builds on. Action protocol, resolver cascade, executor
  shape, state machine — all unchanged.
- **`100-arch.orchestration-v2.md`**: agent registry, provider
  profiles, `ClaudeSDKAgent` path — consumed unchanged.
