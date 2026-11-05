---
docType: review
layer: project
reviewType: slice
slice: reviewer-recall
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/427-slice.reviewer-recall.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: ef6d51a92bef416c09d60faee087b218920b0079
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
effort: high
turns: 10
promptTokens: 420647
cachedTokens: 324195
cacheWriteTokens: 96442
completionTokens: 10962
durationSeconds: 95.0
costUsd: 0.565875
costBasis: provider
squadronVersion: 0.24.22
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "The matcher's \"a finding can never match two defects\" invariant does not hold, and the stated response is to raise"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md#D6 — The matching rule (and D4 Spacing)"
  - id: F002
    severity: concern
    category: integration
    summary: "Reviewer key depends on effort that is only known after the first review, but the bound, run id and resume need it earlier"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md#D8, #D10"
  - id: F003
    severity: concern
    category: dependencies
    summary: "Coupling to 425 is bidirectional and disagrees with 425's own document"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md#D9, #D11, Integration Requirements"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure modes for new build and run I/O paths are incomplete"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md#D4, #D10, Data Flow"
  - id: F005
    severity: concern
    category: under-specification
    summary: "Defect location is undefined for deletion operators"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md#D3, #D4, #D6, PlantedDefect"
  - id: F006
    severity: note
    category: scope
    summary: "Proportionality"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md#Technical Scope"
  - id: F007
    severity: pass
    category: architecture
    summary: "Alignment with the architecture's recall, cost and answer-protection principles"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md#D2, #D9, #D10, Special Considerations"
---

# Review: slice — slice 427

**Verdict:** FAIL
**Model:** claude-sonnet-5-5

## Findings

### [FAIL] The matcher's "a finding can never match two defects" invariant does not hold, and the stated response is to raise

D4 spacing separates defects by `2W+1` lines. D6 then says a finding matching two defects is "impossible by D4 and raises". Two cases break that:
- **Anchor match.** A `path#name` finding matches any defect whose enclosing function or class has that name. D4 only spaces defects by line distance, so up to 3 defects can sit more than 7 lines apart inside the same function. One `path#func` finding then matches all of them.
- **Multi-line spans.** `location_span` can return a range such as `file.py:10-40`. That overlaps the windows of two defects 7 or more lines apart, so spacing says nothing about it.

Both locations are ordinary model output. The matcher is the instrument the slice exists to build, and the plan lists matcher looseness as the main risk to whether the number means anything. As written, the report either crashes on realistic data or, if the raise is removed, one broad finding credits several defects and inflates recall.

Fix before proceeding:
1. Define the many-to-one rule. For example, a finding claims at most one defect, preferring the nearest line match, or anchor matches are made exclusive.
2. Say how an anchor-only finding is treated when several defects share the symbol.
3. Remove the "impossible, raises" clause, or restrict it to a case that is actually impossible.
4. Add matcher tests for a multi-line span covering two defects and an anchor shared by two defects.

### [CONCERN] Reviewer key depends on effort that is only known after the first review, but the bound, run id and resume need it earlier

- **D8:** `effort` is "read from `ReviewResult.effort` on the first review". `reviewer_key` hashes it.
- **D10:** the per-review cost figure is the largest observed cost "for the same `reviewer_key`". The bound prints before the first review, and `recall_run_id` hashes "sorted reviewer keys".
- **Consequence:** none of these three can be computed before a review has run. The run id changes if effort comes back different from what was expected, so resume breaks. A mid-run effort change also splits a run across keys, and the plan does not say how.

425 resolves the effort from the alias before dispatch. State the same here, and say what happens when `ReviewResult.effort` differs from the pre-dispatch value. For example, record the mismatch and refuse, or mark the review. Also state how `None` ("not sent", per the architecture's "absent is not zero") enters the hash.

### [CONCERN] Coupling to 425 is bidirectional and disagrees with 425's own document

The slice plan says 427 needs only 421. This slice depends on 425 in several places:
- It shares `ReviewerRef`, `review_tree_diff` and the bootstrap, and edits 425's `review_flag`.
- Walkthrough step 5 needs a graded 425 benchmark.

It covers both landing orders ("whichever lands first writes it", "if 427 lands before 425, 425 implements it this way"). That doubles the design surface, and the spec for the shared pieces lives only in this document. The 425 design disagrees:
- It has no `review_tree_diff`, no `reviewer_key` and no `latest_recall_for`. Its ReviewerRef (`ReviewerRef` in its schema) has no `reviewer_key` field.
- It says "427 changes `review_flag` alone" (lines 456 and 493). This slice says "425 removes the flag by reading `latest_recall_for`".
- 425 D7 and D14 describe the review call and bootstrap inline and do not name the shared function.

Cut the order-agnostic wording. The slice plan already lists 427 last, so make 425 a stated prerequisite and have 427 import the shared pieces. Then reconcile the following with 425's design, or record the required 425 edits explicitly:
- Who adds `reviewer_key`.
- Who owns `review_flag`.
- The `review_tree_diff` signature.

If 427 must stay independent of 425, the walkthrough needs a step that does not require 425.

### [CONCERN] Failure modes for new build and run I/O paths are incomplete

The doc enumerates rejections and absences well, and requires a test double for each. These paths still have no stated handling:
- **Mutations that hang.** `condition-negate` on a `while` and `call-drop` on a loop-advancing call can produce non-terminating code. The suite then hits `benchmark.suite_timeout_s`. D4's proof accepts only `assertion_failure` or `project_exception`, so the site is skipped. But each hang costs timeout × `verify_runs` × up to 20 attempts per commit, which is unbounded in wall time. Name the timeout outcome. Either skip it and count it, or cap total build time per commit. Add it to the rejection and skip accounting.
- **Baseline suite timeout or `SuiteRunError`.** The baseline suite across the whole candidate has no matching `RecallRejection` value. 425 has `grader_timeout` and `suite_error` for the same event.
- **Review call hang.** `review_failed` covers raise and `UNKNOWN`. No timeout is stated for the call, and no per-review cost cap exists. The "one review of overshoot" bound is also only as good as the observed maximum, and 425 D9 says this explicitly. Add that caveat to the printed bound.
- **Sandbox creation failure at run time.** `HistoryFreeSandbox(P)` can fail when `P` is missing from `--repo`, or `git commit` can fail. Neither is in `RecallAbsence`. Only `diff_apply_failed` is listed.
- **Partial samples and cap-stopped runs.** D10 says an absence drops the case from every config's comparison. It does not say what happens when 1 of K samples fails. Nor does it say whether cases left incomplete by an exit-2 cap stop are excluded, and whether the run is then marked `partial`. D7's `r(c)` assumes K samples. The architecture says a partial run reports only cases completed under every config.

### [CONCERN] Defect location is undefined for deletion operators

`call-drop` and `guard-drop` delete whole lines. `PlantedDefect.line_start` and `line_end` are "in the defected tree", where those lines no longer exist. The doc does not say what span is recorded for a deletion, and D6's window is computed from it. State the rule, for example the line where the deleted text used to start, in defected-tree numbering, with zero width. Add a matcher test on it. Without this, recall for those operators (and the per-operator breakdown) depends on an unspecified choice.

### [NOTE] Proportionality

Effort 3/5 matches the plan. The load is mostly the nine-operator adapter, import-closure selection and verification. Three items could be deferred if the slice runs long:
- The category-agreement column.
- The by-severity split of unmatched findings.
- The two-orders contingency wording (see the 425 coupling concern).

The per-operator breakdown earns its place because the mitigation strategy relies on it. None of this blocks progress.

### [PASS] Alignment with the architecture's recall, cost and answer-protection principles

- **Defect planting.** Mechanical planting with test proof resolves the architecture's open "who writes defects" question. It rejects hand-written and LLM-written defects for reasons that match the non-goals, and the matcher is deterministic with no judge call.
- **No-tools review.** The review uses the same `code` template and no-tools condition as the 425 grader, and the report states that condition.
- **Answer protection.** The commit message is fixed, and `show` and `--keep` are the only paths that expose the answers.
- **Cost and cap.** `--max-cost` is required, the bound prints before dispatch, and the run stops at its cap with records kept and exit 2.
- **Record format.** Records are coarse, optional siblings keyed on `ProjectId`, with no migration. Match results are recomputed, not stored.
- **Statistics.** The case is the unit, and there is no composite score.
- **Recall flag.** The recall-to-425 flag handoff is read-only, so it measures and does not gate.

### Run Digest

- Response length: 8731 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 10
- Tokens — prompt / cached / cache write / completion / reasoning: 420647 / 324195 / 96442 / 10962 / not computed
- Duration: 95.0 s
- Cost: $0.57 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Responses

- **F001 (fixed):** D6 now says a finding claims at most one defect: of the not-yet-found defects it reaches, a line span claims the nearest and a shared anchor claims the first by `defect_id`. The "impossible, raises" clause is gone, D4 and the overview no longer claim spacing prevents all double matches, and matcher tests for a two-defect span and a shared anchor are added.
- **F002 (fixed):** D8 resolves effort before dispatch, as 425 does (the alias's effort when the provider applies effort, else `None`), so the bound, run id and resume need no prior review. A review whose sent effort differs is `review_failed` with both values in `detail`, and `None` hashes as JSON `null`.
- **F003 (fixed):** 425 is now a stated prerequisite and D9 imports `ReviewerRef` with `reviewer_key`, `review_tree_diff` and `bootstrap_mean_interval` from 425. All either-order wording is cut, and D11 says 427 changes `review_flag` alone to return the recall line, matching 425's design.
- **F004 (fixed):** Added `baseline_failed` and `mutant_timeout` rejections; a mutation run that times out ends the commit's attempts, so a hang costs at most one suite timeout per commit. Sandbox and commit failures at run time join `case_setup_failed` (renamed from `diff_apply_failed`), the bound notes it is an estimate with no per-review cap, and D10 says any absent sample drops the case and a cap-stopped run is `partial`, reporting only complete cases.
- **F005 (fixed):** D4 defines a deletion's span as zero width at the line where the deleted text began, in defected-tree numbering, with a matcher test.
- **F006 (noted):** Cut the by-severity split of unmatched findings and the two-orders wording. The category-agreement column stays because it is one ratio and is what D6 relies on to keep category out of the match.
