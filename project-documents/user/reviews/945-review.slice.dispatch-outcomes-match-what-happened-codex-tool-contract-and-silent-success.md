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
reviewedSha: c86635980ba75bce310397562e194983a76a63d9
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 35.9
runId: run-20261014-p4-dcdd93aa
squadronVersion: 0.21.7
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Plan-assigned silent-success cases are excluded without reconciling against the plan entry"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:40-41"
  - id: F002
    severity: concern
    category: correctness
    summary: "D3 row 3 can fail legitimate read-only steps; the rule is broader than the stated intent"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:112"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Generic `NEEDS_DECISION_OUTPUT` mechanism and `ToolDescriptor.writes` are larger than the one consumer needs"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:128-131, 138-141"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Bundled scope: #202 and #212 item 2 are unrelated to the dispatch-outcome core"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:36-37"
  - id: F005
    severity: note
    category: documentation
    summary: "Frontmatter dependencies differ from the plan entry"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:6"
  - id: F006
    severity: note
    category: error-handling
    summary: "Failure modes for the new refusal paths are explicit"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:98-104, 116"
  - id: F007
    severity: pass
    category: architecture
    summary: "Layering and dependency direction"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md#Technical Decisions"
---

# Review: slice — slice 945

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Plan-assigned silent-success cases are excluded without reconciling against the plan entry

The plan entry for 945 describes four probe cases. All four used bare `dispatch` steps. It also lists "zero tool calls on a step that needs them" among the signals that should fail a step. The design excludes bare dispatch with no `allowed_tools`. That leaves the fake tool-call markup case (deepseek, no tools) and a bare Codex dispatch on a read-only sandbox still ending `completed`, `success: True`. These are the plan's headline symptom, and they now only log a WARNING.

The reasoning is sound: squadron cannot tell intent from prose. But the plan entry says "a dispatch that must write on a read-only sandbox fails loudly", and the design's only handling for bare dispatch is a WARNING plus a metadata stamp.

The Overview says the slice fixes "three things" after listing four cases. No success criterion covers the fake-markup case. Dropping or deferring plan-assigned scope is a CONCERN. Do one of these:
- Record the exclusion back on the plan entry and issue #211 as a deliberate deferral.
- State explicitly that this slice closes only the declared-`allowed_tools` and phase-step cases.
- Add an opt-in way to mark a bare dispatch as write-required. The design rejected a per-step `writes: true` key (D1), but that key would be the only route to covering `close-out`-style steps.

### [CONCERN] D3 row 3 can fail legitimate read-only steps; the rule is broader than the stated intent

The design says to fail "where the step cannot have done its job". Row 3 (`failed_tool_calls == tool_calls_made`) applies to any step with declared tools, not only write-required ones. A read-only analysis step that makes a single `grep` or `read_file` call, gets one error and then answers from context would be failed, even though it could have done its job. Row 4 already treats partial failure as recoverable.

Either scope row 3 to write-required steps, or require a minimum call count. If it stays as written, say why a failed read on a non-write step is fatal. The Risk Assessment covers only row 2's false-failure risk.

### [CONCERN] Generic `NEEDS_DECISION_OUTPUT` mechanism and `ToolDescriptor.writes` are larger than the one consumer needs

D6 needs one thing: an unfinished-tasks merge refusal ends `paused`. The design adds three pieces for that:
- a new `BranchFailure.UNFINISHED_TASKS` kind
- a new action output flag, `NEEDS_DECISION_OUTPUT`, defined in `models.py`
- an executor branch that reads the flag

Integration Points then advertises the flag as "a generic way for an action to end its step paused", which is speculative. A lighter option is for the branch action to return the existing failure kind. The executor would map it to `PAUSED` directly, with no new cross-layer output channel. If the flag is kept, justify it against that lighter option.

Likewise, `ToolDescriptor.writes` is listed as "for any later tool policy". Keep only what D2's write-tool lookup needs. Also consider dropping `metadata["tool_warnings"]`, since WARNING logging already carries it.

### [CONCERN] Bundled scope: #202 and #212 item 2 are unrelated to the dispatch-outcome core

The component table touches about ten modules across providers, tools, events, branch ops, the executor and dispatch. Items 5 and 6 touch different subsystems from items 1-4 and are independent of them. The plan does assign them to this slice, so this is not scope creep. The 900 guideline allows grouped slices only when "each item commits separately and can be reverted without touching the others".

The Implementation Notes order does keep them separable (steps 6 and 7), but the design never states that independence. Add a sentence saying D5 and D6 commit and revert independently. Otherwise the slice's review and revert cost exceeds the plan's 3/5 effort.

### [NOTE] Frontmatter dependencies differ from the plan entry

Frontmatter lists `dependencies: [942, 944]`. The plan entry says "Dependencies: none". The design's list is more accurate, since it builds on 942's merge gate and 944's #200 loop path, but the plan should be updated to match.

### [NOTE] Failure modes for the new refusal paths are explicit

The design handles each new failure path explicitly:
- Spawn-time `ProviderError` refusals, with messages that name the fix.
- Each D3 row's outcome, with a WARNING log and a metadata record.
- The no-telemetry case on SDK phase steps, which are covered by the #15 post-condition and the merge gate.
- A required test asserting that a log record is produced.

No new network I/O or message type is introduced, so the parent's failure-mode enumeration requirement is met. The parent architecture states no NFR on these paths, so nothing needs restating.

### [PASS] Layering and dependency direction

Provider-specific knowledge, such as the Codex sandbox credential, stays in the provider (D2). Dispatch holds only the provider-agnostic backstop and outcome rules. It consumes 942's merge gate and 944's loop-exit behavior without changing them beyond the failure kind. The slice also fits the 900 scope: operational error-handling and bug fixes that span subsystems.

### Run Digest

- Response length: 6773 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 35.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
