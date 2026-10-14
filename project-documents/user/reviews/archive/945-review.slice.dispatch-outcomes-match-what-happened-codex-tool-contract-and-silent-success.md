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
reviewedSha: e068f9852a12930b2fa431f48482555530d26197
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 35.2
runId: run-20261014-p4-dcdd93aa
squadronVersion: 0.21.7
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Scope and layering match the maintenance architecture"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md#Technical Scope"
  - id: F002
    severity: concern
    category: scope-alignment
    summary: "D6 may not fix the bug the plan assigns (#212 item 2)"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:144-150"
  - id: F003
    severity: concern
    category: failure-modes
    summary: "The claim to cover `implement` and revise dispatches is inconsistent with the doc's own telemetry limits"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:134-136"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Backstops and metadata with no current consumer make the design heavier than needed"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:122-134"
  - id: F005
    severity: note
    category: scope-alignment
    summary: "Bare dispatch with no tools (deepseek fake-markup case) is deliberately not failed"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:48-61"
  - id: F006
    severity: note
    category: error-handling
    summary: "Failure modes for new paths are mostly enumerated and observable"
    location: "project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md:141-142"
---

# Review: slice — slice 945

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Scope and layering match the maintenance architecture

The slice is bug-fix and operational work that spans subsystems, which 900 names as in scope. Items 5 and 6 are explicitly split into separate commits, which satisfies the "grouped slice … can be reverted without touching the others" guideline. D2 keeps the sandbox knowledge inside the Codex provider. The new `dispatch_outcome.py` sits in the pipeline layer and reads only response metadata. Dependency direction is correct, and prerequisites 942 and 944 are complete.

### [CONCERN] D6 may not fix the bug the plan assigns (#212 item 2)

The plan entry says a run stopped by a hard gate ends `completed` and should end `paused`. The slice's own Open Item admits that a `completed` end means the merge gate passed. So the gate was not what stopped the run in #212, and the cause is unconfirmed. D6 only converts an existing `FAILED` (unchecked items at merge) into `PAUSED`, so it does not address the reported `completed` outcome. The slice has no step that reproduces or diagnoses the actual path. The repo guidelines require concrete evidence before a fix. Options:
- Make obtaining the #212 run state a gate before D6 is implemented.
- Re-scope D6 and state plainly that it is not the #212 fix.

### [CONCERN] The claim to cover `implement` and revise dispatches is inconsistent with the doc's own telemetry limits

D3 says rows 2 and 5 "do not apply where no tool telemetry exists", and that SDK phase steps stamp telemetry only when `allowed_tools` is declared. D3's #15 note then says this slice "covers `implement` and revise dispatches (rows 2–3)". On the default SDK profiles that coverage is absent:
- The only backstop for an SDK `implement` that does nothing is the merge gate.
- The Special Considerations section records that the merge gate passes when cf lists no task files.
- The persistent-session path is excluded.

The silent-success class named in the title therefore remains open for the default provider. Either state this residual gap explicitly in Excluded and Risk, or correct the coverage claim.

### [CONCERN] Backstops and metadata with no current consumer make the design heavier than needed

- **Row 1:** it backstops "any provider that ignores `allowed_tools` without raising". After D2, the SDK and OpenAI-compatible agents honor `allowed_tools` and Codex refuses it, so no provider needs it. It is speculative; cut it or defer it until a provider needs it.
- **Row 5 and `tools_suppressed_reason`:** these add a new metadata key and a fail rule for a case the doc says "reduces to row 2's situation".
- **`tool_warnings`:** it duplicates the WARNING log and the counts already recorded in metadata.

Together these make `assess_tool_outcome` carry five rules where rows 2 and 3, plus the D2 refusals, meet the plan's cases.

### [NOTE] Bare dispatch with no tools (deepseek fake-markup case) is deliberately not failed

The plan lists the no-tools deepseek probe among the four recorded cases. The slice reconciles it as "not failed" and gives a reasoned basis: squadron cannot tell a refusal from an answer without parsing prose. This is a documented, justified narrowing of "fail where the step cannot have done its job". It is visible to the PM, so no change is required. Confirm that the PM accepts it.

### [NOTE] Failure modes for new paths are mostly enumerated and observable

The slice adds no new I/O or message types. The new failure paths are spawn refusals, D3 failures, D5 one-line errors, and D6 pauses. Each has a named outcome, and the Technical Requirements require a WARNING or ERROR log and a test asserting the log record. No NFR in the parent architecture applies to these paths.

### Run Digest

- Response length: 5065 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 35.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
