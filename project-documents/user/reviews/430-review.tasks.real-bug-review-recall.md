---
docType: review
layer: project
reviewType: tasks
slice: real-bug-review-recall
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/430-tasks.real-bug-review-recall.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261116
dateUpdated: 20261116
reviewedSha: 72121a87cf53f51bfe9187f82912d983e45a0caa
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
effort: xhigh
turns: 9
promptTokens: 314473
cachedTokens: 203233
cacheWriteTokens: 111232
completionTokens: 83337
durationSeconds: 355.3
costUsd: 0.184485
costBasis: provider
runId: run-20261116-p5-c59b9eb6
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "Task 30 makes the live D11 call that the task file says no task makes"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:264"
  - id: F002
    severity: concern
    category: coverage
    summary: "Live stage identity is never derived from the alias config"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:219"
  - id: F003
    severity: concern
    category: coverage
    summary: "The live path never writes the comb input file or the raw-output sidecar"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:203"
  - id: F004
    severity: concern
    category: consistency
    summary: "The fixture case file the walkthrough uses is never created in the repo"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:95"
  - id: F005
    severity: concern
    category: testing
    summary: "Task 23's leak verdicts are not asserted with a WARNING log"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:212-213"
  - id: F006
    severity: concern
    category: consistency
    summary: "Task 3 changes the `combs` key type from the design without a recorded correction"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:76"
  - id: F007
    severity: concern
    category: sizing
    summary: "Tasks 21 and 24 each bundle too many deliverables; scoring has no split plan"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:192"
  - id: F008
    severity: note
    category: sequencing
    summary: "`extra_locations` has two triggers, and Task 17's store is built before Task 16 writes it"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:174"
  - id: F009
    severity: note
    category: consistency
    summary: "The case-id input list is ambiguous"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:70"
  - id: F010
    severity: note
    category: consistency
    summary: "The `recall_fetch_timeout_s` default duplicates the sandbox's fixed bound"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:102"
  - id: F011
    severity: note
    category: consistency
    summary: "Conflicts between person labelers are not defined"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:245"
  - id: F012
    severity: note
    category: scope
    summary: "Task 30's \"any mismatch fixed\" has no bound"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:263"
  - id: F013
    severity: note
    category: sizing
    summary: "Some tasks are small enough to merge"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:68"
  - id: F014
    severity: pass
    category: coverage
    summary: "Every success criterion and D8 row has a task, except the leak warning"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:486"
  - id: F015
    severity: pass
    category: sequencing
    summary: "Sequencing has no cycles, and the existing code the tasks name is present"
    location: "src/squadron/benchmark/bench_lock.py:54"
  - id: F016
    severity: pass
    category: process
    summary: "Test-with pattern and commit markers follow the rules"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:92"
---

# Review: tasks — slice 430

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 30 makes the live D11 call that the task file says no task makes

The Context Summary (line 39) says the live D11 run is walkthrough step 7 and "no task runs it." Design D11 (line 393) says it is not an implementation task. Task 30's D11 bound item runs `sq benchmark recall run --set real-bugs-nonsquadron ... --max-cost 0.000001 --call-cost 1`. That makes one real stage call on the real store and writes its run record, which step 7 was meant to create. Task 24's test (line 221) already checks the bound on the committed `haiku-sol-luna-opus.yaml` over a fake 14-case set, so the live call adds little. Spend is pre-authorized, so this is a consistency problem, not an approval one. Either drop the live invocation and rely on Task 24's test, or state in the Context Summary and D11 that Task 30 makes one call and what step 7 then resumes from.

### [CONCERN] Live stage identity is never derived from the alias config

Task 24 expands recipes "to live stage keys," and Task 18 depends on `config_key` and `entry_key` for live entries. A live key needs model, profile, template hash, `tool_use`, `max_output_tokens` and configured effort. D10 specifies the imported side; no task says how an alias produces these on the live side. The likely sources exist: `ReviewerRef` (`src/squadron/metrology/grade_models.py:78`) and `template_content_hash` (`src/squadron/metrology/identity.py:287`). The task should name them and say where `tool_use` and `max_output_tokens` come from. Otherwise the implementer invents the mapping, and a wrong mapping silently splits or merges rows against the imported ones.

### [CONCERN] The live path never writes the comb input file or the raw-output sidecar

(a) Task 22 says `_stage` "reads upstream findings" from `--input FILE`, but no task says who writes that file. For a two-stage comb, stage two's input must be stage one's kept findings (design D2, line 188). Task 23 lists the `_stage` argv and not the input file. (b) Design D4 (line 232) says every entry's `raw_ref` is a sha256 in the `REVIEWS` sidecar. Task 13 does this for imports only (line 148). Task 23 writes live output to `recall-out/` (line 210), and no task moves it into `ContentSidecars` (`src/squadron/metrology/content_sidecars.py:45`) before the entry is stored. Assign both to Task 23.

### [CONCERN] The fixture case file the walkthrough uses is never created in the repo

Task 6 builds the fixture repo "in a temp dir" and "writes `case.yaml` beside it," so the case file lands in a temporary directory. Design walkthrough step 5 (line 570), which Task 30 runs on the real store (line 262), calls `cases add tests/benchmark/recall/fixtures/bug_repo/case.yaml`. No task creates that path. The step fails, or it records a case whose `repo:` points at a deleted temp path. Name a stable output location (git-ignored if generated), and have Task 30 run the build before step 5.

### [CONCERN] Task 23's leak verdicts are not asserted with a WARNING log

D8's leak row (design line 310) requires a WARNING for `leaked` and `scan_unavailable`. Context Summary line 51 says every D8 row is asserted on outcome and log. Task 23's outcome bullet logs WARNING, but the leak tests (line 213) check only the verdict ("→ `leaked`", "is recorded so"). Add the WARNING assertion to those tests. Also, Task 9 (line 118) covers the ERROR for a `git show` failure but not the timeout case that Task 7 tests (line 105).

### [CONCERN] Task 3 changes the `combs` key type from the design without a recorded correction

Design D4 (`project-documents/user/slices/430-slice.real-bug-review-recall.md:220`) specifies `combs: dict[(entry_key, chain_key), StageEntry]`. Task 3 uses the string `"<entry_key>|<chain_key>"`. The string is the right choice, since a tuple cannot be a JSON object key. But Task 1's edit list (line 60) does not include it, so the design keeps the tuple, and line 41 ("later tasks follow the corrections") does not cover it. Add it to Task 1's list.

### [CONCERN] Tasks 21 and 24 each bundle too many deliverables; scoring has no split plan

Task 21 covers text and JSON rendering, the `report` command, three test files, and both reproduction suites with the pool and fan-out checks. Implementation Notes step 4 (design line 609) calls the reproduction tests the first point where the PM gets a result, so they should be their own task. Task 24 (line 218) covers expansion, stored-key drops, retry-pending, auth preflight, five refusals, bound arithmetic, rendering and a committed-recipe test. Split it into expansion and drops, then refusals, preflight and bound. Tasks 18–20 all write `scoring.py` (lines 178, 183, 188), which the design lists as one module. The project keeps source files near 300 lines where practical, so name a split or accept the overrun.

### [NOTE] `extra_locations` has two triggers, and Task 17's store is built before Task 16 writes it

Task 10 (line 124) adds `extra_locations` where the case text or graded hits cite a file. Task 17 (line 174) adds them when an imported HIT fails the gate. Name one trigger. The gate test is the mechanical one, so Task 10 should transcribe the markdown and leave gate misses to Task 17. Task 17 also says the temp store is built "by Tasks 13–15," but Task 16 writes the records. Changing a case file changes its `case_id` (design line 145), which is harmless before Task 30 (Task 10, line 127); say so in Task 17.

### [NOTE] The case-id input list is ambiguous

Design D1 says "any change gives a new case id" (line 145), but the hashed fields are listed as (kind, repo name, base, head, host repo, bugs with resolved locations). Task 2 repeats the list without saying whether a bug's id, description or proof is included. Those are the fields most likely to be edited once records exist. Fix the exact field list in Task 2 now.

### [NOTE] The `recall_fetch_timeout_s` default duplicates the sandbox's fixed bound

Task 7 describes the key's default of 120 as "the per-command bound HistoryFreeSandbox uses." Design D7 (line 285) says the sandbox keeps its own fixed 120-second bound and is unchanged, so the key does not drive it. Two places hold 120 with no link. Describe the key as independent and define its default once in `config/keys.py`.

### [NOTE] Conflicts between person labelers are not defined

Task 15 (line 161) gives person labels precedence over import labels but says nothing about two person labelers. Task 28's `label --hit` does not refuse a key that is already labelled, so a later `person:<name>` label can displace the `person:results-section-12` adjudication. Design line 470's "newest write wins" allows that. Decide whether it is intended and say so in Task 28.

### [NOTE] Task 30's "any mismatch fixed" has no bound

A walkthrough mismatch could require reworking Tasks 2–27, and the item does not limit the fix. State that a fix belongs in the owning task, and that anything beyond it is recorded as `BLOCKED:` under the item.

### [NOTE] Some tasks are small enough to merge

Tasks 2, 3 and 4 are three small model modules with one test file each. Task 6's smoke test checks only the fixture builder and could fold into Task 7. Merging is optional, and the Task 5 commit already covers Tasks 2–5.

### [PASS] Every success criterion and D8 row has a task, except the leak warning

Each functional and technical criterion maps to a task: 17 cases and four sets (10), import counts and idempotence (13–16), sections 1 and 5 reproduction (21), `run` bound, caps, resume and retry (23–26), leak verdicts (23, 27), hit rule (17), `label` (28), real share (19), `report --json` schema (21), the stub-kind seam (8, 27), and the D11 recipe file (12). The one gap is the leak WARNING noted above. No NFR is restated, so no load-test or CI-gate task is needed. No task lacks a criterion; the CHANGELOG bullet in Task 29 follows the project's bug-fix convention.

### [PASS] Sequencing has no cycles, and the existing code the tasks name is present

Each dependency comes earlier: the registry (8) precedes `cases add` (9), the store (5) precedes import (16), the parser (11) precedes comb import (14), and `_stage` (22) precedes the stage runner (23). The existing symbols the tasks rely on are present: `BenchmarkLock`, `check_review_timeout`, `pair_seed`, `compare_pair`, `write_record` in `metrology/store.py`, `TemplateOutput.DECISIONS`, `run_auth_check`, `resolve_sq_path`, `transcript_source_for`, and the committed `comb.yaml` and `RESULTS.md`. `MIN_PAIRED_CASES` is 5 in `paired_stats.py`, and Task 20 correctly uses the runbook's 8 instead.

### [PASS] Test-with pattern and commit markers follow the rules

Every implementation task has a test item directly after it. The 16 `**Commit**:` markers are plain lines at tested points (after Tasks 1, 5, 6, 9, 10, 11, 12, 16, 21, 22, 23, 26, 27, 28, 29 and 30). Task 21's commit spans Tasks 17–21, which is acceptable. Every checklist item carries a `[ ]` box, and no task merges or pushes.

### Run Digest

- Response length: 11375 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 314473 / 203233 / 111232 / 83337 / not computed
- Duration: 355.3 s
- Cost: $0.18 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 16
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 16
- Finding-shaped matches — surviving validation: 16
