---
docType: review
layer: project
reviewType: tasks
slice: review-grounding
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/918-tasks.review-grounding-1.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: ca9929a17fed0645eedcd2b27e05ae2a8f01fea9
findings:
  - id: F001
    severity: concern
    category: process-checkpoint
    summary: "No per-part commit checkpoint tasks anywhere in either file"
    location: "project-documents/user/tasks/918-tasks.review-grounding-1.md:47"
  - id: F002
    severity: note
    category: test-coverage-sequencing
    summary: "T1.4/T1.7 plumbing steps have no test immediately after them"
    location: "project-documents/user/tasks/918-tasks.review-grounding-1.md:161"
  - id: F003
    severity: pass
    category: nfr-load-test
    summary: "Concurrency criterion is correctness test, not load-tier"
    location: "project-documents/user/tasks/918-tasks.review-grounding-1.md:200"
  - id: F004
    severity: pass
    category: coverage
    summary: "Every Part 1 success criterion traces to a specific task"
    location: "project-documents/user/slices/918-slice.review-grounding.md:202"
  - id: F005
    severity: pass
    category: coverage
    summary: "Part 2/3 criteria fully covered, no scope creep"
    location: "project-documents/user/tasks/918-tasks.review-grounding-2.md:19"
---

# Review: tasks — slice 918

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] No per-part commit checkpoint tasks anywhere in either file

917's task breakdown had explicit "Task N.M — Verify and commit Part N" checklist items per part, each with a literal commit message and a "before each commit: ruff/pyright" reminder. 918's two task files have no equivalent — "commit" appears only in passing prose, and the only ruff/pyright/test-suite instruction is in the final Closeout at the end of file 2. A junior AI following the checklist literally has no per-part commit checkpoint to stop at; work risks batching into one end-of-slice commit, and an interrupted run has no committed fallback point.

### [NOTE] T1.4/T1.7 plumbing steps have no test immediately after them

T1.4 (thread the jail spec through the five factories) and T1.7 (template field/loader) aren't followed by a dedicated test task — verification is deferred to the T1.11 integration test several tasks later. Reasonable for pure signature-threading with no new logic, but it's a gap versus the test-immediately-follows pattern the other pairs (T1.1→T1.2→T1.3, T1.5→T1.6) show.

### [PASS] Concurrency criterion is correctness test, not load-tier

The "two reviews with different exclusions running concurrently" criterion is covered by T1.6's isolation test rather than a `tests/load/` load test, with no CI-gating task — correctly so, since this is state-isolation correctness, not an event-loop/throughput path, and the slice restates no NFR.

### [PASS] Every Part 1 success criterion traces to a specific task

All six Part 1 criteria map onto T1.3, T1.6, T1.9, T1.11, T1.12; spot-checked code anchors (ToolFactory, resolve_in_jail/contained_in_jail, all seven templates' allowed_tools) matched the current tree exactly.

### [PASS] Part 2/3 criteria fully covered, no scope creep

Every Part 2 and Part 3 criterion maps to T2.1–T2.9 and T3.1–T3.5 respectively; deferred-specification tasks (T1.9, T2.9) correctly mirror the design's evidence-first decisions rather than pre-committing to speculative fixes, and no task pulls in out-of-scope work (#65's dependency findings stay routed to 907).
