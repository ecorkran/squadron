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
reviewedSha: 84aedd8237087e20a2149ad4e301772b4cc82cc5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
durationSeconds: 50.9
squadronVersion: 0.21.3
findings:
  - id: F001
    severity: pass
    category: architecture
    summary: "Fits the maintenance initiative's scope"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md#overview"
  - id: F002
    severity: pass
    category: architecture
    summary: "Interface parity and one shared function"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:41-45"
  - id: F003
    severity: note
    category: integration
    summary: "The slice plan lists an MCP path; the design drops it"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:24"
  - id: F004
    severity: concern
    category: under-specification
    summary: "Multi-part outcome is ambiguous and the signature doesn't match the data flow"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:43-48"
  - id: F005
    severity: concern
    category: correctness
    summary: "The \"starts with merge\" pattern contradicts the negative fixtures"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:58-63"
  - id: F006
    severity: concern
    category: hidden-dependency
    summary: "Tests read files from other repositories"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:91-92"
  - id: F007
    severity: concern
    category: integration
    summary: "Saved FAIL artifact has no defined model, profile or cost fields"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:96-97"
  - id: F008
    severity: note
    category: concurrency
    summary: "Synchronous file reads inside the async pipeline path"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:45"
  - id: F009
    severity: note
    category: error-handling
    summary: "Failure modes are covered; decode errors aren't"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:65-66"
  - id: F010
    severity: note
    category: interfaces
    summary: "`resolve_slice_inputs` is a private method"
    location: "project-documents/user/slices/933-slice.deterministic-task-file-gate.md:37"
---

# Review: slice — slice 933

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [PASS] Fits the maintenance initiative's scope

This is a tooling check across subsystems that enforces an existing guide rule. It adds no new feature area, which matches the arch's "Tooling and CI" and "Operational" scope. It is a single focused item that can be reverted on its own, as the arch guidelines ask. The parent architecture states no NFRs, so the slice doesn't need to restate any.

### [PASS] Interface parity and one shared function

`task_gate.py` holds pure functions with no I/O, and both the CLI and the pipeline call the same gate (line 116). The pattern table is the only place that defines what counts as a merge step. Dependencies point the right way: the CLI and pipeline depend on `squadron.review`, not the other way round. I confirmed the hook points exist:
- `review_tasks` has a per-part loop.
- `ReviewAction._review` validates every part before the first model call.

### [NOTE] The slice plan lists an MCP path; the design drops it

The slice plan entry (900-slices, item 31) lists "MCP" among the paths the gate must cover. The design says squadron's server has no review tool today. I found no MCP server or tool registration under `src/`, so dropping it is correct. Add one line saying that any future MCP review tool must call `merge_gate_result`, so the parity requirement isn't lost.

### [CONCERN] Multi-part outcome is ambiguous and the signature doesn't match the data flow

- **Signature vs data flow:** `merge_gate_result(scans) -> ReviewResult | None` returns one result. The Data Flow says "build a FAIL `ReviewResult` per offending part" and save each under its own `part-N` slot.
- **Clean parts are unspecified:** when part 2 fails the gate, do parts 1 and 3 still get a model review?
  - "skip the model" and the free-rejection argument (line 19) suggest no.
  - Per-part slots suggest the clean parts still get their normal model review and artifacts.

**Fix:** pick one rule and change the signature to match. For example, any hit means no model call for any part, and a FAIL is saved only for the offending parts. Also say how the result enters the CLI's worst-verdict exit code and the pipeline's `fold_review_parts`.

### [CONCERN] The "starts with merge" pattern contradicts the negative fixtures

Pattern 1 flags any checklist item whose first word is `merge`. Lines 62–63 list `merge defaults` and `merges built-in and user profiles` as must-not-flag.
- A real item such as `- [ ] Merge defaults from config into profile` would be flagged, so these negatives only pass if they appear in prose. The fixture set doesn't say that.
- Pattern 3 (`merge` near `slice`/`target`) has the same risk, for example `Merge slice config overrides`.

**Fix:** either require a git object or branch verb after the leading `merge`, or add these vocabulary phrases as negative fixtures on checklist items. The project rule asks for fixtures in the format the parser actually reads, which here means checklist lines.

### [CONCERN] Tests read files from other repositories

"A test runs the gate over each real file from the list". Those files live in trading-data, trading-data-maintenance and trading-ui, not in squadron, so the test suite would depend on sibling checkouts.

**Fix:** state that the real files (or their relevant excerpts, with line numbers kept) are vendored under squadron's `tests/` fixtures. Then the test is self-contained and still uses real input. Also, "trading-ui 124/125 where present" leaves the fixture set open-ended; make it a fixed list.

### [CONCERN] Saved FAIL artifact has no defined model, profile or cost fields

The requirement says "The FAIL artifact is saved and readable by existing review readers". Saved reviews and their summary readers normally carry model, profile and cost or telemetry. The design doesn't say what those fields hold when no model ran.

The project forbids silent fallbacks, so specify explicit placeholder values, for example a gate marker as the model name and zero cost. Check them against the existing readers. Otherwise the implementer will invent values or break a reader.

### [NOTE] Synchronous file reads inside the async pipeline path

`ReviewAction._review` is `async`. The project's Python rules require any synchronous code in an async function to finish in under 1ms in the worst case. Reading a few small local task files is almost certainly fine. The design should still say where the reads happen, either inline as small sync reads or alongside the existing synchronous input validation, so the reviewer can check it against the rule.

### [NOTE] Failure modes are covered; decode errors aren't

- **Covered:** the scan raises on a read error and is never skipped. A missing file is already handled by `missing_input_files`.
- **Not mentioned:** `UnicodeDecodeError` on a badly encoded file. Raising with the file path is enough.

The gate is local and pure, so hang, timeout and disconnect don't apply.

### [NOTE] `resolve_slice_inputs` is a private method

In the pipeline the method is `ReviewAction._resolve_slice_inputs`, which is private. The gate only needs the resolved part paths that already exist in `_review` by the time it runs, so it shouldn't depend on this method. Reword the line so the task breakdown doesn't create a dependency on a private method.

### Run Digest

- Response length: 7234 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 50.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
