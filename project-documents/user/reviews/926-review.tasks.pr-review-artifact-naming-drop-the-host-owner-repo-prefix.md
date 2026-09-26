---
docType: review
layer: project
reviewType: tasks
slice: pr-review-artifact-naming-drop-the-host-owner-repo-prefix
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/926-tasks.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260925
dateUpdated: 20260925
reviewedSha: 2b89f38d2a90ad391ff89f443630374c4bff3474
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Success criteria trace cleanly to tasks"
    location: "project-documents/user/tasks/926-tasks.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Test-with-implementation pattern followed"
    location: "project-documents/user/tasks/926-tasks.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md:55-167"
  - id: F003
    severity: concern
    category: sequencing
    summary: "All squadron commits batched into a single end-of-slice task"
    location: "project-documents/user/tasks/926-tasks.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md:336-342"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "DEFAULT and CONFIG rules aren't exercised at the CLI/integration level"
    location: "project-documents/user/tasks/926-tasks.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md:156-167"
  - id: F005
    severity: note
    category: task-granularity
    summary: "B.1–B.3 are one unit of work split into three trackable tasks"
    location: "project-documents/user/tasks/926-tasks.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md:104-111"
  - id: F006
    severity: note
    category: test-coverage
    summary: "`--json` stem success criterion has no task-level test"
    location: "project-documents/user/tasks/926-tasks.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md:113-136"
---

# Review: tasks — slice 926

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [PASS] Success criteria trace cleanly to tasks

Every Functional/Technical/Integration Requirement in the slice design maps to a specific task: `repository_scoped` (A.1/A.2), stem rebuild (B.1/B.2), directory-resolution reordering (B.3/B.4), D6 fixture preservation (C.1/C.2), `path_key` docstring (D.1), metrology message (D.2/D.3), glob pin (E.1), docs (F.1/F.2), full verification (G.1-G.3). No task is present that doesn't trace back to a design decision — no scope creep.

### [PASS] Test-with-implementation pattern followed

Every code-changing task is immediately followed by its test task in the same Part (A.1→A.2, B.1/B.3→B.2/B.4, D.2→D.3), each ending in an explicit `pytest ... -x` run command. No batching of tests to the end.

### [CONCERN] All squadron commits batched into a single end-of-slice task

Across ~15 tasks (Parts A–G), the only squadron-repo commit is Task G.3, at the very end. CLAUDE.md states "Git add and commit from project root at least once per task," and this breakdown has zero commits for Parts A through F. `git status` would show hours of uncommitted work accumulating before the first commit — the opposite of "distributed checkpoints." Split into per-Part (or per-task) commits, e.g. after A.2, after B.4, after C.2, after D.3, after E.1, after F.1.

### [CONCERN] DEFAULT and CONFIG rules aren't exercised at the CLI/integration level

The slice's Functional Requirements list four directory scenarios (PROJECT, DEFAULT, CONFIG via `review.external_reviews_dir`, FLAG via `--reviews-dir`), but Task B.4 only wires a `sq review pr` CLI test for PROJECT and FLAG. DEFAULT and CONFIG (`ReviewsDirRule.CONFIG = "review.external_reviews_dir"` in `src/squadron/review/reviews_dir.py:41`) are covered only indirectly through A.2's `repository_scoped` boolean-mapping unit test, not through an end-to-end test proving `review_pr` actually threads `rule.repository_scoped` into `qualify` correctly for those two rules specifically. A wiring bug isolated to CONFIG (e.g. an `if rule == ReviewsDirRule.FLAG` check instead of `rule.repository_scoped`) would pass every task in this breakdown.

### [NOTE] B.1–B.3 are one unit of work split into three trackable tasks

Task B.1 explicitly permits landing with a placeholder `qualify` value and says the three tasks are "tightly coupled" and should be "done together in one commit." That's a reasonable call given the placeholder is an obviously-fake value (allowed per CLAUDE.md), but it means B.1's own checklist item can't be verified standalone (no `Run:` line, no working `PrTarget` until B.3 lands). Consider merging B.1–B.3 into one task if they're always going to be executed and committed together — the current three-way split implies independent completability that doesn't actually exist.

### [NOTE] `--json` stem success criterion has no task-level test

The design's Functional Requirements state "`--json` produces the same stems with `.json`." No task calls this out explicitly; it's presumably covered by the pre-existing `test_stem_varies_only_by_review_type` (B.2, ~line 129) continuing to pass, but that reliance is implicit rather than stated as a check in B.2's task text.

## Response (20260925)

All four findings accepted; the task file has been revised.

- **F003: accepted.** Added a commit task at the end of every Part (A.3, B.4→now the trailing task in Part B, C.3, D.4, E.2, F.3), each naming a suggested semantic commit message and confirming cwd first, per CLAUDE.md's "commit at least once per task" and "confirm cwd" rules. G.3 (final task) is no longer the sole commit point — it's now a closing verification that `git status` is clean and the per-part commit history reads coherently. F.2's `ai-project-guide` commit and F.3's squadron-side `docs/COMMANDS.md` commit are now explicitly separated so nobody commits into the wrong repo.
- **F004: accepted.** The old B.4 only exercised PROJECT and FLAG. Replaced with a new Task B.3 that runs the real `sq review pr` CLI path against all four `ReviewsDirRule` values (PROJECT, DEFAULT via a redirected `user_reviews_root()`, CONFIG via `review.external_reviews_dir`, FLAG via `--reviews-dir`) and asserts both the resulting filename and qualification per rule — closing the gap where a wiring bug isolated to CONFIG could pass every other task.
- **F005: accepted.** Merged the old B.1–B.3 into one Task B.1, with a note explaining why: the `qualify` parameter has no working caller until the directory-resolution reordering lands, so the three-way split implied an independent completability that didn't exist. It's now one task, one commit.
- **F006: accepted.** B.2 (stem tests) now explicitly calls for a `review_type="json"` parametrize case in `test_stem_varies_only_by_review_type`, rather than leaving the `--json` requirement's coverage implicit in the existing `"code"`/`"slice"`/`"arch"` cases.

### Run Digest

- Response length: 4002 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
