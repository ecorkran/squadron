---
docType: review
layer: project
reviewType: slice
slice: plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: efe8eb010180b4bcb618e63bc2254d1d0ec97e81
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 18
findings:
  - id: F001
    severity: concern
    category: architecture-alignment
    summary: "Boundary tension with the parent architecture's \"no 140 code modified / grammar changes out of scope\" principle is unacknowledged"
    location: "project-documents/user/slices/195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan.md#architecture"
  - id: F002
    severity: concern
    category: integration-verification
    summary: "Global phase-step reordering rests on an unverified cf ordering claim and changes runtime behavior of every existing pipeline"
    location: "project-documents/user/slices/195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan.md:197"
  - id: F003
    severity: note
    category: documentation
    summary: "Frontmatter dependency set drifts from both the plan and the design's own body"
    location: "project-documents/user/slices/195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan.md:6"
  - id: F004
    severity: note
    category: concurrency
    summary: "Concurrent cf consumers during a batch run are unaddressed"
    location: "project-documents/user/slices/195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan.md#state-management"
  - id: F005
    severity: note
    category: scope
    summary: "Unconditional report file and stdout summary extend to every existing `each` user"
    location: "project-documents/user/slices/195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan.md:260"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes for new I/O paths and decision points are enumerated with explicit, observable outcomes"
    location: "project-documents/user/slices/195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan.md#patterns-and-conventions"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "Faithful to the parent plan's slice 195 scope, with explicit exclusions"
    location: "project-documents/user/slices/195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan.md"
---

# Review: slice — slice 195

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] Boundary tension with the parent architecture's "no 140 code modified / grammar changes out of scope" principle is unacknowledged

The parent architecture states "No 140 code is modified. 180 registers new strategies, new resolver backends, and new action behaviors through the registries 140 establishes" (`180-arch.pipeline-intelligence.md:40`), lists "Changes to 140's pipeline grammar (only registration of new strategies/behaviors)" under Out of Scope (line 702), and its Package Structure says all initiative code lives in `pipeline/intelligence/`. This design instead directly modifies 140's executor (`_execute_step` router, `_execute_each_step`, `_execute_loop_body`, `_parse_loop_config`, `LoopCondition`), three step types (`steps/collection.py`, `steps/loop.py`, `steps/phase.py` — including a new `plan:` key on phase steps), three actions (`cf_op`, `dispatch`, `review`), and adds pipeline-grammar keys (`on_item_failure`, `accept_if`, `skip_if_met`, `feedback: review`), plus new modules `pipeline/sources.py` and `pipeline/batch_report.py` outside the `intelligence/` package. The parent slice plan (item 195: "Engine pieces are general so each phase is a YAML file, not an engine change") explicitly authorizes this shape, and slice 194 — marked complete in the same plan — already established the precedent by adding the `loop:` step type to the grammar. So this is a conflict between the architecture document and its own slice plan, not a design error. However, the design never acknowledges the deviation or cites its authorization, and the architecture doc's Scope Boundaries have not been updated to match what the initiative now ships. A reviewer auditing this slice against the architecture alone would read it as a scope violation. Recommend a short "Architecture alignment" note in the design stating that the slice plan supersedes the architecture's grammar boundary for 194/195, and/or updating the architecture's Out of Scope section.

### [CONCERN] Global phase-step reordering rests on an unverified cf ordering claim and changes runtime behavior of every existing pipeline

D2's "Order fix" flips `PhaseStepType.expand()` from today's `set_phase` → `set_slice` order (phase.py:156-157) to `set_slice` → `set_phase`, explicitly for every phase step ("This applies to every phase step, not just batch pipelines") — i.e., P4, P5, `app.yaml`, `judge-cycle`, and `findings-addressed-cycle` all change at runtime, while the Integration Requirements verify only that they "load and validate unchanged" and the walkthrough exercises the new ordering only through the batch's own steps (which always carry `plan:`). The flip is justified by the cf switching sequence in D2 ("`cf set phase {phase}`, always after the slice"), but unlike the design's other cf claims (`cf list slices/tasks {archIndex} --json` are explicitly "verified against cf as installed"), this ordering-semantics claim carries no verification evidence. If `cf set phase` before `cf set slice` is in fact order-independent in cf, the global flip is unnecessary blast radius on shared pipelines; if it is genuinely required, pre-slice pipelines have been misordered all along, which is itself a finding worth stating. Recommend verifying the ordering semantics against cf as installed (matching the design's own evidentiary standard) or scoping the reorder to `plan:`-carrying steps, and recording the evidence in D2.

### [NOTE] Frontmatter dependency set drifts from both the plan and the design's own body

`dependencies: [194, 181]` omits 927, which the parent plan lists for slice 195 and which the #139 half of this design genuinely builds on — D12 places its new frontmatter keys "after `diffTruncated`" (a 927 key) and regenerates 927-era snapshot fixtures. Conversely, the body's Prerequisites list 909 and the Context Forge CLI, which are absent from frontmatter. Also, `interfaces: []` under-sells the "Provides to Other Slices" section, which names building blocks (per-item `each` + loop composition, batch report, `accept_if`/`skip_if_met`/`feedback: review`) that future slices (a Phase 6 batch, `judge-cycle`, `findings-addressed-cycle`) are expected to compose. Cosmetic, but the frontmatter is the machine-readable summary other tooling reads.

### [NOTE] Concurrent cf consumers during a batch run are unaddressed

State Management documents that the batch mutates workspace-global cf state per item (arch, plan, slice, phase) and never restores it, with manual restore in walkthrough step 9 — a deliberate, well-documented choice. What it does not address is a concurrently executed cf-consuming operation during the run: a PM who runs `sq review slice N` (or any phase step) mid-batch would resolve scope against the batch's transient arch/plan state, the same wrong-document failure mode D2 exists to prevent. Low likelihood for an unattended terminal run, but worth one sentence in State Management (e.g., "don't run cf-consuming commands while a batch is active").

### [NOTE] Unconditional report file and stdout summary extend to every existing `each` user

D9 makes every `each` step write a report file and `sq run` print a summary line, including `app.yaml`'s, with no opt-out ("one behavior with no opt-in flag"). This is a deliberate DRY decision and prompt-only mode cannot render `each` steps (issue #145), so no known stdout-parsing consumer exists today — but the integration requirement for `app.yaml` only covers load/validate, not this new runtime output. Acceptable as designed; noting it so the app.yaml runtime change is at least a conscious one.

### [PASS] Failure modes for new I/O paths and decision points are enumerated with explicit, observable outcomes

No "TBD" or implicit propagation anywhere in the design. D5 enumerates FAILED / PAUSED / pre-`flag_reason` handling under both failure policies, with a defined error-message fallback chain; D8 fails the revise dispatch explicitly ("feedback: review but no prior review in scope"); D1 defines three distinct, human-readable flag reasons (missing review / unreadable verdict / below threshold) rather than a silent skip; D2 fails `set_arch` on a parentless plan with an error naming the file; D7 raises `ValueError` when `action.success` is used as a verdict threshold; cf unavailability fails the whole `each` step rather than falling back per-item; and the Patterns section requires every new failure to log at WARNING and appear in the report. This matches the parent architecture's observability-first stance ("the first implementation should prioritize observability over optimization").

### [PASS] Faithful to the parent plan's slice 195 scope, with explicit exclusions

Every element the parent plan itemizes for slice 195 is present and nothing plan-specified is missing: plan-aware selection sources with status/`designFile`/task-file filtering, per-item isolation in `each`, a bounded revise-and-re-review loop composed from the 194 `loop:` step, the two-threshold pass/accept semantics (`pass-threshold` ends the loop, `accept-threshold` decides accept-vs-flag on exhaust), flag list + end-of-run report in the run directory + stdout summary, model/review-model as params, `design-batch.yaml` superseded (deleted with all three references enumerated), the #139 traceability fix with its concrete frontmatter/JSON deliverables, and the Phase 6 batch explicitly out of scope. The Excluded section gives a reason and a follow-up home for each omission (judge nodes → `findings-addressed` gate, prompt-only rendering → issue #145, Claude Code refusal → #144). Prerequisites 194 and 181 are confirmed complete in the plan, and the additional 909 dependency is verified complete in its own slice design (`909-slice.pipeline-phase-step-correctness.md` frontmatter).

## Disposition (20260926)

Verdict stands at **CONCERNS**. Four findings addressed in the design, one accepted as designed.

### F001 — fixed

Accurate. The 180 slice plan authorizes engine changes for 194/195, and the design didn't say so. Added a paragraph under Architecture citing that authorization and the 194 precedent. The 180 architecture doc's scope statement and Out of Scope list now name the 194/195 exception.

### F002 — fixed (evidence recorded; the global scope stays)

The arch → slice → phase sequence is the PM's stated cf operating rule, not an inference. So the phase-first order is wrong in every pipeline. Narrowing the fix to `plan:`-carrying steps would leave the existing pipelines wrong. D2 now records the source and says that pre-slice pipelines were misordered.

### F003 — fixed in part

Added 909 and 927 to `dependencies`, and 927 to Prerequisites. `interfaces` stays `[]`: no current slice consumes the new building blocks, and listing hypothetical consumers would be invented structure.

### F004 — fixed

Added a "No concurrent cf use" line to State Management.

### F005 — accepted as designed

The unconditional report is a deliberate one-behavior choice (D9), and no stdout consumer of `app.yaml` exists. No change.

### Run Digest

- Response length: 10236 chars
- Response is newline-free: no
- Tool calls made: 18
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 54189
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
