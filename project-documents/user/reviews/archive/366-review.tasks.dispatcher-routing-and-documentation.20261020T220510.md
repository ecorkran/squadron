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
reviewedSha: bac1b89cf6ea2da1b0f63a0d433d3ea9b66d4dad
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 193287
cachedTokens: 90089
cacheWriteTokens: 103192
completionTokens: 17883
durationSeconds: 87.2
costUsd: 0.031215
costBasis: provider
runId: run-20261020-p5-9edaa59e
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Commit checkpoints are batched or missing for most tasks"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:114"
  - id: F002
    severity: concern
    category: consistency
    summary: "Task 7 step 4 contradicts the \"both copies carry both surfaces\" rule"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:163"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Tasks 11 and 17 depend on a project-root helper that no task defines"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:287"
  - id: F004
    severity: concern
    category: contract
    summary: "Contract types `analysis_skill_installed` and `understand_plugin_installed` as `bool`, but the design emits `null`"
    location: "project-documents/user/reference/capability-probe-contract.md:47"
  - id: F005
    severity: concern
    category: testing
    summary: "Plugin-detection tests use only synthetic JSON for an undocumented file"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:274"
  - id: F006
    severity: concern
    category: process
    summary: "Task 0 omits the worktree registration check"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:75"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Task count is high for a 2/5 slice"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md"
  - id: F008
    severity: note
    category: design-deviation
    summary: "Task 13 changes the design's `resolve_root(local=True)` approach"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:242"
  - id: F009
    severity: note
    category: scope
    summary: "Task 21 puts the `sq probe` CLI reference in `docs/COMMANDS.md`"
    location: "project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md:340"
  - id: F010
    severity: note
    category: coverage
    summary: "Coverage checks that passed"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:324"
---

# Review: tasks — slice 366

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Commit checkpoints are batched or missing for most tasks

AGENTS.md requires a commit at least once per task. Tasks 0, 1, 3, 4, 7, 8, 10, 11, 13, 15, 17, and 23 have no commit step. Task 3 says "Do not commit yet," so the drift test, dispatcher edits, and `dispatcher_skills` edits all land in Task 5's commit. The same batching happens for Tasks 7–9, 10–12, and 13–16. Give each task its own commit, or name the task-group commit explicitly and justify the deviation.

### [CONCERN] Task 7 step 4 contradicts the "both copies carry both surfaces" rule

Step 4 says to "give the user the commands for the surface the skill is running on." The Context Summary (line 48) and Task 9's test assert that all three commands appear in both copies. An agent following step 4 literally would omit the `curl` command from the Claude copy and fail Task 9. Remove step 4 or reword it to "show the commands for both surfaces, marking which applies to the current surface."

### [CONCERN] Tasks 11 and 17 depend on a project-root helper that no task defines

Task 17 says `build_probe` should resolve the project root "same rule as graph detection; reuse the function from `graph.py`." Task 11 describes the root rule inline but never names a function. Task 13's skill detection also needs the project root as an input. Task 11 should define `project_root(cwd: Path) -> Path` as a named function, and Tasks 13 and 17 should reference it by that name.

### [CONCERN] Contract types `analysis_skill_installed` and `understand_plugin_installed` as `bool`, but the design emits `null`

The contract table types both fields as `bool` (lines 47 and 50). Design D7 and D8 and Task 10 return `null` on unexpected dispatcher or plugin-file shapes, and the contract's "Null means unknown" clause (line 58) supports that. Task 18 follows the table, so its test cannot allow `null` for these two fields. With a temporary HOME both are `false`, so the test passes and the `null` path is never checked against the contract. Resolve the type with CF before code (for example, change the table to `bool or null`), because it changes what CF reads. Task 18 should then assert the nullable form.

### [CONCERN] Plugin-detection tests use only synthetic JSON for an undocumented file

Task 16's cases all use hand-written JSON. AGENTS.md's parsing rules require the fixture to match the format the parser consumes in production. Design D8 says `~/.claude/plugins/installed_plugins.json` is an undocumented Claude Code internal file. Add a case that uses a real `installed_plugins.json` from this machine (redacted), and make Task 16 record which Claude Code version produced it.

### [CONCERN] Task 0 omits the worktree registration check

The session is a git worktree. AGENTS.md requires `cf worktree list --json` to show an entry whose `worktreePath` matches the checkout root. If it does not, the agent must stop and ask the PM before starting. Task 0 should include that check as its first step.

### [CONCERN] Task count is high for a 2/5 slice

The file has 25 tasks for a slice the design rates 2/5. Several are single-step tasks that can merge without losing a commit checkpoint:
- Task 0 into Task 1.
- Tasks 7 and 8 into one task that applies the same paragraph to both copies.
- Task 10 into Task 11 (report types are needed only by the graph module and the builder).
- Task 16 into Task 14 (same test file, same fixtures).
- Task 20 into Task 19 (test with implementation).
- Task 22 into Task 21.

That brings it to about 18 tasks without losing any test-with-implementation pairing.

### [NOTE] Task 13 changes the design's `resolve_root(local=True)` approach

Design D7 says to use `DELIVERIES[target].resolve_root(local=)`. Task 13 instead joins `project_root` with `local_root`. The reason is sound: `resolve_root(local=True)` uses `Path.cwd()` (`src/squadron/skills/targets.py:132`). The deviation is disclosed in the task, but D7 should be amended to match so the design and tasks do not diverge.

### [NOTE] Task 21 puts the `sq probe` CLI reference in `docs/COMMANDS.md`

Scope item 5 says "one line for `sq probe` in the CLI reference." The task file reinterprets that as a new `## probe` entry in `docs/COMMANDS.md` plus a README pointer. The reinterpretation is disclosed at the top of the task file (lines 45–47), so this is acceptable.

### [NOTE] Coverage checks that passed

- Every functional, technical, and integration criterion maps to a task or to a walkthrough step (Tasks 4–9, 12–14, 18, 20, 23, 24).
- The architecture amendment exists in `360-arch` (lines 59, 130, 403, 428).
- The 365 design already names #247 as the `/sq:overview` owner (`365-slice.overview-command.md:373`), so D4's amendment needs no task.
- `DELIVERIES[...].local_root` exists (`targets.py:117`), so Task 13's reference is accurate.
- Test-with pairings are in order, and the probe-related tests follow their implementations.
- No merge appears as a task (Phase 7 rule respected).

### Run Digest

- Response length: 6483 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 193287 / 90089 / 103192 / 17883 / not computed
- Duration: 87.2 s
- Cost: $0.03 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
