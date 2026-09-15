---
docType: tasks
slice: claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement
project: squadron
lld: user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md
dependencies: []
projectState: Slice 920 has an approved (PASS) design. No production code written yet.
dateCreated: 20260915
dateUpdated: 20260915
status: in_progress
---

## Context Summary
- Working on the `claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement` slice (index 920), fixing [issue #30](https://github.com/ecorkran/squadron/issues/30).
- Current state: `pyproject.toml` pins `claude-agent-sdk>=0.1.38`; a ~50-line parser-patching shim in `src/squadron/providers/sdk/rate_limit.py` (`install_rate_limit_parser_shim`) works around that version's parser raising on the CLI's `rate_limit_event` message type.
- The design is a bump to `>=0.2.152` (the parser now handles `rate_limit_event` natively as a typed `RateLimitEvent`) plus a re-key of throttle detection from "parse failure occurred" to "typed event says `status == 'rejected'`". Full rationale, decisions D1–D6, and probe findings: see the LLD referenced above — tasks below reference it rather than restating it.
- No dependencies on other in-flight slices.
- Delivers: shim removed, SDK floor raised, throttle detection re-keyed onto the native typed event across all three dispatch paths (query mode, agent client mode, pipeline `dispatch`), tests rewritten to exercise the real mechanism, and both a live review and a live metrology audit run to confirm no silent backoff loss.
- Next planned slice: none currently queued behind this one; see `900-slices.maintenance-and-refactoring.md` for the parent architecture's remaining backlog.

## Tasks

- [x] **1. Raise the SDK dependency floor**
  - [x] Edit `pyproject.toml`: change `"claude-agent-sdk>=0.1.38"` to `"claude-agent-sdk>=0.2.152"` (floor only — no ceiling; see LLD Decision D2 for why a ceiling would recreate the defect).
  - [x] Run `uv lock` to refresh `uv.lock` against the new floor.
  - [x] Run `uv sync` and confirm the resolved version: `python -c "import importlib.metadata as m; print(m.version('claude-agent-sdk'))"` reports `>= 0.2.152`.
  - [x] Success: `pyproject.toml` shows the new floor, `uv.lock` is regenerated and committed, resolved version confirmed ≥ 0.2.152.
  - [x] Commit: `chore: raise claude-agent-sdk floor to 0.2.152`

- [x] **2. Add typed classification and the dedicated throttle exception**
  - [x] In `src/squadron/providers/sdk/rate_limit.py`, add `event_blocks(event: RateLimitEvent) -> bool` per LLD Decision D3 — delegates to the same `_STATUS_REJECTED` constant `rate_limit_event_blocks` already uses, reading `event.rate_limit_info.status` (not `.raw`).
  - [x] Add `class RateLimitRejected(ClaudeSDKError)` per LLD Decision D4, with a docstring explaining it signals a typed `rejected` event (a genuine throttle) — do not implement any behavior beyond subclassing.
  - [x] Add a module-level `is_throttle(exc: Exception) -> bool` helper: `True` for `RateLimitRejected`, or for any other `ClaudeSDKError` whose `str(exc)` contains `RATE_LIMIT_MARKER` (the retained substring path for a genuine 429 surfaced as plain text — LLD D4).
  - [x] Import `RateLimitEvent` from `claude_agent_sdk` at the top of `rate_limit.py`.
  - [x] Success: `event_blocks`, `RateLimitRejected`, and `is_throttle` exist in `rate_limit.py`; `_STATUS_REJECTED` remains the single definition referenced by both classifiers (no duplicated literal).
  - [x] Commit: `feat: add typed rate-limit classification and RateLimitRejected`

- [x] **3. Unit tests for the new classification helpers**
  - [x] In `tests/providers/sdk/test_agent.py` (or a new focused test module if preferred — keep with existing `TestRateLimitBackoff` class if adding to that file), add tests constructing a real `RateLimitEvent(rate_limit_info=RateLimitInfo(status=..., ...), uuid=..., session_id=...)` for each of `rejected`, `allowed`, `allowed_warning` and assert `event_blocks` returns `True` only for `rejected`.
  - [x] Add a test asserting `is_throttle(RateLimitRejected("x"))` is `True`.
  - [x] Add a test asserting `is_throttle(ClaudeSDKError("rate_limit_event: slow down"))` is `True` (retained substring path) and `is_throttle(ClaudeSDKError("some other error"))` is `False`.
  - [x] Run: `uv run pytest tests/providers/sdk/test_agent.py -q -k "classif or throttle or RateLimitRejected"` — confirm new tests pass.
  - [x] Success: new tests pass; they construct real SDK types, not fabricated exceptions.
  - [x] Commit: `test: add unit coverage for typed rate-limit classification`

- [x] **4. Translation: recognize `RateLimitEvent` explicitly**
  - [x] In `src/squadron/providers/sdk/translation.py`, add an explicit `isinstance(sdk_msg, RateLimitEvent)` branch in `translate_sdk_message` per LLD Decision D6: return one `Message` with `message_type=MessageType.system`, `metadata={"sdk_type": "rate_limit_event", "status": <event.rate_limit_info.status>}`. Import `RateLimitEvent` from `claude_agent_sdk`.
  - [x] Do not raise or filter here — dispatch-site inspection (Task 6/7) happens before translation ever sees a `rejected` event; this branch only needs to make the type observable rather than silently dropped via the existing `return []` default.
  - [x] Success: `translate_sdk_message` returns a non-empty list for a `RateLimitEvent` input instead of falling through to `return []`.
  - [x] Commit: `feat: translate RateLimitEvent into an observable system message`

- [x] **5. Test the translation branch**
  - [x] In `tests/providers/sdk/test_translation.py` (create if it does not exist, following the existing test-file layout for this module), add a test constructing a real `RateLimitEvent` and asserting `translate_sdk_message` returns one message with `metadata["sdk_type"] == "rate_limit_event"` and the correct status.
  - [x] Run: `uv run pytest tests/providers/sdk/test_translation.py -q` — confirm pass.
  - [x] Success: new test passes and exercises the real `RateLimitEvent` type, not a mock standing in for it.
  - [x] Commit: `test: add coverage for RateLimitEvent translation`

- [x] **6. Re-key `agent.py`'s `_skip_unparseable`, and rewrite its dependent tests in the same task**
  - [x] In `src/squadron/providers/sdk/agent.py`, rewrite `_skip_unparseable` per LLD Decision D4/D5:
    - [x] Remove the `except MessageParseError` branch's `is_rate_limit_event(exc.data)` special case — after the upgrade, `rate_limit_event` parses natively, so a `MessageParseError` cannot carry one at the pinned floor. Keep the branch itself (WARNING log, skip) for genuinely unknown future types.
    - [x] Add inspection of yielded messages: when a yielded `sdk_msg` is a `RateLimitEvent` with `event_blocks(sdk_msg)` true, raise `RateLimitRejected` — the event is intercepted here and never yielded onward. Otherwise (informational), log at DEBUG and **yield the event through unchanged**, exactly like any other message this generator passes along — it reaches the caller's loop and then `translate_sdk_message` (Task 4's branch) the same way an `AssistantMessage` does. Do not special-case it into a "continue without yielding" — that would drop it, which is the opposite of LLD Decision D6's intent (see the LLD's corrected D4 wording).
    - [x] Rewrite the method's docstring — it currently narrates the shim's now-removed mechanics (`install_rate_limit_parser_shim`, stream-already-dead framing). Replace with the two-concern description from LLD Decision D5: (1) unparseable message → WARNING, skip, stream ends cleanly; (2) typed `RateLimitEvent` → inspect; `rejected` raises and is intercepted, informational is yielded through to translation; stream stays alive either way.
  - [x] In the same file, replace both `RATE_LIMIT_MARKER in str(exc)` gates (in `_handle_query_mode` and `_handle_client_mode`) with `is_throttle(exc)`, per LLD Decision D4.
  - [x] Remove the now-unused `is_rate_limit_event` import; remove the `MessageParseError` import only if no branch still references it (it should still be referenced by the retained unparseable-skip branch — keep the import).
  - [x] **In this same task**, rewrite the tests in `tests/providers/sdk/test_agent.py` that the above changes immediately break or make obsolete — do not defer these to a later task, per the test-with pattern:
    - [x] Rewrite `test_a_rejected_rate_limit_event_reaches_the_backoff` — replace the `MessageParseError` fabrication with a generator that yields a real `RateLimitEvent(rate_limit_info=RateLimitInfo(status="rejected", ...), uuid=..., session_id=...)`; assert the same outcome (`ProviderRateLimitError` raised, `slept` length equals the retry budget).
    - [x] Rewrite `test_stats_accumulate_across_retries` and `test_exhausted_rate_limit_raises_a_distinct_error` — replace each `_make_error_gen(ClaudeSDKError("rate_limit_event: slow down"))` / `(...quota")` with a generator yielding a real `RateLimitEvent` with `status="rejected"` on every call (mirroring `_make_error_gen`'s repeat-forever shape, or a small local helper if the shape doesn't fit directly).
    - [x] **Do not rewrite `test_retries_actually_sleep`.** Change only its fabricated payload from `ClaudeSDKError("rate_limit_event: slow down")` to a plain `ClaudeSDKError("rate_limit: slow down")` (still contains `RATE_LIMIT_MARKER`, no `rate_limit_event` payload attached) and keep it going through `is_throttle`'s retained substring path unchanged. This is the slice's only integration-level (through the real retry loop, not just the `is_throttle` unit test from Task 3) coverage of Success Criterion 7 — keep its docstring/comment updated to say so explicitly.
    - [x] Rewrite `test_budget_resets_when_work_comes_through` — replace the `raise ClaudeSDKError("rate_limit_event: slow down")` inside `receive_response` with `yield RateLimitEvent(rate_limit_info=RateLimitInfo(status="rejected", ...), ...)` (a yield, not a raise — the whole point of this test and this slice is that the stream stays alive). Assert the same outcome (`throttles == max_throttles`, message count, final state `idle`).
    - [x] Delete the four shim-specific tests that test a mechanism this task removes: `test_the_shim_absorbs_informational_events`, `test_the_shim_lets_a_rejected_event_raise`, `test_the_shim_patches_both_sdk_call_sites`, `test_the_shim_leaves_other_parse_failures_alone`.
    - [x] `TestUnparseableMessages`'s three tests (`test_unparseable_message_does_not_kill_the_stream`, `test_content_after_an_unparseable_message_still_arrives`, `test_other_unknown_messages_are_still_skipped`) test a genuinely-unknown (non-rate-limit) type and are unaffected in mechanism — verify they still pass; update only comments referencing the removed shim.
    - [x] Add a new test for LLD Success Criterion 10: an `allowed_warning` `RateLimitEvent` fed through `_skip_unparseable` must **not** raise, must **not** increment `RateLimitStats.throttles`, and must be yielded through to the caller (assert it appears, translated, among the returned messages) rather than silently dropped.
  - [x] Success: `agent.py` no longer imports `is_rate_limit_event`; both query-mode and client-mode retry gates use `is_throttle`; `_skip_unparseable`'s docstring accurately describes post-upgrade behavior. `grep -n "MessageParseError.*rate_limit\|ClaudeSDKError(\"rate_limit_event" tests/providers/sdk/test_agent.py` returns no matches. Run `uv run pytest tests/providers/sdk/test_agent.py -q` — all tests pass, with no commit in this task leaving the suite red.
  - [x] Commit: `refactor: re-key agent.py throttle detection onto typed RateLimitEvent`

- [x] **7. Re-key `sdk_session.py`'s `dispatch` — the asymmetric path with no `_skip_unparseable` wrapper — and rewrite its dependent test in the same task**
  - [x] In `src/squadron/pipeline/sdk_session.py`, remove the `install_rate_limit_parser_shim` import and its call in `connect()`; remove the associated comment block referencing the shim.
  - [x] Inside `dispatch`'s `async for sdk_msg in self.client.receive_response():` loop, add inline inspection **before** the existing `ResultMessage.is_error` check: when `sdk_msg` is a `RateLimitEvent` with `event_blocks(sdk_msg)` true, raise `RateLimitRejected`. Otherwise let it continue to `translate_sdk_message` as normal, same as every other message type in this loop (informational events must become observable per Task 4, not dropped).
  - [x] This is the asymmetric path called out in LLD Decision D4 and flagged in the design as "the most likely place for the slice to half-land" — there is no `_skip_unparseable` wrapper here, so this inspection cannot be shared with Task 6's change; it must be added directly in this loop.
  - [x] Replace the `RATE_LIMIT_MARKER in str(exc)` gate in `dispatch`'s `except ClaudeSDKError` branch with `is_throttle(exc)`.
  - [x] Rewrite the stale comments in `dispatch` (the "Informational rate-limit events never reach here: the parser shim absorbs them..." block) to describe the new mechanism per LLD Decision D5's two-concern framing.
  - [x] **In this same task**, rewrite `test_dispatch_retries_on_rate_limit` in `tests/pipeline/test_sdk_session.py` — do not defer to a later task. Replace `raise ClaudeSDKError("rate_limit_event")` inside `_gen()` with a `yield` of a real `RateLimitEvent(rate_limit_info=RateLimitInfo(status="rejected", ...), uuid=..., session_id=...)` on the first two calls, succeeding on the third. Assert the same outcome (`"done" in result`, `call_count == 3`).
  - [x] Success: `sdk_session.py` no longer imports or calls `install_rate_limit_parser_shim`; the `dispatch` loop inspects `RateLimitEvent` inline before the `ResultMessage.is_error` check; the retry gate uses `is_throttle`. `grep -n "ClaudeSDKError(\"rate_limit_event" tests/pipeline/test_sdk_session.py` returns no matches. Run `uv run pytest tests/pipeline/test_sdk_session.py -q` — all tests pass, with no commit in this task leaving the suite red.
  - [x] Commit: `refactor: re-key sdk_session.dispatch throttle detection onto typed RateLimitEvent`

- [x] **8. Extend `dispatch`'s `sdk_type` exclusion set — required by LLD Decision D6 — and test it in the same task**
  - [x] In `src/squadron/pipeline/sdk_session.py`'s `dispatch`, find the `if sdk_type not in (SDK_RESULT_TYPE, "tool_use", "tool_result"):` check that gates `response_parts.append`. Add `RATE_LIMIT_EVENT_TYPE` (imported from `squadron.providers.sdk.rate_limit`, where it already exists — `RATE_LIMIT_EVENT_TYPE = "rate_limit_event"`) to that exclusion tuple. Use the existing constant, not a new string literal — `sdk_session.py` already imports from `rate_limit.py`, and the project convention is one definition per comparison value.
  - [x] This is not optional: without it, an informational rate-limit notice concatenates into the returned prose — the exact defect class from issue #23. Verify no other `sdk_type` exclusion list exists elsewhere in the codebase that also needs the addition (grep for `SDK_RESULT_TYPE` across `src/`).
  - [x] Add a test in `tests/pipeline/test_sdk_session.py` for LLD Success Criterion 10: an `allowed`/`allowed_warning` `RateLimitEvent` yielded from `receive_response` must not trigger a retry and must not appear in the returned response text.
  - [x] Success: a `RateLimitEvent`-derived message never appears in `dispatch`'s returned response string; the new test passes.
  - [x] Commit: `fix: exclude rate_limit_event from dispatch response text`

- [x] **9. Remove the shim itself and its call sites**
  - [x] In `src/squadron/providers/sdk/rate_limit.py`, delete `install_rate_limit_parser_shim` in its entirety and delete `is_rate_limit_event` (loses its only production caller per Task 6).
  - [x] Rewrite the module docstring — it currently narrates the shim's history and purpose as the module's lead description; per LLD Part A, update it to describe the module's post-upgrade role (typed classification, backoff constants, stats) without referencing the removed shim as current behavior. A brief historical note (why the constants/classifier exist) is fine; the shim's mechanics are not.
  - [x] In `src/squadron/providers/sdk/provider.py`, remove the `install_rate_limit_parser_shim` import and its call in `create_agent` (with its preceding comment).
  - [x] Confirm `src/squadron/pipeline/sdk_session.py` no longer references it (done in Task 7 — verify here as a checkpoint).
  - [x] By this point in the sequence, Task 6 has already deleted the four shim-specific tests in `test_agent.py` that imported `install_rate_limit_parser_shim` from `claude_agent_sdk._internal` — this task's grep below confirms that deletion held, it does not perform it.
  - [x] Success: `grep -rn "install_rate_limit_parser_shim" src tests` returns no matches (both directories — Success Criterion 2 covers both). `grep -rn "is_rate_limit_event" src tests` returns no matches. `grep -rn "claude_agent_sdk._internal" src` returns no matches (per LLD Success Criterion 2).
  - [x] Commit: `refactor: delete rate-limit parser shim, floor makes it unreachable`

- [x] **10. Verify `test_provider.py` and `test_audit_cli.py` need no fabrication rewrite, only plumbing checks**
  - [x] `tests/providers/sdk/test_provider.py`: `test_rate_limit_overrides_reach_the_agent` tests config plumbing (`max_rate_limit_retries`, `rate_limit_cap_s` reach the agent constructor) and does not fabricate an SDK exception — confirm it still passes unmodified after Task 9 removes the shim call from `provider.py`. If `create_agent`'s test setup ever asserted the shim was installed, remove that assertion (grep first to confirm it doesn't exist — it wasn't found in the current file).
  - [x] `tests/metrology/test_audit_cli.py`: `test_rate_limited_campaign_stops_instead_of_grinding` and `test_rate_limit_is_reported_distinctly_from_a_bad_run` construct `AuditRunResult(failure=AuditRunFailure.RATE_LIMITED, detail="rate_limit_event: quota")` directly — this is CLI-layer plumbing decoupled from the SDK parser mechanism (never touches `MessageParseError`/`ClaudeSDKError`), so it needs no rewrite for Success Criterion 9. Confirm both pass unmodified.
  - [x] Run: `uv run pytest tests/providers/sdk/test_provider.py tests/metrology/test_audit_cli.py -q` — all pass with no source changes needed in these two files.
  - [x] Do not modify `tests/providers/openai/test_agent.py` — confirmed out of scope per LLD's "Not affected" note (it constructs `openai.RateLimitError` on an independent provider path and never imports `claude_agent_sdk`).
  - [x] Success: both files pass unmodified; a one-line note in the DEVLOG entry (Task 14) records that no changes were needed here, so a reviewer doesn't wonder if they were missed.

- [x] **11. Full suite, lint, and type-check pass**
  - [x] Run: `uv run pytest tests/providers/sdk tests/pipeline/test_sdk_session.py -q` — confirm green.
  - [x] Run: `uv run pytest tests/providers tests/metrology -q` — confirm green (broader regression sweep per LLD walkthrough step 2).
  - [x] Run: `uv run pytest -q` (full suite) — confirm green; no unrelated regressions.
  - [x] Run: `uv run ruff format --check .` — confirm clean; if not, run `uv run ruff format .` and re-check.
  - [x] Run: `uv run ruff check .` — confirm zero errors.
  - [x] Run: `uv run pyright` — confirm zero errors (merge blocker per project guidelines).
  - [x] Success: all four commands report clean/green with no unaddressed output.
  - [x] Commit: `chore: format and lint pass for slice 920` (no-op: format/lint/pyright were already clean, nothing to commit)

- [ ] **12. Live end-to-end verification — real review run**
  - [ ] **Run from a straight CLI terminal, not from an IDE-extension or Claude Code session** — the SDK-backed paths under test spawn a Claude Code subprocess, which is blocked inside an existing Claude session (LLD Verification Walkthrough, step 3 note).
  - [ ] Run: `uv run sq review code --diff HEAD~1 -v` from the squadron repo root.
  - [ ] Confirm: the review completes, writes an artifact with a parsed verdict, the run logs no `Unknown message type` warning, and no `rate_limit_event` text appears in the artifact's prose (if a `rate_limit_event` fires during the run at all).
  - [ ] Success: run completes cleanly; verdict artifact present; no leaked rate-limit text in output. Record the observed outcome (including whether a live throttle occurred) in the DEVLOG entry (Task 14).

- [ ] **13. Live end-to-end verification — real metrology audit and forced-throttle observation**
  - [ ] **Run from a straight CLI terminal**, same constraint as Task 12.
  - [ ] Run: `uv run sq metrology audit run -v` — the workload that exposed the original bug; subagent fan-out makes a live `rate_limit_event` likely.
  - [ ] Confirm: the audit runs to completion rather than dying mid-stream. If throttling occurs, the run reports a rate-limit summary (`N rate-limit pauses, Ns spent waiting`) and resumes rather than aborting. A clean run with no throttling observed is also a pass for this step (per LLD walkthrough step 4) — but if no live throttle occurs, proceed to the forced observation below to close that gap.
  - [ ] Forced-throttle observation (LLD Verification Walkthrough step 5): temporarily inject a `rejected` `RateLimitEvent` at the `receive_response` seam (a local, uncommitted patch or test double) in one dispatch path, confirm the WARNING fires, `RateLimitStats.throttles` increments, and the run continues. **Revert this injection before committing** — it must not land in the codebase.
  - [ ] Success: audit either completes cleanly or reports rate-limit pauses and resumes; the forced-throttle observation independently confirms the WARNING/stats/continuation behavior. Record both outcomes in the DEVLOG entry (Task 14).

- [ ] **14. DEVLOG entry and slice closeout**
  - [ ] Add a dated entry to the root `DEVLOG.md` (not the deprecated `project-documents/DEVLOG.md` stub) summarizing: SDK floor raised to `>=0.2.152`, shim removed, throttle detection re-keyed onto `RateLimitEvent` across all three dispatch paths, test rewrites completed alongside their implementation tasks (Tasks 6–8, satisfying criteria 9–10), and the outcomes of the two live verification runs (Tasks 12–13), including whether a live throttle was observed or only the forced observation confirmed the behavior.
  - [ ] Note explicitly that `tests/providers/sdk/test_provider.py` and `tests/metrology/test_audit_cli.py` needed no source changes (Task 10), and that `tests/providers/openai/test_agent.py` was correctly left untouched.
  - [ ] Update the slice design's frontmatter `status` from `not_started` to `complete` in `user/slices/920-slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md`, and update `dateUpdated`.
  - [ ] Update the parent architecture doc `user/architecture/900-slices.maintenance-and-refactoring.md` entry 18 — mark slice 920 complete, add a pointer to this task file and to the DEVLOG entry. Update `dateUpdated`.
  - [ ] Delegate final task-file checklist verification to the `task-checker` agent (per project guidelines) rather than hand-editing checkboxes for the earlier tasks in this file.
  - [ ] Success: DEVLOG entry present at repo root; slice design and architecture doc both reflect `complete` status; task-checker confirms all checkboxes accurately reflect completed work.
  - [ ] Commit: `docs: close out slice 920 — SDK upgrade and shim retirement complete`

## Notes

- Tasks 6 and 7 touch the two structurally different dispatch mechanisms called out in the LLD — do not attempt to unify them into one shared code path in this slice; `_skip_unparseable` and the pipeline's inline loop are separate call shapes and unifying them is out of scope (not listed in LLD Technical Scope).
- Every task that adds or rewrites a test constructs the actual `RateLimitEvent`/`RateLimitInfo` SDK types (imported from `claude_agent_sdk`) rather than mocking them — this is the entire point of Success Criterion 9 and must not be worked around with a `MagicMock(spec=RateLimitEvent)` that never exercises the real dataclass shape.
- `StreamEvent` and `ConversationResetMessage` handling is explicitly out of scope per the LLD — do not add branches for them in this slice.
- `ClaudeSDKClient` methods gained in 0.2.x (`get_context_usage`, `stop_task`, `rewind_files`, MCP controls) are explicitly out of scope.
