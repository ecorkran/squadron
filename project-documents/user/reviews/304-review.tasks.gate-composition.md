---
docType: review
layer: project
reviewType: tasks
slice: gate-composition
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/304-tasks.gate-composition.md
aiModel: moonshotai/kimi-k2.6
status: complete
dateCreated: 20260716
dateUpdated: 20260716
findings:
  - id: F001
    severity: pass
    category: task-sequencing
    summary: "Test tasks consistently follow their implementation tasks (test-with pattern)"
    location: project-documents/user/tasks/304-tasks.gate-composition.md
  - id: F002
    severity: pass
    category: scope-management
    summary: "F002 executor touch is clearly scoped as a STOP-gate with escalation boundary"
    location: project-documents/user/tasks/304-tasks.gate-composition.md
  - id: F003
    severity: concern
    category: testing
    summary: "Missing end-to-end test for `None`-verdict normalization driving checkpoint firing"
    location: project-documents/user/tasks/304-tasks.gate-composition.md
    resolution: addressed
  - id: F004
    severity: concern
    category: process
    summary: "Commit checkpoints are batched entirely at the end"
    location: project-documents/user/tasks/304-tasks.gate-composition.md
    resolution: addressed
  - id: F005
    severity: concern
    category: validation
    summary: "Gate step load-time validation omits prior-step existence check"
    location: project-documents/user/tasks/304-tasks.gate-composition.md
    resolution: addressed
---

# Review: tasks — slice 304

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.6

## Findings

### [PASS] Test tasks consistently follow their implementation tasks (test-with pattern)

Each implementation task (T1, T3, T5, T7, T9) is immediately followed by a dedicated test task (T2, T4, T6, T8, T10), satisfying the test-with pattern and keeping feedback loops tight.

### [PASS] F002 executor touch is clearly scoped as a STOP-gate with escalation boundary

T3 explicitly frames the `step_outputs` read surface as a pure additive change, forbids edits to `_find_review_verdict` and the checkpoint contract, and mandates up-front 140 sign-off with an explicit escalation to option (b) if the change cannot stay pure. This matches the slice design’s coordination intent.

### [CONCERN] Missing end-to-end test for `None`-verdict normalization driving checkpoint firing

The slice design success criteria require a single test asserting that a source leg with `verdict=None` normalizes to `UNKNOWN`, reduces to `UNKNOWN`, **fires the checkpoint**, and logs at `WARNING+`. T6 covers the action-level normalization and logging, and T10 covers checkpoint firing for fixed-verdict pairs, but the task breakdown never combines the two: no task tests a `None` input end-to-end through the checkpoint. Add a `None`-leg case to T10 (or a dedicated integration task) so the fail-closed behavior is proven at the checkpoint boundary.

### [CONCERN] Commit checkpoints are batched entirely at the end

Only T13 contains a commit checkpoint, after all implementation, tests, and docs are complete. The slice introduces at least four distinct deliverables (reduction core, executor read surface, gate action/step, authoring guide) that should each be committed as they are validated. Distributing commits after T2, T4, T6, T8, and T10 (or a subset) would improve bisectability and keep the branch reviewable. As written, a single final commit risks a large, monolithic delta.

### [CONCERN] Gate step load-time validation omits prior-step existence check

The slice design’s failure-mode table states that a misspelled/missing source step name should be caught by gate-step **load-time** validation, failing fast. T7 only tasks validating that `judge_from` and `review_from` are strings and that an optional `policy` key is known; it omits verifying that the named steps actually exist in the assembled pipeline. Without this cross-reference check, a typo in a step name will not be caught until execute time (T5’s runtime `UNKNOWN` fallback), contradicting the intended fail-fast behavior. Update T7 to include validation that both names refer to real prior steps in the pipeline.

## Resolution (20260716)

All three concerns addressed in the task file; the two PASS findings (F001 test-with, F002 STOP-gate scoping) stand.

**F003 — end-to-end `None`→checkpoint test (addressed).** Added a `None`-leg case to **T10**: a source leg with `verdict=None` normalizes to `UNKNOWN`, reduces to `UNKNOWN`, **fires the same-step checkpoint**, and asserts the WARNING+ log *on that path*. This closes the gap the reviewer identified between T6 (action-level normalization + log) and T10 (checkpoint firing for fixed pairs) — the fail-closed behavior is now proven at the checkpoint boundary, not only inside the action.

**F004 — distributed commits (addressed).** Commits are now distributed across the four deliverables instead of one final T13: **T2c** (reduction core), **T4c** (executor read surface — commit body must record the 140 sign-off, else hold), **T8c** (gate action + step + loader validation), and **T13** (example pipeline + boundary test + authoring guide, plus the full-suite gate). T13 also verifies the branch reads as four bisectable commits.

**F005 — load-time cross-step validation (addressed, with a correction to the reviewer's suggested locus).** The reviewer's fix is correct but its home is not T7's step-type `validate`: the `StepType.validate(config)` protocol sees **only its own step's config** (verified in `steps/protocol.py`), so it structurally cannot check that other steps exist. The cross-reference check belongs in the loader's `validate_pipeline` (`loader.py:147`), which iterates all steps and already validates review-template references the same way (`loader.py:210`). Added as new task **T7b**: `validate_pipeline` verifies `judge_from`/`review_from` each name a real step appearing **earlier** in `definition.steps` (a gate cannot reference a later step), emitting a clear `ValidationError` at load. T7's own `validate` is clarified to own-config presence/type checks only. **T8** now asserts both the load-time failure (nonexistent name, later-step name) and the clean case — distinct from T5's execute-time `UNKNOWN` fallback (which remains as defense-in-depth).

Verdict left `CONCERNS` as the historical record; concerns dispositioned above. Task file grew from 314 → 398 lines (within the ~450 target; no split).
