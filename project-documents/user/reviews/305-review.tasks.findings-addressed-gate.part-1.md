---
docType: review
layer: project
reviewType: tasks
slice: findings-addressed-gate
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/tasks/305-tasks.findings-addressed-gate-1.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260802
dateUpdated: 20260802
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "T4 depends on T6's per-policy field mapping, but T6 is scheduled after T4 in task order"
    location: project-documents/user/tasks/305-tasks.findings-addressed-gate-1.md:198-201
  - id: F002
    severity: concern
    category: process
    summary: "No commit checkpoints anywhere in file 1; the only commit instruction in the whole 30-task slice is the final close-out task"
    location: project-documents/user/tasks/305-tasks.findings-addressed-gate-1.md
  - id: F003
    severity: pass
    category: coverage
    summary: "Success criteria coverage is complete once both task files are combined"
    location: project-documents/user/tasks/305-tasks.findings-addressed-gate-2.md
  - id: F004
    severity: pass
    category: scope
    summary: "No scope creep; Part A's out-of-slice-looking work is justified as a hard prerequisite"
    location: project-documents/user/tasks/305-tasks.findings-addressed-gate-1.md:42-92
  - id: F005
    severity: pass
    category: nfr-coverage
    summary: "No NFR/load-test gap applicable"
    location: unverified
---

# Review: tasks — slice 305

**Verdict:** FAIL
**Model:** claude-sonnet-5

## Findings

### [FAIL] T4 depends on T6's per-policy field mapping, but T6 is scheduled after T4 in task order

T4 (Part B, "Unconsumed-verdict rule in `_validate_verdict_count`") instructs: "Collect the consumed names by reading each inner gate step's config ... for whichever reference fields that gate's policy declares — reuse the per-policy field list defined in Task T6, do not duplicate the literal field names here" (lines 198-201). But T6 ("Gate policy enum and per-policy reference fields", lines 222-234), which defines that exact mapping and introduces the `findings-addressed` policy value into `VALID_GATE_POLICIES`, lives in **Part C**, after Part B. As sequenced, a junior implementer doing T4 has no mapping to reuse — it doesn't exist yet. Worse, T5's test task (line ~207-208) constructs a loop body with `gate(review_from=fresh-review, policy=findings-addressed)`, but `findings-addressed` is not yet a valid policy value until T6 lands, and step expansion for it would `KeyError` until T8 lands (T8 itself states the current `expand()` "would `KeyError` on a valid `findings-addressed` step," line ~260). So T4 and T5 are not completable in the order the file presents them. Fix: either move T6 (and likely the minimal pieces of T7/T8 needed for a valid `findings-addressed` step to validate/expand) ahead of T4/T5, or restructure Part B to come after Part C.

### [CONCERN] No commit checkpoints anywhere in file 1; the only commit instruction in the whole 30-task slice is the final close-out task

Parts A, B, and C (T1–T11) each end with a dedicated, immediately-following test task (T3, T5, T11) — good test-with structure — but none instructs a git commit. Checking file 2 confirms the *only* commit instruction in the entire breakdown is T30 ("`ruff format` immediately before the commit; commit from the project root"), at the very end of a 30-task, 3/5-effort slice. This contradicts the project guideline "Git add and commit from project root at least once per task" and the review criterion that commit checkpoints be distributed, not batched at the end. Parts A, B, and C are each independently testable (their own success criteria say so) and are natural commit boundaries — e.g., after T3/T5/T11 each pass their full test suite. Recommend adding an explicit commit step after each Part's test task completes.

### [PASS] Success criteria coverage is complete once both task files are combined

All 14 checkboxes in the slice design's Success Criteria section trace to a task: most-severe regression → T7/T28; target loop shape validates/runs → T10/T26/T28; two-reviews-no-gate rejection → T5/T11 (file 1); byte-identical FAIL → T14/T16; round-1 `no_prior_round` → T13/T16; exact-match `unaddressed` → T15/T16; contradiction downgrade → T20/T22; judge-failure fail-closed path → T19/T21/T28; no-commit-source rejected at validation → T10/T11 (file 1); `moved` without successor → T20/T22; `unverified` excluded from Screen 2 → T15/T16; gate-evidence filename/discovery exclusion → T23/T25; metadata parity → T24; example pipeline → T26/T28. No orphaned success criteria found. The file-1/file-2 split is explicit and internally cross-referenced, so reviewing file 1 in isolation correctly shows partial coverage (criteria 3 and 9) rather than a gap.

### [PASS] No scope creep; Part A's out-of-slice-looking work is justified as a hard prerequisite

T1/T2 touch `executor.py`/`models.py`, files the slice design's "Files touched" table doesn't list. The task file explicitly discloses this (lines 90-92) and grounds each defect in a concrete code citation (`executor.py:959`, `:1382`, `:1400-1402`, `:1417-1440`), explaining why the target shape is unreachable without the fix and why it's additive (no existing behavior changes). This is legitimate prerequisite work, not scope creep.

### [PASS] No NFR/load-test gap applicable

The slice design's Risk Assessment and Success Criteria contain no performance/throughput/latency NFR — the risks are judge-quality, matching-brittleness, and resume-correctness, all functional/correctness concerns covered by unit and integration tests (T16, T22, T28). No `tests/load/` task or CI-gating task is warranted here, and none is missing.

---

## Resolution (20260802)

Both actionable findings resolved in `305-tasks.findings-addressed-gate-1.md`.

**F001 (FAIL) — resolved by reordering the parts, not by patching the reference.**
The finding is correct in full, including its second half: `_walk_valid_inner_action_types`
(`steps/loop.py:196-206`) calls `expand()` on every inner step that passes its own
`validate()`, so a `findings-addressed` gate step in a loop body would `KeyError`
on `cfg["judge_from"]` before the unconsumed-verdict rule ever ran. The policy
vocabulary must exist first. Part B and Part C are now swapped:

- **Part B — Policy Config Surface** (T4 enum + per-policy field mapping, T5
  dispatch, T6 step validate/expand, T7 loader, T8 tests)
- **Part C — Loop Validation** (T9 unconsumed-verdict rule, T10 loop-scoped
  `findings-addressed` validation, T11 tests)

Both parts now carry a preamble stating the dependency direction so the order is
not "corrected" back later. Task numbers were reassigned so numbering matches
execution order rather than leaving the sequence out of order.

One forward dependency the finding did not name was also removed: T5 (policy
dispatch) previously said the `findings-addressed` entry "delegates to the new
module from Part D" — a reference to a module that does not exist yet. T5 now
registers only `most-severe`; the policy module self-registers its own entry when
Part D creates it, following the `register_action(...)` precedent every action
module already uses.

**F002 (CONCERN) — resolved.** Commit instructions added at each part boundary,
as the final sub-item of that part's test task: Part A after T3, Part B after T8,
Part C after T11. Each names a semantic commit message. Part A's is called out as
independently valuable — it repairs a gate inside a loop for every policy,
including 304's `most-severe`, so it is worth its own revert point regardless of
what follows.

The three PASS findings are recorded as-is; no action taken.
