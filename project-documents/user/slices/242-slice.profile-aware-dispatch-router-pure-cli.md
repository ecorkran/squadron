---
docType: slice-design
slice: profile-aware-dispatch-router-pure-cli
project: squadron
parent: 240-slices.pipeline-auth-boundary-flexibility.md
dependencies:
  - 241-is-sdk-profile-predicate-re-homing
  - 170-profile-aware-dispatch-model-routing
  - 145-dispatch-action
interfaces: []
dateCreated: 20260503
dateUpdated: 20260503
status: complete
---

# Slice Design: Profile-Aware Dispatch Router (pure CLI)

## Overview

Slice 170 fixed profile-aware dispatch routing on the **IDE / `/sq:run`**
axis: the prompt-only renderer emits a runnable `sq _dispatch-run`
command for non-SDK profiles, and the slash handler executes it via
Bash. The **pure-CLI / SDK-executor** axis still has the analogous
defect. When `sq run … --param model=<non-sdk>` runs through
`_run_pipeline_sdk`, an `SDKExecutionSession` has already been
constructed at startup, so `ActionContext.sdk_session is not None` for
every step. `DispatchAction._dispatch` (line 134) routes purely on
`sdk_session is not None`, so a non-SDK alias like `minimax` is sent to
`_dispatch_via_session` — which calls `session.set_model(model_id)` on
a Claude SDK session. The model-id is accepted (it is just a string),
the persistent Claude session dispatches the prompt to *Claude* under
that label, and the user sees Claude output where they expected
minimax output.

This slice closes that defect with the smallest possible change: branch
`_dispatch` on `is_sdk_profile(profile)` (now imported from its
canonical home in `providers/profiles.py` after slice 241) and route
non-SDK profiles to `_dispatch_via_agent` even when a persistent SDK
session is available.

No session-construction changes. The persistent session is still
constructed at executor startup; this slice only changes how an
already-constructed session is *used*. Conditional construction is
slice 244's job.

## Problem Statement

**Concrete defect.** From a real terminal:

```
sq run P4 183 --param model=minimax
```

Today's path through `_run_pipeline_sdk`:

1. Executor constructs `SDKExecutionSession` at startup (Claude auth
   required regardless of resolved models).
2. Each step's `ActionContext` carries `sdk_session=<the session>`.
3. `DispatchAction._dispatch` sees `context.sdk_session is not None`
   and routes to `_dispatch_via_session`.
4. `_dispatch_via_session` resolves `minimax` → `(minimax-…,
   "openrouter")`, then calls `session.set_model("minimax-…")` on a
   *Claude* session. The session accepts the string and dispatches
   the prompt to Claude.
5. User receives Claude's response in their design artifact, with
   `metadata.profile == "sdk-session"` and `metadata.model ==
   "minimax-…"`. Silent misrouting — no error, no warning.

The IDE axis (slice 170) is already correct because the prompt-only
renderer at [prompt_renderer.py:159](src/squadron/pipeline/prompt_renderer.py#L159)
already branches on `is_sdk_profile(profile)` and emits the
`sq _dispatch-run` command for non-SDK profiles. The SDK executor has
no such branch.

## Goals

- `sq run P4 183 --param model=minimax` from a real terminal routes
  the dispatch through `_dispatch_via_agent` (one-shot agent via
  registry, OpenRouter provider) regardless of whether
  `context.sdk_session` is set.
- `sq run P4 183` (no `--param model`) with a default Claude profile
  continues to use `_dispatch_via_session` and the persistent SDK
  session, identical to current behaviour.
- A mixed pipeline (some steps default Claude, some explicit
  `step_model: minimax`) routes per-step correctly: Claude steps via
  `_dispatch_via_session`, non-SDK steps via `_dispatch_via_agent`.
- The `metadata.profile` field on the dispatch result accurately
  reflects which path executed (`"sdk-session"` for session path,
  the resolved profile name for agent path).

## Non-Goals

- **No conditional session construction.** The persistent session is
  still built at startup. If the *entire* pipeline is non-SDK, the
  session is still constructed and connected (and unused). That
  optimisation is slice 244.
- **No pre-scan.** Routing decisions are made per-step at action
  execution time, using the same resolver cascade the action already
  uses. That's slice 243.
- **No new diagnostics.** `sq run --explain` is slice 246.
- **No changes to `_dispatch_via_agent` itself.** The path already
  exists and is exercised by IDE-axis flows; this slice only
  changes when the executor reaches it.
- **No changes to summary, review, compact, or any other action.**
  Their routing concerns are addressed by their own slices (164 for
  summary already lives in production).

## Design

### 1. Branch routing in `DispatchAction._dispatch`

[src/squadron/pipeline/actions/dispatch.py:132-136](src/squadron/pipeline/actions/dispatch.py#L132-L136) currently:

```python
async def _dispatch(self, context: ActionContext) -> ActionResult:
    """Route to session or agent dispatch path."""
    if context.sdk_session is not None:
        return await self._dispatch_via_session(context, context.sdk_session)
    return await self._dispatch_via_agent(context)
```

The change resolves the model first, applies the predicate, and uses
the session only when *both* the session is present and the resolved
profile is SDK:

```python
async def _dispatch(self, context: ActionContext) -> ActionResult:
    """Route to session or agent dispatch path based on resolved profile.

    Precedence:
    1. If no persistent session is available → agent path.
    2. If a session is available but the resolved profile is non-SDK
       → agent path (session bypassed for this step).
    3. Otherwise (session + SDK profile, including the None-profile
       default per is_sdk_profile contract) → session path.
    """
    if context.sdk_session is None:
        return await self._dispatch_via_agent(context)

    _, alias_profile = self._resolve_model(context)
    if not is_sdk_profile(alias_profile):
        return await self._dispatch_via_agent(context)

    return await self._dispatch_via_session(context, context.sdk_session)
```

`_resolve_model(context)` is a small private helper extracted from
the existing duplicated cascade in `_dispatch_via_session` and
`_dispatch_via_agent` (both currently inline the same
`action_model` / `step_model` / `resolver.resolve(...)` block). The
extraction is in scope for this slice because the routing decision
needs the *same* resolution the action will use, and duplicating the
resolve call risks drift if either branch evolves. The two
downstream methods continue to take `ActionContext` as today; the
helper is called once by `_dispatch` and once by whichever branch
actually executes (resolver is pure — calling twice is cheap and
keeps the branches' signatures unchanged).

Alternative considered: pass `(model_id, profile)` as a tuple into
the branch methods. Rejected because it widens both private method
signatures purely to save one resolver call (~µs, pure dict
lookup), and complicates resume-time mocking in tests.

### 2. `is_sdk_profile` import

Top of file imports the predicate from its canonical home:

```python
from squadron.providers.profiles import is_sdk_profile
```

This is the only new import at module level. Slice 241 already
established this import path elsewhere
([prompt_renderer.py:23](src/squadron/pipeline/prompt_renderer.py#L23),
[actions/summary.py:11](src/squadron/pipeline/actions/summary.py#L11)).

### 3. Predicate contract usage

`is_sdk_profile(None)` returns `True` per the slice-241 contract
(arch iteration 3). Concretely: when `--param model` is absent and
no `step_model` is configured, the resolver returns `(model_id,
None)` and the routing branch falls through to the session path.
This preserves today's default-Claude behaviour exactly. The
contract is the reason this slice does not need a separate "no
model specified" branch — `is_sdk_profile` already encodes that
case.

### 4. Metadata correctness

`_dispatch_via_session` writes `metadata.profile = "sdk-session"`.
`_dispatch_via_agent` writes the resolved profile name (e.g.
`"openrouter"`). Today, the session path is reached for non-SDK
profiles and the misrouted result still claims `"sdk-session"` —
which is technically accurate (Claude session was used) but
masks the bug in artifact metadata. After this slice, profile
metadata is always truthful: a `metadata.profile == "openrouter"`
result was actually dispatched to OpenRouter, not Claude with an
OpenRouter alias slapped on.

No metadata schema changes; the existing strings continue to mean
what they have always meant. The fix is that the routing now
matches what the metadata claims.

### Data flow

```
sq run P4 183 --param model=minimax
  └─ _run_pipeline_sdk
       ├─ constructs SDKExecutionSession (unchanged this slice)
       └─ for each step, builds ActionContext with sdk_session=<session>
            └─ DispatchAction._dispatch
                 ├─ resolver.resolve(action_model="minimax", …)
                 │     → ("minimax-…", "openrouter")
                 ├─ is_sdk_profile("openrouter") → False
                 └─ _dispatch_via_agent(context)
                       └─ one_shot_dispatch(...) → registry → minimax response

sq run P4 183  (default Claude)
  └─ _run_pipeline_sdk
       └─ DispatchAction._dispatch
            ├─ resolver.resolve(action_model=None, …) → (claude-…, None)
            ├─ is_sdk_profile(None) → True
            └─ _dispatch_via_session(context, session)
                  └─ session.set_model + session.dispatch (unchanged)
```

### Failure Modes

The new branch introduces no new I/O paths; both `_dispatch_via_*`
methods exist today with their own failure semantics (slice 170 for
agent path; slice 145 for session path). The only failure surface
unique to this slice is the routing decision itself.

- *Resolver raises during routing.* `_resolve_model` can raise
  `ModelResolutionError` or `ModelPoolNotImplemented` (same as today
  inside the branches). The existing `try/except` in
  `DispatchAction.execute` ([dispatch.py:114](src/squadron/pipeline/actions/dispatch.py#L114))
  already catches both and returns
  `ActionResult(success=False, error=…)`. No new handling needed.
  Observable: the error string in `ActionResult.error` and standard
  pipeline halt.
- *`is_sdk_profile` returns unexpected value.* Cannot — the function
  is a pure dict lookup over the static profiles registry with a
  documented `bool` return. Tested in slice 241.
- *`_resolve_model` returns `(model_id, "")` (empty string profile).*
  The slice-241 contract returns `False` for `""`, routing to the
  agent path. The agent path then resolves the profile from the
  alias inside `_dispatch_via_agent`. If that re-resolution also
  yields no profile, `ProfileName.SDK` is the existing fallback at
  [dispatch.py:241](src/squadron/pipeline/actions/dispatch.py#L241). No new
  failure mode.

### Performance Notes

The resolver cascade is invoked one extra time per dispatch step
(once in `_dispatch` for routing, once in the chosen branch). The
cascade is `dict.get` over a small in-memory mapping; cost is
sub-microsecond. No measurable impact on pipeline latency.

The motivating case (`--param model=<non-sdk>`) still pays the
persistent-session-construction cost at startup (Claude auth +
spawn). That waste is the price of "no session-construction
changes" in this slice's non-goals; slice 244 addresses it.

## Cross-Slice Dependencies

- **Slice 241 (`is_sdk_profile` re-homing)** — required. This slice
  imports the predicate from `squadron.providers.profiles`. Slice
  241 is complete (commit `393af52`).
- **Slice 170 (Profile-Aware Dispatch Model Routing)** — sibling. The
  IDE-axis fix; this slice is its pure-CLI mirror. No code shared,
  but the logical contract is identical: "route to agent path when
  the resolved profile is non-SDK." Slice 170 is complete.
- **Slice 145 (Dispatch Action)** — base. `DispatchAction` and its
  two `_dispatch_via_*` methods are slice 145; this slice extends
  the routing inside `_dispatch` only.

No interface contracts change. `ActionContext`, `ActionResult`,
`SDKExecutionSession`, and `ModelResolver` are unchanged.

## Migration Plan

This is a pure-routing refactor, not a migration. Source/destination
of the routing decision both live in `_dispatch`. No file moves, no
import-site fan-out (`is_sdk_profile` is already importable from
`squadron.providers.profiles` since slice 241).

Behaviour verification: existing `tests/pipeline/actions/test_dispatch.py`
and `tests/pipeline/actions/test_dispatch_session.py` cover today's
path semantics; the new tests below cover the routing branch.

## Success Criteria

1. `sq run P4 <slice> --param model=minimax` from a real terminal
   produces a dispatch result with `metadata.profile == "openrouter"`
   (or the resolver's chosen non-SDK profile name) and the dispatched
   prompt was handled by minimax via OpenRouter, not by the
   persistent Claude session.
2. `sq run P4 <slice>` with default Claude continues to produce a
   dispatch result with `metadata.profile == "sdk-session"`, identical
   to current main.
3. A pipeline with two dispatch steps where step A has no `step_model`
   (default Claude) and step B has `step_model: minimax` routes step A
   through `_dispatch_via_session` and step B through
   `_dispatch_via_agent`. Asserted by step-level metadata.
4. `is_sdk_profile(None)` falls through to the session path
   (regression guard for the slice-241 contract).
5. Unit tests below pass; `tests/pipeline/actions/test_dispatch.py` and
   `tests/pipeline/actions/test_dispatch_session.py` continue to pass.
6. `ruff format` / `ruff check` / `pyright` clean; full pytest suite
   green.

## Test Plan

New unit tests in `tests/pipeline/actions/test_dispatch.py` (or a
dedicated `test_dispatch_routing.py` if the existing file is large —
decision deferred to task breakdown):

- `test_dispatch_routes_to_agent_when_session_present_but_profile_non_sdk`
  — fake `SDKExecutionSession` provided; `--param model=minimax`;
  resolver mocked to return `("minimax-…", "openrouter")`; assert
  `_dispatch_via_agent` was called and `_dispatch_via_session` was
  not. Verifies `metadata.profile` matches the agent-path value.
- `test_dispatch_routes_to_session_when_profile_is_sdk` — fake
  session present, default model resolves to `(claude-…, None)`;
  `is_sdk_profile(None) == True`; assert session path runs.
- `test_dispatch_routes_to_session_for_explicit_sdk_profile` — fake
  session present, alias resolves to `(claude-…, "sdk")`; assert
  session path runs.
- `test_dispatch_routes_to_agent_when_no_session` — `sdk_session=None`
  in context; assert agent path runs regardless of profile (today's
  behaviour, regression guard).
- `test_dispatch_mixed_pipeline_routes_per_step` — two consecutive
  dispatches in one test, one default and one with non-SDK alias;
  asserts each routed independently and per-step metadata is correct.

The existing test files cover the leaf behaviours of each branch;
this slice adds coverage of the *router* in front of them.

End-to-end manual coverage in the verification walkthrough.

## Risks

- **Resolver double-call shape.** `_resolve_model` is invoked once
  in `_dispatch` and again inside the chosen `_dispatch_via_*`
  branch. Both branches use the same cascade with the same inputs,
  and the resolver is pure (verified in slice 243's research notes
  and by inspection of [resolver.py](src/squadron/pipeline/resolver.py)).
  The risk is a future change to the resolver that introduces a
  side-effect (caching, telemetry) where the doubled call would
  matter. Mitigation: the slice-243 inspection note already calls
  out resolver purity as a contract; if that ever changes, both
  this slice and slice 243 need to reroute through a memoised
  resolution. Documented in this slice and in the slice-244
  ActionContext-propagation work.

## Verification Walkthrough

This is the demo script the user runs after implementation. Assumes
a squadron project at the current working directory with at least
one design slice (e.g. 183) and provider profiles configured for
both Claude (`sdk`) and a non-SDK alias (`minimax` → `openrouter`).

**Step 1 — Pure-CLI non-SDK model routes through agent path.**

In a real terminal (no IDE):

```
sq run P4 183 --param model=minimax
```

Expected:
- Pipeline executor builds `SDKExecutionSession` (Claude auth
  required at startup — slice 244 will fix this).
- Dispatch action's `metadata.profile == "openrouter"` (visible in
  `~/.config/squadron/runs/<run-id>/state.json` under the dispatch
  step's `result.metadata`).
- `metadata.model == "<resolved minimax id>"`.
- Design artifact under `project-documents/user/slices/` is the
  work of minimax, not Claude.

**Step 2 — Pure-CLI default Claude still uses session path.**

```
sq run P4 183
```

Expected:
- Dispatch action's `metadata.profile == "sdk-session"`.
- Same artifact behaviour as current main (regression guard).

**Step 3 — Mixed pipeline routes per-step.**

Configure a pipeline with two dispatch steps:
- Step `dispatch-a`: no `step_model` (default Claude).
- Step `dispatch-b`: `step_model: minimax`.

Run:

```
sq run <pipeline-with-both-steps>
```

Expected:
- `dispatch-a.metadata.profile == "sdk-session"`.
- `dispatch-b.metadata.profile == "openrouter"`.
- Each step's response content reflects the model that actually
  handled it (Claude vs. minimax).

**Step 4 — IDE axis unchanged.**

In Claude Code IDE:

```
/sq:run P4 183 --param model=minimax
```

Expected:
- Slash handler still emits `sq _dispatch-run` command (slice 170
  path, unchanged).
- This slice does not affect prompt-only rendering; verify by
  inspecting the rendered JSON shows `command` field present, no
  `model_switch`.

**Step 5 — Quality gates.**

```
uv run ruff format src/ tests/
uv run ruff check src/ tests/
uv run pyright
uv run pytest
```

Expected: all clean / green.

**Step 6 — Targeted test suite.**

```
uv run pytest tests/pipeline/actions/test_dispatch.py \
              tests/pipeline/actions/test_dispatch_session.py -q
```

Expected: all dispatch tests pass, including the new routing tests
added by this slice.
