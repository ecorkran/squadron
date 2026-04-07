---
docType: review
reviewType: tasks
slice: review-provider-model-selection
project: squadron
verdict: CONCERNS
dateCreated: 20260321
dateUpdated: 20260321
status: not_started
---

# Review: tasks — slice 119

**Verdict:** CONCERNS
**Model:** opus

## Findings

### [PASS] — Task sequencing and dependency ordering

Tasks follow a logical build-up: data model (T1) → config (T3) → resolution logic (T4/T6) → core execution (T9) → CLI wiring (T12) → user templates (T15) → docs (T18). Dependencies flow forward with no circular references. Implementation/test pairing is consistent (T1/T2, T4/T5, T6/T7, T9/T10, T12/T13, T15/T16).

### [PASS] — Commit checkpoints well-distributed

Five commits (T8, T11, T14, T17, T20) are evenly spaced throughout, each capturing a logical unit of work. No batching at end.

### [PASS] — Core functional requirements covered

SC1–5 (profile routing, backward compatibility, model inference) map cleanly to T9/T12 (routing), T4/T6 (resolution/inference), and T19 (regression). SC6–8 (user templates, config default) map to T15, T3/T4. SC10 (slash commands) maps to T18.

### [CONCERN] — SC9: Auto-save / `--json` / `--no-save` parity has no explicit test

The slice requires: *"Review auto-save and `--json`/`--no-save` flags work identically regardless of profile."* No task or test verifies this. If auto-save happens in the CLI layer after receiving `ReviewResult`, it may work implicitly, but there's risk of regression if `run_review_with_profile()` returns a `ReviewResult` with different structure or missing fields on the non-SDK path. **Recommendation:** Add a test case in T10 or T13 verifying that a non-SDK `ReviewResult` flows correctly through auto-save and JSON output, or at minimum add a checklist item in T12 confirming `--json` and `--no-save` are tested with a non-SDK profile.

### [CONCERN] — T12 implementation guidance is ambiguous

T12 says: *"Replace `_run_review_command()` call with `run_review_with_profile()` (or wire profile through `_run_review_command`)"*. The "or" leaves the implementer choosing between two different architectural approaches. A junior AI may pick the wrong one or waste time deliberating. **Recommendation:** Pick one approach and make it explicit. Since `_run_review_command()` likely handles auto-save, JSON output, and error handling, the cleaner path is probably wiring `profile` through `_run_review_command()` and having it call `run_review_with_profile()` internally.

### [CONCERN] — `_resolve_profile()` signature changes between T4 and T6

T4 defines `_resolve_profile(flag: str | None, template: ReviewTemplate | None = None) -> str`. T6 adds model inference and says *"Integrate into `_resolve_profile()`"*, which requires adding a `model` parameter. Tests in T5 are written against the T4 signature and may need updating after T6. Since T5 and T7 both test this function and both fall within the T8 commit, this is manageable but could confuse sequential execution. **Recommendation:** Define the full signature in T4 (including `model: str | None = None`) and simply skip inference logic until T6, or note in T5 that tests may be updated in T7.

### [CONCERN] — `review list` command call site update is implicit

Verification walkthrough #6 requires `sq review list` to show both built-in and user templates. T15 mentions *"Update all call sites that reference `load_builtin_templates`"* but doesn't specifically identify the `review list` command. T16 includes a test for it. A junior AI might miss this call site. **Recommendation:** Explicitly list `review list` as a call site to update in T15.

### [PASS] — Scope matches slice boundaries

No tasks venture into excluded scope (Anthropic API provider, ensemble review, MCP exposure, tool support for non-SDK). The exclusions are respected.

### [PASS] — Task granularity is appropriate

No task is too large (the biggest, T9, is well-scoped with clear subtasks) and none are too granular. Each task is independently completable with clear success criteria (`pyright`/`ruff`/`pytest` gates).

### [PASS] — Post-implementation section is appropriate

Manual verification walkthroughs are correctly separated from AI-automatable tasks and cover the key live-test scenarios from the slice's verification section.
