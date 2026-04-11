---
docType: tasks
slice: profile-aware-summary-model-routing
project: squadron
lld: user/slices/164-slice.profile-aware-summary-model-routing.md
dependencies: [161-summary-step-with-emit-destinations]
projectState: Slice 164 design complete and reviewed (PASS by minimax-m2.7). Working tree clean on main; CI green after pyright fix in 32fc9e7.
dateCreated: 20260411
dateUpdated: 20260411
status: complete
---

## Context Summary

- Working on slice 164: Profile-Aware Summary Model Routing
- Goal: route summary action through the provider registry (one-shot)
  for non-SDK profiles, mirroring the pattern review uses via
  `run_review_with_profile()`. SDK profiles keep the existing
  `SDKSession.capture_summary()` path.
- Implementation centers on `_execute_summary()` in
  `src/squadron/pipeline/actions/summary.py` (the shared helper used by
  both `SummaryAction` and `CompactAction` per slice 161 reuse).
- New module `src/squadron/pipeline/summary_oneshot.py` houses the
  one-shot helper (`capture_summary_via_profile`) and the
  `_is_sdk_profile()` predicate. Deliberate near-copy of the relevant
  ~40 lines from `run_review_with_profile()`; not a refactor of review.
- Prompt-only `_render_summary` in
  `src/squadron/pipeline/prompt_renderer.py` splits its output: SDK
  profiles get `model_switch`, non-SDK profiles get `command` (shape
  finalized in T7 — preferred Option A: new hidden `sq summary-run`
  subcommand from OQ1).
- Unblocks cheap external models (minimax, gemini-flash) for pipeline
  summaries.
- Risk surface is mostly test restructuring; production code change is
  small and additive.
- Next: Phase 6 implementation.

---

## Tasks

### T1: Verify source files and locate insertion points

- [x] Read `src/squadron/pipeline/actions/summary.py` — confirm
  `_execute_summary()` body, the `context.sdk_session is None` early
  return at line ~121, and the resolver call at line ~132 that already
  destructures `(model_id, profile)` but discards `profile`
- [x] Read `src/squadron/pipeline/sdk_session.py` — confirm
  `capture_summary()` signature and that nothing else needs to change
  on the SDK side
- [x] Read `src/squadron/review/review_client.py` — re-read
  `run_review_with_profile()` lines 51–164; identify exactly which
  ~40 lines (provider lookup → AgentConfig → create_agent → handle_message
  → shutdown) are the reusable shape
- [x] Read `src/squadron/providers/profiles.py` and
  `src/squadron/providers/base.py` — confirm `ProfileName.SDK.value`
  is the canonical "is-SDK" comparison string
- [x] Read `src/squadron/pipeline/resolver.py` — confirm
  `ModelResolver.resolve()` returns `tuple[str, str | None]` where the
  second element is the profile name string (or `None`)
- [x] Read `src/squadron/pipeline/prompt_renderer.py` `_render_summary`
  at line ~242 — confirm current `model_switch` handling
- [x] Read `src/squadron/pipeline/actions/compact.py` lines ~173–251 —
  confirm compact's SDK branch delegates to `_execute_summary()` and
  inherits the fix automatically
- [x] Read `tests/pipeline/actions/test_summary.py` — catalog every
  test that asserts on `sdk_session.capture_summary` being called or
  on the "no SDK session returns failure" path
- [x] Read `tests/pipeline/test_summary_render.py` — catalog tests that
  assert on `model_switch` content for summary actions
  - [x] All insertion points and test sites understood before
    proceeding

---

### T2: Create `summary_oneshot.py` with `_is_sdk_profile()` predicate

- [x] Create new file `src/squadron/pipeline/summary_oneshot.py` with
  module docstring and `from __future__ import annotations`
- [x] Add `_is_sdk_profile(profile: str | None) -> bool`:
  - Returns `True` when `profile is None` (unannotated alias)
  - Returns `True` when `profile == ProfileName.SDK.value`
  - Returns `False` otherwise
- [x] Import `ProfileName` from `squadron.providers.base`
- [x] Function is module-public (no underscore) so it can be imported
  by both `summary.py` and `prompt_renderer.py` without going through
  a private name
- [x] Rename to `is_sdk_profile` (drop the leading underscore — it's
  cross-module)
  - [x] File created at correct path
  - [x] `ProfileName.SDK.value` is the only string compared (no raw
    `"sdk"` literal)
  - [x] Function has a one-line docstring naming the contract:
    "None and 'sdk' both route through the SDK session"

### T3: Test `is_sdk_profile()`

- [x] Create `tests/pipeline/test_summary_oneshot.py` (or reuse if
  someone else opened it first)
- [x] Parametrized test covering: `None` → `True`, `"sdk"` → `True`,
  `"openrouter"` → `False`, `"openai"` → `False`, `"gemini"` → `False`,
  `"local"` → `False`, `"openai-oauth"` → `False`, `"unknown-future"`
  → `False`
- [x] Run: `uv run pytest tests/pipeline/test_summary_oneshot.py -v`
  - [x] All cases pass
  - [x] Test imports `is_sdk_profile` from
    `squadron.pipeline.summary_oneshot`

---

### T4: Implement `capture_summary_via_profile()` in `summary_oneshot.py`

- [x] Add async function with signature:
  ```python
  async def capture_summary_via_profile(
      *,
      instructions: str,
      model_id: str | None,
      profile: str,
  ) -> str:
  ```
- [x] Body mirrors `run_review_with_profile()` lines 70–149, with
  these deliberate omissions:
  - No structured-output instructions appended to system prompt
  - No file-content injection (no `_inject_file_contents` call)
  - No rules content
  - No verbosity branches / prompt log writing
  - No `parse_review_output` call — return the raw concatenated string
  - System prompt is the empty string (`""`) — summary instructions are
    self-describing, carried in the user prompt
- [x] Provider lookup:
  - `provider_profile = get_profile(profile)`
  - `ensure_provider_loaded(provider_profile.provider)`
  - `provider = get_provider(provider_profile.provider)`
- [x] Build `AgentConfig` with:
  - `name=f"summary-oneshot"`
  - `agent_type=provider_profile.provider`
  - `provider=provider_profile.provider`
  - `model=model_id`
  - `instructions=""`
  - `api_key=None`
  - `base_url=provider_profile.base_url`
  - `cwd=None`
  - `allowed_tools=[]`
  - `permission_mode="default"`
  - `setting_sources=[]`
  - `credentials={"api_key_env": provider_profile.api_key_env, "default_headers": provider_profile.default_headers, "hooks": [], "mode": "client"}`
- [x] Send a single `Message`:
  - `sender="summary-system"`
  - `recipients=[config.name]`
  - `content=instructions`
  - `message_type=MessageType.chat`
- [x] Iterate `agent.handle_message(message)` and accumulate
  `response.content` into a string, skipping responses where
  `response.metadata.get("sdk_type") == SDK_RESULT_TYPE` (same
  duplication guard review uses)
- [x] Wrap agent lifecycle in `try` / `finally` with
  `await agent.shutdown()` in `finally`
- [x] Return the concatenated string
- [x] Imports at top of `summary_oneshot.py`:
  - `from squadron.providers.base import ProfileName`
  - `from squadron.providers.profiles import get_profile`
  - `from squadron.providers.registry import get_provider, ensure_provider_loaded`
  - `from squadron.providers.config import AgentConfig` (or correct
    module — confirm in T1)
  - `Message`, `MessageType`, `SDK_RESULT_TYPE` from the same locations
    `review_client.py` imports them
  - [x] Function returns a `str`
  - [x] No review-specific code paths leaked in (no rules, no
    structured output, no parsing)
  - [x] `agent.shutdown()` is in `finally` so it always runs

### T5: Test `capture_summary_via_profile()` with a stub provider

- [x] In `tests/pipeline/test_summary_oneshot.py`, add tests using a
  fake provider that records the message it received and returns a
  canned response
- [x] Test: happy path — fake provider returns one
  `AgentMessage(content="SUMMARY OUTPUT")`; result equals
  `"SUMMARY OUTPUT"`
- [x] Test: multi-chunk response — fake provider yields two messages;
  result is the concatenation
- [x] Test: SDK_RESULT_TYPE duplication is filtered — fake provider
  yields one normal message and one with `metadata={"sdk_type": SDK_RESULT_TYPE}`
  having the same content; result has the content only once
- [x] Test: agent.shutdown() is called even when handle_message raises
  — fake provider raises mid-iteration; assert shutdown was called
- [x] Use a registered fake profile + provider for the duration of the
  test (register in a fixture, restore in teardown — see how
  `test_review_client_profiles.py` does it if it exists, otherwise use
  `monkeypatch` on the registry dicts)
- [x] Run: `uv run pytest tests/pipeline/test_summary_oneshot.py -v`
  - [x] All tests pass
  - [x] No test depends on a real network call
  - [x] Fake provider does not leak between tests

### T6: Update `_execute_summary()` to branch on profile

- [x] In `src/squadron/pipeline/actions/summary.py` `_execute_summary()`:
  - [x] Capture both elements from the resolver:
    `model_id, profile = context.resolver.resolve(action_model=summary_model_alias, step_model=None)`
    when `summary_model_alias` is set
  - [x] When `summary_model_alias is None`, set `profile = None` and
    `model_id = None` (the resolver isn't called; the SDK fallback uses
    the session's current model)
- [x] Replace the unconditional `context.sdk_session is None` early
  return with a more precise guard:
  - [x] If any emit destination has `kind is EmitKind.ROTATE` AND
    `context.sdk_session is None`, fail with a clear error: "rotate
    emit requires an SDK session"
  - [x] If `is_sdk_profile(profile)` AND `context.sdk_session is None`,
    fail with the existing error: "summary action requires SDK
    execution mode for SDK-profile models"
  - [x] Otherwise, proceed (non-SDK profile + non-rotate emit can run
    without a session)
- [x] Add validation: if `is_sdk_profile(profile) is False` AND any
  emit destination has `kind is EmitKind.ROTATE`, return failure with
  error: "rotate emit is incompatible with non-SDK summary profile
  '{profile}'" — return *before* doing any provider work
- [x] Capture the summary by branching:
  ```python
  if is_sdk_profile(profile):
      restore_model = context.sdk_session.current_model
      summary = await context.sdk_session.capture_summary(
          instructions=instructions,
          summary_model=model_id,
          restore_model=restore_model,
      )
  else:
      assert profile is not None  # narrowed by is_sdk_profile False
      summary = await capture_summary_via_profile(
          instructions=instructions,
          model_id=model_id,
          profile=profile,
      )
  ```
- [x] Wrap both branches in the existing `try` / `except Exception`
  that produces the failure `ActionResult` (preserve current error
  shape)
- [x] Imports added at top of `summary.py`:
  - `from squadron.pipeline.summary_oneshot import capture_summary_via_profile, is_sdk_profile`
  - [x] SDK fallback path is byte-identical for SDK-profile models
  - [x] Non-SDK path goes through the new helper, never touches
    `set_model`
  - [x] Rotate-validation error is raised before any provider call

### T7: Test `_execute_summary()` profile branching

- [x] In `tests/pipeline/actions/test_summary.py`:
- [x] **Update existing test** `test_execute_summary_no_sdk_session_returns_failure`:
  - Rename to `test_execute_summary_sdk_profile_without_session_fails`
  - Narrow assertion: failure occurs when profile resolves to SDK
    (or alias is None) AND `sdk_session is None`
- [x] **Add** `test_execute_summary_routes_non_sdk_profile_via_oneshot`:
  - Mock `capture_summary_via_profile` to return a known string
  - Configure summary step with `model_alias` resolving to
    `(model_id, "openrouter")`
  - Provide a context with `sdk_session=None` and stdout emit
  - Assert `capture_summary_via_profile` was called once with the
    expected `instructions`, `model_id`, `profile`
  - Assert `sdk_session.capture_summary` was NOT called (sdk_session
    is None — ensure `set_model` etc. are never reached)
  - Assert `ActionResult.success is True` and `outputs["summary"]`
    matches the mocked return
- [x] **Add** `test_execute_summary_non_sdk_profile_with_rotate_fails`:
  - Mock the resolver to return a non-SDK profile
  - Configure emit destinations including `EmitKind.ROTATE`
  - Assert the action fails fast with an error mentioning "rotate"
    and "non-SDK"
  - Assert `capture_summary_via_profile` was NOT called (validation
    fires before dispatch)
- [x] **Add** `test_execute_summary_sdk_profile_path_unchanged`:
  - Existing happy path with mock SDK session — confirm the SDK branch
    still calls `sdk_session.capture_summary` with the same arguments
    as before
- [x] **Add** `test_execute_summary_unannotated_alias_uses_sdk_path`:
  - Resolver returns `(model_id, None)` (alias has no profile)
  - Confirm the SDK branch is taken
- [x] Run: `uv run pytest tests/pipeline/actions/test_summary.py -v`
  - [x] All new tests pass
  - [x] Updated test is named accurately for its narrower contract
  - [x] No mock leaks between tests

### T8: Resolve OQ1 — design the prompt-only non-SDK summary command

- [x] Decide between Option A (new hidden `sq summary-run` subcommand)
  and Option B (keep `sq summary-instructions` and have the harness
  dispatch). **Default to Option A per slice doc preference.**
- [x] If Option A: design the subcommand surface:
  - Name: `sq summary-run` (hidden, like `sq _summary-instructions`)
  - Required args: `--template <name>`, `--profile <name>`,
    `--model <model_id>`
  - Optional: `--params key=value` repeatable, for template
    substitution
  - Behavior: load compaction template, render with params, call
    `capture_summary_via_profile`, print resulting summary text to
    stdout, exit 0
  - Errors: missing template → exit 1 with stderr message; provider
    error → exit 1 with stderr message
- [x] Document the chosen shape inline in this task file under T8
  before proceeding to T9 (so T9 has a stable target)
- [x] If a different shape is preferred, replace this and the
  following implementation tasks accordingly and note the divergence in
  the slice doc's OQ1 section
  - [x] OQ1 resolution recorded
  - [x] CLI surface fully specified before any code is written

### T9: Implement `sq summary-run` hidden subcommand

- [x] Locate the appropriate Typer module (likely
  `src/squadron/cli/commands/` — check how `summary_instructions.py` is
  registered for the existing `sq _summary-instructions` pattern)
- [x] Add `summary_run` function with Typer signature matching T8:
  - `template: str = typer.Option(...)`
  - `profile: str = typer.Option(...)`
  - `model: str = typer.Option(...)`
  - `param: list[str] = typer.Option([], "--param", "-p", help="key=value, repeatable")`
- [x] Function body:
  - Parse `param` list into a `dict[str, str]` (split on first `=`,
    error on missing `=`)
  - Load compaction template via `load_compaction_template(template)`
  - Render via `render_instructions(template, pipeline_params=params)`
  - Run `asyncio.run(capture_summary_via_profile(instructions=..., model_id=model, profile=profile))`
  - Print the result to stdout
- [x] Register the command in the CLI app, hidden from `--help`
  (mirror the registration of `sq _summary-instructions`)
- [x] Add error handling: catch and re-raise as `typer.Exit(code=1)`
  with a stderr message for: bad `param` format, missing template,
  unknown profile, provider failure
  - [x] Command is reachable as `sq summary-run` (or `sq _summary-run`,
    matching the project's existing hidden-command convention — confirm
    with T1)
  - [x] Hidden from `--help`
  - [x] Returns nonzero on error with descriptive stderr

### T10: Test `sq summary-run` subcommand

- [x] In `tests/cli/commands/test_summary_run.py` (new file):
- [x] Test: happy path — invoke via Typer test runner with mocked
  `capture_summary_via_profile` returning canned text; assert stdout
  contains the text and exit code is 0
- [x] Test: bad `--param` format (no `=`) → exit 1 with stderr
  mentioning the bad value
- [x] Test: missing template → exit 1 with stderr mentioning the
  template name
- [x] Test: provider raises → exit 1 with stderr mentioning the error
- [x] Run: `uv run pytest tests/cli/commands/test_summary_run.py -v`
  - [x] All tests pass
  - [x] No test relies on a real network call

### T11: Update `_render_summary()` in `prompt_renderer.py`

- [x] In `src/squadron/pipeline/prompt_renderer.py` `_render_summary()`:
  - [x] When `model_raw is not None`, capture both elements from the
    resolver: `model_id, profile = resolver.resolve(alias)`
  - [x] Branch on `is_sdk_profile(profile)`:
    - SDK profile (or `None`): set
      `model_switch = f"/model {alias}"`, leave `command = None`
    - Non-SDK profile: set `model_switch = None`, build `command` as
      `sq summary-run --template <template_name> --profile <profile> --model <model_id>` plus a `--param` flag for each `(key, value)` in `params` (matching T8/T9 surface)
  - [x] Quote params correctly so they survive shell parsing (use
    `shlex.quote` for each value or a join helper that does it)
- [x] Import `is_sdk_profile` from
  `squadron.pipeline.summary_oneshot`
- [x] When `model_raw is None`, behavior is unchanged: no
  `model_switch`, no `command`, the harness uses the session's current
  model
- [x] Update the returned `ActionInstruction` to include `command` in
  the non-SDK case (the dataclass already has the field; just populate
  it)
  - [x] SDK profile branch matches the pre-164 behavior exactly
  - [x] Non-SDK profile branch emits a runnable `sq summary-run …`
    command
  - [x] No path emits both `model_switch` and `command`

### T12: Test `_render_summary()` profile branching

- [x] In `tests/pipeline/test_summary_render.py`:
- [x] **Add** `test_render_summary_sdk_profile_emits_model_switch`:
  - Resolver returns `("haiku-model-id", "sdk")`
  - Assert `model_switch == "/model haiku"` (or whatever the alias was)
  - Assert `command is None`
- [x] **Add** `test_render_summary_unannotated_alias_emits_model_switch`:
  - Resolver returns `("some-id", None)` — `None` is treated as SDK
  - Same assertions
- [x] **Add** `test_render_summary_non_sdk_profile_emits_command`:
  - Resolver returns `("minimax-01", "openrouter")`
  - Assert `model_switch is None`
  - Assert `command` starts with `sq summary-run` and contains
    `--template`, `--profile openrouter`, `--model minimax-01`
- [x] **Add** `test_render_summary_non_sdk_profile_quotes_params`:
  - Pipeline params include a value with shell-special characters
    (e.g. `slice="a slice with spaces"`)
  - Assert the rendered command has the value quoted such that
    `shlex.split` recovers it correctly
- [x] **Update** existing tests as needed: any test that asserted
  `model_switch is set` for a summary step should be split into the
  SDK and non-SDK cases (the existing tests use SDK aliases by default,
  so most should pass unchanged — verify)
- [x] Run: `uv run pytest tests/pipeline/test_summary_render.py -v`
  - [x] All new tests pass
  - [x] Existing tests still pass or are correctly split

### T13: Verify compact-via-summary inheritance

- [x] Read `src/squadron/pipeline/actions/compact.py` `execute()` SDK
  branch (lines ~203–218) — confirm it still delegates to
  `_execute_summary()` and that no compact-specific changes are needed
- [x] Spot-check: a compact step with a non-SDK model and stdout/file
  emit should now work for free (same code path as summary). A compact
  step with rotate emit and a non-SDK model should fail validation
  (rotate is SDK-only by design)
- [x] Add a single confirmation test in
  `tests/pipeline/actions/test_compact.py` (or wherever the action's
  tests live):
  - `test_compact_non_sdk_profile_non_rotate_emit_succeeds` — mock
    `_execute_summary` so the test focuses on call wiring, assert
    compact passes through to summary's profile branch
  - `test_compact_non_sdk_profile_with_rotate_fails` — assert validation
    error with the same message shape as the summary case
- [x] Run: `uv run pytest tests/pipeline/actions/test_compact.py -v`
  - [x] Compact tests pass
  - [x] No new compact-specific code was needed

### T14: Full test suite, lint, format, type-check

- [x] `uv run ruff format .` — confirm no changes (or commit
  formatting in this step)
- [x] `uv run ruff check` — zero errors
- [x] `uv run pyright` — zero errors (this slice's predecessor failed
  CI on a `dict[str, object]` narrow in `prompt_renderer.py`; the new
  branch must not reintroduce that pattern)
- [x] `uv run pytest tests/ -v` — all tests pass
  - [x] Lint, format, and type-check are all clean
  - [x] Full suite green

### T15: Verification walkthrough (slice success criteria)

Run each scenario from the slice doc's Verification Walkthrough section
and confirm:

- [x] **Scenario A** — non-SDK summary in SDK execution mode: create
  throwaway pipeline `/tmp/test-164-summary.yaml` with
  `model: minimax`, `emit: [stdout]`; run via `sq run`; confirm summary
  text printed and `metadata.summary_model` matches the resolved
  minimax model ID
- [x] **Scenario B** — non-SDK + rotate fails validation: same
  pipeline with `emit: [rotate]`; `sq run --validate` returns the
  expected error
- [x] **Scenario C** — SDK summary unchanged: pipeline with
  `model: haiku`, `emit: [stdout]`; runs via `sdk_session.capture_summary`
- [x] **Scenario D** — prompt-only rendering split: SDK pipeline emits
  `model_switch`, non-SDK pipeline emits `command`
- [x] **Scenario E** — compact-via-summary with non-SDK + stdout: works
- [x] **Regression** — existing P4 pipeline (haiku stopgap) still
  works identically
  - [x] All 6 verification scenarios pass
  - [x] No regression in real-world pipelines

### T16: Commit implementation

- [x] `uv run ruff format .`
- [x] `git add` changed files: `src/squadron/pipeline/summary_oneshot.py`,
  `src/squadron/pipeline/actions/summary.py`,
  `src/squadron/pipeline/prompt_renderer.py`,
  `src/squadron/cli/commands/summary_run.py` (or correct path),
  CLI registration files, all new and updated test files
- [x] `git commit -m "feat: route summary action through provider registry for non-SDK profiles"`
- [x] If T14 or T15 had to fix anything, fold those into the same
  commit OR a follow-up `fix:` commit — do not leave broken state
  between commits
  - [x] Commit message follows the project's semantic-prefix
    convention (`feat:` for the main change)
  - [x] No formatting churn in unrelated files

### T17: Update slice doc and DEVLOG, mark slice complete

- [x] In `project-documents/user/slices/164-slice.profile-aware-summary-model-routing.md`:
  - Update frontmatter `status: complete`, `dateUpdated: <today>`
  - Note OQ1 resolution under the Open Questions section (which option
    was taken, link to the new subcommand)
- [x] In `project-documents/user/architecture/140-slices.pipeline-foundation.md`:
  - Mark slice 164's checkbox `[x]` (line 73)
- [x] Write a DEVLOG entry summarizing:
  - What changed (the profile branch + new helper + new subcommand)
  - OQ1 resolution
  - Any surprises during implementation (e.g. test fixture pain,
    provider registry quirks)
  - Pipelines unblocked (cheap-model summaries)
- [x] `git add -A && git commit -m "docs: mark slice 164 complete"`
  - [x] Slice frontmatter status flipped to complete
  - [x] Slice plan checkbox flipped to `[x]`
  - [x] DEVLOG entry written
