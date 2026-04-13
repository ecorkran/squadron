---
docType: tasks
slice: dispatch-summary-context-injection
project: squadron
lld: user/slices/191-slice.dispatch-summary-context-injection.md
dependencies: [161-summary-step-with-emit-destinations, 164-profile-aware-summary-model-routing]
projectState: 140-band slices 161 and 164 complete. Main branch clean at b0f9dd6.
dateCreated: 20260412
dateUpdated: 20260412
status: not_started
---

## Context Summary

- Working on slice 191: Dispatch Summary Context Injection
- Non-SDK summary models receive only compaction template instructions with zero
  pipeline context, producing empty or hallucinated summaries. Slice 164 unblocked
  routing to non-SDK models but did not solve the context problem.
- This slice fixes the problem by assembling prior pipeline step results into a
  context block and prepending it to the instructions sent to one-shot summary models.
- The SDK summary path (`is_sdk_profile` == True) is untouched throughout.
- Deliverables: one new module (`summary_context.py`), a ~5-line edit to
  `_execute_summary()`, unit tests, and integration tests.
- **Implementation note:** `ActionType` has no `COMPACT` entry — the compact step
  expands to a `"summary"` action. The `match/case` in `_extract_content` only needs
  to handle `ActionType.SUMMARY`; a separate `COMPACT` arm is not needed.
- Next slice: 181 (Pool Resolver Integration and CLI)

---

## Tasks

- [ ] **T1 — Create `src/squadron/pipeline/summary_context.py`**
  - [ ] Add module docstring explaining its purpose and pure-function contract
  - [ ] Define `_HEADER` and `_FOOTER` module-level constants (see slice design for exact text)
  - [ ] Define `_SKIP_TYPES: frozenset[str]` containing `ActionType.CHECKPOINT` and
    `ActionType.COMMIT`
  - [ ] Implement `assemble_dispatch_context(prior_outputs: dict[str, ActionResult]) -> str`
    - Iterates `prior_outputs` in insertion order
    - Skips entries whose `action_type` is in `_SKIP_TYPES`
    - Calls `_extract_content(result)` and skips steps with empty content
    - Builds `## Step: {name} ({action_type})` header for each included step
    - Returns `""` when no sections are produced (no bare frame)
    - Wraps sections in `_HEADER` / `_FOOTER` delimiters
  - [ ] Implement `_extract_content(result: ActionResult) -> str` (private)
    - Returns `f"[Step failed: {result.error}]"` when `result.success` is False
    - Uses `match result.action_type` with `ActionType` enum values (not strings):
      - `DISPATCH` → `outputs["response"]`
      - `REVIEW` → calls `_format_review(result)`
      - `CF_OP` → `outputs["stdout"]` only when `outputs["operation"] == "build_context"`;
        returns `""` for other cf-op operations
      - `SUMMARY` → `outputs["summary"]` (covers both `summary` and `compact` steps,
        since compact expands to a `summary` action)
      - default `case _` → `""`
  - [ ] Implement `_format_review(result: ActionResult) -> str` (private)
    - Formats `Verdict: {verdict}` line if `result.verdict` is set
    - Formats `Findings:` block with `- {finding}` lines if `result.findings` is non-empty
    - Returns joined string
  - [ ] Add `__all__ = ["assemble_dispatch_context"]`
  - [ ] Verify: `from squadron.pipeline.summary_context import assemble_dispatch_context`
    imports cleanly (no circular imports)
  - [ ] Success: module exists, imports cleanly, function signature matches slice design

- [ ] **T2 — Unit tests for `assemble_dispatch_context` (`tests/pipeline/test_summary_context.py`)**
  - [ ] Create `tests/pipeline/test_summary_context.py`
  - [ ] Add fixture helper that creates `ActionResult` instances with minimal fields
    (avoid duplicating `ActionResult` boilerplate across every test)
  - [ ] `test_empty_prior_outputs_returns_empty_string` — `{}` input → `""`
  - [ ] `test_dispatch_output_included` — single dispatch result with non-empty `response`
    key → output contains response text and `## Step:` header
  - [ ] `test_review_output_includes_verdict_and_findings` — review result with verdict
    `"CONCERNS"` and two findings → output contains `Verdict: CONCERNS` and both findings
  - [ ] `test_review_verdict_only` — review result with verdict but empty findings → only
    verdict line, no `Findings:` header
  - [ ] `test_cf_op_build_context_included` — cf-op result with
    `operation="build_context"` and non-empty `stdout` → stdout content included
  - [ ] `test_cf_op_non_build_context_skipped` — cf-op result with `operation="set_phase"`
    → step produces no section (skipped silently)
  - [ ] `test_failed_step_included_with_error` — result with `success=False` and an error
    string → output contains `[Step failed: ...]` with the error text
  - [ ] `test_checkpoint_skipped` — checkpoint result → not included in output
  - [ ] `test_commit_skipped` — commit result → not included in output
  - [ ] `test_summary_output_included` — summary result with non-empty `summary` key →
    summary text included
  - [ ] `test_multiple_steps_ordered` — three steps (dispatch, review, dispatch) →
    output sections appear in insertion order
  - [ ] `test_step_with_empty_response_skipped` — dispatch with `response=""` → no
    section produced for that step
  - [ ] `test_header_and_footer_present` — any non-empty result → output starts with
    `_HEADER` text and ends with `_FOOTER` text
  - [ ] Run: `uv run pytest tests/pipeline/test_summary_context.py -v` — all pass
  - [ ] Success: all 13 tests pass, zero failures, no network calls or provider mocks needed

- [ ] **T3 — Integrate context injection into `_execute_summary()` in `actions/summary.py`**
  - [ ] Locate the non-SDK branch in `_execute_summary()` at
    `src/squadron/pipeline/actions/summary.py`
    (the `else:` branch after `if is_sdk_profile(profile):`)
  - [ ] In the non-SDK branch, before the call to `capture_summary_via_profile`:
    - Import `assemble_dispatch_context` from `squadron.pipeline.summary_context`
      (local import inside the `else` block to avoid circular import risk)
    - Call `context_block = assemble_dispatch_context(context.prior_outputs)`
    - Build `augmented_instructions`: if `context_block` is non-empty, prepend with
      `f"{context_block}\n\n{instructions}"`; otherwise use `instructions` unchanged
    - Pass `augmented_instructions` (not `instructions`) to `capture_summary_via_profile`
  - [ ] Verify the SDK branch (`if is_sdk_profile(profile):`) is completely unmodified
  - [ ] Verify no new top-level imports are added to the module (local import only)
  - [ ] Run: `uv run pytest tests/pipeline/actions/test_summary.py -v` — pre-existing tests
    still pass
  - [ ] Success: non-SDK branch passes augmented instructions; SDK branch unmodified;
    existing tests pass

- [ ] **T4 — Integration tests for context injection (`tests/pipeline/actions/test_summary.py`)**
  - [ ] Open `tests/pipeline/actions/test_summary.py` and read existing test structure
    to understand fixtures in use
  - [ ] Add `test_non_sdk_summary_injects_prior_context`:
    - Build an `ActionContext` with `sdk_session=None`, a non-SDK `profile`, and
      `prior_outputs` containing one dispatch result with a known response string
    - Mock `capture_summary_via_profile` to return a fake summary string
    - Mock the `ModelResolver` to return a non-SDK `(model_id, profile)` pair
    - Call `_execute_summary(...)` (or `SummaryAction.execute(context)`)
    - Assert the `instructions` argument passed to the mock contains the pipeline
      context header (`"--- Pipeline Context"`) and the dispatch response text
    - Assert the action returns `success=True`
  - [ ] Add `test_sdk_summary_does_not_inject_context`:
    - Build an `ActionContext` with a non-None `sdk_session` mock and `prior_outputs`
      containing a dispatch result
    - Call `_execute_summary(...)` with an SDK profile
    - Assert `capture_summary_via_profile` is NOT called
    - Assert the `instructions` passed to `sdk_session.capture_summary` does NOT contain
      `"--- Pipeline Context"`
    - Assert the action returns `success=True`
  - [ ] Run: `uv run pytest tests/pipeline/actions/test_summary.py -v` — all pass
  - [ ] Success: 2 new tests pass; all pre-existing tests still pass

- [ ] **T5 — Full test suite verification and commit**
  - [ ] Run: `uv run pytest tests/pipeline/ -v` — all pipeline tests pass
  - [ ] Run: `uv run ruff format src/squadron/pipeline/summary_context.py
    src/squadron/pipeline/actions/summary.py
    tests/pipeline/test_summary_context.py
    tests/pipeline/actions/test_summary.py`
  - [ ] Run: `uv run ruff check src/squadron/pipeline/summary_context.py
    src/squadron/pipeline/actions/summary.py` — no errors
  - [ ] Commit from project root:
    `git add src/squadron/pipeline/summary_context.py src/squadron/pipeline/actions/summary.py tests/pipeline/test_summary_context.py tests/pipeline/actions/test_summary.py`
    then commit with message `feat: add dispatch context injection for non-SDK summary models`
  - [ ] Success: commit on main (or slice branch), all tests pass, ruff clean

- [ ] **T6 — End-to-end verification**
  - [ ] Confirm minimax alias resolves to a non-SDK profile:
    `uv run python -c "from squadron.models.aliases import resolve_model_alias; print(resolve_model_alias('minimax'))"`
    — expect `('minimax/...', 'openrouter')`
  - [ ] Create `/tmp/test-191.yaml` per Scenario 1 in the slice design Verification
    Walkthrough (dispatch step → minimax summary)
  - [ ] Run: `sq run /tmp/test-191.yaml -vv` — summary output references the dispatch
    step content; does NOT say "no prior history"
  - [ ] Create `/tmp/test-191-sdk.yaml` per Scenario 2 (dispatch step → haiku summary)
  - [ ] Run: `sq run /tmp/test-191-sdk.yaml -vv` — summary runs via SDK session path;
    log does NOT show pipeline context header in the instructions
  - [ ] Create `/tmp/test-191-empty.yaml` per Scenario 3 (no prior steps → minimax summary)
  - [ ] Run: `sq run /tmp/test-191-empty.yaml -vv` — completes without error; no empty
    delimiter frame in the instructions
  - [ ] Success: all three scenarios produce the expected behavior described in the
    Verification Walkthrough

- [ ] **T7 — Mark slice complete**
  - [ ] Update `user/slices/191-slice.dispatch-summary-context-injection.md` frontmatter:
    set `status: complete` and `dateUpdated: 20260412` (or today's date)
  - [ ] Update `user/architecture/180-slices.pipeline-intelligence.md`: check off
    `[ ] **(191) Dispatch Summary Context Injection**` → `[x]`
  - [ ] Commit: `git add` both files, commit with `docs: mark slice 191 complete`
  - [ ] Success: slice design and plan both reflect completed status
