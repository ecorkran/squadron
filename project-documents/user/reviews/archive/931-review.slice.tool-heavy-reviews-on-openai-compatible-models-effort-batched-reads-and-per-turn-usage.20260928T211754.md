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
reviewedSha: fc47c8e4dcb89d52ab7669bc2586bff9cd645a0e
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
runId: run-20260928-slices-plan-783dab3a
squadronVersion: 0.15.1
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Slice bundles three changes against \"small and focused\" and \"independently deliverable\""
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Technical Scope"
  - id: F002
    severity: concern
    category: scope
    summary: "Part A adds a new user-facing capability, which the architecture excludes"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Overview"
  - id: F003
    severity: concern
    category: alignment
    summary: "The design cannot be verified against the architecture's slice-plan reference"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md:5"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated with signals and tests"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#D12 — Failure modes and their signals"
  - id: F005
    severity: pass
    category: nfr
    summary: "NFR restated with a specific target"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Special Considerations"
  - id: F006
    severity: pass
    category: architecture
    summary: "Dependency direction and abstraction boundaries are sound"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Component Structure"
  - id: F007
    severity: note
    category: risk
    summary: "Merge precondition on the Gemini probe is explicit"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Mitigation Strategies"
---

# Review: slice — slice 931

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Slice bundles three changes against "small and focused" and "independently deliverable"

The architecture says to prefer many small slices and to keep each independently deliverable. This slice ships three parts (A, B, C) that touch about 20 components across `core`, `models`, `pipeline`, `cli`, `providers` (three of them), `review`, `tools`, and data files. The slice admits that "the three parts could each ship alone."

The justification (shared measurement, shared files, PM bundling) is reasonable and recorded. It is still a deliberate departure from the guideline. The doc also adds a merge precondition that gates the whole bundle on a Gemini probe. A gate on one part blocks the other two, which is the coupling the guideline is meant to avoid. Splitting C from B and A would let B and A land without waiting on the Gemini result.

### [CONCERN] Part A adds a new user-facing capability, which the architecture excludes

The architecture says new features or capabilities belong in a feature initiative. The slice argues it is maintenance because each part fixes a defect. That holds for B (a read pattern) and C (an under-reporting digest line). It is weaker for A. A new alias field `effort`, a new `Effort` vocabulary, a new capability flag, and provider mappings are a new configuration capability, not a fix. The doc says "The new surface is two optional inputs," and that concedes the point.

The doc has no basis for calling this "an effort nobody chose" a defect rather than an enhancement. A short note in the doc, or a PM decision recorded against the architecture's scope rule, would settle it.

### [CONCERN] The design cannot be verified against the architecture's slice-plan reference

The frontmatter `parent` points to `900-slices.maintenance-and-refactoring.md`, which is the slice plan. That is fine per the review instructions. The architecture document itself defines no NFRs, boundaries, or layers beyond scope and guidelines, so the slice's layering claims cannot be checked against a parent. The dependency-direction rules (`review/` imports only `core.usage` and `providers.errors`) are the slice's own invention. They look sound but nothing above the slice checks them.

### [PASS] Failure modes are enumerated with signals and tests

D12 covers the new I/O paths: mid-loop stream failure, missing usage, malformed usage, backend rejection, batch budget, all-fail batch, and hung reads. Each has a behavior, an observable signal, and a test. The one exception (raw `httpx` errors outside the conversion list) is explicitly marked "unchanged" rather than left implicit. The hung-read case is a documented non-fix with reasoning. This meets the failure-mode criterion.

### [PASS] NFR restated with a specific target

The architecture states no NFRs, and the slice says so. It restates the one constraint it does have: usage reading in `_stream_turn` stays under the 1 ms event-loop rule, and blocking reads stay inside a single `asyncio.to_thread` call.

### [PASS] Dependency direction and abstraction boundaries are sound

Provider-neutral `TokenUsage` and `RunTelemetry` live in `core/usage.py`. The OpenAI wire-format reader stays in `providers/openai/usage.py`. `review/` never imports the OpenAI package. The design avoids string dispatch on profile name and offers a per-profile field as the fallback. Capability gating mirrors the slice 924 `applies_output_budget` precedent. The `agent.py` size overage is handled by putting the reader in its own module.

### [NOTE] Merge precondition on the Gemini probe is explicit

The unresolved fact (Gemini `stream_options`) is named, given a concrete probe, and given a decision tree, including "stop and ask the PM" if the probe stays unreachable. This is good practice. It does make the slice's mergeability depend on an external service's availability.

### Run Digest

- Response length: 5120 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
