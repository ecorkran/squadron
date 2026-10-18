---
docType: review
layer: project
reviewType: slice
slice: unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261017
dateUpdated: 20261017
reviewedSha: 7ee3dbe5eb016a1ef7d66ca2280625e756e573b7
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 86193
cachedTokens: 47946
cacheWriteTokens: 38243
completionTokens: 2682
durationSeconds: 22.1
costUsd: 0.194234
costBasis: provider
runId: run-20261018-p4-16dfa489
squadronVersion: 0.23.2
findings:
  - id: F001
    severity: concern
    category: scope-creep
    summary: "Scope exceeds a \"lighter-weight\" maintenance slice; the cost cap is a new feature area"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#Technical Scope"
  - id: F002
    severity: concern
    category: under-specification
    summary: "Item 5 is committed in scope but its core mechanism is deferred to a probe result"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#D11"
  - id: F003
    severity: concern
    category: boundary-violation
    summary: "POST_ACTION contract change leaks to all bindings, including user-defined ones"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#D7"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Cost cap NFR/failure paths: concurrency and unknown-cost gaps weaken the enforcement claim"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#D5"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Parent architecture reference and failure-mode enumeration for the new I/O path are partly implicit"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#D11"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#Component Structure"
  - id: F007
    severity: pass
    category: scope-management
    summary: "Excluded scope and deferral are explicit"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#Excluded"
---

# Review: slice — slice 947

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Scope exceeds a "lighter-weight" maintenance slice; the cost cap is a new feature area

The architecture (900) says maintenance slices are "lighter-weight". It also allows grouping only when "each item commits separately and can be reverted without touching the others". It excludes "new feature areas", except for small conveniences over existing commands, files and config. This slice bundles five items:
- a review-prompt criterion;
- a CLAUDE.md rule;
- an executor-wide spend ledger with a new `FailureKind` and `FailureClass`;
- a new POST_ACTION contract (`awaits_human` pause);
- an SDK shell-wait mechanism that is still undefined.

The slice defends the cost cap as one config key over the existing executor. In practice it adds a new module (`run_spend.py`), a new parameter threaded through `_execute_step`, `loop`, `each` and `fan_out`, a replay classification, and documented overshoot semantics. That is closer to a feature than to a convenience. The slice does say the plan assigns the cap to this slice (plan entry 41), so this is a proportionality concern rather than a boundary violation. The "independently committable" claim (Implementation Notes) is also uneven. The `awaits_human` copy in the executor and the `slice_task_paths` extraction touch shared paths used by other items.

Recommendation: confirm that the plan's grouping still holds. If it does, state that the five parts are revertable separately and split the shell work into its own slice if the probe yields a non-trivial mechanism (see the next finding).

### [CONCERN] Item 5 is committed in scope but its core mechanism is deferred to a probe result

D11 is marked "Status: decided". It leaves the wait mechanism unwritten: whether the agent is resumed by an injected turn or by a turn squadron sends, and whether shell progress frames count as activity. Those are the core of #234. The design is still open on how the dispatch behaves when a shell is running.

The slice does manage this risk with a gating rule: the wait task cannot start until D11 is amended. It also has a documented fallback to reporting-only. Even so, the design does not specify the integration with `_collect_turns`/`DispatchTurns`, the turn-count and telemetry interaction, or the idle-timeout semantics. The "Provides/Consumes" and Success Criteria sections therefore cannot be checked against a concrete design for this item.

Recommendation: either mark D11 "decided" only for the reporting part and "pending" for the wait, or split the wait into a follow-up slice that is designed after the probe. Reporting plus the probe is a cheap, self-contained unit.

### [CONCERN] POST_ACTION contract change leaks to all bindings, including user-defined ones

D7 changes the event-outcome loop so that any failing event action with `awaits_human=True` pauses the run instead of failing it. The slice acknowledges this affects user-defined bindings. It argues that built-in behavior is unchanged, but it does not address user actions that already set `awaits_human` on a failure. The contract is also not documented as a versioned or opt-in behavior. A narrower option meets the requirement. The `blocked-tasks` action could be handled as a distinct outcome type, or the pause semantics could apply only to built-in actions. The design should show that this option was weighed, or confirm that no existing user event sets `awaits_human`. `docs/EVENTS.md` is listed for updating, but no compatibility note is called out.

### [CONCERN] Cost cap NFR/failure paths: concurrency and unknown-cost gaps weaken the enforcement claim

The cap is best-effort. It is bounded per invocation, `fan_out` can overshoot by one action per branch, and unknown-cost actions are not counted. The slice states these limits clearly, and they are observable (WARNING, error text). However, the overview and Value sections still present it as "a real per-run cap" that "stops at a dollar cap the PM set". The rationale in D1 for pre-authorizing spend in review prompts ("spend is bounded by the run's enforced cost cap") rests on that stronger claim. With no cap configured, which is the default, spend is unbounded, yet the criterion tells reviewers that spend is pre-authorized. Recommendation: align the D1 criterion wording with the best-effort, opt-in nature of the cap. For example, avoid saying spend is "bounded by the run's enforced cost cap" when no cap is set.

### [CONCERN] Parent architecture reference and failure-mode enumeration for the new I/O path are partly implicit

D11 enumerates failure modes for the shell wait (non-zero exit, timeout, stream close, extra turn). It does not cover a shell that never emits a terminal frame, or a ledger entry left stale because the terminal frame was dropped. It also does not cover what happens when the idle-timeout stop itself fails (`_stop_background` error). The slice names the existing `ProviderError` path only for the stream-closing case. Recommendation: add these two cases, each with a WARNING signal and a test, to the failure list and to the "failure modes each have an observable signal and a test" criterion.

### [PASS] Layering and dependency direction

Spend tracking sits in the executor and reads usage records already stamped by actions, so the actions do not depend on the ledger. The review criterion is assembled in one place, and `slice_task_paths()` is extracted rather than duplicated. The slice also avoids the alternatives it rejects: a second cap source, persisted spend, and accumulating inside `UsageCapture`. Those choices keep proportionality and respect the DRY and single-definition rules.

### [PASS] Excluded scope and deferral are explicit

Excluded items (the pending-decision check in #240, `--max-cost`, YAML cap field, persistence, prompt-only runs) each carry a reason and a tracking issue where one is needed. This keeps the slice within the maintenance-container charter.

### Run Digest

- Response length: 7133 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 86193 / 47946 / 38243 / 2682 / not computed
- Duration: 22.1 s
- Cost: $0.19 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
