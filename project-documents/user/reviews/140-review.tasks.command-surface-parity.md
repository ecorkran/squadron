---
docType: review
layer: project
reviewType: tasks
slice: command-surface-parity
project: squadron
verdict: PASS
sourceDocument: project-documents/user/tasks/140-tasks.command-surface-parity.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260328
dateUpdated: 20260328
---

# Review: tasks — slice 140

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] All success criteria have corresponding tasks

Each functional requirement from the slice design maps to at least one task:
- Criteria 1-4 (all review subcommands): covered by T1 (creation) and T10 (smoke test)
- Criterion 5 (number shorthand): T1 content spec + T10 test case
- Criterion 6 (usage on missing/unrecognized subcommand): T1 input parsing spec + T2 flag check + T10 bogus subcommand test
- Criterion 7 (`/sq:auth status`): T3 + T10
- Criterion 8 (old hyphenated commands removed): T4 + T10
- Criterion 9 (`/sq:run slice` or deprecation): T6 + T10
- Criterion 10 (no stale files in target): T7 + T8

### [PASS] No scope creep detected

All tasks trace directly to in-scope items from the slice design. Out-of-scope items (CLI changes, slice 151 implementation, review template/pipeline) are not addressed.

### [PASS] Commit checkpoints are distributed throughout

Three commits are correctly placed:
- **T5**: Slash command consolidation (after T1-T4)
- **T9**: Installer stale-file cleanup (after T7-T8)
- **T11**: Slice closure and documentation

### [PASS] Test-with pattern is respected

Tests immediately follow their implementation:
- T2 (verification) follows T1 (review.md creation)
- T8 (stale removal test) follows T7 (install.py update)
- T10 (smoke test) follows the consolidation commit

### [CONCERN] T10 lacks explicit test for bare `/sq:review` invocation

**Description:** The success criterion states "`/sq:review` with no subcommand shows usage rather than silently failing." T10 tests `/sq:review bogus` (unrecognized subcommand) but does not explicitly test `/sq:review` with no arguments at all. While T1 specifies input parsing behavior for this case, T10's explicit success checklist does not include this test case.

**Recommendation:** Add to T10's success criteria:
> - In Claude Code: invoke `/sq:review` alone — confirm usage message shown, no silent failure

### [CONCERN] T10 does not verify the new `/sq:review arch` subcommand in smoke test

**Description:** T10 includes test cases for `/sq:review code`, `/sq:review tasks`, and `/sq:auth status`, but does not explicitly test `/sq:review arch` (the new subcommand introduced by this slice). While T1's arch section and T2's flag verification exist, the functional smoke test in T10 only exercises `arch` via the "number shorthand" test case `/sq:review code 191` — it does not directly invoke `/sq:review arch`.

**Recommendation:** Add to T10's success criteria:
> - In Claude Code: invoke `/sq:review arch 140` — confirm it runs `sq review arch 140 -v` and produces output (this is listed but appears to be the only arch test)

### [PASS] Tasks are appropriately sized

- **T1** is comprehensive (reading three files, creating four sections, new arch content) but this matches the scope of consolidating four commands into one file
- **T10** covers five distinct test scenarios with multiple sub-cases, which is appropriate for a final integration smoke test
- No tasks are overly granular or should be merged

### [PASS] No circular dependencies

T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10 → T11 is a clean linear sequence. Each task depends only on prior work completed.

### [PASS] T2 scope is appropriately narrow

T2 is titled "Verify `review.md` against CLI help" and focuses specifically on flag matching. While this is a narrow verification, T10 handles broader functional behavior. The division of labor is intentional and effective.
