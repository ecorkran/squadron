---
docType: review
layer: project
reviewType: tasks
slice: sq-onboard
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/440-tasks.sq-onboard.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261026
dateUpdated: 20261026
reviewedSha: 5a78145a9488b0a4de57fa89cae2e14be85a2391
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 196561
cachedTokens: 97487
cacheWriteTokens: 99068
completionTokens: 5559
durationSeconds: 51.3
costUsd: 0.462353
costBasis: provider
runId: run-20261026-p5-9ba2586e
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: concern
    category: test-coverage
    summary: "T5's verification misses the other `list_slices` callers"
    location: "src/squadron/integrations/context_forge.py"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Implementation and test tasks are split into pairs, which inflates the count"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md"
  - id: F003
    severity: concern
    category: proportionality
    summary: "CLI tests repeat error cases already tested at lower levels"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md"
  - id: F004
    severity: concern
    category: clarity
    summary: "The fixture source file is not located"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:40"
  - id: F005
    severity: note
    category: clarity
    summary: "T3's config-key test has no named file"
    location: "tests/config"
  - id: F006
    severity: note
    category: test-coverage
    summary: "\"No writes\" test cannot observe the `cf project list` comparison"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:225"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Success criteria coverage"
    location: "project-documents/user/slices/440-slice.sq-onboard.md:299-317"
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Sequencing and checkpoints"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md"
---

# Review: tasks — slice 440

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] T5's verification misses the other `list_slices` callers

T5 adds a strict `retroactive` check that raises for a missing key. D11 states it applies to every `list_slices` caller. T5's success criterion runs only `pytest tests/integrations tests/pipeline`. A grep shows `list_slices` or `SliceEntry(` used or mocked in tests outside those directories: `tests/events/builtin/`, `tests/review/`, `tests/cli/` (including `tests/cli/conftest.py`), `tests/pr/` and `src/squadron/review/persistence.py`. Their mock cf output will not carry the new key. Because the strict check is deliberate, those mocks must be updated in T5, and a narrow run will not catch them until T12 or T26. Change T5's criterion to the full `pytest` suite, or add a step to grep for every `list_slices` and `SliceEntry(` use and update the mocks.

### [CONCERN] Implementation and test tasks are split into pairs, which inflates the count

The slice is Effort 3/5, yet the file has 26 tasks. Thirteen are test-only tasks, each of Effort 2 and each following one implementation task (T2/T3, T6/T7, T8/T9, T10/T11, T14/T15, T16/T17, T18/T19, T20/T21 and so on). T13 already combines implementation and test in one task, so the file is inconsistent about this. Merge each implementation and test pair into one task, as T13 does. That gives about 14 tasks, each with one commit, and the test-with pattern is kept. T26 is a one-off grep check and can fold into the final docs task or the last implementation task.

### [CONCERN] CLI tests repeat error cases already tested at lower levels

T19.2 re-tests the envelope, unknown `reportVersion`, unknown `outcome` and timeout cases, which T9 and T3 already cover at the parser and client level. T11.6 separately re-asserts the timeout value passed to `subprocess.run`. The slice needs only that the CLI maps `ContextForgeError` and `ContextForgeNotAvailable` to exit 1 with one stderr line. One parametrized test over a fake client that raises each error class covers that. Trim T19.2 to that table and drop or merge T11.6 into T11.1.

### [CONCERN] The fixture source file is not located

T1 copies the report shapes from the cf 271 design, which Context Summary describes as a context-forge repo file `project-documents/user/slices/271-slice.adoption-primitives-for-sq-onboard.md` at commit `93ee3511`. The file has no path from the squadron repo and no instruction for reading it. A junior AI cannot start T1 without that file. Give the absolute or relative path to the context-forge checkout, or say how to read the file at that commit. If it isn't reachable, T1 should hold the JSON shapes inline.

### [NOTE] T3's config-key test has no named file

T3 says "add a test in the config-keys tests" without naming a file. Name the existing test module for `config/keys.py`.

### [NOTE] "No writes" test cannot observe the `cf project list` comparison

The slice success criterion compares the tree, `.context-forge.toml` and `cf project list --json` before and after. T19.3 uses a fake client, so the project-list comparison cannot fail. Asserting that the fake records no `init_project` or `decline` call is the right substitute. The real comparison belongs to walkthrough step 1, which is correctly tracked as a precondition (#273).

### [PASS] Success criteria coverage

Every functional criterion maps to a task:
- **No writes:** T19.3.
- **D1 rows, including a resumed run:** T15 and T17.4.
- **D7 version, outcome, envelope and timeout cases:** T3, T4 and T9.
- **D8 `register`, `decline` and `prompt`:** T11 and T21.
- **D4 monorepo:** T19.4.
- **D11:** T5 and T7.
- **`sq probe` removed:** T12.

The technical criteria (single definitions, no cf store reads, files under ~300 lines, lint and typecheck) are covered by T26 and the per-task criteria. The live integration criterion is correctly held out as a slice precondition. I found no scope creep. T25 is required by the slice, and the contract-doc supersession is in scope.

### [PASS] Sequencing and checkpoints

Dependencies are respected and there are no cycles. Fixtures (T1) come before their consumers. The client changes (T2–T4) precede the adoption client (T8–T10). The probe move (T12) precedes `build_onboard_report` (T16). The CLI (T18, T20) precedes the agent-surface tests (T24). Commits come at the end of each implementation-plus-test group across the file, not batched at the end. No merge or push step appears, which matches the Git rules. No NFR is restated in the slice, so no load test or CI gating task is needed.

### Run Digest

- Response length: 5355 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 196561 / 97487 / 99068 / 5559 / not computed
- Duration: 51.3 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
