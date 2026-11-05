---
docType: review
layer: project
reviewType: tasks
slice: effort-audit-across-dispatch-paths
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261105
dateUpdated: 20261105
reviewedSha: dfbe0e172ec846c6e9d8e4093cbc9f5b03271085
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
effort: xhigh
turns: 14
promptTokens: 670528
cachedTokens: 533893
cacheWriteTokens: 136621
completionTokens: 52350
durationSeconds: 322.5
costUsd: 0.168093
costBasis: provider
runId: run-20261105-p5-03049c49
squadronVersion: 0.24.22
findings:
  - id: F001
    severity: fail
    category: decision-conflict
    summary: "Task 3 narrows D5, and its set_model test asserts the opposite"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:70"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 1's gate fails on the current working tree"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:44"
  - id: F003
    severity: concern
    category: coverage
    summary: "Compaction's failure path gets no stamp"
    location: "src/squadron/pipeline/actions/compact.py:82"
  - id: F004
    severity: concern
    category: implementation-guidance
    summary: "`context.sdk_session.effort` will fail pyright strict"
    location: "src/squadron/pipeline/actions/compact.py:72"
  - id: F005
    severity: concern
    category: decision-conflict
    summary: "Task 12 moves the identity function out of report.py, contrary to D6"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:142"
  - id: F006
    severity: concern
    category: success-criteria
    summary: "Success criterion 7 names three fields; D6 and Task 12 use five"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md:177"
  - id: F007
    severity: concern
    category: sizing
    summary: "Task 14 is rated Effort 2 but bundles five kinds of work"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:167"
  - id: F008
    severity: note
    category: coverage
    summary: "Path 9 and path 10 already have named tests"
    location: "tests/cli/test_review_profile.py:622"
  - id: F009
    severity: note
    category: metadata
    summary: "Frontmatter omits #216"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:6"
  - id: F010
    severity: note
    category: design-question
    summary: "Pre-slice and post-slice records fall into different rows"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md:145"
  - id: F011
    severity: pass
    category: coverage
    summary: "Functional criteria map to tasks; sequencing and commit markers hold"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:43"
  - id: F012
    severity: pass
    category: verification
    summary: "Named paths, symbols and prerequisites exist"
    location: "src/squadron/pipeline/usage_capture.py:45"
---

# Review: tasks — slice 420

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Task 3 narrows D5, and its set_model test asserts the opposite

Task 3 excludes the `set_model` failure and the outer `except Exception` from stamping, and says this "narrows" D5 to what the code can reach. D5 (slice design line 136) says to stamp every result "built after the model is resolved, success or failure", and names the `except Exception` branch explicitly. The design also has a second rule: Scope (line 32) says "whenever an action reaches a provider". In `dispatch.py`, `resolve_full` runs at line 660 and `session.set_model` at line 667, so the set_model failure happens after resolution. Under D5 it must carry `effort_sent`. The test at line 76 ("no `effort_sent` key") asserts the opposite.

The outer handler (`dispatch.py:467`) cannot see the effort, because resolution happens inside `_dispatch_via_session` and `_dispatch_via_agent`. Task 3's reasoning is right for that handler. But an unexpected exception after resolution then produces no stamp, which is the failed-run-reads-as-not-sent defect D5 exists to fix. Amend the design to one rule and record the outer-handler gap as a known residual if it stays. Then correct Task 3's exclusions and test. The task should not narrow the design on its own.

### [CONCERN] Task 1's gate fails on the current working tree

The session-start git status lists this task file as modified (`M`). Task 1 says to write `BLOCKED:` if `git status --short` prints anything, so the first step stops unless the planning change is committed. The breakdown never says to commit the planning documents to the target before branching. Add that as a prerequisite, or scope the check to implementation paths.

### [CONCERN] Compaction's failure path gets no stamp

The except branch at lines 82–89 returns an `ActionResult` with no metadata. The design's Components section (slice line 88) says compact.py calls `stamp_effort_sent` "on success and failure paths", and D5 covers every result built after resolution. Task 6 (line 92) stamps only the success path. Add a failure-path step and test: a failed compaction carries `effort_sent` equal to the session's effort.

### [CONCERN] `context.sdk_session.effort` will fail pyright strict

`sdk_session` is Optional on the context. The existing function suppresses the union-attr error with `# type: ignore[union-attr]` at lines 72 and 77. Task 6 says to read `context.sdk_session.effort` directly, which will raise the same error on the new line. That breaks the "pyright zero errors" criterion on the commit. Tell the implementer to read the session's effort from a local narrowed inside `_execute_sdk_rotate`, and not to copy the ignore comments.

### [CONCERN] Task 12 moves the identity function out of report.py, contrary to D6

D6 (slice line 146) says "A private `config_identity` in `replay/report.py`", and Integration (line 162) says the slice "ships no shared identity type". Task 12 creates `replay/config_identity.py` with a public `config_identity`. The size reason holds: `report.py` is 311 lines. So either amend D6 to the new module, or keep identity private and extract only `config_label`. Task 12 also combines a behavior-neutral extraction with the behavior change. Split it so the extraction is its own step and can be checked alone.

### [CONCERN] Success criterion 7 names three fields; D6 and Task 12 use five

The criterion says aliases that "sent the same model, profile and effort fall into one report row". D6 (line 145) adds `tool_use` and `max_output_tokens`, and Task 12's test (line 149) expects two rows when those differ. The task file's Context (line 34) resolves this in favor of D6, but the criterion was never updated. Anyone verifying against it would mark correct behavior as failing. Update line 177 to the five-field rule.

### [CONCERN] Task 14 is rated Effort 2 but bundles five kinds of work

It combines the CHANGELOG, a GitHub issue plus a design edit, lint, typecheck and the full suite, tests for every touched file, and four live walkthrough runs. The live runs need configured aliases and can fail for environmental reasons, which would hide the code result. Split it into 14a (CHANGELOG, issue, lint, typecheck, suite) and 14b (live walkthrough with recorded results), or raise the rating.

### [NOTE] Path 9 and path 10 already have named tests

`test_alias_effort_reaches_the_review` covers path 9 (`sq review` CLI). `tests/pipeline/test_prompt_renderer.py:749-779` covers path 10 (`_summary-run`). No task names either one; Task 13 would find them by grep. Naming them in its path table (line 162) makes the one-test-per-path criterion checkable without a search.

### [NOTE] Frontmatter omits #216

`dependencies` lists 931 and 175. The Context (line 36) also names #216 as a prerequisite. Add it so the frontmatter matches.

### [NOTE] Pre-slice and post-slice records fall into different rows

Pre-slice records have `tool_use` = None; new records have True. The same model, profile and effort will therefore split into two rows across the slice boundary. The design says old records "load unchanged" but does not say whether they should group with new ones. Settle this before 421–427 compare configs over time.

### [PASS] Functional criteria map to tasks; sequencing and commit markers hold

Every functional criterion (slice lines 171–177) maps to a task: inventory (13), compaction (6), replay judge (7), findings judge on both entry points (8), `_dispatch-run` and renderer (9), failure attribution (3, 10), row merging (12). The technical criteria map too: per-path tests (3–10, 13), capability gate (2), the compaction assertion update (6, at `tests/pipeline/actions/test_compact.py:292`), gates (14), and CHANGELOG (14). Dependencies run 2 → 3–6 → 7–8 → 9 → 10 → 11 → 12 → 13 → 14 with no cycles. Each implementation task carries its own tests. The `**Commit**:` markers sit at working points (2, 5, 6, 8, 9, 10, 12, 13, 14).

### [PASS] Named paths, symbols and prerequisites exist

`EFFORT_SENT_KEY`, `note_effort_sent`, `effort_sent_by_profile`, `read_effort_sent` and `effort_for_session` exist. `resolve_full` exists (`pipeline/resolver.py:179`), as do `model_allows_tools` and `model_max_output_tokens` (`models/aliases.py:277,294`), and `ProducerConfigRef` and `JudgeRef` (`metrology/replay_models.py:64,73`). Every existing test file the breakdown names resolves. `stamp_effort_sent` and `action_effort_sent` do not exist yet, which matches Task 2's "add" wording.

### Run Digest

- Response length: 9747 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 14
- Tokens — prompt / cached / cache write / completion / reasoning: 670528 / 533893 / 136621 / 52350 / not computed
- Duration: 322.5 s
- Cost: $0.17 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
