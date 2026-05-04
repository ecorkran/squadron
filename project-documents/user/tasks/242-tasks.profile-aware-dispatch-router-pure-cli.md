---
docType: task-breakdown
slice: profile-aware-dispatch-router-pure-cli
project: squadron
lldReference: 242-slice.profile-aware-dispatch-router-pure-cli.md
dependencies:
  - 241-is-sdk-profile-predicate-re-homing
dateCreated: 20260503
dateUpdated: 20260503
status: complete
---

# Task Breakdown: Profile-Aware Dispatch Router (pure CLI)

## Context Summary

`DispatchAction._dispatch` routes solely on `context.sdk_session is not None`.
When `sq run … --param model=<non-sdk>` runs through `_run_pipeline_sdk`, a
persistent session is always present, so non-SDK aliases (e.g. `minimax`) are
silently misrouted to `_dispatch_via_session` and dispatched to Claude.

This slice adds three things to `src/squadron/pipeline/actions/dispatch.py`:
1. A private `_resolve_model(context)` helper that extracts the duplicated
   `action_model / step_model / resolver.resolve(...)` block from both branches.
2. A new `is_sdk_profile` import from `squadron.providers.profiles` (canonical
   home after slice 241).
3. Updated `_dispatch` that calls `_resolve_model`, applies `is_sdk_profile`,
   and routes non-SDK profiles to `_dispatch_via_agent` even when a session
   exists.

A new test file `tests/pipeline/actions/test_dispatch_routing.py` covers the
five routing cases. Existing test files must stay green.

---

## Tasks

### T1 — Add `is_sdk_profile` import to `dispatch.py`

- [x] Open `src/squadron/pipeline/actions/dispatch.py`.
- [x] Add `from squadron.providers.profiles import is_sdk_profile` to the
      import block, grouped with the other `squadron.providers.*` imports
      (currently lines 13–16).
- [x] Verify no existing import for `is_sdk_profile` is present (there should
      be none; it was only in `summary_oneshot.py` before slice 241).
- [x] **Success:** `grep "from squadron.providers.profiles import is_sdk_profile"
      src/squadron/pipeline/actions/dispatch.py` returns one hit.

### T2 — Extract `_resolve_model` helper

- [x] In `DispatchAction`, add a private method `_resolve_model` that extracts
      the `action_model / step_model / resolver.resolve(...)` cascade shared by
      `_dispatch_via_session` and `_dispatch_via_agent`.

  Signature and body:

  ```python
  def _resolve_model(self, context: ActionContext) -> tuple[str, str | None]:
      action_model = (
          str(context.params["model"]) if "model" in context.params else None
      )
      step_model = (
          str(context.params["step_model"])
          if "step_model" in context.params
          else None
      )
      return context.resolver.resolve(action_model, step_model)
  ```

- [x] Place the method between `_resolve_prompt` and `_dispatch_via_agent`
      (preserving the existing read order of the class).
- [x] **Do not** replace the inline cascade in `_dispatch_via_session` or
      `_dispatch_via_agent` yet — that is T3. This task is addition only.
- [x] **Success:** `_resolve_model` exists and is callable; no behaviour change
      yet (existing tests still pass).

### T3 — Rewrite `_dispatch` to branch on resolved profile

- [x] Replace the body of `_dispatch` (currently lines 132–136) with the
      profile-aware routing logic from the slice design §1:

  ```python
  async def _dispatch(self, context: ActionContext) -> ActionResult:
      """Route to session or agent dispatch path based on resolved profile.

      Precedence:
      1. No persistent session → agent path.
      2. Session present but resolved profile is non-SDK → agent path.
      3. Session present and SDK profile (or None, per is_sdk_profile
         contract) → session path.
      """
      if context.sdk_session is None:
          return await self._dispatch_via_agent(context)

      _, alias_profile = self._resolve_model(context)
      if not is_sdk_profile(alias_profile):
          return await self._dispatch_via_agent(context)

      return await self._dispatch_via_session(context, context.sdk_session)
  ```

- [x] `_dispatch_via_session` and `_dispatch_via_agent` retain their full
      inline resolve cascade (they still call `resolver.resolve` internally).
      `_resolve_model` is only called from `_dispatch` for the routing branch.
- [x] **Success:** the three-branch docstring matches the code; no other
      methods in the file are changed; `ruff check` passes on the file.

### T4 — Verify existing dispatch tests still pass

- [x] Run:
  ```
  uv run pytest tests/pipeline/actions/test_dispatch.py \
                tests/pipeline/actions/test_dispatch_session.py -q
  ```
- [x] All tests must pass. If any fail, diagnose and fix before proceeding.
- [x] **Success:** exit code 0, no failures or errors.

### T5 — Create `test_dispatch_routing.py` with routing unit tests

`test_dispatch.py` is already 412 lines; the five new routing tests go in a
dedicated file.

- [x] Create `tests/pipeline/actions/test_dispatch_routing.py`.
- [x] Copy the `_make_context` helper and any needed fixtures from
      `test_dispatch.py` (or import them via `conftest.py` if they are already
      shared — check first).
- [x] Implement the five test cases from the slice design §Test Plan:

  **T5a** — `test_dispatch_routes_to_agent_when_session_present_but_profile_non_sdk`
  - [x] Build context with a fake `sdk_session` (MagicMock); resolver returns
        `("minimax-text-01", "openrouter")`.
  - [x] Patch `_dispatch_via_agent` to return a known `ActionResult`; patch
        `_dispatch_via_session` to raise `AssertionError("should not be called")`.
  - [x] Assert returned result is the agent-path result.
  - [x] Assert `metadata.profile == "openrouter"` on the returned result.

  **T5b** — `test_dispatch_routes_to_session_when_profile_is_none`
  - [x] Build context with fake session; resolver returns `("claude-sonnet-4-20250514", None)`.
  - [x] `is_sdk_profile(None)` returns `True` per slice-241 contract.
  - [x] Patch `_dispatch_via_session` to return known result; patch
        `_dispatch_via_agent` to raise.
  - [x] Assert session-path result is returned.

  **T5c** — `test_dispatch_routes_to_session_for_explicit_sdk_profile`
  - [x] Build context with fake session; resolver returns `("claude-sonnet-4-20250514", "sdk")`.
  - [x] Patch `_dispatch_via_session` to return known result; patch
        `_dispatch_via_agent` to raise.
  - [x] Assert session-path result is returned.

  **T5d** — `test_dispatch_routes_to_agent_when_no_session`
  - [x] Build context with `sdk_session=None`; resolver returns
        `("minimax-text-01", "openrouter")`.
  - [x] Patch `_dispatch_via_agent` to return known result; patch
        `_dispatch_via_session` to raise.
  - [x] Assert agent-path result is returned (regression guard — today's
        no-session path must remain unchanged).

  **T5e** — `test_dispatch_mixed_pipeline_routes_per_step`
  - [x] Execute two consecutive dispatches on the same `DispatchAction` instance:
        - First context: fake session, resolver returns `(claude-id, None)`.
        - Second context: fake session, resolver returns `(minimax-id, "openrouter")`.
  - [x] Assert first dispatch used session path; second used agent path.
  - [x] Assert per-step `metadata.profile` values differ appropriately.

- [x] **Success:** all five tests pass when run in isolation.

### T6 — Run full routing test file

- [x] Run:
  ```
  uv run pytest tests/pipeline/actions/test_dispatch_routing.py -v
  ```
- [x] All five tests (T5a–T5e) pass; zero failures.
- [x] **Success:** exit code 0.

### T7 — Quality gates

- [x] Run in sequence:
  ```
  uv run ruff format src/ tests/
  uv run ruff check src/ tests/
  uv run pyright
  ```
- [x] Zero ruff errors or warnings; zero pyright errors.
- [x] If ruff auto-formats anything, re-verify tests still pass.
- [x] **Success:** all three commands exit 0.

### T8 — Full test suite

- [x] Run:
  ```
  uv run pytest -q
  ```
- [x] Net count ≥ (baseline 1764 + 5 new routing tests) = 1769 passed.
- [x] Zero failures or errors.
- [x] **Success:** exit code 0, count at or above expected.

### T9 — Commit

- [x] `git add src/squadron/pipeline/actions/dispatch.py
      tests/pipeline/actions/test_dispatch_routing.py`
- [x] Commit from project root:
  ```
  git commit -m "fix: route non-SDK profiles to agent path in pure-CLI dispatch"
  ```
- [x] `git status` shows clean working tree.
- [x] **Success:** commit lands on the slice branch; no untracked changes remain.

### T10 — Verification walkthrough

Unit tests verify routing logic in isolation. This task verifies the fix
end-to-end in a real `sq run` invocation. Requires a live minimax alias and
Claude auth configured (skip individual steps that require live credentials
if unavailable; document which steps were skipped in the DEVLOG).

- [x] **Step 1 — Non-SDK model routes through agent path.**
  Run from a real terminal (not IDE):
  ```
  sq run P4 183 --param model=minimax
  ```
  Inspect `~/.config/squadron/runs/<run-id>/state.json`. Find the dispatch
  step's `result.metadata`.
  - [x] `metadata.profile` is `"openrouter"` (not `"sdk-session"`).
  - [x] `metadata.model` is the resolved minimax model id (not a Claude id).
  - [x] Design artifact content is recognisably minimax output, not Claude output.

- [x] **Step 2 — Default Claude still uses session path.**
  Run:
  ```
  sq run P4 183
  ```
  - [x] Dispatch step's `metadata.profile == "sdk-session"`.
  - [x] Behaviour identical to current main (regression guard).

- [x] **Step 3 — IDE axis unchanged (prompt-only, no regression).**
  Inside Claude Code IDE:
  ```
  /sq:run P4 183 --param model=minimax
  ```
  - [x] Rendered step JSON contains `command` field starting with
        `sq _dispatch-run …` (slice 170 path, unchanged by this slice).
  - [x] No `model_switch` field present.

- [x] **Success:** steps 1 and 2 confirm per-step `metadata.profile`
      matches the actual path taken; step 3 confirms no regression to
      the IDE-axis rendering.

### T11 — Slice closeout

- [x] Update frontmatter in
      `project-documents/user/slices/242-slice.profile-aware-dispatch-router-pure-cli.md`:
      - `status: complete`
      - `dateUpdated: <today>`
- [x] Flip the slice-plan checkbox in
      `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md`
      entry 2 from `[ ]` to `[x]`, appending:
      `**Complete (commit <sha>, <date>).**`
- [x] Add a DEVLOG entry for Phase 6 completion following the `prompt.ai-project.system.md`
      Session State Summary guidance.
- [x] Delegate checklist updates to the `task-checker` agent.
- [x] **Success:** slice status is `complete`; slice-plan entry is checked off.

