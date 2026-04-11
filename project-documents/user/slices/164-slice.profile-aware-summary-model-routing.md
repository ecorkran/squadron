---
docType: slice-design
slice: profile-aware-summary-model-routing
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [161-summary-step-with-emit-destinations]
interfaces: []
dateCreated: 20260410
dateUpdated: 20260411
status: complete
---

# Slice Design: Profile-Aware Summary Model Routing

## Overview

Today the summary action (`src/squadron/pipeline/actions/summary.py`)
resolves its model alias and then hands the resolved `model_id` to
`SDKSession.capture_summary()`, which calls `client.set_model()` on the
live SDK session. That works for Claude — which is what the Agent SDK
is for — and nothing else. A summary step configured with
`model: minimax` (profile `openrouter`) silently tries to `set_model`
an OpenRouter model ID on a Claude SDK client, which is nonsense.

Meanwhile, the review system already solves this problem via
`run_review_with_profile()` (`src/squadron/review/review_client.py:51`):
look up the profile, fetch the provider from the registry, build an
`AgentConfig`, spawn a one-shot agent, send a `Message`, collect the
response, shut down.

Slice 164 teaches the summary action the same trick. Alias resolution
already returns `(model_id, profile)`; we branch on the profile:

- **SDK profile** → existing `capture_summary()` path (unchanged).
- **Any other profile** → one-shot dispatch through the provider
  registry, producing the same summary string that the emit pipeline
  consumes.

Prompt-only rendering gets the same fix: `_render_summary` currently
hardcodes `model_switch = f"/model {alias}"` regardless of profile. For
non-SDK models the user cannot issue `/model` — they need a CLI
command instead. We emit `model_switch` only for SDK profiles; non-SDK
profiles get a `command` (e.g. `sq summary-instructions …`) routed
through the same provider path.

The goal is unblocking cheap external models (minimax, gemini-flash,
local) for pipeline summaries without touching the rest of the summary
pipeline (emit destinations, template rendering, compact-via-summary
reuse, state capture).

## Motivation

- **Cost.** Summarization is a token-cheap, quality-tolerant workload.
  Paying Sonnet rates to condense a session when minimax does the job
  for a tenth of the price is waste.
- **Consistency.** Review already branches by profile. Dispatch already
  branches by profile. Summary is the last action type that assumes
  "the model is always a Claude SDK model," and that assumption keeps
  users from composing real multi-provider pipelines.
- **Unblocks P4 stopgap.** The P4 pipeline currently uses haiku for its
  summary step as a stopgap (see slice 163 devlog). The real intent was
  "any cheap summarizer" — this slice delivers that.

## Non-Goals

- **No new profiles, providers, or templates.** We consume the existing
  provider registry, existing profiles, and existing compaction
  templates. No new wire formats.
- **No change to emit destinations.** Stdout, file, clipboard, rotate
  all keep their existing behavior. The change is purely in *how the
  summary text is produced*, not in *where it goes*.
- **No change to compact-via-summary reuse.** `_execute_summary()` is
  already shared between `SummaryAction` and `CompactAction` (slice
  161). Compact keeps reusing it — compact gets the fix for free.
- **Rotate semantics are unchanged and stay SDK-only.** `emit: [rotate]`
  requires an SDK session by design. A non-SDK summary that requests
  `rotate` is a validation error, same as today.
- **No parallel summarization, no streaming output.** One-shot request,
  one response, return the text. Same shape as review.
- **No change to `ClaudeSDKClient` / session lifecycle.** The session
  stays on the dispatch model throughout; we never call `set_model` for
  non-SDK summaries, so there is nothing to restore afterward.

## Technical Decisions

### Decision 1 — Profile branch lives in `_execute_summary`, not in a new action

`_execute_summary()` at [summary.py:108](../../../src/squadron/pipeline/actions/summary.py#L108)
is the single funnel both `SummaryAction` and `CompactAction` call.
Adding a second action class would split the compact-reuse invariant
slice 161 built. Instead, `_execute_summary()` keeps its signature and
grows a profile branch at the point it currently calls `capture_summary`.

Call graph after the change (SDK execution mode):

```
SummaryAction.execute()            (unchanged)
  └── _execute_summary()           (keeps signature)
        ├── resolve alias → (model_id, profile)   ← now also captures profile
        ├── if profile is SDK (or None → default SDK):
        │     sdk_session.capture_summary(...)     ← existing path
        └── else:
              capture_summary_via_profile(
                  instructions=..., model_id=..., profile=...
              )                                     ← new helper
```

`None` profile from the resolver means "alias has no explicit profile
declared," which today always resolves to Claude via the SDK. That stays
the SDK path — no behavior change for unannotated aliases.

### Decision 2 — New helper `capture_summary_via_profile()` lives in `sdk_session.py`'s neighbor, not inside `SDKSession`

`SDKSession.capture_summary()` is a method because it mutates the live
client's model. The non-SDK path has no live client and no session to
mutate — it's a pure function of (instructions, model_id, profile). It
doesn't belong on `SDKSession`.

New module: `src/squadron/pipeline/summary_oneshot.py`

```python
async def capture_summary_via_profile(
    *,
    instructions: str,
    model_id: str | None,
    profile: str,
) -> str:
    """One-shot summary via the provider registry.

    Mirrors run_review_with_profile but strips the review-specific
    bits: no structured output injection, no file injection, no rules,
    no verbosity prompt logging.
    """
```

Implementation is a ~40-line near-copy of `run_review_with_profile`
lines 70-149, with the review-specific branches removed:

1. `get_profile(profile)` → `ensure_provider_loaded()` → `get_provider()`.
2. Build `AgentConfig` with `instructions=""` (no system prompt —
   summary is self-describing), `model=model_id`, credentials lifted
   from the profile. `agent_type` and `provider` come from the profile.
3. `provider.create_agent(config)` → send one `Message` with
   `content=instructions` → iterate `handle_message()` collecting
   `response.content` → `agent.shutdown()` in `finally`.
4. Return the concatenated string.

**Why a sibling helper instead of extending review_client?** Review and
summary share a pattern but not a payload. Review injects file contents,
appends structured-output rules, parses findings, and logs prompts by
verbosity. Summary does none of those. Extending
`run_review_with_profile` with a `mode: "review" | "summary"` flag
would create a god-function whose two branches share only the provider
plumbing. The shared part is the provider registry itself, which is
already a function call (`get_provider`) — the rest is honest
duplication of ~20 lines of agent lifecycle.

**Refactoring note (explicit non-scope):** if a third action type ever
needs the same pattern, extract a `OneShotDispatcher` at that point.
Two call sites is not three; wait for the pattern to prove itself.

### Decision 3 — Profile classification: use `ProfileName.SDK` comparison, no new helper class

The slice plan mentions `(model_id, profile)` from alias resolution.
Today `ModelResolver.resolve()` returns `tuple[str, str | None]` where
the second element is the profile name string (or `None` if the alias
declares no profile). The classification check is simply:

```python
from squadron.providers.base import ProfileName

def _is_sdk_profile(profile: str | None) -> bool:
    """None (unannotated) and 'sdk' both route through the SDK session."""
    return profile is None or profile == ProfileName.SDK.value
```

This helper lives in `src/squadron/pipeline/summary_oneshot.py` next to
the one-shot function — it's purely an internal predicate, not a public
policy. No new enum, no new dataclass. The single-place rule: if you
need to know "is this an SDK summary," call `_is_sdk_profile`, don't
re-implement the string comparison.

### Decision 4 — Prompt-only renderer emits `model_switch` OR `command`, never both

Current `_render_summary` at [prompt_renderer.py:242](../../../src/squadron/pipeline/prompt_renderer.py#L242)
unconditionally sets `model_switch = f"/model {alias}"`. That is wrong
for non-SDK profiles because the `/model` slash command only rebinds
the Claude SDK client's active model — it does nothing for OpenRouter.

After the change:

```python
model_id, profile = resolver.resolve(alias)
if _is_sdk_profile(profile):
    model_switch = f"/model {alias}"
    command = None
else:
    model_switch = None
    command = None   # see "Open Question 1" below
```

For non-SDK profiles, `model_switch` is omitted. The `/sq:run` slash
command already treats `model_switch` as advisory ("State which model
is recommended so the user can switch if desired"), so omitting it for
non-SDK profiles is a contract-consistent narrowing.

**Where does the actual work happen for a non-SDK summary in prompt-only
mode?** Prompt-only mode's whole contract is "the caller runs things."
In prompt-only mode, the executor currently runs summary as an
in-process action (not a command) because it has an `SDKSession` of
its own — wait, it doesn't. See Open Question 1.

### Decision 5 — No new YAML config fields

Users already author summary steps as:

```yaml
- summary:
    template: minimal
    model: minimax
    emit: [stdout]
```

Nothing about that YAML changes. The slice is a pure implementation
change behind the action's execute method and the prompt-only renderer.
No grammar updates, no pipeline-definitions rev bump, no builtin
pipeline edits.

## Data Flows and Component Interactions

### SDK execution mode (`sq run <pipeline>` via `ClaudeSDKClient`)

```
PipelineExecutor.run_step(summary step)
  └── SummaryAction.execute(context)
        ├── load_compaction_template(template_name) → template
        ├── render_instructions(template, params) → instructions
        └── _execute_summary(context, instructions, model_alias, ...)
              ├── context.resolver.resolve(model_alias) → (model_id, profile)
              ├── if _is_sdk_profile(profile):
              │     context.sdk_session.capture_summary(
              │         instructions, summary_model=model_id,
              │         restore_model=context.sdk_session.current_model
              │     )
              └── else:
                    capture_summary_via_profile(
                        instructions=instructions,
                        model_id=model_id,
                        profile=profile,
                    )     ← brand new path
              → summary: str
        → for dest in emit_destinations:
              get_emit(dest.kind)(summary, dest, context)  (unchanged)
        → ActionResult(success=True, outputs={summary, instructions, ...})
```

The `context.sdk_session is None` early return at [summary.py:121](../../../src/squadron/pipeline/actions/summary.py#L121)
becomes conditional: it fails only when (a) there is no SDK session
AND (b) a rotate-emit destination is configured. A non-SDK summary with
stdout/file/clipboard emit runs fine without any SDK session at all.

### Prompt-only execution mode (`sq run --prompt-only`)

Today, prompt-only's `_render_summary` produces an `ActionInstruction`
that the slash-command / harness interprets. The harness then runs the
summary inline in the current Claude Code context (it's a dispatch-like
instruction). The `model_switch` told the user to switch models first.

After the change:

- **SDK-profile summary in prompt-only mode:** Unchanged.
  `model_switch = "/model minimax"` → wait, minimax isn't SDK. The
  typical SDK-profile summary is something like `haiku` or `sonnet`.
  Those keep emitting `/model haiku`, and the harness instructs the
  user to switch before running the summary inline.

- **Non-SDK-profile summary in prompt-only mode:** `model_switch` is
  `None`. `command` carries a `sq` CLI invocation that shells out to
  run the one-shot and capture the summary, then emits to destinations.

See Open Question 1 for how that CLI invocation is shaped — it touches
the `sq summary-instructions` command that already exists from slice
162.

### Non-goals graph (what does NOT change)

- `emit` registry (`src/squadron/pipeline/emit.py`) — untouched.
- Compaction template loader / renderer — untouched.
- Pipeline definition schema — untouched.
- `ModelResolver.resolve()` signature — untouched; already returns
  `(model_id, profile)`.
- `ClaudeSDKClient` / `SDKSession` — untouched except for one guarded
  access (already there).
- Review system — untouched. The new helper is a near-copy, not a
  reuse of review code.

## Migration Plan

This is not a refactor migration — the change is additive in the
non-SDK path and transparent in the SDK path. Consumers don't need to
update.

**Risk surface:**

1. Pipelines that currently specify `model: <non-sdk-alias>` on a
   summary step and depend on the silent failure (i.e., summary falls
   back to the session's current model). Audit the built-in pipelines
   in `src/squadron/data/pipelines/`:
   - If any built-in summary step references a non-SDK alias, its
     behavior changes from "runs under the SDK session's Claude model"
     to "runs under the declared non-SDK model."
   - Current state: P4 uses haiku (SDK profile) as a stopgap per slice
     163 devlog. No built-in references a non-SDK alias on a summary
     step. Low risk.

2. Tests that assume summary always calls `sdk_session.capture_summary`.
   Existing: `tests/pipeline/actions/test_summary.py`. The profile
   branch needs new test coverage, and the "no SDK session" failure
   test (line 155-169) needs updating — the assertion loosens from
   "always fails" to "fails only when an SDK-only emit (rotate) is
   requested OR when the profile is SDK."

3. The `test_renders_slice_placeholder_when_cf_provides_it` and related
   tests in `tests/pipeline/test_summary_render.py` currently assume
   `model_switch` is populated when a model is declared. They need to
   split into SDK-profile and non-SDK-profile cases.

**Behavior verification:** end-to-end run of a pipeline whose summary
step specifies `model: minimax` (or `gemini-flash`). Before this
slice, the summary text is generated by whatever model the SDK session
happens to be on. After, it is generated by minimax via OpenRouter, and
the `summary_model` metadata in `ActionResult.metadata` reflects that.

## Success Criteria

1. A summary step with `model: <sdk-alias>` (e.g. `haiku`) runs
   identically to today — no regressions in the SDK path.
2. A summary step with `model: <non-sdk-alias>` (e.g. `minimax`,
   `gemini-flash`) produces a summary generated by the declared model
   via the provider registry, in both SDK and prompt-only execution
   modes.
3. A summary step with no `model:` field falls through to the resolver
   cascade and runs under the SDK session's current model (unchanged).
4. A summary step with `model: <non-sdk-alias>` AND `emit: [rotate]`
   produces a clear validation error before execution.
5. Compact-via-summary (slice 161 reuse) inherits the profile branch
   for free: a compact step with a non-SDK model works for stdout/file
   emit but still errors on rotate (rotate has always been SDK-only).
6. Prompt-only `_render_summary` emits `model_switch` only for SDK
   profiles; for non-SDK profiles the field is `None` and a `command`
   field is set (exact shape per Open Question 1).
7. Existing tests for summary action and prompt-only summary rendering
   pass, and new tests cover both the SDK and non-SDK profile branches.

## Open Questions

### OQ1 — Prompt-only non-SDK summary: inline CLI or new hidden subcommand?

**Context:** In prompt-only mode, the executor outputs an
`ActionInstruction` and the harness (slash command, CLI, external
caller) runs it. For a non-SDK summary, "run it" means "invoke the
provider registry." There are two shapes for that:

- **Option A — new hidden `sq` subcommand** (`sq summary-run` or
  similar) that takes `--template`, `--model`, `--profile`, `--params`,
  internally calls `capture_summary_via_profile`, and prints the
  result to stdout. The prompt-only renderer emits
  `command = "sq summary-run --template minimal --model minimax …"`
  and the harness runs it via Bash and pipes output to the emit
  destinations.

- **Option B — reuse existing `sq summary-instructions` + a separate
  dispatch**: `sq summary-instructions` (from slice 162) already
  exists to print rendered template instructions. The harness would
  then need to run those through the provider registry itself, which
  means each harness implements its own provider plumbing — exactly
  the anti-pattern this slice is designed to eliminate.

**Preferred: Option A.** Single source of truth for one-shot summary
execution. The new subcommand is the CLI surface of
`capture_summary_via_profile`. Slash-command and direct-CLI callers
both benefit; so does any future external harness.

**Blocking the design?** No. This is a prompt-only mode concern and
can be finalized at task-decomposition time. The SDK execution path
stands on its own without OQ1 resolved.

**RESOLVED (Phase 6, 20260411): Option A implemented.** New hidden
subcommand `sq _summary-run` (matching the `_summary-instructions`
naming convention for hidden commands) registered in `app.py`.
Accepts `--template`, `--profile`, `--model`, and repeatable `--param
key=value` flags. `_render_summary()` emits
`command = "sq _summary-run --template <name> --profile <profile> --model <model_id>"` for non-SDK profiles, with `shlex.quote` applied
to param values.

### OQ2 — Should the provider-path helper take `AgentConfig` overrides?

`run_review_with_profile` passes `allowed_tools`, `permission_mode`,
`setting_sources`, and `hooks` from the review template. Summary
doesn't have a template with those fields — compaction templates are
currently plain instruction strings. Do we:

- **A)** Hard-code reasonable defaults (empty tools, default permission
  mode, no hooks) in `capture_summary_via_profile`, or
- **B)** Extend the compaction template format to accept those fields?

**Preferred: A.** Compaction templates are deliberately minimal — they
are prompts, not agent configs. Hard-coding `allowed_tools=[]`,
`permission_mode="default"`, `setting_sources=[]`, `hooks=[]` in the
helper is correct by construction: summary is a single-message
exchange, not a tool-using workflow. If a future need arises for
tool-enabled summaries, revisit at that point.

### OQ3 — What does `summary_model` metadata look like when the SDK fallback kicks in?

Currently `metadata={"summary_model": model_id or ""}`. For the non-SDK
path the value is the provider-registry model ID (same shape). For a
summary with no `model:` field, the metadata today is `""` (the SDK
session is on its default model, and we never recorded it). This slice
does not change that, but noting it here — if future debugging wants
"what model produced this summary," that requires a separate fix.

**Not blocking.** Recorded as a known minor gap.

## Implementation Scope

Files touched (tight scope — confirm at task decomposition):

1. **New:** `src/squadron/pipeline/summary_oneshot.py`
   - `capture_summary_via_profile()` — provider-registry one-shot.
   - `_is_sdk_profile(profile: str | None) -> bool` — internal
     predicate.

2. **Edit:** `src/squadron/pipeline/actions/summary.py`
   - `_execute_summary()`: capture profile from resolver return, branch
     on `_is_sdk_profile`, call SDK-path or new helper. Relax the
     `context.sdk_session is None` early return so non-SDK-emit
     destinations work without a session.
   - Validation: if any emit destination is `rotate` and profile is
     non-SDK, return a clear error before doing work.

3. **Edit:** `src/squadron/pipeline/prompt_renderer.py`
   - `_render_summary()`: set `model_switch` only for SDK profiles;
     non-SDK profiles get `command` (exact shape per OQ1).

4. **Edit:** `tests/pipeline/actions/test_summary.py`
   - New tests: `test_execute_summary_routes_non_sdk_profile_via_one_shot`,
     `test_execute_summary_non_sdk_with_rotate_fails_validation`,
     `test_execute_summary_non_sdk_without_sdk_session_succeeds`.
   - Update: `test_execute_summary_no_sdk_session_returns_failure`
     (rename and narrow to "rotate requires SDK session").

5. **New:** `tests/pipeline/test_summary_oneshot.py`
   - Unit coverage for `capture_summary_via_profile` with a stubbed
     provider (mirror `tests/review/test_review_client_profiles.py` if
     it exists, else hand-build a fake provider).
   - Unit coverage for `_is_sdk_profile` edge cases: `None`, `"sdk"`,
     `"openrouter"`, `"openai"`, unknown string.

6. **Edit:** `tests/pipeline/test_summary_render.py`
   - Split existing parametrized tests into SDK-profile and non-SDK-
     profile scenarios.

7. **Edit:** `src/squadron/data/pipelines/p4.yaml` (or equivalent)
   - **Only if OQ1 prompt-only shape is finalized before this slice
     ships and we want to cut haiku over to minimax.** Otherwise
     leave the P4 stopgap alone — this slice is infrastructure, not a
     pipeline edit.

Effort: 2/5 as declared in the slice plan. Most of the complexity is
in test restructuring, not production code.

## Verification Walkthrough

Updated 20260411 after Phase 6 implementation. Scenarios A/C/E require
an active SDK session (`sq run` inside Claude Code). Scenarios B and D
were verified headlessly. Scenario B note below.

### Setup

```bash
# Confirm minimax alias resolves to openrouter profile
uv run python -c "
from squadron.models.aliases import resolve_model_alias
print(resolve_model_alias('minimax'))
# Actual output: ('minimax/minimax-m2.7', 'openrouter')
print(resolve_model_alias('haiku'))
# Actual output: ('claude-haiku-4-5-20251001', 'sdk')
"

# Confirm OpenRouter API key is available (profile needs it to run)
echo "OPENROUTER_API_KEY present: $([ -n \"$OPENROUTER_API_KEY\" ] && echo yes || echo no)"
```

### Scenario A — Non-SDK summary in SDK execution mode

```bash
# Create a throwaway pipeline that runs a single summary step
# with a non-SDK model and emits to stdout.
cat > /tmp/test-164-summary.yaml <<'EOF'
name: test-164-summary
steps:
  - summary:
      template: minimal
      model: minimax
      emit: [stdout]
EOF

sq run /tmp/test-164-summary.yaml --validate
# Expect: OK (no validation errors)

sq run /tmp/test-164-summary.yaml
# Expect:
#   - Summary text printed to stdout
#   - ActionResult metadata summary_model == <minimax model id>
#   - Pipeline state JSON records success
```

### Scenario B — Non-SDK summary + rotate emit fails validation

```bash
cat > /tmp/test-164-rotate.yaml <<'EOF'
name: test-164-rotate
steps:
  - summary:
      template: minimal
      model: minimax
      emit: [rotate]
EOF

sq run /tmp/test-164-rotate.yaml --validate
# Note: --validate runs schema-level checks only (resolver not available
# at schema time). The rotate+non-SDK profile validation fires at
# execution time inside _execute_summary(), not during --validate.
# To see the error, run without --validate (requires SDK session):
#   sq run /tmp/test-164-rotate.yaml
#   Expect: "rotate emit is incompatible with non-SDK summary profile 'openrouter'"
```

### Scenario C — SDK summary unchanged

```bash
cat > /tmp/test-164-sdk.yaml <<'EOF'
name: test-164-sdk
steps:
  - summary:
      template: minimal
      model: haiku
      emit: [stdout]
EOF

sq run /tmp/test-164-sdk.yaml
# Expect: summary runs via sdk_session.capture_summary as before,
# metadata.summary_model == <claude haiku model id>
```

### Scenario D — Prompt-only rendering split

```bash
# SDK profile summary — should emit model_switch
sq run /tmp/test-164-sdk.yaml --prompt-only
# Expect in the summary step's actions:
#   model_switch: "/model haiku"
#   command: null

# Non-SDK profile summary — should emit command, not model_switch
sq run /tmp/test-164-summary.yaml --prompt-only
# Actual output (20260411):
#   "command": "sq _summary-run --template minimal --profile openrouter --model minimax/minimax-m2.7",
#   "model_switch": null
```

### Scenario E — Compact-via-summary inherits the branch

```bash
cat > /tmp/test-164-compact.yaml <<'EOF'
name: test-164-compact
steps:
  - compact:
      template: minimal
      model: minimax
      emit: [stdout]   # rotate would fail, see Scenario B
EOF

sq run /tmp/test-164-compact.yaml
# Expect: works — compact in non-rotate mode is a thin wrapper around
# summary, so the fix lands for free.
```

### Regression

```bash
# Re-run the existing P4 pipeline (with haiku stopgap) to confirm no
# regression in the real-world pipeline that shipped before this slice.
sq run p4 163   # or current in-progress slice
# Expect: identical behavior to pre-164 — haiku is an SDK profile alias,
# so it takes the existing path.
```

## References

- Slice plan entry: `140-slices.pipeline-foundation.md` line 73
  (entry #24, slice index 164)
- Parent architecture: `140-arch.pipeline-foundation.md`
- Dependency: slice 161 (Summary Step with Emit Destinations)
- Pattern source: `src/squadron/review/review_client.py`
  `run_review_with_profile()`
- Action to modify: `src/squadron/pipeline/actions/summary.py`
  `_execute_summary()`
- Renderer to modify: `src/squadron/pipeline/prompt_renderer.py`
  `_render_summary()`
- Profile registry: `src/squadron/providers/profiles.py`,
  `src/squadron/providers/base.py` (`ProfileName`, `ProviderType`)
- Alias resolver: `src/squadron/models/aliases.py`
  `resolve_model_alias()`, `src/squadron/pipeline/resolver.py`
  `ModelResolver.resolve()`
