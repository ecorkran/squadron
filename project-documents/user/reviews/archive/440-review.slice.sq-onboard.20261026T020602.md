---
docType: review
layer: project
reviewType: slice
slice: sq-onboard
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/440-slice.sq-onboard.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261025
dateUpdated: 20261025
reviewedSha: bac114f78ba34cc6d8d3e44342e5ed432d6db38c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 264920
cachedTokens: 172758
cacheWriteTokens: 92154
completionTokens: 4507
durationSeconds: 38.5
costUsd: 0.431709
costBasis: provider
runId: run-20261026-p4-35b5511c
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "No hang or timeout handling for the new cf subprocess paths"
    location: "project-documents/user/slices/440-slice.sq-onboard.md#D7 — One report call and one error reader"
  - id: F002
    severity: concern
    category: proportionality
    summary: "The design is heavier than the slice needs"
    location: "project-documents/user/slices/440-slice.sq-onboard.md#Implementation Details"
  - id: F003
    severity: note
    category: architecture-alignment
    summary: "Graph gating deviates from the architecture's step table, and the design says why"
    location: "project-documents/user/slices/440-slice.sq-onboard.md#D2 — The graph gates only until a comprehension doc exists"
  - id: F004
    severity: note
    category: scope
    summary: "The retroactive guard covers more phases than the architecture states"
    location: "project-documents/user/slices/440-slice.sq-onboard.md#D11 — Retroactive entries are refused at `set_slice`"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Boundaries, dependency direction and integration points match the architecture"
    location: "project-documents/user/slices/440-slice.sq-onboard.md#Architecture"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Version, outcome and envelope handling matches the \"refuse what isn't understood\" and \"one error reader\" principles"
    location: "project-documents/user/slices/440-slice.sq-onboard.md#D7 — One report call and one error reader"
---

# Review: slice — slice 440

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] No hang or timeout handling for the new cf subprocess paths

The slice adds six cf call paths: `detect`, `project list`, `init`, `config set`, `prompt get` and the new `run_report`. D7 and D8 cover these failure modes:
- non-JSON stdout
- an unexpected exit code
- an error envelope
- `ok: false`
- cf not installed

They never say what happens when a call hangs or is killed. `cf init` installs guides and commands, and `cf prompt get` reads the guide, so either can stall. The existing `ContextForgeClient` has no timeout (I found none in `context_forge.py`), and the design doesn't add one to `run_report`. An agent loop blocked on a hung `sq onboard --json` is the worst place for a silent stall.

The design also doesn't say whether failures are logged at WARNING or above, or which test asserts the signal. Most paths do surface a one-line stderr error, which is observable. The two exceptions are the swallowed WARNING for skipped comprehension files, which is logged, and the unknown-staleness path.

State a timeout policy for `run_report` and the other calls. It should come from config, not a magic default. Also state that a timeout raises `ContextForgeError` naming the command. Add one test that asserts it.

### [CONCERN] The design is heavier than the slice needs

Several parts restate other material or build for cases this slice doesn't have. These can be cut or shrunk:
- **Migration Plan table and Consumers list.** Both repeat Technical Scope and the Component Structure tree. Keep a single list of what moves and what is deleted.
- **Success Criteria and Verification Walkthrough.** They largely restate the D-decisions and the test list in Development Approach. Walkthrough steps 1–6 duplicate what the tests assert. Step 1 also clones a third-party repo from the network. Keep a short live end-to-end check (step 7) and the no-writes check.
- **`decide_step` exhaustiveness.** The `assert_never` mechanism plus the exhaustive `match` is more than needed for a six-row table that has one test per row.
- **D8 `register --ide TARGET`.** It is justified by the Codex skill. Say explicitly that the value is passed through to cf unvalidated, so squadron holds no target list.
- **Output fields `derived_architectures` and `existing_state_plan`.** No step branches on them. They only pad the report, so keep them only if the non-JSON report must show them.

None of this drops scope the slice plan assigns, so it is an economy concern, not a gap.

### [NOTE] Graph gating deviates from the architecture's step table, and the design says why

The architecture's table sends a "graph absent or stale" directory to `build-graph`. D2 narrows this to "no comprehension doc and the graph is absent, behind HEAD, or of unknown staleness". The reason given is sound: with no stored state, the PM's "keep the stale graph" answer can't be remembered. It also fits the principle that a comprehension doc older than the graph is kept. The consequence is that the "asked once" guarantee holds only within one agent session. If the session ends before a doc is written, the PM is asked again. That is acceptable and already implied by "no stored state". I suggest recording the deviation as an update to the architecture table, so the two documents stay aligned.

### [NOTE] The retroactive guard covers more phases than the architecture states

The architecture and slice plan say "P5 or P6". D11 refuses at `set_slice`, so P4 is covered too. D11 justifies this, because `cf check` already errors on a design for a retroactive entry. The guard sits at the pipeline boundary and reads only cf's `retroactive` boolean, so the direction rule holds. Treating a missing key as an error follows the "no silent fallback" rule and matches the architecture's statement that the field is stable.

### [PASS] Boundaries, dependency direction and integration points match the architecture

- Squadron calls cf, and cf never names squadron's files.
- Squadron finds only its own comprehension doc by its own name. The concept, derived architectures and the plan come from `cf detect` only.
- `build_onboard_report` takes a `Protocol` client, so tests can use recorded JSON.
- `CfAdoptionClient` sits in `integrations/` and `onboard/` depends on it, which keeps the layers one-directional.
- `ContextForgeClient` changes are additive, and `_run` and `_run_json` stay as they are.
- `project_root()` is deleted so the root is never widened to the git toplevel.
- `is_registered` uses `cf project list --json` instead of reading cf's store, as the architecture requires.

### [PASS] Version, outcome and envelope handling matches the "refuse what isn't understood" and "one error reader" principles

`_checked_report` checks `reportVersion` before the envelope, with separate constants for detect and init. An unknown `outcome` raises an error naming the value. A failed `cf init` step is handled as `ok: false`, not as an exception. The design also states the reasons for rejecting `cf init` and `cf get` as registration checks, which the architecture left open. The tests mapped to each of these cases are listed in the Success Criteria.

### Run Digest

- Response length: 6313 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 264920 / 172758 / 92154 / 4507 / not computed
- Duration: 38.5 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
