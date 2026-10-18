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
reviewedSha: 97dbd541e58ec5db6733ec9ab8e719d2452dbeb5
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 86166
cachedTokens: 47946
cacheWriteTokens: 38216
completionTokens: 2812
durationSeconds: 22.3
costUsd: 0.195416
costBasis: provider
runId: run-20261018-p4-16dfa489
squadronVersion: 0.23.2
findings:
  - id: F001
    severity: pass
    category: scope
    summary: "Fits the maintenance initiative's scope"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#Overview"
  - id: F002
    severity: concern
    category: scope-creep
    summary: "The cost cap is a new feature, which the architecture excludes from this initiative"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#Technical Scope"
  - id: F003
    severity: concern
    category: proportionality
    summary: "The design is heavy for a \"lighter-weight\" maintenance slice"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#Technical Decisions"
  - id: F004
    severity: concern
    category: under-specification
    summary: "Unspecified integration points: `BLOCKED_TASK` and the replay reader"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#API Contracts"
  - id: F005
    severity: concern
    category: boundaries
    summary: "The executor takes on cross-cutting responsibilities and a hidden event-outcome change"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#Component Structure"
  - id: F006
    severity: concern
    category: error-handling
    summary: "NFR and failure-mode gaps on the new shell-wait I/O path"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#D11 — Report running shells now; write the wait mechanism from the probe"
  - id: F007
    severity: note
    category: documentation
    summary: "Parent field and NFR handling"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md:5"
  - id: F008
    severity: pass
    category: boundaries
    summary: "Dependency directions and layering"
    location: "project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md#Dependencies"
---

# Review: slice — slice 947

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Fits the maintenance initiative's scope

The architecture (900) accepts operational and error-handling improvements that span subsystems, plus non-trivial bug fixes. The slice bundles three issues (#235, #223, #234) with related causes. It also adds one control, the cost cap.

The architecture says a grouped slice is valid when each item commits separately and can be reverted on its own. The "Development Approach" section says this directly ("Each part is independently committable"). The decision to defer the pre-implement pending-decision check to #240, because it depends on context-forge#121, keeps the slice from absorbing cross-project work.

### [CONCERN] The cost cap is a new feature, which the architecture excludes from this initiative

Architecture 900 excludes "new feature areas" and allows only "small conveniences over existing commands, files and config." The cost cap adds the following:
- a new public contract: a pipeline YAML field and a config key
- a new `FailureKind` member
- a new persisted `RunState` field
- a new module, `run_spend.py`
- a new run-level spend ledger
- a pre-run gate, a post-action gate, and documented overshoot and crash-loss bounds

This goes beyond a small convenience over existing config. The slice should either state why it qualifies, for example by pointing to the slice plan entry that assigns it here, or move it to a feature initiative. At minimum it needs a one-line justification under "Technical Scope". Without one, a reader can't tell whether the scope is in bounds.

### [CONCERN] The design is heavy for a "lighter-weight" maintenance slice

The architecture asks for "lighter-weight" process on maintenance work. This design has 11 decisions, 5 scope items, and about 10 touched components. Several parts can be cut or deferred:
- **Persisted spend for resume (D6).** This adds the `RunState.spent_usd` field, a pre-1.0 migration WARNING, an observer signature change, and a "crash loss" bound to document. A lighter option meets the requirement. Fail the run on cap crossing, and on resume start the count from zero with one stated limit.
- **Pre-run cap check on resume (D5).** It exists only because of persisted spend, so it goes if D6 is simplified.
- **Two cap sources with lowest-wins resolution and a dual-value error message (D3).** One source is enough until something needs the second. Config alone covers "per-project", and the slice already drops the CLI flag.
- **Shell tracking and wait (D10/D11).** The slice itself says the cause of #234 is unconfirmed and that the wait may turn out "not needed". The shell-ledger and `background_shells_running` metadata work can be deferred until the probe shows a real backgrounding path. The probe alone should be this slice's deliverable.
- **`FailureKind.BLOCKED_TASK`.** It's added in "API Contracts", but D7 never sets it. The "Failure modes" tests and the design don't mention it.

Each is a CONCERN under the proportionality criterion. The finding to act on is the cut list above.

### [CONCERN] Unspecified integration points: `BLOCKED_TASK` and the replay reader

"API Contracts" says both new `FailureKind` members "are read by the replay outcome reader without matching on error text." No component in the table covers the replay reader. D7 builds the BLOCKED `ActionResult` without setting `FAILURE_KIND_KEY`. If the pause is meant to carry `BLOCKED_TASK`, D7 must say where it is set. If it isn't, drop the member. The claim about the replay reader needs a named component and a test, or it should be removed.

### [CONCERN] The executor takes on cross-cutting responsibilities and a hidden event-outcome change

Two changes affect behavior beyond this slice.
1. The executor starts copying `awaits_human` from any failing event outcome. This applies to every POST_ACTION binding, including user-defined ones, not just `squadron.blocked-tasks`. The slice calls it "one line", but it changes the event contract. The "Provides to Other Slices" section should say so, along with whether an existing or user event returning `awaits_human` now pauses a run, and the slice should add a test for that.
2. `_execute_step_once` now both runs actions and enforces the cap. The slice should say where `RunSpend` is injected and how `fan_out` branches share it. "Share the one event loop" is asserted, but the branch-sharing mechanism isn't described.

### [CONCERN] NFR and failure-mode gaps on the new shell-wait I/O path

D11 leaves the wait mechanism undefined ("written after the probe"). It still lists "shell timeout" as a failure mode with a test. The failure modes for this I/O path are only partly enumerated:
- The shell exits non-zero.
- The CLI process dies while a shell runs.
- The SDK stream closes mid-wait.
- The wait resumes the agent through an extra turn, which also adds cost. That cost must count against the cap, and the design doesn't say how.

Deferring the mechanism is acceptable only if the slice design is amended before the wait task starts. The task list and success criteria should make that a gating step, and say what happens if the amendment is skipped.

### [NOTE] Parent field and NFR handling

The `parent` field points to `900-slices.maintenance-and-refactoring.md` (the slice plan), which is expected. Architecture 900 states no NFRs, so there is nothing to restate. The design does state its own bounds for the cap (D5 overshoot and crash loss) and for the shell wait (`background_idle_timeout_s`).

### [PASS] Dependency directions and layering

Dependencies run in the right direction. The executor consumes usage records stamped by actions, the BLOCKED check consumes `slice_task_paths()`, and the extraction is shared with the merge guard without changing its behavior. The deferred check stays with context-forge, so squadron doesn't parse decision status itself. The review criterion lives at one assembly point and excludes judge templates, which avoids shifting baselines.

### Run Digest

- Response length: 7409 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 86166 / 47946 / 38216 / 2812 / not computed
- Duration: 22.3 s
- Cost: $0.20 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
