---
docType: review
layer: project
reviewType: slice
slice: dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261014
dateUpdated: 20261014
reviewedSha: 03f77032f86611fcd6d2e79c216e81fee50379ed
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 34.9
runId: run-20261014-p4-dcdd93aa
squadronVersion: 0.21.7
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "#212 item 2 is reinterpreted, and its root cause is unconfirmed"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md#D6 — Unfinished tasks at merge pause the run"
  - id: F002
    severity: concern
    category: architecture
    summary: "Executor is coupled to a branch-specific failure kind"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md#Component Structure"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Proportionality: unused metadata and bundled unrelated work"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md#Component Structure"
  - id: F004
    severity: note
    category: coverage
    summary: "Default SDK path has no tool telemetry, so D3 does not cover it"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md#D3 — Which signals fail a step and which warn"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes for new I/O paths are enumerated"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md#Technical Decisions"
  - id: F006
    severity: pass
    category: dependencies
    summary: "Dependency directions and integration points"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md#Dependencies"
---

# Review: slice — slice 945

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] #212 item 2 is reinterpreted, and its root cause is unconfirmed

The plan entry says "a run stopped by a hard gate ends `completed`; it ends `paused`". D6 does not detect a hard-gate stop. It does two other things:
- It closes the empty-task-list path in the merge gate.
- It changes the existing #942 unchecked-items failure from `FAILED` to `PAUSED`.

D6 itself says the actual #212 path is unknown. The other candidate, close-out checking off the gated item, is explicitly not fixed here (#212 item 1). So the slice may ship without changing the reported behavior.

The `FAILED` to `PAUSED` change for unchecked items also alters slice 942 semantics, and the plan entry does not assign it. The "Open item for the PM" is not a gate. The decision should be made before implementation, not deferred to Phase 6. Either confirm the path from the #212 run state first, or state that item 2 is only partially addressed.

### [CONCERN] Executor is coupled to a branch-specific failure kind

The executor, a generic orchestration layer, is changed to inspect the `failure` output for `UNFINISHED_TASKS`, a value defined in `pipeline/branch_ops.py`. That puts action-specific knowledge in the executor. Each future "pause instead of fail" outcome would need another special case there (an OCP smell).

A lighter and more generic option is for the action result to carry a pause signal. The executor then maps that one signal to `PAUSED` without importing branch semantics. The doc should name the contract between the branch action and the executor, or justify the direct coupling.

### [CONCERN] Proportionality: unused metadata and bundled unrelated work

- The Codex agent row says "stamp `sandbox` in metadata". Nothing in D1–D6 or the success criteria consumes it, and the refusal logic reads the credential directly. Cut it, or name the requirement it serves.
- `tool_errors` capture adds a `_TOOL_ERROR_LIMIT` constant, truncation, and a path-disclosure note. It serves the "run state records why" value, so it is justified. But D3 row 2 is the only consumer, and only the first entry is used. Consider storing just the first error to cut the limit constant and the list handling.
- Items 5 and 6 share no code with items 1–4. The 900 guidelines allow grouping when each item commits separately, and the doc says so. The risk is only that the review and test surface is large for a "Medium risk, 3/5" slice. Keep the commit separation strict.

### [NOTE] Default SDK path has no tool telemetry, so D3 does not cover it

`implement` and revise dispatches on the default SDK path rely on the merge gate and the #15 post-condition. The doc states this openly. That is acceptable. Plan Reconciliation also explains why bare dispatch with no tools is not failed. This leaves the plan's own probe scenarios (bare dispatch that must write) unfixed for luna and deepseek. The reasoning is sound and consistent with the "no prose parsing" exclusion. Make sure the CHANGELOG does not overstate the guarantee.

### [PASS] Failure modes for new I/O paths are enumerated

Each new refusal (D2) and outcome rule (D3) has an explicit message and an observable signal: WARNING or ERROR logging, step metadata, and a test asserting the log record. D5 handles the cf error without a traceback. The slice adds no new network or message type, so hang and timeout handling is not needed. The 900 architecture states no NFRs for the paths touched here.

### [PASS] Dependency directions and integration points

Providers refuse locally and dispatch does not read provider credentials. `AgentConfig.requires_writes` is the only new cross-layer field. The reuse of 944/#200 loop handling and the 942 merge gate is accurately described. The slice declares no prerequisites, which matches the plan entry's "Dependencies: none".

### Run Digest

- Response length: 5286 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 34.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Response (20261014)

Design edited in place; accepted at CONCERNS.

- **F001 (#212 item 2 reinterpreted):** PM decided: unchecked items at merge end `paused`, changing 942's status on purpose. D6 now records the decision and states that #212 item 2 is only partly fixed until its run id shows which path it took.
- **F002 (executor coupled to a branch failure kind):** fixed. `ActionResult` gains `awaits_human`; the branch action sets it for `UNFINISHED_TASKS`, and the executor pauses on the flag without importing `branch_ops`.
- **F003 (proportionality):** the `sandbox` metadata stamp is cut. `tool_errors` and its limit constant become one `first_tool_error` string. Items 5 and 6 stay in the slice with separate commits.
- **F004 (default SDK path not covered):** the CHANGELOG requirement now names the covered providers and forbids claiming the default SDK path.
- D4 (SDK failed-call count) verified against claude-agent-sdk 0.2.162.
