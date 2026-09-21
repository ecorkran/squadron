---
docType: review
layer: project
reviewType: tasks
slice: small-fixes-batch-2
project: squadron
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/tasks/922-tasks.small-fixes-batch-2-1.md
aiModel: deepseek/deepseek-v4-pro
status: complete
dateCreated: 20260920
dateUpdated: 20260920
reviewedSha: 9181041439f0a482271594ab47de2ac0fa8b5766
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "All 11 success criteria trace to specific tasks"
    location: "unverified"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Test-with pattern and commit checkpoints are correctly structured"
    location: "unverified"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "No scope creep — all tasks trace to design decisions or implementation notes"
    location: "unverified"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "`test_jail.py` exclusion-related tests are left to discovery rather than explicitly named"
    location: "tests/tools/test_jail.py"
  - id: F005
    severity: note
    category: sequencing
    summary: "A1 comment references A4 issue number but tasks are ordered A1→A4"
    location: "unverified"
---

# Review: tasks — slice 922

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4-pro

## Findings

### [PASS] All 11 success criteria trace to specific tasks

Cross-reference confirms complete coverage: FR1→F1-F3, FR2→F2, FR3→F4, FR4→A1-A3, FR5→A2-A3, FR6→A2-A3, FR7→B1,B3, FR8→B2,B3, FR9→C1-C4, FR10→E1-E2, FR11→D1-D4. Technical requirements covered by G1, integration requirements by A5+G2 and G3. No criteria are orphaned.

### [PASS] Test-with pattern and commit checkpoints are correctly structured

Each fix follows the pattern: implementation sub-tasks → test sub-task → verify-and-commit sub-task. Commit checkpoints (A5, B4, C4, D4, E3, F6) are distributed across the two task files, never batched at the end. Fix 2 is correctly ordered first (unblocks hook-clean commits) and Fix 1 last (regenerates `uv.lock`).

### [PASS] No scope creep — all tasks trace to design decisions or implementation notes

A4 (upstream context-forge issue) is called for by the design's Implementation Notes. F5 (dependency-set test) is consistent with the technical requirement that every fix has tests. F6 (CHANGELOG) is explicitly required by the design's Special Considerations. No task goes beyond what the design authorizes.

### [CONCERN] `test_jail.py` exclusion-related tests are left to discovery rather than explicitly named

Task D3 explicitly names three affected tests in `test_jail_exclusions.py` by line number (90–97, 112–127, 140–148) but only says "Check `tests/tools/test_jail.py` … for further WARNING-pinned exclusion assertions and update any found." Two tests in that file **will** break when exclusion log levels drop to DEBUG and should be named:

- `test_an_exclusion_refusal_emits_exactly_one_warning` (~line 206) — captures at `logging.WARNING` and asserts `jail_violation` for an exclusion emits exactly one WARNING. After D1, `jail_violation` will log exclusions at DEBUG, so this assertion on `levelno == logging.WARNING` will find zero records.
- `test_an_exclusion_refusal_is_worded_distinguishably_from_a_jail_escape` (~line 253) — captures at `logging.WARNING` and asserts both an exclusion (`contained_in_jail` with an excluded path) and a jail escape produce two WARNING records distinguished by wording. After D1 the exclusion record moves to DEBUG, so `len(messages) == 2` will fail.

The asymmetrical treatment (three tests named precisely, two left to grep) increases the risk a junior implementer will update only the three named tests and miss the two in `test_jail.py`.

### [NOTE] A1 comment references A4 issue number but tasks are ordered A1→A4

Task A1 says "Add a comment at the predicate recording its removal condition … Link the context-forge issue filed in task **A4**." Task A4 comes after A1 in sequence. A junior implementer following the checklist linearly would add the comment in A1 without the issue number, and the task file gives no instruction to return to A1 after A4 completes. Either A4 should come before A1, or A1 should note that the comment must be updated after A4.

### Run Digest

- Response length: 3620 chars
- Response is newline-free: no
- Tool calls made: 32
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 21520
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5

### Raw Response

Now I have a thorough understanding of both the slice design and tasks. Let me compile my cross-reference and findings.

## Summary

The task breakdown is solid: all 11 functional requirements, both technical requirements, and both integration requirements trace to specific tasks. Sequencing is correct (Fix 2 first for hook-unblocking, Fix 1 last for lockfile regeneration), test tasks follow implementation tasks, and commit checkpoints are distributed throughout. I identified two minor issues and no blockers.

## Findings

### [PASS] All 11 success criteria trace to specific tasks
location: unverified

Cross-reference confirms complete coverage: FR1→F1-F3, FR2→F2, FR3→F4, FR4→A1-A3, FR5→A2-A3, FR6→A2-A3, FR7→B1,B3, FR8→B2,B3, FR9→C1-C4, FR10→E1-E2, FR11→D1-D4. Technical requirements covered by G1, integration requirements by A5+G2 and G3. No criteria are orphaned.

### [PASS] Test-with pattern and commit checkpoints are correctly structured
location: unverified

Each fix follows the pattern: implementation sub-tasks → test sub-task → verify-and-commit sub-task. Commit checkpoints (A5, B4, C4, D4, E3, F6) are distributed across the two task files, never batched at the end. Fix 2 is correctly ordered first (unblocks hook-clean commits) and Fix 1 last (regenerates `uv.lock`).

### [PASS] No scope creep — all tasks trace to design decisions or implementation notes
location: unverified

A4 (upstream context-forge issue) is called for by the design's Implementation Notes. F5 (dependency-set test) is consistent with the technical requirement that every fix has tests. F6 (CHANGELOG) is explicitly required by the design's Special Considerations. No task goes beyond what the design authorizes.

### [CONCERN] `test_jail.py` exclusion-related tests are left to discovery rather than explicitly named
category: test-coverage
location: tests/tools/test_jail.py

Task D3 explicitly names three affected tests in `test_jail_exclusions.py` by line number (90–97, 112–127, 140–148) but only says "Check `tests/tools/test_jail.py` … for further WARNING-pinned exclusion assertions and update any found." Two tests in that file **will** break when exclusion log levels drop to DEBUG and should be named:

- `test_an_exclusion_refusal_emits_exactly_one_warning` (~line 206) — captures at `logging.WARNING` and asserts `jail_violation` for an exclusion emits exactly one WARNING. After D1, `jail_violation` will log exclusions at DEBUG, so this assertion on `levelno == logging.WARNING` will find zero records.
- `test_an_exclusion_refusal_is_worded_distinguishably_from_a_jail_escape` (~line 253) — captures at `logging.WARNING` and asserts both an exclusion (`contained_in_jail` with an excluded path) and a jail escape produce two WARNING records distinguished by wording. After D1 the exclusion record moves to DEBUG, so `len(messages) == 2` will fail.

The asymmetrical treatment (three tests named precisely, two left to grep) increases the risk a junior implementer will update only the three named tests and miss the two in `test_jail.py`.

### [NOTE] A1 comment references A4 issue number but tasks are ordered A1→A4
category: sequencing
location: unverified

Task A1 says "Add a comment at the predicate recording its removal condition … Link the context-forge issue filed in task **A4**." Task A4 comes after A1 in sequence. A junior implementer following the checklist linearly would add the comment in A1 without the issue number, and the task file gives no instruction to return to A1 after A4 completes. Either A4 should come before A1, or A1 should note that the comment must be updated after A4.

---

## Response (20260920)

Both findings confirmed against the code and addressed. Task file updated at
`922-tasks.small-fixes-batch-2-1.md`.

### F004 [CONCERN] — `test_jail.py` tests left to discovery — **confirmed, fixed**

Verified both named tests exist and will fail after D6:

- `test_an_exclusion_refusal_emits_exactly_one_warning`
  (`tests/tools/test_jail.py:201`) — filters `levelno == logging.WARNING` and
  asserts `len(warnings) == 1`. After D6 that filter finds zero.
- `test_an_exclusion_refusal_is_worded_distinguishably_from_a_jail_escape`
  (`tests/tools/test_jail.py:246`) — asserts `len(messages) == 2` at WARNING.
  After D6 only the escape half remains at WARNING.

The review's line estimates (~206, ~253) pointed at the `caplog.at_level`
lines inside each test; the task file now cites the `def` lines (201, 246).

D3 now names both tests as explicit sub-items rather than a grep instruction.
Two additions beyond what the finding asked for:

- The second test exists to prove the two refusals are **worded
  distinguishably** — a property D6 explicitly preserves. The task says to
  keep that proof by capturing at DEBUG and asserting wording across both
  levels, rather than deleting the exclusion half, which would silently drop
  the assertion the test was written for.
- `tests/tools/test_jail.py:194` is called out as **not** needing a change: it
  asserts the walk predicate emits *nothing* at WARNING, which stays true
  after D6. Without that note a implementer sweeping the file for
  `logging.WARNING` could "fix" a test that is already correct.

`test_jail_symlinks.py` remains a grep instruction — unlike `test_jail.py`, no
WARNING-pinned exclusion assertion was found there to name.

### F005 [NOTE] — A1 cites an issue number filed in A4 — **confirmed, fixed**

Real ordering defect. Fixed by taking the finding's first option: the issue
filing moved to **A1**, so the number exists before any task cites it. Part A
renumbered A1–A5 (filing → predicate → zero branch → test → verify), one
sequential pass with no revisit. The alternative — a note telling the
implementer to return to the comment later — leaves a step that is easy to
skip and invisible when skipped.

### F001–F003 [PASS]

No action needed.
