---
docType: review
layer: project
reviewType: tasks
slice: one-commit-per-planning-document-loops-collapse-their-own-round-commits
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: 33813f538bc0660ac339f9de924100a17a1586bb
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 181356
cachedTokens: 90655
cacheWriteTokens: 90695
completionTokens: 3482
durationSeconds: 32.1
costUsd: 0.407448
costBasis: provider
runId: run-20261101-p5-3954488f
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Message derivation (5.4) has no source for the loop's subject and scope"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:130-158"
  - id: F002
    severity: concern
    category: scope
    summary: "Task 8.1 repeats an architecture edit already committed"
    location: "project-documents/user/architecture/180-arch.pipeline-intelligence.md:65"
  - id: F003
    severity: note
    category: test-coverage
    summary: "Integration criterion for `sq review resolve` is covered only by a proxy"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:194-195"
  - id: F004
    severity: note
    category: proportionality
    summary: "Task weight is on the heavy side but defensible"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:201-241"
  - id: F005
    severity: pass
    category: coverage
    summary: "Success-criteria traceability"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:51-273"
  - id: F006
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:67-273"
---

# Review: tasks — slice 202

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Message derivation (5.4) has no source for the loop's subject and scope

Task 5.1 gives the signature `collapse_loop_commits(ledger, target, step_name, cwd, cf_client)`. Task 2.1 defines the ledger as only `base_sha`, `commits` and `unprovable`. Task 5.4 needs `subject_paths` and `compose_message`, which depend on the loop's subject and scope (the `round_commit_params` result). Nothing in tasks 2, 5 or 7.4 says how that reaches collapse. A junior implementer would have to either re-derive it inside `loop_collapse.py` or change the signature without guidance. The design's Component Structure has the same gap.
Fix: add the round params (or subject plus scope) to the `collapse_loop_commits` signature in 5.1, and have 7.4 pass them. The alternative is to store them on the ledger in 2.1.

### [CONCERN] Task 8.1 repeats an architecture edit already committed

The 180 architecture file already has the slice 202 exception bullet at line 65, plus a pointer at line 52. This matches recent commit `1910eaed docs: record slice 202 loop-collapse in the 180 architecture`. Task 8.1 tells the implementer to add that bullet again, so it risks a duplicate bullet or a pointless edit. Replace 8.1 with a check that the existing text matches what was built, or drop it. The task 8 commit message and effort estimate then shrink to the CHANGELOG and validation.

### [NOTE] Integration criterion for `sq review resolve` is covered only by a proxy

The design says `sq review resolve` against a collapsed round's review file resolves its `reviewedSha` through the backup ref. Task 6.2 checks `merge-base --is-ancestor` from the backup ref, and that is a reasonable stand-in. No task runs the resolve path itself. I don't think a dedicated test is needed, since reachability is the mechanism. Say in 6.2 that the ancestry check is the intended proof for this criterion.

### [NOTE] Task weight is on the heavy side but defensible

Task 7 (effort 4) has five subtasks, and 7.5 has nine test bullets. Task 6.2 has seven. Most trace to a named success criterion. The `caplog` once-only assertions in 6.2 and the `--decision accept` item-rerun bullet in 7.5 are close to the minimum the criteria need. Steps 5.2 and 6.1 restate the design's git commands in full. That is redundant with the design but harmless. I would not cut anything beyond the 8.1 fix.

### [PASS] Success-criteria traceability

Each functional criterion maps to a task:
- One commit with the right message: 7.5 and 5.5.
- Skip or single commit: 7.5.
- Exhaustion accept versus pause, fail and skip: 7.5.
- Pause and resume: 4.x and 7.5.
- Refusals leave history identical and log one WARNING: 5.3 and 6.2.
- `each` item rerun: 7.5.
- Staged and unstaged changes preserved: 6.2.
- Backup ref: 6.2.
- Code loops never collapse: 3.2 and 7.5.
- Findings-addressed gate unchanged: 7.5.
- CHANGELOG: 8.2.
- Module size and call-sites-only: 8.3.

I found no scope creep.

### [PASS] Sequencing and commit cadence

The order is commit outputs, then ledger model, then open, record and carry, then proof checks, then writes, then executor wiring. Each task depends only on earlier ones, with no cycles. Each implementation task is followed immediately by its tests in the same commit group. Every task ends with a `**Commit**:` marker, so checkpoints are distributed rather than batched. The live walkthrough in task 9 is explicitly evidence, not a gate, and the 7.5 tests are the gate. No load-test or NFR is restated in the slice, so no `tests/load/` or CI wiring task is required.

### Run Digest

- Response length: 4781 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 181356 / 90655 / 90695 / 3482 / not computed
- Duration: 32.1 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
