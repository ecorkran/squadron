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
reviewIteration: 2
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
  3. `_dispatch_via_session` silently absorbs SDK API errors: the SDK's
     `ResultMessage` has an `is_error: bool` field; when `is_error=True` the
     existing `_check_cli_error` text-prefix check misses it.
- Key files: `src/squadron/pipeline/prompt_renderer.py` (fix renderer),
  `src/squadron/pipeline/actions/dispatch.py` (factor `_one_shot_dispatch`
  helper; fix SDK error detection),
  `src/squadron/pipeline/sdk_session.py` (raise `ProviderAPIError` on
  `ResultMessage.is_error=True`),
  `src/squadron/cli/commands/dispatch_run.py` (new hidden subcommand),
  `src/squadron/cli/app.py` (register hidden subcommand),
  `commands/sq/run.md` (update slash handler dispatch branch).
- `is_sdk_profile()` is already in `src/squadron/pipeline/summary_oneshot.py`
  and imported by `prompt_renderer.py`. No ownership change needed (initiative
  240 will promote it; out of scope here).
- The `_dispatch_via_agent` body (lines 179–255 of `dispatch.py`) contains the
  one-shot agent spawn sequence that `_one_shot_dispatch` will extract.
- SDK error path (T10): `ResultMessage` in `claude_agent_sdk` has `is_error: bool`
  and `subtype: str`. `_translate_result` in `translation.py` already routes
  non-success subtypes as `MessageType.system` messages with
  `metadata={"sdk_type": SDK_RESULT_TYPE, "subtype": msg.subtype}`. The fix
  adds a check in `SDKExecutionSession.dispatch` after `translate_sdk_message`:
  if a translated message has `sdk_type == SDK_RESULT_TYPE` and its source
  `ResultMessage.is_error is True`, raise `ProviderAPIError` before returning
  the joined text. The existing `_CLI_ERROR_PREFIX` text-prefix check in
  `_check_cli_error` is preserved as a backstop.

---

## Tasks

### T1: Read and confirm insertion points

- [ ] Read `src/squadron/pipeline/prompt_renderer.py` lines 123–150
  (`_render_dispatch`) — confirm whether `resolver` is already the third
  parameter; confirm the `model_id, _ = resolver.resolve()` call that discards
  the profile, and the `model_switch`-only return shape
- [ ] Read `src/squadron/pipeline/prompt_renderer.py` lines 336–370
  (`_BUILDERS` dict and `_build_action_instruction`) — confirm where
  `ActionType.DISPATCH` is mapped and how the resolver is passed to it
- [ ] Read `src/squadron/pipeline/actions/dispatch.py` lines 179–255
  (`_dispatch_via_agent`) — identify exactly which lines constitute the
  spawn-agent → send-message → collect → shutdown sequence to extract into
  `_one_shot_dispatch`
- [ ] Read `src/squadron/pipeline/actions/dispatch.py` lines 29–40
  (`_check_cli_error`) — note the `_CLI_ERROR_PREFIX` constant and the
  `response_text.startswith(...)` check
- [ ] Read `src/squadron/pipeline/sdk_session.py` lines 115–176 (`dispatch()`)
  — confirm the `translate_sdk_message` loop; note that `ResultMessage` is
  filtered by `SDK_RESULT_TYPE` check but `is_error` is never inspected
- [ ] Read `src/squadron/cli/commands/summary_run.py` — note the exact
  structure: arg parsing, `asyncio.run(capture_summary_via_profile(...))`,
  stdout print, stderr error handling; this is the template for `dispatch_run.py`
- [ ] Read `src/squadron/cli/app.py` — confirm line numbers for
  `_summary-run` hidden registration; identify where to add `_dispatch-run`
- [ ] Read `commands/sq/run.md` lines 60–70 — confirm the current dispatch
  section text ("This is in-session work…") that needs branching
- [ ] Read `tests/pipeline/actions/test_dispatch.py` and
  `tests/pipeline/actions/test_dispatch_session.py` — catalog tests asserting
  on `_check_cli_error`, session routing, and agent routing
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
  (with `SDK_RESULT_TYPE` skip) → `registry.shutdown_agent` in `finally`
  → return `"".join(response_parts)`
- [ ] `_dispatch_via_agent` becomes a thin caller: resolve model/profile from
  context, call `_one_shot_dispatch(...)`, then wrap in `_check_cli_error` and
  build `ActionResult` (token metadata stays in `_dispatch_via_agent`)
  - [ ] `_dispatch_via_agent` behavior is byte-identical before and after the refactor
  - [ ] Helper is importable from `dispatch.py` (used by `dispatch_run.py`)
  - [ ] No logic change — pure extraction

### T3: Test extraction and commit

- [ ] Run: `uv run pytest tests/pipeline/actions/test_dispatch.py -v`
  - [ ] All existing dispatch tests pass unchanged
- [ ] `uv run ruff format . && uv run ruff check && uv run pyright`
  - [ ] Clean
- [ ] `git add src/squadron/pipeline/actions/dispatch.py && git commit -m "refactor: extract _one_shot_dispatch helper from _dispatch_via_agent"`

---

### T4: Fix `_render_dispatch` in `prompt_renderer.py`

- [ ] **If `resolver` is not yet the third parameter of `_render_dispatch`**
  (confirm in T1): add it with type annotation `resolver: ModelResolver`,
  then update `_BUILDERS` dispatch in `_build_action_instruction` to pass
  `resolver` to `ActionType.DISPATCH` — mirror exactly how `ActionType.SUMMARY`
  is handled. If it already accepts `resolver`, skip this sub-step.
- [ ] Change `model_id, _ = resolver.resolve(action_model)` to
  `model_id, profile = resolver.resolve(action_model)` (capture profile)
- [ ] Branch on `is_sdk_profile(profile)`:
  - SDK (or `None`): keep the current `model_switch = f"/model {action_model}"`
    shape; `command = None`; `instruction = "Execute the work using the
    assembled context"`
  - Non-SDK: set `command` to the `sq _dispatch-run` invocation (shape below);
    set `model_switch = None`; set `instruction = "Run the 'command' field via
    Bash. Capture stdout as the dispatch response."`
- [ ] Non-SDK command shape emitted by the renderer:
  ```
  sq _dispatch-run --prompt-file {tmp_path} --model <model_id> --profile <profile>
  ```
  where `{tmp_path}` is a literal placeholder string; the slash handler replaces
  it after writing the temp file. Append `--param key=<shlex.quote(value)>` for
  each entry in `params` that is not an internal key (`_fan_out_branch_index`,
  `prompt`, `system_prompt`, `model`, `step_model`, `profile`).
- [ ] When `action_model is None`, behavior is unchanged: no `model_switch`,
  no `command`, default SDK path
  - [ ] SDK profile path produces identical output to current `main`
  - [ ] Non-SDK path produces a `command` starting with `sq _dispatch-run` and no `model_switch`
  - [ ] No path emits both `model_switch` and `command`

### T5: Test `_render_dispatch` branching and commit

- [ ] In `tests/pipeline/test_dispatch.py` (or new
  `tests/pipeline/test_dispatch_render.py` if the file is action-level only):
- [ ] `test_render_dispatch_sdk_profile_emits_in_session_instruction` —
  resolver returns `("claude-opus-…", "sdk")`; assert `model_switch` is set,
  `command` is `None`
- [ ] `test_render_dispatch_non_sdk_profile_emits_command` — resolver
  returns `("minimax-…", "openrouter")`; assert `command` starts with
  `sq _dispatch-run`, `model_switch` is `None`
- [ ] `test_render_dispatch_no_model_param` — no model in config; assert
  in-session instruction, no `model_switch`, no `command`
- [ ] `test_render_dispatch_command_contains_prompt_file_placeholder` —
  non-SDK profile; assert `command` contains `--prompt-file {tmp_path}`
- [ ] Run: `uv run pytest tests/pipeline/ -k "dispatch" -v`
  - [ ] All new tests pass; no existing tests broken
- [ ] `uv run ruff format . && uv run ruff check && uv run pyright`
  - [ ] Clean
- [ ] `git add src/squadron/pipeline/prompt_renderer.py tests/ && git commit -m "feat: branch _render_dispatch on resolved profile for non-SDK models"`

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
  2. If `--profile` was not given, resolve it via `ModelResolver` (default
     resolver); use `resolved_profile` as the profile and the resolved model ID
     as `model_id`. If `--profile` was given, use it directly and treat
     `--model` as the already-resolved model ID.
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

### T7: Register `sq _dispatch-run` in `app.py`

- [ ] In `src/squadron/cli/app.py`:
  - Add `from squadron.cli.commands.dispatch_run import dispatch_run`
  - Add `app.command("_dispatch-run", hidden=True)(dispatch_run)` next to
    the `_summary-run` registration
  - [ ] `hidden=True` confirmed

### T8: Test `sq _dispatch-run` and commit

- [ ] Create `tests/cli/commands/test_dispatch_run.py`:
- [ ] `test_dispatch_run_with_prompt_file` — write a temp file, mock
  `_one_shot_dispatch` to return `"response text"`, invoke via Typer test
  runner; assert stdout contains the text and exit code 0
- [ ] `test_dispatch_run_resolves_profile_from_alias` — `--profile` omitted;
  mock `ModelResolver.resolve` to return `("model-id", "openrouter")`; assert
  `_one_shot_dispatch` called with `profile_name="openrouter"`
- [ ] `test_dispatch_run_errors_when_prompt_file_missing` — non-existent path;
  assert exit code != 0 and stderr contains a "not found" message
- [ ] `test_dispatch_run_hidden_from_help` — `sq --help` output does not
  contain `"_dispatch-run"`
- [ ] `test_dispatch_run_bad_param_format` — `--param "noequals"`; assert
  exit 1 and stderr mentions the bad value
- [ ] Run: `uv run pytest tests/cli/commands/test_dispatch_run.py -v`
  - [ ] All tests pass; no real network calls
- [ ] `uv run ruff format . && uv run ruff check && uv run pyright`
  - [ ] Clean
- [ ] `git add src/squadron/cli/commands/dispatch_run.py src/squadron/cli/app.py tests/ && git commit -m "feat: add hidden sq _dispatch-run subcommand for non-SDK pipeline dispatch"`

---

### T9: Update `commands/sq/run.md` dispatch section and commit

- [ ] In `commands/sq/run.md`, replace the `### dispatch` section with a
  branched version:
  ```markdown
  ### dispatch
  If the `command` field is present:
    Write the assembled context prompt to a temp file via Bash (`mktemp`).
    Replace `{tmp_path}` in the `command` field with the temp file path.
    Run the command via Bash. Capture stdout as the dispatch response.
    Remove the temp file after capture (`rm -f <path>`).
  Else:
    This is in-session work — you perform the task described in `instruction`.
    If `model_switch` is present, note the recommended model for the user.
    Model switching cannot be automated — only the user can issue `/model`
    commands.
  ```
- [ ] Keep the else-branch wording as close to the original as practical
  - [ ] Temp file cleanup is explicit
  - [ ] The branch mirrors the existing `### review` and `### summary` patterns
- [ ] `git add commands/sq/run.md && git commit -m "feat: branch sq:run dispatch handler on command field for non-SDK models"`

---

### T10: Fix SDK synthetic-error detection in `sdk_session.py`

**Pre-resolved decision**: `ResultMessage` in `claude_agent_sdk` has
`is_error: bool`. The `_translate_result` helper in `translation.py` already
routes non-success subtypes as `MessageType.system` messages. The fix is in
`SDKExecutionSession.dispatch` in `sdk_session.py` — not in `dispatch.py` or
`translation.py`. No changes to `translate_sdk_message` are needed.

- [ ] In `src/squadron/pipeline/sdk_session.py` `dispatch()`, inside the
  `async for sdk_msg in self.client.receive_response():` loop, after calling
  `translate_sdk_message(sdk_msg, sender="pipeline")`:
  - If `isinstance(sdk_msg, ResultMessage) and sdk_msg.is_error`:
    raise `ProviderAPIError(f"SDK reported is_error=True: {sdk_msg.result or sdk_msg.subtype}")`
  - Place this check before appending translated content to `response_parts`
    so no partial error text is returned
- [ ] Import `ResultMessage` from `claude_agent_sdk` at the top of
  `sdk_session.py` (if not already imported)
- [ ] The existing `_check_cli_error` text-prefix check in `dispatch.py`
  is **not removed** — it remains as a backstop for the `"API Error:"` prefix
  shape the Claude CLI can emit
  - [ ] `ProviderAPIError` is raised before any content is appended to
    `response_parts` on the error path
  - [ ] No error message text reaches `_check_cli_error` or the caller
    on the `is_error=True` path

### T11: Test SDK synthetic-error detection and commit

- [ ] In `tests/pipeline/actions/test_dispatch_session.py`:
- [ ] `test_sdk_session_api_error_text_prefix_fails_action` — existing
  behavior: fake session `dispatch` returns `"API Error: 500 …"`; assert
  `ActionResult.success is False` (regression guard for `_check_cli_error`)
- [ ] `test_sdk_session_is_error_message_fails_action` — patch
  `SDKExecutionSession.dispatch` to raise `ProviderAPIError`; assert
  `DispatchAction.execute` returns `ActionResult(success=False)` with
  a non-empty `error` field
- [ ] `test_no_artifact_written_on_sdk_error` — error result `outputs` does
  not contain a design file path; the error text is in `error`, not written
  to any artifact
- [ ] Run: `uv run pytest tests/pipeline/actions/test_dispatch_session.py -v`
  - [ ] All tests pass
- [ ] `uv run ruff format . && uv run ruff check && uv run pyright`
  - [ ] Clean
- [ ] `git add src/squadron/pipeline/sdk_session.py tests/ && git commit -m "fix: raise ProviderAPIError when SDK ResultMessage.is_error is True"`

---

### T12: Full suite verification

- [ ] `uv run pytest tests/ -v` — all tests pass
  - [ ] Full suite green with no regressions

### T13: Verification walkthrough

Run each scenario from the slice doc's Verification Walkthrough:

- [ ] **Step 1 — In-IDE non-SDK model routes through agent path.**
  Inside Claude Code: `/sq:run P4 183 --param model=minimax`. Confirm the
  dispatch JSON contains `command` starting with `sq _dispatch-run … --profile
  openrouter …` and no `model_switch`. The IDE session does not generate
  the design output.
- [ ] **Step 2 — Real-terminal non-SDK model.** `sq run P4 183 --param
  model=minimax`. Same routing via `_dispatch_via_agent`.
- [ ] **Step 3 — Default model uses SDK session.** `sq run P4 183` (no
  `--param model`). `_dispatch_via_session` path, behavior identical to main.
- [ ] **Step 4 — SDK API error halts pipeline cleanly.** Integration test
  covers this; manual re-run optional. Confirm pipeline state shows
  `status=failed`, no design file written.
- [ ] **Step 5 — `sq _dispatch-run` standalone debug.**
  `echo "Write a haiku." > /tmp/p.txt && sq _dispatch-run --prompt-file /tmp/p.txt --model minimax`.
  Confirm haiku on stdout, exit 0, `sq --help` does not list `_dispatch-run`.
  - [ ] All 5 steps pass

### T14: Final cleanup commit (if needed)

- [ ] If any formatting-only or minor fix commits accumulated during T3–T11,
  confirm the working tree is clean; otherwise skip.
- [ ] `git status` — working tree clean (all changes committed in T3, T5,
  T8, T9, T11)
  - [ ] No stray uncommitted changes

### T15: Update slice doc, slice plan, and DEVLOG

- [ ] In `project-documents/user/slices/170-slice.profile-aware-dispatch-model-routing.md`:
  - Update `status: complete`, `dateUpdated: <today>`
- [ ] In the slice plan that tracks slice 170 (confirm in T1 read of
  `100-slices.orchestration-v2.md` or `140-slices.pipeline-foundation.md`):
  mark the slice 170 checkbox `[x]`
- [ ] Write DEVLOG entry summarizing:
  - What changed (renderer fix, new hidden subcommand, SDK `is_error` fix)
  - SDK error path: `ResultMessage.is_error` was not inspected before;
    fix raises `ProviderAPIError` in `sdk_session.py` before returning text
  - Pipelines unblocked (cheap-model dispatch from IDE)
- [ ] `git add -A && git commit -m "docs: mark slice 170 complete"`
  - [ ] Slice frontmatter `status: complete`
  - [ ] Slice plan checkbox `[x]`
  - [ ] DEVLOG entry written
