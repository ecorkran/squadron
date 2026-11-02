---
docType: review
layer: project
reviewType: slice
slice: isolated-file-in-file-out-dispatch-steps
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: d2f0df4c6caf860cc357d896895b433209522c62
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 171795
cachedTokens: 86268
cacheWriteTokens: 85521
completionTokens: 3872
durationSeconds: 34.0
costUsd: 0.390209
costBasis: provider
runId: run-20261102-p4-037d1fcf
squadronVersion: 0.24.13
findings:
  - id: F001
    severity: pass
    category: scope-alignment
    summary: "Scope matches slice plan entry 43 (949)"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Technical Scope"
  - id: F002
    severity: pass
    category: boundaries
    summary: "Layering and dependency direction"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Architecture"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes enumerated with observable signals"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Failure surface"
  - id: F004
    severity: note
    category: scope-creep
    summary: "Prompt-only rejection (D9) and the `feedback` conflict rule go beyond the plan entry"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#D9"
  - id: F005
    severity: note
    category: proportionality
    summary: "Two-file write rollback is the heaviest mechanism"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#D5"
  - id: F006
    severity: note
    category: interface-design
    summary: "`--strict` now has two meanings"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#D8"
  - id: F007
    severity: note
    category: behavior-change
    summary: "No-tools guard is limited to dispatch steps and changes `allowed_tools: []` at run time"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#D6"
---

# Review: slice — slice 949

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Scope matches slice plan entry 43 (949)

Each of the plan's five capabilities has a matching decision:
1. File content in the prompt: D1 and D2.
2. Reply hand-off: D3 and D4.
3. Reply and delivered-prompt files: D5.
4. No-tools guard: D6.
5. `--validate --strict` with one known-keys list per step type: D7 and D8.

The `reply_from` narrowing to top-level steps is already recorded in the plan entry, so the design does not drop or defer any assigned scope. Plan item 5 asks for a known-keys list "shared by `validate` and `expand`". The design does this for dispatch (D7, `DISPATCH_FORWARDED_KEYS`). The other step types only get a module constant, and criterion 8 (every built-in pipeline passes `--strict`) is the drift check there.

### [PASS] Layering and dependency direction

- File and reply logic goes into a new `actions/dispatch_io.py`, which keeps the ~1000-line `actions/dispatch.py` from growing much.
- The guard tests the `can_read_files` capability and never tests provider identity.
- `results_for_step` sits next to `prior_output_key`, so the key format is defined in one module.
- Key names are constants, with no scattered literals.
- Strict validation lives in the loader and reads `inner_steps`, so the loader does not hard-code step types.

### [PASS] Failure modes enumerated with observable signals

The failure table covers each new I/O path:
- A missing, directory, FIFO, permission-denied or invalid-UTF-8 prompt file fails before any model call.
- A failed or empty upstream reply is covered, including on resume.
- A reply with no JSON object fails the step.
- A write failure restores the prompt file.
- A failed restore logs at ERROR.

Each row names its signal: a WARNING or ERROR log, or `metadata["failure_kind"]`. The Technical Requirements section requires a test per signal. The model call's own hang and timeout behavior is unchanged and explicitly left to existing handling.

### [NOTE] Prompt-only rejection (D9) and the `feedback` conflict rule go beyond the plan entry

The plan entry does not list either item. Both are small and prevent silent divergence between `sq run` and prompt-only mode, so they are justified. Record them in the plan entry when the slice closes, as was done for the `reply_from` narrowing.

### [NOTE] Two-file write rollback is the heaviest mechanism

Capturing the prior bytes, restoring them, and handling a failed restore adds a code path for a rare case. The plan's "a failed step writes nothing and leaves existing files alone" justifies keeping some guarantee. If implementation cost grows, a lighter alternative is to write `reply_file` first, since it is the file consumers read, and document the residual window for the prompt file. As written it is acceptable and fully tested.

### [NOTE] `--strict` now has two meanings

Reusing the existing flag follows the exact command named in the issue, and the help text covers both meanings. The overload is an accepted trade-off.

### [NOTE] No-tools guard is limited to dispatch steps and changes `allowed_tools: []` at run time

The dispatch-only scope and the behavior change are stated openly in Excluded, Risk Assessment and the CHANGELOG requirement. The exclusion of `review` and `summary` steps is a reasonable reading of plan item 4. The design also checked `src/squadron/data/` for existing uses of `allowed_tools: []`.

### Run Digest

- Response length: 4276 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 171795 / 86268 / 85521 / 3872 / not computed
- Duration: 34.0 s
- Cost: $0.39 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
