---
docType: review
layer: project
reviewType: tasks
slice: proportionate-reviews-review-and-revise-loops-that-can-cut-scope
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/943-tasks.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261011
dateUpdated: 20261011
reviewedSha: 108be30e587ec2ec353ffb142c3aacb60874a9dd
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
turns: 11
promptTokens: 354772
cachedTokens: 300544
completionTokens: 48454
reasoningTokens: 45035
durationSeconds: 188.2
squadronVersion: 0.21.4
findings:
  - id: F001
    severity: pass
    category: completeness
    summary: "Every slice success criterion traces to at least one task"
    location: "project-documents/user/tasks/943-tasks.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:25"
  - id: F002
    severity: concern
    category: scope
    summary: "Task 4 replaces a bullet that carries two criteria the design did not authorize removing"
    location: "project-documents/user/tasks/943-tasks.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:46"
  - id: F003
    severity: concern
    category: verification-gap
    summary: "Task 9 drops the review-file real-gap check from walkthrough step 4"
    location: "project-documents/user/tasks/943-tasks.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:73"
  - id: F004
    severity: note
    category: testing
    summary: "Task 3's test command omits `tests/pipeline/test_dispatch.py`, which also exercises `_resolve_prompt`'s prior-review path"
    location: "project-documents/user/tasks/943-tasks.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:41"
  - id: F005
    severity: note
    category: task-sizing
    summary: "Task 9 bundles the full rerun, coverage analysis, cleanup and multi-document recording"
    location: "project-documents/user/tasks/943-tasks.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:69"
---

# Review: tasks — slice 943

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Every slice success criterion traces to at least one task

Cross-referencing the slice design's Success Criteria against the tasks:
- FR1 (proportionality criterion in `slice.yaml`, `tasks.yaml`, `arch.yaml`) → Tasks 4, 5, 6.
- FR2 (gap qualifier in `slice.yaml` and `tasks.yaml`) → Task 4 sub-item 2, Task 5 sub-item 2.
- FR3 (revise paragraph in `_findings_block`) → Task 2 (+ Task 3 tests).
- TR "test in `tests/pipeline/actions/test_dispatch.py`" → Task 3 sub-item 1 (the exact-match test `test_single_file_prompt_is_unchanged` at `tests/pipeline/actions/test_dispatch.py:744` is the one that pins the full prompt string).
- TR "existing template-load and review-parse tests stay green" → Task 7 (`pytest tests/review -q`).
- TR "ruff/pyright clean" → Task 3 step; Context Summary line 22 states the per-code-task convention.
- TR "CHANGELOG Unreleased bullet" → Task 8.
- Integration requirement (slice 127 rerun) → Task 9.

No success criterion is orphaned, and no task lacks a trace to a criterion (Task 1 branch setup and Task 7 verification are procedural but support the code/template tasks). No load-test or CI-wiring obligation arises: the slice restates no NFR and adds no `tests/load/` task, so the tasks-template rules for those do not trigger.

### [CONCERN] Task 4 replaces a bullet that carries two criteria the design did not authorize removing

Task 4 instructs: "Replace the 'Common antipatterns' bullet with the proportionality bullet from the design." The current bullet (`src/squadron/data/templates/slice.yaml:14`) is `- Common antipatterns: over-engineering, under-specification, hidden dependencies` — three criteria in one line. The design's Technology Choices say only that "The existing over-engineering bullet folds into it," and the drafted proportionality text covers over-engineering-shaped concerns (unused configuration/abstraction, "the heaviest option where a lighter one meets the requirement") but says nothing about under-specification or hidden dependencies, which appear nowhere else in that template. Executing Task 4 literally therefore silently drops two live review criteria — the opposite of this slice's stated purpose. Task 6 handles the same concern correctly ("Fold the 'Over-engineering' antipattern line into a new PROPORTIONALITY block"), so Task 4 is inconsistent with its sibling. Task 4 should extract the over-engineering element rather than replace the whole line, or the design must explicitly state the removal.

### [CONCERN] Task 9 drops the review-file real-gap check from walkthrough step 4

Design Verification Walkthrough step 4 requires two checks: coverage against 127's slice plan entry / the approved cut `0589e8e`, **and** "Read the review files too: any CONCERN the baseline run raised about a real gap (a missing failure mode on a new I/O path, a missing NFR target) should still be raised, or the design should already handle it" (slice design line 164). Task 9 sub-item 4 keeps only the first half — it checks the plan entry and cut and lists deferrals — and never reads the review files for suppressed real-gap CONCERNs. This is the one check that discriminates the design's third named failure cause ("the gap qualifier silenced a real gap," slice design line ~170), which is precisely the risk introduced by FR2's qualifier. Without it, a rerun where the qualifier over-suppresses would pass Task 9's Success criterion ("coverage holds") while leaving real gaps unraised. Add the review-file CONCERN check to Task 9.

### [NOTE] Task 3's test command omits `tests/pipeline/test_dispatch.py`, which also exercises `_resolve_prompt`'s prior-review path

Task 3 runs `pytest tests/pipeline/actions/test_dispatch.py tests/review -q`, mirroring the design's step 1. A second file, `tests/pipeline/test_dispatch.py`, also drives the changed function (`test_prior_review_with_no_findings_uses_initial_pass_message` at line 139 and `test_no_explicit_prompt_uses_prior_review_findings` at line ~90). Those assertions are substring-based (`"initial improvement pass" in result`), so the added paragraph does not break them today — which is why this is a NOTE rather than a CONCERN. Still, the verify command excludes a file that touches the modified method; widening it to `tests/pipeline` costs nothing and guards the change.

### [NOTE] Task 9 bundles the full rerun, coverage analysis, cleanup and multi-document recording

Task 9 has seven sub-items spanning an environment build, a throwaway worktree creation, a full `sq run P4` execution, word-count collection, a two-part coverage analysis (see the CONCERN above), a conditional stop-and-report path, worktree teardown, and edits to three documents plus a commit. It maps cleanly to walkthrough steps 2–5, so it is coherent, but it is the largest task in an otherwise 2/5 effort breakdown. Acceptable as written; consider splitting teardown/recording from the run if the pipeline run and the coverage read are expected to be long.

### Run Digest

- Response length: 5709 chars
- Response is newline-free: no
- Tool calls made: 27
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 191001
- Effort: backend default
- Turns: 11
- Tokens — prompt / cached / completion / reasoning: 354772 / 300544 / 48454 / 45035
- Duration: 188.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5

## Response

- **F002:** accepted. Task 4 now removes only "over-engineering" from the antipatterns bullet; under-specification and hidden dependencies stay.
- **F003:** accepted. Task 9 adds the review-file real-gap check.
- **F004:** accepted. Task 3 runs `tests/pipeline` instead of the single file.
- **F005:** no change. Task 9 is one walkthrough with one pass condition; splitting it adds tasks without a requirement behind them.
