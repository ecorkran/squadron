---
docType: review
layer: project
reviewType: tasks
slice: dispatcher-routing-and-documentation
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 4b07e4b7f0ad95e17be4f659e83846c56809b092
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 190900
cachedTokens: 92566
cacheWriteTokens: 98328
completionTokens: 16933
durationSeconds: 83.3
costUsd: 0.029792
costBasis: provider
runId: run-20261020-p5-9edaa59e
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria and design decisions are covered by tasks"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:324-355"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 6 ships an unimplemented callable in its own commit"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:209-211"
  - id: F003
    severity: concern
    category: process
    summary: "Walkthrough steps 2–5 have no skip rule"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:323-335"
  - id: F004
    severity: concern
    category: coverage
    summary: "Outside-any-repo exit 0 is only verified by hand"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:289-292"
  - id: F005
    severity: concern
    category: convention
    summary: "Task-level deviations from the design are not recorded in the design"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:228-229"
  - id: F006
    severity: concern
    category: convention
    summary: "Numbered sub-steps have no checkboxes"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:107-123"
  - id: F007
    severity: note
    category: granularity
    summary: "Test granularity could be trimmed"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:96-100"
  - id: F008
    severity: note
    category: proportionality
    summary: "Effort label is stale after folding in the probe"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:406"
  - id: F009
    severity: note
    category: security
    summary: "Unpinned `curl | bash` install is documented in three places"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:156-159"
---

# Review: tasks — slice 366

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Success criteria and design decisions are covered by tasks

Mapping checked: dispatcher routing (Task 2), usage and unrecognized-flow handling (Task 2, walkthrough step 4), missing-graph message (Task 4), installer receipt (Task 3), probe JSON shape and exit codes (Tasks 8–9), pre-366 dispatcher detection (Task 6), contract field names (Task 8), README, CHANGELOG, and COMMANDS (Task 10), and the drift test (Tasks 1–2). Scope items 8 and 10 are correctly excluded as already done. Anchors checked against the code: `local_root` exists at `src/squadron/skills/targets.py:117`, the contract has a `## Shape` block and "or null" rows, and the skill's "unrecognized" stop exists at `commands/analysis/understand.md:399`.

### [CONCERN] Task 6 ships an unimplemented callable in its own commit

Task 6 declares `understand_plugin_installed` on `SurfaceSpec` and says it is "filled in Task 7". The Task 6 commit therefore contains a placeholder callable whose behavior is unspecified, which conflicts with the no-silent-fallback rule. Merge Tasks 6 and 7 into one task, or have Task 6 add the field only when Task 7 implements it.

### [CONCERN] Walkthrough steps 2–5 have no skip rule

Steps 2–5 need an interactive Claude Code session to run slash commands. Only steps 6 (Codex) and 7 (`/plugin`) say what to record when a step cannot run. Add the same rule for steps 2–5, for example "record 'skipped: <reason>' and continue". Otherwise the agent either fabricates results or stalls. Step 1 also writes into the real `~/.claude` and `~/.agents`, which should be called out.

### [CONCERN] Outside-any-repo exit 0 is only verified by hand

The success criterion "`sq probe --json` ... exits 0 ... outside any repository" has no automated test. Task 5 covers non-repo at the graph-function level only, and Task 9's CLI cases do not include it. Add a `CliRunner` case that runs from a `tmp_path` outside any repo (`monkeypatch.chdir`) and asserts exit 0 with one JSON line on stdout.

### [CONCERN] Task-level deviations from the design are not recorded in the design

Several choices appear only in the task file:
- Task 6 uses `project root / local_root` instead of `resolve_root(local=True)` (D7). This is the right fix, since `resolve_root(local=True)` reads `Path.cwd()`, but D7 still says the opposite.
- Task 10 adds `docs/COMMANDS.md` as the "CLI reference" (D4 names the README).
- Task 2 edits the Codex frontmatter `description` and the Input-parsing sentence, which the dispatcher list in D1–D2 does not name.

Amend the design to match, so the design remains the source of truth for later reviewers and implementers.

### [CONCERN] Numbered sub-steps have no checkboxes

The project convention requires `[ ]` on every item and subitem. Numbered sub-steps in Tasks 2 (lines 107–111, 115–123), 4 (146–158), 6 (220–223, 225–230), and 7 (239–244) have no checkbox, so task-checker cannot track them. Convert each to `- [ ]`.

### [NOTE] Test granularity could be trimmed

Task 1's seven parser cases go beyond what the criteria need. The drift test's set-equality check exercises the parser end to end, so keeping the whitespace, case-folding, and real-file cases is enough. Task 3 is a single assertion and could be folded into Task 2, which already edits `tests/skills/`. Both are optional.

### [NOTE] Effort label is stale after folding in the probe

The design still reads "Relative Effort: 2/5", but the slice now adds six source modules, seven test files, and a CLI command. Update the label so planning reflects the actual size.

### [NOTE] Unpinned `curl | bash` install is documented in three places

The Codex install runs a script fetched from `main` through `bash`. The design acknowledges this and chose it on purpose, so no change is required. Flag it for the PM, because the remote script can change without review.

### Run Digest

- Response length: 5569 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 190900 / 92566 / 98328 / 16933 / not computed
- Duration: 83.3 s
- Cost: $0.03 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
