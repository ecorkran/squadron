---
docType: review
layer: project
reviewType: tasks
slice: real-bug-review-recall
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/430-tasks.real-bug-review-recall.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261116
dateUpdated: 20261116
reviewedSha: 4cce3af0f528475ae961f7033d6e034b5e1d7db2
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 21
effort: xhigh
turns: 22
promptTokens: 693666
cachedTokens: 562344
cacheWriteTokens: 131308
completionTokens: 78370
durationSeconds: 343.2
costUsd: 0.22202
costBasis: provider
runId: run-20261116-p5-c59b9eb6
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Tasks 16 and 20 depend on live stage identity that Task 22 builds later"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:171"
  - id: F002
    severity: concern
    category: consistency
    summary: "Report entry selection contradicts D4's identity rule"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:48"
  - id: F003
    severity: concern
    category: sizing
    summary: "Task 2 is too large, and its enum handling is not specified"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:71"
  - id: F004
    severity: concern
    category: sizing
    summary: "Task 23 bundles too many concerns"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:210"
  - id: F005
    severity: concern
    category: sizing
    summary: "Task 8 has no stop condition and commits data known to be incomplete"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:115"
  - id: F006
    severity: concern
    category: verification
    summary: "Set list file format is undefined, but a test parses it"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:117"
  - id: F007
    severity: concern
    category: verification
    summary: "Final validation omits two files the design says must be unchanged"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:262"
  - id: F008
    severity: concern
    category: scope-creep
    summary: "Person-labeler disagreement listing and newest-wins are not in the design"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:153"
  - id: F009
    severity: note
    category: process
    summary: "Task 1 commit message describes a file that already has history"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:60"
  - id: F010
    severity: note
    category: scope-creep
    summary: "Duplicate-reviewer refusal in Task 10 is not in the design"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:132"
  - id: F011
    severity: note
    category: verification
    summary: "D11 criterion is met only at plan level, and walkthrough paths are ambiguous"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:223"
  - id: F012
    severity: note
    category: verification
    summary: "Task 27 end-to-end test does not cover each D8 mode"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:241"
  - id: F013
    severity: note
    category: verification
    summary: "Load-test tier may apply to the sandbox and model-call paths"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:210"
  - id: F014
    severity: pass
    category: coverage
    summary: "Every D8 failure mode maps to a task with a test"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:226"
  - id: F015
    severity: pass
    category: process
    summary: "Commit markers sit at working, tested points"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:65"
  - id: F016
    severity: pass
    category: coverage
    summary: "Design success criteria are covered, subject to the findings above"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:486"
---

# Review: tasks — slice 430

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Tasks 16 and 20 depend on live stage identity that Task 22 builds later

Task 16's test "a recipe naming alias B scores a live entry stored under alias A … as one row" needs the alias's live `config_key` and `entry_key`. The Context Summary rule (line 48) matches live entries that way. Those values come from `live_stage_config` in Task 22 (line 205). That function needs the `comb` template hash, which only exists after Task 21 (line 197). Task 20's `report` command (line 190) also needs the live identity to select entries, even though its reproduction tests use imported entries only. Fix: move the identity part of Task 22 and all of Task 21 ahead of Task 16. Alternatively, inject an alias-to-identity resolver into the pure scoring modules and test it with a stub.

### [CONCERN] Report entry selection contradicts D4's identity rule

The Context Summary says a recipe stage matches a live entry when `entry_key` is equal. `entry_key` includes configured effort (design line 239). Design D4 (line 238) says report identity is (`config_key`, `effort_sent`), and that aliases with the same model and settings that send the same effort are one row. Under the Context Summary rule, two aliases with different configured efforts that send the same effort would be two rows. Task 16's test (line 171) asserts D4's behaviour and would fail under this rule. Fix: report selection uses (`config_key`, `effort_sent`). Keep `entry_key` only for `run`'s stored-entry check, and write both into the design in Task 1.

### [CONCERN] Task 2 is too large, and its enum handling is not specified

One task writes three payload modules with about 15 classes, enums and helpers, plus three test files. Split it into 2a (case models and ids), 2b (run models and ids) and 2c (label models), each with its tests. The Python rules in this repo ask for one class per model file, while the task groups them in `*_models.py`. The task should state which convention applies. Also, `RecallLeakVerdict` is described as "424's verdicts plus confined, not_scanned". It should reuse 424's `LeakVerdict` members (`NO_LEAK_DETECTED`, `SCAN_UNAVAILABLE`, as used in `src/squadron/benchmark/leak_scan.py`) instead of retyping their strings.

### [CONCERN] Task 23 bundles too many concerns

Task 23 covers the scrubbed subprocess, argv construction, the comb input file, output parsing, sidecar storage, `effort_sent`, six outcome mappings, a leak scan with ten inputs and four verdicts, and about nine test scenarios. Split it into 23a (subprocess and outcomes, with their tests) and 23b (leak verdicts and scan inputs, with their tests).

### [CONCERN] Task 8 has no stop condition and commits data known to be incomplete

Task 8 authors 17 YAML files, reads `origin` remotes and manifests from six external repos, and captures `proof_files.json` with `git show`. It gives no instruction for a missing repo, remote, manifest or commit. The design treats a missing repo as a run-time harness failure (D8), not a fallback for authoring, so the implementer could guess values. Also, the commit at line 121 happens before Task 15 (line 166) finds graded-hit files missing from `extra_locations`, so the commit ships known-incomplete data. Fix: add a `BLOCKED:` stop for unreachable repos or commits. Either hold Task 8's commit until Task 15's gate test passes, or say in the commit that locations are completed in Task 15.

### [CONCERN] Set list file format is undefined, but a test parses it

Task 8 writes `user/reference/review-recall-sets.md` with "the file list for each set", and its test checks that each list "resolves to existing files with the stated counts". The task never defines the format, so the test must parse a format nobody specified. Fix: define the format (for example, one heading per set with a fenced list of relative paths), and have the test parse that exact format.

### [CONCERN] Final validation omits two files the design says must be unchanged

The design's technical requirement (design line 527) says `HistoryFreeSandbox`, `ReviewerRef`, `build_leak_rules` and `sq review code` are unchanged. Task 30's diff covers only `metrology/grade_models.py` and `cli/commands/review.py`. It omits `src/squadron/replay/history_free_sandbox.py` (`HistoryFreeSandbox` at line 71) and `src/squadron/benchmark/leak_rules.py` (`build_leak_rules` at line 51). Add both paths to the final `git diff --stat`.

### [CONCERN] Person-labeler disagreement listing and newest-wins are not in the design

Task 13 adds "among person labelers the record with the newest `updated` wins", and Task 28 lists person disagreements in `label`. Design line 212 sets only person-over-import precedence. Newest-write-wins appears in the design only for storage (line 470). The disagreement listing is new command output that no design criterion asks for. Cut it, or record the decision in the design before building it.

### [NOTE] Task 1 commit message describes a file that already has history

The file already has commits (`4cce3af0`, `e87807dc`, `72121a87`). The pending change is a revision, so the message `docs: add slice 430 tasks` is misleading. Use `docs: revise slice 430 tasks`.

### [NOTE] Duplicate-reviewer refusal in Task 10 is not in the design

D2 does not call for refusing duplicate reviewers. The check is harmless, but it is an addition. Keep it only if it is wanted.

### [NOTE] D11 criterion is met only at plan level, and walkthrough paths are ambiguous

The criterion "`run` with it on `real-bugs-nonsquadron` prints its bound" (design line 519) is tested at plan level in Task 24 with a fake runner. Task 27 covers bound printing with fake services. No task runs the CLI against the nonsquadron set, and Task 30 skips step 7. This is consistent with D11. Separately, the design's walkthrough uses `recipes/…` paths (design lines 552–590), while Task 10 writes recipes to `user/reference/review-recall-recipes/`. Task 30 should give the full path.

### [NOTE] Task 27 end-to-end test does not cover each D8 mode

Design Implementation Approach step 5 (design line 610) asks for an end-to-end run "including a leaking call and each D8 mode". Task 27 covers only the leak and the stub kind. Each D8 mode is covered by unit tests in Tasks 23, 25 and 26, so the success criterion is met. Add the others to Task 27 only if you want the end-to-end run to exercise them.

### [NOTE] Load-test tier may apply to the sandbox and model-call paths

The Python rules require at least one `tests/load/` test for code on network or environment-layer paths. The sandbox, the scrubbed subprocess and the model-call path may qualify. The design restates no NFR, so the reviewer criteria do not force a load-test task. Decide whether these paths count and record it in the design. If they do, add a load-test task and a CI gate.

### [PASS] Every D8 failure mode maps to a task with a test

All rows of both D8 tables have a task that asserts the outcome and the log level: auth preflight (24), subprocess and output failures (23), sandbox and fetch (25), leak verdicts (23), orphan, retry and `write_record` (26), `cases add` (5, 7), import (11, 13), and lock (27). The incomplete-stage row is covered by Task 16.

### [PASS] Commit markers sit at working, tested points

There are 16 plain-line `**Commit**:` markers, none as checkboxes. Each follows a group that ends in passing tests. Groups without markers (for example 11–13, 15–19) are followed by a marker within the same run of work. Each implementation task is followed by its tests.

### [PASS] Design success criteria are covered, subject to the findings above

Case files and sets (8, 7), import counts and idempotence (11–14), section 1 and section 5 reproduction (20), recipes and pool (10, 17, 20), undecided ranges and paired intervals (17–19), run refusals, bound, caps, resume and retry (24–27), leak verdicts (23), the hit rule (15), real share (17), the `RecallKind` seam (6, 27), and `report --json` (19) each map to a task. The unmapped items are the issues above.

### Run Digest

- Response length: 10446 chars
- Response is newline-free: no
- Tool calls made: 21
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 22
- Tokens — prompt / cached / cache write / completion / reasoning: 693666 / 562344 / 131308 / 78370 / not computed
- Duration: 343.2 s
- Cost: $0.22 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 16
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 16
- Finding-shaped matches — surviving validation: 16
