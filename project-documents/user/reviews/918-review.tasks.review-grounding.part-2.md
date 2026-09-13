---
docType: review
layer: project
reviewType: tasks
slice: review-grounding
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/918-tasks.review-grounding-2.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: ca9929a17fed0645eedcd2b27e05ae2a8f01fea9
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task sequence carries values onto `ReviewResult` fields before those fields exist"
    location: "project-documents/user/tasks/918-tasks.review-grounding-2.md:79-96"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Digest render task depends on a computation defined in the next task"
    location: "project-documents/user/tasks/918-tasks.review-grounding-2.md:99-116"
  - id: F003
    severity: concern
    category: process-checkpoint
    summary: "No per-part commit checkpoint tasks in this file"
    location: "project-documents/user/tasks/918-tasks.review-grounding-2.md:19"
  - id: F004
    severity: note
    category: test-coverage-sequencing
    summary: "T2.4/T2.5 plumbing steps have no dedicated test immediately after them"
    location: "project-documents/user/tasks/918-tasks.review-grounding-2.md:74-97"
  - id: F005
    severity: pass
    category: coverage
    summary: "Part 2 and Part 3 success criteria fully covered"
    location: "project-documents/user/slices/918-slice.review-grounding.md:351-414"
  - id: F006
    severity: pass
    category: scope
    summary: "No scope creep"
    location: "project-documents/user/tasks/918-tasks.review-grounding-2.md:1-280"
---

# Review: tasks — slice 918

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] Task sequence carries values onto `ReviewResult` fields before those fields exist

T2.4 ("Read the facts back in `review_client`") instructs "Carry them onto `ReviewResult` (T2.5)" — but T2.5 ("Add the `ReviewResult` fields") is the *next* task, sequenced after T2.4. Executed in order, a junior AI reaches T2.4 and is told to assign `stop_reason`/`reasoning_chars`/`failed_tool_calls` onto a model that does not yet declare those fields. The design's D11 (add the fields) is logically prerequisite to D8/D9's read-back, so T2.5 should precede T2.4, or the two should be merged into one task with the field-addition sub-step first.

### [CONCERN] Digest render task depends on a computation defined in the next task

T2.6 ("Render the facts in the Run Digest") lists a fourth digest line as "the newline-free indicator (T2.7)" — but T2.7 ("Report a newline-free response") is the task that actually computes that boolean/line-count, and it comes *after* T2.6 in the file. Same defect as above: the consuming task is sequenced before the producing task. Swap the order (T2.7 before T2.6) or fold the newline-free computation into T2.6 directly.

### [CONCERN] No per-part commit checkpoint tasks in this file

Neither Part 2 nor Part 3 has an explicit "verify and commit" task with a literal commit message, unlike the immediately preceding sibling slice's task breakdown (`917-tasks.review-artifact-integrity-1.md:119,213,331` — "Task N.M — Verify and commit Part N", each with `[ ] Commit: {message}` and a pre-commit ruff/pyright reminder). Here the only ruff/pyright/test-suite/commit-adjacent instruction is the single Closeout block at the very end of the file (lines 263-280), after both parts and both files are done. A junior AI following the checklist literally has no committed fallback point mid-file; an interrupted run risks losing both parts' work uncommitted, and this also deviates from CLAUDE.md's "Git add and commit from project root at least once per task."

### [NOTE] T2.4/T2.5 plumbing steps have no dedicated test immediately after them

T2.4 (read-back in `review_client`) and T2.5 (add `ReviewResult` fields) aren't followed by their own test task — verification is deferred to T2.8, three tasks and two other implementation steps later. This mirrors the same gap already noted in Part 1 (T1.4/T1.7 vs. the T1.1→T1.2→T1.3 and T1.5→T1.6 test-immediately-after pairs). Low severity since the fields are simple plumbing, but worth a one-line assertion (e.g., in T2.4 or T2.5 itself) rather than relying entirely on the end-to-end T2.8 digest test to catch a wiring mistake.

### [PASS] Part 2 and Part 3 success criteria fully covered

Every Part 2 criterion (digest carries all three facts on success and degradation, #92 signature readable, kimi27 made==failed signature with a dedicated test, `0` vs. not-computed distinction, newline-free detection with a test, SDK path renders not-computed, reproduction re-run and DEVLOG'd) maps to a specific task (T2.1-T2.3, T2.6, T2.3/T2.8, T2.6/T2.8, T2.7/T2.8, T2.2/T2.3/T2.8, T2.8/T2.9). Every Part 3 criterion (user-file survival with regression test, bundled files refreshed, symmetric uninstall, idempotent re-run, pre-receipt install deletes nothing) maps to T3.2-T3.5. No criterion is unaddressed.

### [PASS] No scope creep

Every task traces to a decision (D7-D15) or success criterion in the slice design. Deferred-specification tasks (T2.9) correctly mirror the design's evidence-first D7 rule rather than pre-committing to a speculative fix. #65's dependency findings are correctly left out of Closeout's issue-closing list and routed to the existing 907 entry, matching the design's non-goal.
