---
docType: review
layer: project
reviewType: slice
slice: tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: 8fc47d463362c1e6655c3ca0dd2d746d09cfb44f
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
runId: run-20260928-slices-plan-783dab3a
squadronVersion: 0.15.1
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Slice is large for an initiative that prefers small, focused slices"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Technical Scope"
  - id: F002
    severity: concern
    category: scope
    summary: "Part A leans on \"configuration improvements\" and edges toward a new capability"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Initiative fit"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Hang and timeout handling for the stream is inherited, not specified"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#D12 — Failure modes and their signals"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure-artifact telemetry depends on every `ProviderError` exit being wrapped"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#D12 — Failure modes and their signals"
  - id: F005
    severity: concern
    category: architecture
    summary: "Dependency direction: `core/usage.py` gains a consumer from `review/` and a producer in `providers/`"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Dependency direction"
  - id: F006
    severity: note
    category: metadata
    summary: "Frontmatter parent points at a slices document"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md:5"
  - id: F007
    severity: pass
    category: risk
    summary: "Gemini `stream_options` risk is isolated by a declared profile field"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Mitigation Strategies"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for each new I/O path with signals and tests"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#D12 — Failure modes and their signals"
  - id: F009
    severity: pass
    category: nfr
    summary: "NFR handling and integration points are explicit"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Special Considerations"
---

# Review: slice — slice 931

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Slice is large for an initiative that prefers small, focused slices

The 900 architecture says "prefer many small slices over few large ones" and "Lighter-weight given the maintenance nature". This slice bundles three parts (effort, batched reads, usage). It touches about 25 components across core, models, pipeline, CLI, providers (openai/sdk/codex), review, tools, and data. It also carries a 12-row failure table and a new `core/usage.py` module. The doc records the bundling as a PM decision and adds mitigations: separate commits, C→B→A ordering, and separate revertability. That is a reasonable answer, but "independently deliverable" is met only at the commit level, not the slice level. B shares no code with A or C, so its bundling rests only on the PM decision and the shared fixture regeneration. Consider allowing B to be cut into its own slice if the implementation runs long.

### [CONCERN] Part A leans on "configuration improvements" and edges toward a new capability

The architecture excludes "new features or capabilities". The doc argues that A is not one because it adds no new command or workflow. But the alias field lets users choose reasoning effort across three providers, a control that did not exist before. The 924 `max_output_tokens` precedent supports the "operational configuration" reading. The argument is defensible, but it is the weakest of the three mappings. The recorded-level fix is the part that clearly belongs in this initiative, and the doc should say so explicitly. It could also say the alias field is included because it is the smallest control that makes the recorded level meaningful.

### [CONCERN] Hang and timeout handling for the stream is inherited, not specified

The D12 table covers a mid-loop stream failure by relying on the existing conversions to `ProviderTimeoutError`. It does not say what happens when the stream hangs with no error raised, or when the peer stops sending the final usage chunk. The `stream_options` request adds a trailing chunk. A backend that accepts the parameter but never sends the trailing usage chunk would stall the stream until the client timeout fires. The doc should either state that the existing client timeout bounds this, or state that the loop does not wait on the usage chunk. The "read hangs" row is handled explicitly. The equivalent stream-side row should be too.

### [CONCERN] Failure-artifact telemetry depends on every `ProviderError` exit being wrapped

The design says an outer `except ProviderError` attaches a `RunTelemetry` snapshot and re-raises. Raw exceptions outside the conversion list are explicitly left unconverted and produce no artifact. That is honest, but it means a common failure class (an unwrapped `httpx` error) still loses all the gathered telemetry, which is what #158 wanted preserved. The doc should say whether the WARNING with turns and tokens also fires on that path, since the log is the only record there. The current design has no signal on it beyond the traceback.

### [CONCERN] Dependency direction: `core/usage.py` gains a consumer from `review/` and a producer in `providers/`

The layering argument is sound: `review/` imports only shared provider modules and `core`, and `providers/openai` imports `core.usage`. However, `ProviderError` in `providers/errors.py` now holds a `RunTelemetry` from `core.usage`, so `providers/errors.py` gains a `core` import. This is a correct direction, but the doc should confirm that `core` does not already import from `providers`. The doc also relies on a grep for the `review/` to `providers/openai` rule. It could add the reverse check, so `core/usage.py` stays free of any provider import.

### [NOTE] Frontmatter parent points at a slices document

The `parent` field names `900-slices.maintenance-and-refactoring.md`, the slice plan. That is the expected form, so it is not flagged as an error.

### [PASS] Gemini `stream_options` risk is isolated by a declared profile field

The one unverified external fact is handled by `sends_stream_usage = False` on the gemini profile. It is a declared per-profile field, not string dispatch on the profile name, so nothing in the slice waits on the answer. User-defined profiles default to sending it and can opt out through config, with no code change. This matches the "independently deliverable" guideline and the project's no-string-dispatch rule.

### [PASS] Failure modes are enumerated for each new I/O path with signals and tests

The table covers stream failure mid-loop, no usage reported, malformed usage, backend rejection of new parameters, batch budget exhaustion, an all-failed batch, and a hung read. Each row has a stated behavior, an observable signal (WARNING or above), and a named test. This meets the failure-mode enumeration criterion apart from the stream-hang gap noted above.

### [PASS] NFR handling and integration points are explicit

The 900 architecture defines no NFRs, and the doc says so. It restates the one constraint it does have (usage reading stays cheap inside the event loop, and blocking reads stay off the loop). Integration points with 924, 927, 195, `collect_turn`, and the failure artifact are named, and the interface parity requirement between `sq review` and `sq run` is stated.

### Run Digest

- Response length: 7124 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
