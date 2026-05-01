---
docType: tasks
slice: profile-aware-dispatch-model-routing
project: squadron
lld: user/slices/170-slice.profile-aware-dispatch-model-routing.md
dependencies:
  - 145-dispatch-action
  - 164-profile-aware-summary-model-routing
  - 119-review-provider-and-model-selection
projectState: Slice 170 design complete, review iteration 2 resolved (all findings addressed verbally). Working tree clean on main.
dateCreated: 20260501
dateUpdated: 20260501
status: not_started
---

## Context Summary

- Working on slice 170: Profile-Aware Dispatch Model Routing
- Goal: mirror slice 164's profile-aware summary fix on the dispatch axis. When
  a non-SDK model alias is resolved, the prompt-only renderer emits a `command`
  field invoking `sq _dispatch-run` instead of emitting `model_switch` and
  expecting the IDE session to do the work.
- Three concrete defects to fix:
  1. `_render_dispatch` in `prompt_renderer.py` ignores the resolved profile
     and always emits the in-session path.
  2. No hidden `sq _dispatch-run` subcommand exists yet (analogous to slice
     164's `sq _summary-run`).
  3. `_dispatch_via_session` silently absorbs SDK API errors with `is_error=True`
     metadata that the current `_check_cli_error` text-prefix check misses.
- Key files: `src/squadron/pipeline/prompt_renderer.py` (fix renderer),
  `src/squadron/pipeline/actions/dispatch.py` (factor `_one_shot_dispatch`
  helper; fix SDK error detection),
  `src/squadron/cli/commands/dispatch_run.py` (new hidden subcommand),
  `src/squadron/cli/app.py` (register hidden subcommand),
  `commands/sq/run.md` (update slash handler dispatch branch).
- `is_sdk_profile()` is already in `src/squadron/pipeline/summary_oneshot.py`
  and imported by `prompt_renderer.py`. No ownership change needed (initiative
  240 will promote it; out of scope here).
- The `_dispatch_via_agent` body (lines 179–255 of `dispatch.py`) contains the
  one-shot agent spawn sequence that `_one_shot_dispatch` will extract.

---

## Tasks

### T1: Read and confirm insertion points

- [ ] Read `src/squadron/pipeline/prompt_renderer.py` lines 123–150
  (`_render_dispatch`) — confirm the current `model_id, _ = resolver.resolve()`
  call that discards the profile, and the `model_switch`-only return shape
- [ ] Read `src/squadron/pipeline/actions/dispatch.py` lines 179–255
  (`_dispatch_via_agent`) — identify exactly which lines constitute the
  spawn-agent → send-message → collect → shutdown sequence to extract into
  `_one_shot_dispatch`
- [ ] Read `src/squadron/pipeline/actions/dispatch.py` lines 90–125
  (`_dispatch_via_session` and `_check_cli_error`) — note the `_CLI_ERROR_PREFIX`
  constant and the existing `response_text.startswith(...)` check; confirm
  `is_error` is not yet inspected anywhere here
- [ ] Read `src/squadron/pipeline/sdk_session.py` `dispatch()` (lines 115–176)
  — confirm `is_error` is not surfaced as a separate flag from the current
  `translate_sdk_message` path; note how `ProviderAPIError` is already raised
  on `ProcessError` (non-zero CLI exit)
- [ ] Read `src/squadron/cli/commands/summary_run.py` — note the exact
  structure: arg parsing, `asyncio.run(capture_summary_via_profile(...))`,
  stdout print, stderr error handling; this is the template for `dispatch_run.py`
- [ ] Read `src/squadron/cli/app.py` — confirm line numbers for
  `_summary-run` hidden registration; identify where to add `_dispatch-run`
- [ ] Read `commands/sq/run.md` lines 60–70 — confirm the current dispatch
  section text ("This is in-session work…") that needs branching
- [ ] Read `tests/pipeline/actions/test_dispatch.py` and
  `tests/pipeline/actions/test_dispatch_session.py` — catalog tests that
  assert on the in-session path or `_check_cli_error`
  - [ ] All insertion points understood before any code changes

---

### T2: Factor `_one_shot_dispatch` helper in `dispatch.py`

- [ ] In `src/squadron/pipeline/actions/dispatch.py`, extract the
  agent-spawn sequence from `_dispatch_via_agent` into a module-level
  async function:
  ```python
  async def _one_shot_dispatch(
      *,
      prompt: str,
      model_id: str,
      profile_name: str,
      system_prompt: str = "",
      step_name: str = "dispatch",
      run_id: str = "cli",
  ) -> str:
  ```
- [ ] The helper body owns: profile lookup → `ensure_provider_loaded` →
  `AgentConfig` construction → `registry.spawn` → `handle_message` loop
  (with `SDK_RESULT_TYPE` skip and token metadata collection) → `registry.shutdown_agent`
  in `finally` → return `"".join(response_parts)`
- [ ] `_dispatch_via_agent` becomes a thin caller: resolve model/profile from
  context, call `_one_shot_dispatch(prompt=..., model_id=..., profile_name=...,
  step_name=context.step_name, run_id=context.run_id)`, then wrap in
  `_check_cli_error` and build `ActionResult`
- [ ] Token metadata: keep it in `_dispatch_via_agent`'s `ActionResult` — the
  helper returns the raw response string; metadata collection stays in
  `_dispatch_via_agent` (or accept an out-param dict — whichever is cleaner;
  choose the simpler option)
  - [ ] `_dispatch_via_agent` behavior is byte-identical before and after refactor
  - [ ] Helper is importable from `dispatch.py` for use by `dispatch_run.py`
  - [ ] No logic change — pure extraction

### T3: Test `_one_shot_dispatch` extraction (regression)

- [ ] In `tests/pipeline/actions/test_dispatch.py`, run existing tests to
  confirm the extraction did not change behavior:
  ```
  uv run pytest tests/pipeline/actions/test_dispatch.py -v
  ```
- [ ] If any test directly patches `_dispatch_via_agent` internals (e.g.
  `registry.spawn`), verify the patch still intercepts correctly after the
  extraction
  - [ ] All existing dispatch tests pass unchanged

---

### T4: Fix `_render_dispatch` in `prompt_renderer.py`

- [ ] In `src/squadron/pipeline/prompt_renderer.py` `_render_dispatch`:
  - [ ] Change `model_id, _ = resolver.resolve(action_model)` to
    `model_id, profile = resolver.resolve(action_model)` (capture profile)
  - [ ] Branch on `is_sdk_profile(profile)`:
    - SDK (or `None`): keep the current `model_switch = f"/model {action_model}"`
      shape; `command = None`; `instruction = "Execute the work using the
      assembled context"`
    - Non-SDK: set `command` to the `sq _dispatch-run` invocation (see shape
      below); set `model_switch = None`; set `instruction = "Run the 'command'
      field via Bash. Capture stdout as the dispatch response."`
- [ ] Non-SDK command shape emitted by the renderer:
  ```
  sq _dispatch-run --prompt-file {tmp_path} --model <model_id> --profile <profile>
  ```
  where `{tmp_path}` is a literal placeholder string the slash handler replaces
  after writing the temp file. Include any `--param key=value` entries from
  `params` that are not internal keys (e.g. exclude `_fan_out_branch_index`,
  `prompt`, `system_prompt`; include `model` override if present — but
  `--model` is already set from the resolved ID, so skip `model` from params).
  Use `shlex.quote` on each value.
- [ ] When `action_model is None`, behavior is unchanged: no `model_switch`,
  no `command`, default SDK path
  - [ ] SDK profile path produces identical output to current `main`
  - [ ] Non-SDK path produces a `command` starting with `sq _dispatch-run`
    and no `model_switch`
  - [ ] No path emits both `model_switch` and `command`

### T5: Test `_render_dispatch` profile branching

- [ ] In `tests/pipeline/test_dispatch.py` (or a new
  `tests/pipeline/test_dispatch_render.py` if the existing file is action-level
  only — check first):
- [ ] `test_render_dispatch_sdk_profile_emits_in_session_instruction` —
  resolver returns `("claude-opus-…", "sdk")`; assert `model_switch` is set,
  `command` is `None`
- [ ] `test_render_dispatch_non_sdk_profile_emits_command` — resolver
  returns `("minimax-…", "openrouter")`; assert `command` starts with
  `sq _dispatch-run`, `model_switch` is `None`
- [ ] `test_render_dispatch_no_model_param` — no model in config; assert
  in-session instruction, no `model_switch`, no `command` (default preserved)
- [ ] `test_render_dispatch_command_contains_prompt_file_placeholder` —
  non-SDK profile; assert `command` contains `--prompt-file {tmp_path}`
- [ ] Run: `uv run pytest tests/pipeline/ -k "dispatch" -v`
  - [ ] All new tests pass; no existing tests broken

---

### T6: Implement `sq _dispatch-run` hidden subcommand

- [ ] Create `src/squadron/cli/commands/dispatch_run.py` mirroring the
  structure of `summary_run.py`:
  ```python
  def dispatch_run(
      prompt_file: Path = typer.Option(..., "--prompt-file"),
      model: str = typer.Option(..., "--model"),
      profile: str | None = typer.Option(None, "--profile"),
      param: list[str] = typer.Option([], "--param", "-p"),
      system_prompt: str | None = typer.Option(None, "--system-prompt"),
  ) -> None:
  ```
- [ ] Body:
  1. Read prompt text from `prompt_file` with `encoding="utf-8"`; fail with
     exit 1 + stderr if the file does not exist
  2. If `--profile` was not given, resolve it: `model_id, resolved_profile =
     ModelResolver(...).resolve(model)` — use the default resolver (same one
     the pipeline uses); use `resolved_profile` as the profile. If `--profile`
     was given, use it directly and treat `model` as the resolved model ID.
  3. Parse `param` list into `dict[str, str]` (same pattern as `summary_run.py`);
     fail with exit 1 on missing `=`
  4. Call `asyncio.run(_one_shot_dispatch(prompt=text, model_id=model_id,
     profile_name=profile, system_prompt=system_prompt or ""))`
  5. Print the result to stdout; exit 0
  6. Catch and print to stderr with exit 1: `FileNotFoundError`, bad param
     format, `KeyError` (unknown profile), any `Exception` (provider failure)
- [ ] Import `_one_shot_dispatch` from `squadron.pipeline.actions.dispatch`
- [ ] File has module docstring explaining it is a hidden internal subcommand
  - [ ] `--prompt-file` is required (no inline `--prompt`)
  - [ ] Errors always print to stderr before exit 1 (silent failure is a bug)
  - [ ] Prompt read with explicit `encoding="utf-8"`

### T7: Register `sq _dispatch-run` in `app.py`

- [ ] In `src/squadron/cli/app.py`:
  - Add `from squadron.cli.commands.dispatch_run import dispatch_run`
  - Add `app.command("_dispatch-run", hidden=True)(dispatch_run)` next to the
    `_summary-run` registration
  - [ ] Command appears in `app.commands` or equivalent registration
  - [ ] `hidden=True` confirmed

### T8: Test `sq _dispatch-run` subcommand

- [ ] Create `tests/cli/commands/test_dispatch_run.py`:
- [ ] `test_dispatch_run_with_prompt_file` — write a temp file, mock
  `_one_shot_dispatch` to return `"response text"`, invoke via Typer test
  runner; assert stdout == `"response text\n"` and exit code 0
- [ ] `test_dispatch_run_resolves_profile_from_alias` — `--profile` omitted;
  mock `ModelResolver.resolve` to return `("model-id", "openrouter")`; assert
  `_one_shot_dispatch` is called with `profile_name="openrouter"`
- [ ] `test_dispatch_run_errors_when_prompt_file_missing` — pass a
  non-existent path; assert exit code != 0 and stderr contains "not found"
  (or similar)
- [ ] `test_dispatch_run_hidden_from_help` — invoke `sq --help` via Typer
  test runner; assert `"_dispatch-run"` does not appear in output
- [ ] `test_dispatch_run_bad_param_format` — `--param "noequals"`; assert
  exit 1 and stderr mentions the bad value
- [ ] Run: `uv run pytest tests/cli/commands/test_dispatch_run.py -v`
  - [ ] All tests pass; no real network calls

---

### T9: Update `commands/sq/run.md` dispatch section

- [ ] In `commands/sq/run.md`, replace the `### dispatch` section with a
  branched version:
  ```markdown
  ### dispatch
  If the `command` field is present:
    Write the `prompt_text` field (or the assembled context if no `prompt_text`)
    to a temp file via Bash (`mktemp`). Replace `{tmp_path}` in the `command`
    field with the temp file path. Run the command via Bash. Capture stdout as
    the dispatch response. Remove the temp file after capture (use `trap` or
    an explicit cleanup step).
  Else:
    This is in-session work — you perform the task described in `instruction`.
    If `model_switch` is present, note the recommended model for the user.
    Model switching cannot be automated — only the user can issue `/model`
    commands.
  ```
- [ ] Keep the existing else-branch wording as close to the original as
  practical — only add the `if command` branch
  - [ ] Temp file cleanup is explicit in the slash handler instructions
  - [ ] The branch mirrors the existing `### review` and `### summary` patterns

---

### T10: Fix SDK synthetic-error detection in `_dispatch_via_session`

- [ ] Read `src/squadron/pipeline/sdk_session.py` `translate_sdk_message`
  to understand whether `is_error` is surfaced on the translated message
  metadata today; note what field name is used (if any)
- [ ] In `src/squadron/pipeline/actions/dispatch.py` `_dispatch_via_session`:
  - After `response_text = await session.dispatch(prompt)`, keep the existing
    `_check_cli_error(response_text)` call as the text-prefix backstop
  - Determine where to add the `is_error` check: either in
    `SDKExecutionSession.dispatch` (raise `ProviderAPIError` when any message
    has `is_error=True`) or in `_dispatch_via_session` (inspect return
    metadata from `session.dispatch` if it can surface the flag)
  - Preferred: add detection in `SDKExecutionSession.dispatch` — it already
    raises `ProviderAPIError` on `ProcessError`; add a parallel raise for
    `is_error=True` messages in the `translate_sdk_message` loop. The action
    layer's existing `try/except` at `execute()` catches `ProviderAPIError`
    and returns `ActionResult(success=False, …)`.
  - If `translate_sdk_message` does not expose `is_error`, document what is
    missing and add a `# TODO(240)` comment — do not silently skip the fix.
    Ask the Project Manager before inventing new SDK message fields.
  - [ ] Decision documented in this task before code is written
  - [ ] Existing `_CLI_ERROR_PREFIX` check is preserved as backstop
  - [ ] No API error message reaches artifact files on the error path

### T11: Test SDK synthetic-error detection

- [ ] In `tests/pipeline/actions/test_dispatch_session.py`:
- [ ] `test_sdk_session_api_error_text_prefix_fails_action` — existing
  behavior: fake session returns `"API Error: 500 …"`; assert
  `ActionResult.success is False` (regression guard)
- [ ] `test_sdk_session_is_error_message_fails_action` — fake
  `SDKExecutionSession` whose `dispatch` raises `ProviderAPIError` (simulating
  the `is_error` detection path); assert `DispatchAction.execute` returns
  `ActionResult(success=False)` with a non-empty `error` field
- [ ] `test_no_artifact_written_on_sdk_error` — confirm the error result
  has no artifact path populated (i.e. `outputs` does not contain a design
  file path or the response key contains only the error, not partial model
  output)
- [ ] Run: `uv run pytest tests/pipeline/actions/test_dispatch_session.py -v`
  - [ ] All tests pass

---

### T12: Full suite, lint, format, type-check

- [ ] `uv run ruff format .`
- [ ] `uv run ruff check` — zero errors
- [ ] `uv run pyright` — zero errors
- [ ] `uv run pytest tests/ -v` — all tests pass
  - [ ] Lint, format, and type-check clean
  - [ ] Full suite green

### T13: Verification walkthrough

Run each scenario from the slice doc's Verification Walkthrough:

- [ ] **Step 1 — In-IDE non-SDK model routes through agent path.**
  Inside Claude Code: `/sq:run P4 183 --param model=minimax`. Confirm the
  dispatch JSON contains `command` starting with `sq _dispatch-run … --profile
  openrouter …` and no `model_switch`. The IDE session does not generate the
  design output.
- [ ] **Step 2 — Real-terminal non-SDK model.** `sq run P4 183 --param
  model=minimax`. Same routing via `_dispatch_via_agent`.
- [ ] **Step 3 — Default model uses SDK session.** `sq run P4 183` (no
  `--param model`). `_dispatch_via_session` path, behavior identical to main.
- [ ] **Step 4 — SDK API error halts pipeline cleanly.** Integration test
  covers this; manual re-run optional. Confirm pipeline state shows `status=failed`,
  no design file written.
- [ ] **Step 5 — `sq _dispatch-run` standalone debug.**
  `echo "Write a haiku." > /tmp/p.txt && sq _dispatch-run --prompt-file /tmp/p.txt --model minimax`.
  Confirm haiku on stdout, exit 0, `sq --help` does not list `_dispatch-run`.
  - [ ] All 5 steps pass

---

### T14: Commit implementation

- [ ] `uv run ruff format .`
- [ ] `git add src/squadron/pipeline/actions/dispatch.py
  src/squadron/pipeline/prompt_renderer.py
  src/squadron/cli/commands/dispatch_run.py
  src/squadron/cli/app.py
  commands/sq/run.md` plus all new and updated test files
- [ ] `git commit -m "feat: route dispatch through provider registry for non-SDK profiles"`
  - [ ] Semantic prefix `feat:` for the main change
  - [ ] No formatting churn in unrelated files

### T15: Update slice doc, slice plan, and DEVLOG

- [ ] In `project-documents/user/slices/170-slice.profile-aware-dispatch-model-routing.md`:
  - Update `status: complete`, `dateUpdated: <today>`
- [ ] In the slice plan (`100-slices.orchestration-v2.md` or the 140-slices
  plan — confirm which tracks slice 170): mark the slice 170 checkbox `[x]`
- [ ] Write DEVLOG entry summarizing:
  - What changed (renderer fix, new hidden subcommand, SDK error fix)
  - Any surprises (e.g. `is_error` surfacing gap in `translate_sdk_message`)
  - Pipelines unblocked (cheap-model dispatch from IDE)
- [ ] `git add -A && git commit -m "docs: mark slice 170 complete"`
  - [ ] Slice frontmatter status flipped to `complete`
  - [ ] Slice plan checkbox `[x]`
  - [ ] DEVLOG entry written
