---
docType: review
layer: project
reviewType: slice
slice: deterministic-task-file-gate
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/933-slice.deterministic-task-file-gate.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261010
dateUpdated: 20261010
reviewedSha: 8f701a8dd07f9bff18926a3ce01750f8ad49c92b
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 11
durationSeconds: 51.1
squadronVersion: 0.21.3
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Fixture list leaves out trading-ui 124 and 125, which the slice plan names"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:94"
  - id: F002
    severity: concern
    category: integration
    summary: "`tools_given: []` conflicts with the existing tri-state convention"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:100"
  - id: F003
    severity: concern
    category: under-specification
    summary: "\"Within a few words\" is not a specified matching rule"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:61-64"
  - id: F004
    severity: note
    category: performance
    summary: "Synchronous file reads inside the async pipeline action"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:45"
  - id: F005
    severity: pass
    category: alignment
    summary: "Fits the architecture's scope and guidelines"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md#technical-scope"
  - id: F006
    severity: pass
    category: integration
    summary: "MCP path deviation is justified"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:24"
  - id: F007
    severity: pass
    category: architecture
    summary: "Dependency direction and component boundaries"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md#component-structure"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure modes and result semantics are explicit"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:68-69"
---

# Review: slice — slice 933

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] Fixture list leaves out trading-ui 124 and 125, which the slice plan names

The slice plan entry (900-slices, item 31) names trading-ui 124 ("Merge into the target per the project Git Rules", checked) and 125 as offending files. It also says "the test fixtures are the real lines from the files listed above". The design calls its list "fixed" but includes only trading-data 184/185 and 908/909. The Overview (line 16) leaves trading-ui out too. This matters because the trading-ui 124 wording is the canonical agent phrasing ("Merge into the target"). The design's own rule 1 catches it (`merge` followed directly by `into`), but no fixture proves that. Add the trading-ui 124/125 excerpts with their line numbers, or state why they are excluded.

### [CONCERN] `tools_given: []` conflicts with the existing tri-state convention

`ReviewResult` documents `tools_given`/`tool_calls_made` as a tri-state. Both are `None` when the review "ran without tools". A populated list means tools were offered. The model code warns that an empty list is easy to confuse with "template declared no tools". Persistence only renders tool-call telemetry when `tools_given is not None`. So `[]` writes `toolsGiven: []` / `toolCallsMade: 0`, which implies a tool-capable run that was offered nothing. No model ran at all, so `None` for both fields matches the established meaning, as the slice already does for cost and tokens. Pick `None` or justify `[]`, and have the read-back test assert the rendered frontmatter.

### [CONCERN] "Within a few words" is not a specified matching rule

Rule 3 flags `merge` "followed within a few words by a git object", but never gives the window size. This is the rule most likely to produce false positives, so the window should be a named constant in the pattern table, and the design should state it. Token boundaries are also undefined. The negatives include `merge-base`, `--no-merges` and `mergeFixResults`. A realistic line like `- [ ] Run git merge-base main HEAD` puts `main` within a few words of `merge` (as a substring). Say whether `merge` must be a whole word, separated by whitespace or punctuation and excluding hyphens, and add that line as a negative fixture.

### [NOTE] Synchronous file reads inside the async pipeline action

`ReviewAction._review` is `async def`. The project's Python rules require synchronous code inside an async function to finish in under 1ms in the worst case. Reading a few small local task files will almost always meet that, and the existing `missing_input_files` stat check sets the precedent. Still, the design should say this is a deliberate choice: task files are small and local. Otherwise it should use `asyncio.to_thread`. The parent architecture states no NFR for this path, so no target needs restating.

### [PASS] Fits the architecture's scope and guidelines

This is tooling and operational hardening that spans the CLI and pipeline subsystems, which is in scope for 900 ("Tooling and CI", "Operational"). It is lightweight, with Effort 2/5, as the architecture asks. It adds nothing beyond the slice plan entry. Out-of-scope items are explicit: historical files, other forbidden content, and pipeline `branch: merge` engine ops.

### [PASS] MCP path deviation is justified

The slice plan lists MCP among the paths to gate. The design notes that squadron has no MCP review tool today, and that the slash command shells out to `sq review tasks`. Both claims hold: `src/` has no MCP tool registrations, and `commands/agents/sq-review/SKILL.md` invokes the CLI. The design also requires any future tool to call the same gate, so interface parity is kept.

### [PASS] Dependency direction and component boundaries

`task_gate.py` contains pure functions with no I/O and depends only on `squadron.review.models`. The CLI and pipeline depend on it, not the other way round. Both paths call one function, which avoids a DRY violation. The pattern table is the single place to change what counts as a merge step, and the template-name constant is defined once.

### [PASS] Failure modes and result semantics are explicit

The only new I/O is local file reads. `OSError` and `UnicodeDecodeError` raise with the file path, and the scan is never skipped. Missing files are already handled upstream, and hangs or peer disconnects don't apply to local reads. The FAIL path is also clear:
- **Verdict:** FAIL, with `verdict_source: imposed`, which matches existing usage in `coverage.py`.
- **Artifacts:** one per offending part only.
- **Exits:** the worst-verdict exit code makes the CLI exit non-zero, and `fold_review_parts` handles a subset of parts correctly.
- **Model calls:** a test asserts that no model is called.

### Run Digest

- Response length: 6272 chars
- Response is newline-free: no
- Tool calls made: 11
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 51.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
