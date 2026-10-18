---
docType: review
layer: project
reviewType: tasks
slice: unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/947-tasks.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261018
dateUpdated: 20261018
reviewedSha: 62f4676f69fb6d1c1842f036d3527e97d88e19b0
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 97874
cachedTokens: 8724
cacheWriteTokens: 89146
completionTokens: 5291
durationSeconds: 43.8
costUsd: 0.411044
costBasis: provider
squadronVersion: 0.23.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 18 skip rule contradicts the design's \"reporting ships regardless\" decision"
    location: "project-documents/user/tasks/947-tasks.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md:199"
  - id: F002
    severity: concern
    category: task-scoping
    summary: "Task 20 is an open-ended, three-way branch with no concrete steps or success line"
    location: "project-documents/user/tasks/947-tasks.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md:214-218"
  - id: F003
    severity: concern
    category: scope
    summary: "Task 2 and Task 3 post GitHub comments that the design doesn't ask for or authorize"
    location: "project-documents/user/tasks/947-tasks.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md:56"
  - id: F004
    severity: note
    category: documentation
    summary: "The design's walkthrough and D10 text reference stale task numbers and probe location"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md:198"
  - id: F005
    severity: note
    category: test-coverage
    summary: "No test for the config key registration"
    location: "project-documents/user/tasks/947-tasks.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md:95-114"
  - id: F006
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable; Task 17 could fold into Task 16"
    location: "project-documents/user/tasks/947-tasks.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md:193-196"
  - id: F007
    severity: pass
    category: traceability
    summary: "Success-criteria coverage"
    location: "project-documents/user/tasks/947-tasks.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md"
---

# Review: tasks — slice 947

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 18 skip rule contradicts the design's "reporting ships regardless" decision

- **Task file:** Task 18 says that if the probe records `task_type` as "not reachable", all its items are marked done and the work skips to Task 20. Task 19, the reporting tests, is skipped with it.
- **Design:** D10 says that if no backgrounding path exists, "the slice delivers only the D11 reporting". D11 calls reporting "useful whatever the probe finds". Walkthrough step 6 expects a unit-level check of the end-of-turn WARNING and `background_shells_running`.
- **Gap:** The task file drops the one part the design says always ships.
- **Underlying problem:** `SHELL_TASK_TYPE` has no source if the probe finds nothing, and the design doesn't say what to do then. A junior agent would invent a plausible string, which is a hallucination trap.
- **Fix:** Pick one outcome and state it in both documents.
  - Either reporting is conditional on probe answer (1), and the design's D10/D11 and walkthrough step 6 say so.
  - Or Task 18 defines how a shell is identified when the probe finds none, for example a unit-level fake, and Tasks 18–19 still ship.

### [CONCERN] Task 20 is an open-ended, three-way branch with no concrete steps or success line

- **The branch:** Task 20 says to "implement the mechanism exactly as D11 records it". Its other outcomes are "not needed" and "test only".
- **Why it's weak:** The implementation branch has no steps, files or success criteria, so a junior AI cannot complete it independently. A wait mechanism that sends or injects a turn is likely larger than the Effort 2 on the task.
- **Fix:**
  - Have Task 3's design amendment end with a concrete implementation step list for the wait, or have Task 20 be generated at that point.
  - Alternatively, add a Success line and an explicit "stop and ask the PM if D11 is ambiguous" instruction, and re-estimate the effort.

### [CONCERN] Task 2 and Task 3 post GitHub comments that the design doesn't ask for or authorize

- **Task 2:** It comments on #239 with the commit hash. The design asks for recording probe results on #234 (D10) but says nothing about a #239 comment.
- **Authorization:** The "pre-authorized" line in the Context Summary covers LLM spend, pipeline runs and live probes, not outward-facing issue comments. Posting to a tracker is hard to reverse.
- **Fix:** Drop the #239 comment, or make it an explicit PM-confirmed step. The #234 comment is backed by D10 and can stay.

### [NOTE] The design's walkthrough and D10 text reference stale task numbers and probe location

- **Stale references:** D10 says "Task 1 is a probe". Walkthrough step 5 says "Task 1 probe script … `tests/probes/` or the existing live-test location; Task 1 decides". In the task file the probe is Task 3, and it lives at `scripts/probes/background_shell.py`.
- **Fix:** Task 3's design-amendment item covers "walkthrough step 5 or 6" and D10/D11. Add "correct the task number and probe path" there so Task 24 doesn't follow a wrong path.

### [NOTE] No test for the config key registration

- **Gap:** Task 7 adds `pipeline.max_cost_usd` as `type_=float, default=None`. Task 8 tests `read_cost_cap`, but not that `sq config set/get` round-trips the float key.
- **Why it matters:** The walkthrough exercises this live. Cheap insurance would be one `read_cost_cap` case that reads through the real config layer instead of a stub.

### [NOTE] Proportionality is acceptable; Task 17 could fold into Task 16

- **Size:** 24 tasks in one file for a slice with five decisions plus D12 is on the heavy side but defensible. Each task cites its decision and has a bounded scope.
- **Task 17:** It is a single test with no code change and has its own commit. It could merge into Task 16 without losing anything. This is optional.
- **Commit batching:** Implementation Tasks 1, 10, 15, 18 and 20 are committed by their following test tasks. That is consistent with the test-with pattern and doesn't batch commits at the end.

### [PASS] Success-criteria coverage

- **D12/#239:** Tasks 1–2.
- **D10:** Task 3.
- **D1:** Tasks 4–5.
- **D2:** Task 6.
- **D3/D4:** Tasks 7–8.
- **Replay mapping:** Task 9.
- **D5:** Tasks 10–11.
- **D7:** Tasks 12–16.
- **D8:** Task 17.
- **D11:** Tasks 18–21.
- **Docs and CHANGELOG:** Task 22.
- **Validation and walkthrough:** Tasks 23–24.
- **Failure modes:** Each failure mode listed in the design has a named test. They are cap exceeded, unknown cost, malformed usage, invalid cap config, BLOCKED, unreadable task file, shell timeout and shell left running.
- **Scope creep:** No task lacks a design anchor, apart from the #239 comment above.
- **Load tests:** The slice states no NFR, so no load-test or CI-gating task is required.

## Response

- **F001 (CONCERN): fixed.** Shell reporting now depends on probe answer (1). With no backgrounding path there's no shell to report and no type string to identify one, so D10, D11, the success criterion, walkthrough step 6 and the risk mitigation now say neither reporting nor the wait ships. Task 18 marks Tasks 18–21 done as not reachable and forbids writing a shell type the probe didn't record.
- **F002 (CONCERN): fixed.** Task 3's D11 amendment now ends with a numbered implementation step list for the wait. Task 20 follows that list one sub-item per step, has a Success line, and is re-rated Effort 3. No PM-ask step was added; that is the invented gate this slice removes.
- **F003 (CONCERN): no change.** Posting progress on the GitHub issue is standing project practice (`.claude/rules/bug-fixes.md`: "Post progress on the GitHub issue as a comment when it helps; the issue is the record"). Requiring PM confirmation for it is an invented gate (#235).
- **F004 (NOTE): fixed.** D10 now names Task 3 and `scripts/probes/background_shell.py`. Walkthrough step 5 names the script.
- **F005 (NOTE): fixed.** Task 8 adds a `read_cost_cap` case through the real config layer.
- **F006 (NOTE): no change.** Task 17 keeps its own commit; it pins D8 separately from the action tests.

### Run Digest

- Response length: 6355 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 97874 / 8724 / 89146 / 5291 / not computed
- Duration: 43.8 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
