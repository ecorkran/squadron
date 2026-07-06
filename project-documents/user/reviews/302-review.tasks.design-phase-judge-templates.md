---
docType: review
layer: project
reviewType: tasks
slice: design-phase-judge-templates
project: squadron
verdict: PASS
sourceDocument: project-documents/user/tasks/302-tasks.design-phase-judge-templates.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260705
dateUpdated: 20260705
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "All success criteria cross-referenced and covered"
    location: 302-tasks.design-phase-judge-templates.md
  - id: F002
    severity: pass
    category: error-handling
    summary: "No gaps — each LLD Risk Assessment failure mode is addressed"
    location: 302-tasks.design-phase-judge-templates.md
  - id: F003
    severity: pass
    category: test-design
    summary: "Test-with pattern correctly maintained"
    location: 302-tasks.design-phase-judge-templates.md
  - id: F004
    severity: pass
    category: scope
    summary: "No scope creep — explicitly out-of-scope items are not in tasks"
    location: 302-tasks.design-phase-judge-templates.md
  - id: F005
    severity: pass
    category: process
    summary: "Commit checkpoints distributed throughout, not batched"
    location: 302-tasks.design-phase-judge-templates.md
  - id: F006
    severity: pass
    category: nfr
    summary: "No load-test / CI-gating gap (NFR not restated)"
    location: 302-slice.design-phase-judge-templates.md
  - id: F007
    severity: pass
    category: testing
    summary: "LLD's prompt-quality risk is acknowledged and mitigated"
    location: 302-tasks.design-phase-judge-templates.md
  - id: F008
    severity: note
    category: documentation
    summary: "CLI invocation shape in LLD step 3 is intentionally not a standalone task"
    location: 302-slice.design-phase-judge-templates.md:Verification Walkthrough
---

# Review: tasks — slice 302

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] All success criteria cross-referenced and covered

The mapping table at the end of the task file explicitly traces each LLD change to its task(s). All five Functional Requirements, all Technical Requirements, and all Integration Requirements are covered.

### [PASS] No gaps — each LLD Risk Assessment failure mode is addressed

The Risk Assessment "failure modes on the judge template path" table enumerates five cases. Four are handled by existing infrastructure (301/300). The two that are **new to this slice** (rogue verdict discarded, TEMPLATE_INPUTS resolution failure → UNKNOWN) are explicitly covered:
- **Rogue verdict:** T7 covers this, asserting that a model-emitted `Verdict.FAIL` does not surface on `ActionResult` — proving `enforce_judge()` never reads `result.verdict`.
- **TEMPLATE_INPUTS resolution failure:** T8 covers this, asserting that a `SliceInfo` missing a required field produces `ActionResult(verdict="UNKNOWN", provenance="judge")` via the existing exception handler.

### [PASS] Test-with pattern correctly maintained

- T1 → T2 (template file + loading tests)
- T3 → T4 (template file + loading tests)
- T5 → T6 (registry entries + resolution tests)
- T7 and T8 follow their relevant infrastructure tasks without violating the pattern

### [PASS] No scope creep — explicitly out-of-scope items are not in tasks

The LLD states as out of scope: judge-gated cycle conventions (303), gate composition (304), multi-sample judging, and judge templates beyond `slice-vs-arch` / `tasks-vs-slice`. None of these appear in the task list. The LLD's **corrected finding** from Phase 5 (no `sq review <judge-template>` CLI subcommand) is acknowledged in both the Context Summary and in the T9/T10 verification approach, and no task attempts to add such a subcommand.

### [PASS] Commit checkpoints distributed throughout, not batched

Each of the 11 tasks carries its own `Commit:` line. T11 (`chore: validate design-phase judge templates slice`) is the final integration gate, not a batch of earlier work deferred to the end.

### [PASS] No load-test / CI-gating gap (NFR not restated)

The parent slice design does not restate a latency, throughput, or reliability NFR; no load test task exists in `tests/load/` for this slice, and no CI wiring task is needed. No finding applies.

### [PASS] LLD's prompt-quality risk is acknowledged and mitigated

The LLD flags under Technical Risks: *"Prompt quality is unverifiable until a real provider run happens. Unit tests cover template loading and input resolution; they cannot cover prompt quality."* Tasks T9 and T10 are the mitigation — each runs its judge template against a real in-repo artifact pair and confirms: non-`None` score + criteria, no emitted verdict summary, correctly shaped findings. This matches the risk's own prescribed mitigation strategy ("at least one live-provider verification run per template").

### [NOTE] CLI invocation shape in LLD step 3 is intentionally not a standalone task

The LLD's Verification Walkthrough step 3 contains a note that the exact CLI invocation shape should be confirmed against the current `sq review` CLI surface. The task file explicitly resolves this in its Context Summary: `sq review`'s four subcommands are each pinned to one template name, judge templates are reachable only via `run_review_with_profile()` directly or the pipeline `review` step. T9 and T10 implement the verified approach. No separate task is needed to "confirm the CLI surface" because the task file documents the conclusion and verification uses the confirmed path. No action required.
