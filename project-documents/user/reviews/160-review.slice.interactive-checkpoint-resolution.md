---
docType: review
layer: project
reviewType: slice
slice: interactive-checkpoint-resolution
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/160-slice.interactive-checkpoint-resolution.md
aiModel: claude-sonnet-4-6
status: complete
dateCreated: 20260411
dateUpdated: 20260411
findings:
  - id: F001
    severity: pass
    category: architecture
    summary: "Executor-layer placement of interactive I/O is justified"
  - id: F002
    severity: pass
    category: data-flow
    summary: "`merged_params` as the instruction carrier is architecturally sound"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Non-interactive guard correctly handles CI/piped environments"
  - id: F004
    severity: concern
    category: integration
    summary: "Code sample reads findings from checkpoint `ActionResult`, not from `step_prior`"
    location: 160-slice.interactive-checkpoint-resolution.md (Implementation Details, `_execute_step_once` modification)
  - id: F005
    severity: concern
    category: dependencies
    summary: "`ExecutionMode` dependency is claimed but unused in the implementation"
    location: 160-slice.interactive-checkpoint-resolution.md (Dependencies, Prerequisites)
  - id: F006
    severity: note
    category: data-flow
    summary: "`override_instructions` persists across all downstream steps — no clear reset mechanism"
  - id: F007
    severity: note
    category: documentation
    summary: "Architecture's \"160-band\" note may cause confusion with this slice's number"
    location: 140-arch.pipeline-foundation.md (Notes section)
---

# Review: slice — slice 160

**Verdict:** CONCERNS
**Model:** claude-sonnet-4-6

## Findings

### [PASS] Executor-layer placement of interactive I/O is justified

The architecture assigns the checkpoint action "State serialization, presentation, resume token" responsibility. The slice places interactive terminal I/O in the executor rather than the action. The design justifies this clearly: the executor already holds `run_id`, `step_prior`, and control flow authority. Moving stdin/stdout into the action would require threading I/O through `ActionContext`, which the architecture describes as a "typed struct carrying data" — not a service object. The placement is consistent with the architecture's intent and avoids an inappropriate interface expansion.

---

### [PASS] `merged_params` as the instruction carrier is architecturally sound

`merged_params` is already the executor's cross-step parameter bus. Injecting `override_instructions` there is consistent with how pipeline-scoped params flow today. The decision not to persist it to `RunState` is correct — it avoids a schema version bump and keeps the state file as a structural position record, matching the architecture's stated design.

---

### [PASS] Non-interactive guard correctly handles CI/piped environments

Defaulting to EXIT when `sys.stdin.isatty()` is false or `SQUADRON_NO_INTERACTIVE` is set is the right failure mode. The existing exit path is preserved exactly, so pre-160 behavior is guaranteed in non-interactive contexts.

---

### [CONCERN] Code sample reads findings from checkpoint `ActionResult`, not from `step_prior`

The prose says:

> *"the suggestion text is assembled from the most recent `ActionResult` in `step_prior` that has a non-None `verdict`"*

But the code sample reads:

```python
verdict = result.verdict
findings = [f for f in (result.findings or []) if isinstance(f, dict)]
```

Here `result` is the **checkpoint** action's `ActionResult`. The checkpoint action returns `outputs["checkpoint"] = "paused"` — it does not populate `verdict` or `findings`. Those fields are populated by the **review** action, whose result is already in `step_prior` under a key like `"review-N"`.

`executor.py` already has `_last_with_verdict(results)` which is exactly the pattern needed: scan `step_prior.values()` for the last result with a non-None `verdict`. The code sample should use that (or an equivalent). As written, `verdict` and `findings` will always be `None`/`[]` at the checkpoint detection point, silently defeating the Accept path.

This is a functional specification error that must be corrected before implementation begins.

---

### [CONCERN] `ExecutionMode` dependency is claimed but unused in the implementation

The slice declares that `ExecutionMode` from slice 156 is required: *"the checkpoint interactive handler reads the run_id from the executor context."* But `run_id` is already a direct parameter to `_execute_step_once` — it does not require `ExecutionMode` to retrieve it. None of the code samples reference `ExecutionMode` or `RunState.execution_mode`.

The actual gating on execution mode (SDK vs. prompt-only) is handled implicitly by the `_is_interactive()` guard (`sys.stdin.isatty()` + `SQUADRON_NO_INTERACTIVE`). If `ExecutionMode` is genuinely needed (e.g., to short-circuit the interactive path in one-shot agent mode), the design should show where and why. If not, the dependency claim is misleading and should be removed or narrowed.

---

### [NOTE] `override_instructions` persists across all downstream steps — no clear reset mechanism

Once set in `merged_params`, `override_instructions` propagates to every subsequent dispatch for the lifetime of the run. The design acknowledges this ("the instructions remain relevant context") but does not provide a mechanism for the executor to scope or clear them if a second checkpoint fires with a different decision. The current design replaces the value on a second Accept/Override, which is correct. However, if a later step fires and the instructions are stale, the only recourse is a fresh run. This is an acceptable limitation for a first implementation but should be documented as a known constraint.

---

### [NOTE] Architecture's "160-band" note may cause confusion with this slice's number

The architecture states: *"The 160-band is reserved for Pipeline Intelligence"* and separately *"The 160-band is already claimed by multi-agent communication."* Slice 160 in the pipeline foundation is a sequentially numbered slice within initiative 140, not the Pipeline Intelligence initiative. The architecture's own note is self-contradictory on what 160 means. This is a documentation ambiguity in the architecture document, not a problem with the slice design.
