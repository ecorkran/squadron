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
reviewedSha: 9f0fa457b2c6e8a89f7316f426729864e3e3ba33
revision_number: 3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
runId: run-20260928-slices-plan-783dab3a
squadronVersion: 0.15.1
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Slice weight runs against the initiative's \"small and focused, lighter-weight\" guidance"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Technical Scope"
  - id: F002
    severity: concern
    category: scope
    summary: "Part A's alias field sits at the edge of the \"no new features\" exclusion"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Initiative fit"
  - id: F003
    severity: concern
    category: dependencies
    summary: "Slice frontmatter lists only 924 as a dependency, though 927 and 195 are consumed"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md:6"
  - id: F004
    severity: pass
    category: architecture
    summary: "Layering and dependency direction are explicit and checkable"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Dependency direction"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated with handling, signal and test for each I/O path"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#D12 — Failure modes and their signals"
  - id: F006
    severity: pass
    category: risk
    summary: "The unverified Gemini fact does not gate the slice"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Mitigation Strategies"
  - id: F007
    severity: note
    category: nfr
    summary: "No NFRs in the parent architecture; the slice states its own event-loop constraint"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Special Considerations"
  - id: F008
    severity: note
    category: maintainability
    summary: "`agent.py` already exceeds the 300-line guideline"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Special Considerations"
---

# Review: slice — slice 931

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Slice weight runs against the initiative's "small and focused, lighter-weight" guidance

The 900 architecture says to prefer many small slices over few large ones, and to keep the process lighter-weight given the maintenance nature. This slice bundles three parts (A, B, C). It adds a new `core/usage.py` module, a new `providers/openai/usage.py`, and a new profile flag. It rewires six credential call sites, extends `ProviderError`, adds new frontmatter, digest and JSON keys, and lists 12 D12 failure-mode rows.

The doc handles this well. It records the bundle as a PM decision and orders the parts C → B → A, each a separately revertible commit. It also names B as the part to cut into its own slice if the work runs long, and says A and C must stay together. That mitigates the concern but does not remove it. Treat the B cut-out as a real trigger, not an aspiration, and consider deciding it at task breakdown instead of mid-implementation.

### [CONCERN] Part A's alias field sits at the edge of the "no new features" exclusion

The architecture excludes "new features or capabilities". The doc admits the effort mapping is "the weakest of the three mappings" and argues the recorded level is a fix and the alias field is the smallest enabling control. The argument is reasonable. It follows the 924 `max_output_tokens` precedent and adds no CLI flag, pipeline key or new workflow (D2). But a user-settable reasoning level that changes model behavior is a user-visible capability, whatever the framing.

The doc's splitting of the "fix" half from the "control" half is the right defense. Keep that split visible in the task file. Then, if the PM disagrees on the "control" half, it can be dropped without losing the recording fix.

### [CONCERN] Slice frontmatter lists only 924 as a dependency, though 927 and 195 are consumed

`dependencies: [924]`, but the Dependencies section lists 927 (the per-chunk `chunk.model` read that usage extends) and 195 (the provider-failure artifact that D12 extends) as prerequisites. All three are complete, so nothing blocks. Still, the machine-readable dependency list understates what the slice touches. List them, or state why they are excluded.

### [PASS] Layering and dependency direction are explicit and checkable

The 900 architecture defines no layers, and the doc says so. It derives the rule from CLAUDE.md, `review-code.md` (Dependency Inversion) and the current import graph. `review/` imports only shared provider modules, and the new neutral `core/usage.py` is a leaf. The doc addresses the existing `core` ↔ `providers` coupling and shows that the new edges cannot form a cycle. Two grep checks are proposed as enforcement.

### [PASS] Failure modes are enumerated with handling, signal and test for each I/O path

D12 covers connect and request failure, mid-stream disconnect, stream stall, a usage chunk that never arrives, malformed usage, backend rejection, batch budget exhaustion, all-files-fail, and a hung read. The two unbounded cases (a trickling stream, a hung read) are declared as unchanged behavior and explained, not left as "TBD". Every signal is WARNING or above. The mid-stream `httpx` conversion closes a real gap, since the raw exception would otherwise produce a traceback and no artifact.

### [PASS] The unverified Gemini fact does not gate the slice

Gemini ships with `sends_stream_usage = False` as a declared per-profile field, not string dispatch on the profile name. Its requests stay as they are today. The follow-up is tracked, and the D12 no-usage WARNING makes the gap observable.

### [NOTE] No NFRs in the parent architecture; the slice states its own event-loop constraint

The 900 architecture defines no NFRs, and the doc says so. It restates the one constraint that applies: per-chunk usage reading stays well under 1 ms, and blocking reads stay inside `asyncio.to_thread`.

### [NOTE] `agent.py` already exceeds the 300-line guideline

The slice keeps the growth small by putting the usage reader in its own module and declares the split of `agent.py` out of scope. That is acceptable for a maintenance initiative. The split does fit this initiative's Refactoring scope, so file it as an issue in line with the project's practice.

### Run Digest

- Response length: 5710 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
