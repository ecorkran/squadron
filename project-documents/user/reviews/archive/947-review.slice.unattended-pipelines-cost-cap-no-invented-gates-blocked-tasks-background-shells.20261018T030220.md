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
reviewedSha: 8d813b4ed64ea16a22f8be36581f08c7e1a52aae
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
turns: 9
promptTokens: 435659
cachedTokens: 350148
cacheWriteTokens: 85497
completionTokens: 3465
durationSeconds: 29.1
costUsd: 0.451541
costBasis: provider
runId: run-20261018-p4-16dfa489
squadronVersion: 0.23.2
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Scope fits the maintenance container and the slice plan entry"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#Technical Scope"
  - id: F002
    severity: pass
    category: scope
    summary: "Deferrals are explicit, justified and tracked"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#Technical Scope"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Cost-cap machinery is heavier than the requirement"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#D3–D6"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Shell-wait design is speculative ahead of the probe"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#D10–D11"
  - id: F005
    severity: concern
    category: failure-modes
    summary: "Parallel-branch cap overshoot and crash-loss are accepted without bounds"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#D5"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Unreadable-state and malformed-marker paths lack explicit failure signals for resume with a changed cap source"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#Special Considerations"
  - id: F007
    severity: note
    category: integration
    summary: "BLOCKED check reads task files, but it is a good reuse of the merge guard"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#D7"
  - id: F008
    severity: note
    category: nfr
    summary: "No NFR targets in the parent architecture apply"
    location: "project-documents/user/architecture/900-arch.maintenance-and-refactoring.md"
---

# Review: slice — slice 947

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Scope fits the maintenance container and the slice plan entry

The 900 architecture admits operational, error-handling and configuration work that spans subsystems, and this slice is that. The slice plan entry for 947 asks for five things:
- the review-template criterion;
- the CLAUDE.md rule;
- a `max_cost_usd` cap summed per run and checked in the executor;
- a BLOCKED pause where resume re-runs implement;
- a shell wait bounded by the existing idle timeout, plus end-of-turn reporting.

The design delivers all five. It also checks the #199 deny hook before proceeding, as the plan entry directs (D10, D11).

### [PASS] Deferrals are explicit, justified and tracked

The task-breakdown guide change is already shipped upstream (ai-project-guide#44). The upstream `rules/general.md` change is filed as ai-project-guide#45. The pre-implement decision check is blocked on context-forge#121 and tracked as #240. Each of these departs from the plan entry's wording, and the slice records the reason and the tracking issue.

### [CONCERN] Cost-cap machinery is heavier than the requirement

The plan asks for a cap from pipeline YAML or project config, checked against the run's accumulated cost. The design adds several pieces beyond that:
- a new module with three types (`RunSpend`, `CostCap`, `spend_from_action_dict`);
- a `CostCap.source` field used only to word the error message;
- a `get_optional_positive_float_config` helper;
- a "lowest of two sources wins" rule;
- a `spent_unknown_actions` counter that persists across resume and is not used for any decision.

Cuts to consider:
- Drop `source` tracking and name both candidate sources in the error.
- Drop the persisted `spent_unknown_actions`. The per-alias WARNING already makes unknown cost observable.
- Fold `spend_from_action_dict` into `RunSpend.add`.
- Use a plain function instead of a separate resolve-and-source type.

The persisted `spent_usd` and the pre-run check are justified, so keep them.

### [CONCERN] Shell-wait design is speculative ahead of the probe

D11 specifies the full shell mechanism before the D10 probe has run:
- a second ledger map;
- `shells_active` and `any_active`;
- a fixed `SHELL_CONTINUATION_PROMPT`;
- the send-once rule;
- timer-reset semantics;
- two new metadata counters.

D10 admits that a background shell may be unreachable behind the #199 hook, and that the CLI may or may not inject a continuation turn. The design handles this by branching, but the branches are written out in full anyway. It would be lighter to commit only to the probe plus end-of-turn reporting now. The wait and continuation design could then be written once the probe records which path exists. That leaves the design smaller, and it matches the "act only on recorded evidence" intent in the risk section.

### [CONCERN] Parallel-branch cap overshoot and crash-loss are accepted without bounds

The cap is enforced after each action. With parallel `each`/`fan_out` branches, overshoot is "one action per branch", which the doc does not quantify against the branch count or any bound on concurrent dispatches. The State Management section also says a crash mid-step loses that step's spend. A resume then sees an undercounted total, which weakens the guarantee that spend is "bounded mechanically". The doc says both outcomes are acceptable but sets no limit. State the maximum overshoot (branch concurrency × per-action cost) in the success criteria, or document the cap as best-effort. The Value section currently says "bounded mechanically".

### [CONCERN] Unreadable-state and malformed-marker paths lack explicit failure signals for resume with a changed cap source

A run started before this slice loads with `spent_usd = 0.0`. Resuming it under a new cap then silently undercounts. The doc says the pre-check's docstring will state this, so the only signal is in a code comment. The failure-mode list in Technical Requirements does not cover it. At minimum, log a WARNING on resume when the state file lacks `spent_usd` and a cap is active.

### [NOTE] BLOCKED check reads task files, but it is a good reuse of the merge guard

Extracting `slice_task_paths()` from `branch_ops.py` removes duplication. Binding `squadron.blocked-tasks` before `dispatch-branch-work` is called out and justified. The `awaits_human` copy in the executor reuses the mapping the merge guard already depends on. No layer boundary is crossed.

### [NOTE] No NFR targets in the parent architecture apply

The 900 architecture states no latency or throughput targets, so none need restating. The slice does state its own bounds: the idle timeout for the shell wait, and the cap itself.

### Run Digest

- Response length: 6363 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 435659 / 350148 / 85497 / 3465 / not computed
- Duration: 29.1 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
