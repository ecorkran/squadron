---
docType: review
layer: project
reviewType: tasks
slice: fix-pipeline
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/423-tasks.fix-pipeline.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 9bbc8b1ac91ad370b35a7566421bc74c89db7e09
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: xhigh
turns: 18
promptTokens: 629194
cachedTokens: 486092
cacheWriteTokens: 143090
completionTokens: 46177
durationSeconds: 201.8
costUsd: 0.16117
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "Task 5 omits the \"nothing staged\" test the design requires"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:93"
  - id: F002
    severity: concern
    category: coverage
    summary: "The `/sq:run fix` instructions in run.md have no check"
    location: "commands/sq/run.md"
  - id: F003
    severity: concern
    category: ci-gating
    summary: "CI gating of the new load test is implicit"
    location: ".github/workflows/ci.yml:38"
  - id: F004
    severity: concern
    category: commit-safety
    summary: "Task 1 may commit unrelated DEVLOG.md changes to the target"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:51"
  - id: F005
    severity: concern
    category: verification
    summary: "Walkthrough step 4 cannot prove gh and cf are absent"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:199"
  - id: F006
    severity: concern
    category: sequencing
    summary: "Task 14's file-mode docs wait on Task 13 unnecessarily"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:183"
  - id: F007
    severity: concern
    category: granularity
    summary: "Task 8 bundles four units into one commit"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:113"
  - id: F008
    severity: note
    category: dependency
    summary: "Task 13's precondition is unmet today"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:170"
  - id: F009
    severity: note
    category: commit-convention
    summary: "Task 7 is labeled `refactor:` but changes behavior"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:111"
  - id: F010
    severity: note
    category: design-alignment
    summary: "Design and task file disagree on several points; the design is not updated"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md:34"
  - id: F011
    severity: note
    category: verification
    summary: "\"Scrubbed environment\" criterion is covered only by a PATH restriction"
    location: ".github/workflows/ci.yml:55"
  - id: F012
    severity: pass
    category: coverage
    summary: "Coverage, dependency order and commit structure"
    location: "project-documents/user/tasks/423-tasks.fix-pipeline.md"
---

# Review: tasks — slice 423

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 5 omits the "nothing staged" test the design requires

The design's Technical Requirements list "`fix_commit_plan`: both destinations, HEAD moved, nothing staged" as a unit-test requirement. Task 5 says "nothing staged by this function" in its check order (line 87), but no test in its list asserts it. Add an assertion to the refusal tests that the index is unchanged afterward (for example, `git diff --cached --name-only` is empty).

### [CONCERN] The `/sq:run fix` instructions in run.md have no check

FR7 requires `/sq:run fix <n>` to produce the same prompt, commit message and refusals as the CLI. The Task 12 parity test covers the CLI and renderer, but the slash-command path depends on the new `### fix-context` and `### commit` text in this file (the `{tmp_path}` rule, keeping stdout, exit-1 handling). No task tests that text, and walkthrough step 6 is replaced by a render check (line 205). Add a test that asserts the section headings and the `{tmp_path}` instruction, or make the manual check explicit in Task 15's success line.

### [CONCERN] CI gating of the new load test is implicit

Task 13 adds `tests/load/test_fix_context_fetch.py`, which the Python rules require for a network path. Today it runs only because the `test` job's bare `uv run pytest` collects it: `pyproject.toml` sets `testpaths = ["tests"]` and no marker or addopts deselects `tests/load`. The breakdown neither states this nor adds a wiring step. Its two timing assertions ("well under the block time", "about one block time") also need explicit thresholds with headroom, or they will flake on shared `ubuntu-latest` runners.

### [CONCERN] Task 1 may commit unrelated DEVLOG.md changes to the target

`git status` shows `M DEVLOG.md`. Task 1 says to commit "this task file or its DEVLOG entry" without naming the paths. A junior agent would likely `git add DEVLOG.md` and commit unrelated work to the target. Name the exact paths to stage, or drop DEVLOG from this step.

### [CONCERN] Walkthrough step 4 cannot prove gh and cf are absent

The restricted PATH is `$(dirname "$SQ"):/usr/bin:/bin`. If `gh` or `cf` sits beside `sq`, that PATH keeps them, and the fallback in line 200 only covers `/usr/bin` and `/bin`. The success line also does not say to run `command -v` inside the restricted environment; run in the outer shell it proves nothing. Specify `env PATH=... sh -c 'command -v gh; command -v cf'`, and if either resolves from `dirname "$SQ"`, put `sq` in its own directory first.

### [CONCERN] Task 14's file-mode docs wait on Task 13 unnecessarily

The Context Summary says Tasks 14–15 wait for 13 (line 33). But the file-mode docs (`issue-file`, `commit-to=current`, refusals, the report, `sq _fix-prompt` and `sq _commit`) do not depend on 422. Under the rule to finish what does not depend on the blocked part, split Task 14: the file-mode portion runs before Task 13, and only the fetched-source line waits for it. The existing success criterion "the docs describe only behavior that exists" still holds.

### [CONCERN] Task 8 bundles four units into one commit

Task 8 creates the prompt file, its loader, `FixContextAction` with six ordered refusals, the executor registration and about eight tests, all under one commit. Split at the seam the task already has: (a) the prompt file and loader with the template test, committed; (b) `FixContextAction` and its tests, committed. Task 12 has a similar mix (renderer, run.md, a four-assertion parity test) and could split at run.md.

### [NOTE] Task 13's precondition is unmet today

Verified: there is no `def get_issue` or `def render_issue` under `src/`, so 422 is not yet implemented. Task 13 will stop with `BLOCKED:` on its first run, which is the correct behavior and is written into the task. Tasks 13–15 cannot complete until 422 Tasks 5–6 land.

### [NOTE] Task 7 is labeled `refactor:` but changes behavior

The condition it widens (`dispatch.py:842-844`, which requires `ActionType.CF_OP`) decides which actions can supply a dispatch prompt. That is new behavior, and the project defines `refactor` as no behavior change. Use `feat:`, or justify `refactor` in the message.

### [NOTE] Design and task file disagree on several points; the design is not updated

The task file documents its corrections. Two I verified: the dispatch fallback (`dispatch.py:842-844` requires `CF_OP`, so D2's "`DispatchAction` does not change" is wrong), and "no attribution lines" (no attribution text appears under `src/squadron/pipeline`, so D6's wording is wrong). The other corrections are the `IssueSource` enum versus the `IssueTextLoader` class, and the `fix_keys.py` leaf module. The `--start-branch` flag and `start_branch` output are new to the design: D5, D9 and the API Contracts do not list them. Ask the Project Manager whether to amend the design, since 424 and 425 read it as the contract.

### [NOTE] "Scrubbed environment" criterion is covered only by a PATH restriction

The integration criterion says 424 can run the pipeline "under the scrubbed environment". Task 15 step 4 restricts PATH but not HOME or the rest of the environment. CI's `hermetic` job runs `scripts/test-hostile-env` (line 55). The breakdown does not say whether that job covers the new fix tests. State that it does, or add the file-mode pipeline test to what it runs.

### [PASS] Coverage, dependency order and commit structure

Each design criterion maps to a task or walkthrough step: refusals (8, 10, 15), report defects and `blocked` (4, 5, 6, 10), HEAD moved (5, 10), cost cap (10, 15), parity (12), CLI validate and dry run (9, 15). Dependencies run forward with no cycles, and Task 13 comes after everything it does not block. Commit markers (3, 4, 6, 7, 8, 10–15) sit at tested points, and the untagged Tasks 2, 5 and 9 ride with the next marker. Tests come with their implementation in every task. I verified these references: `_DETACHED_HEAD` at `git_ops.py:25,95,119`; `commit.py` is 286 lines and `_failure` is at `commit.py:165`; `select_remote` takes the bare-number target Task 13 passes; `path_error`, `extract_json_object`, `results_for_step`, `data_dir`, `build_github_host` and `HOST_COMMAND_TIMEOUT_SECONDS` exist; `commands/sq/run.md` is the path Task 12 edits.

### Run Digest

- Response length: 8758 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 629194 / 486092 / 143090 / 46177 / not computed
- Duration: 201.8 s
- Cost: $0.16 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
