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
reviewedSha: f46dc5f58d4c62fd0fc10398d0d9741f1b5456ef
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
runId: run-20260928-slices-plan-783dab3a
squadronVersion: 0.15.1
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Slice bundles three changes and sits at the edge of the initiative's scope"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Technical Scope"
  - id: F002
    severity: concern
    category: architecture
    summary: "Dependency direction: `review` layer imports from `providers/openai`"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Component Structure"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Failure modes for the new I/O paths are only partly enumerated"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Technical Decisions"
  - id: F004
    severity: note
    category: risk
    summary: "Risk on `stream_options` is deferred to Phase 6 instead of being resolved in design"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Risk Assessment"
  - id: F005
    severity: note
    category: nfr
    summary: "NFRs"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Special Considerations"
  - id: F006
    severity: pass
    category: architecture
    summary: "Consistency with existing patterns and boundaries"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#Technical Decisions"
---

# Review: slice — slice 931

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Slice bundles three changes and sits at the edge of the initiative's scope

The 900 architecture says slices should be "small and focused" and that "prefer many small slices over few large ones". It also says new features or capabilities belong in a feature initiative, not here. Slice 931 combines three changes: an effort setting, batched reads, and per-turn usage and timing.

- Together they touch about 20 components across core, models, pipeline, CLI, three providers, review, persistence, tools, and data.
- They also change the persisted artifact contract (new frontmatter keys), the JSON output, and the `read_file` tool schema.
- The slice orders the work C → B → A, and each part is independently deliverable. B and A do not depend on each other.
- The per-alias `effort` field and the `paths` parameter are new user-facing capabilities. They are arguably features rather than maintenance.

Splitting it into three slices, or at least recording in the doc why the bundle stays together, would fit the architecture better. The bundling rationale is that the review runs C first so it can measure B and A. That rationale is not stated as a reason to keep them together. The scope is defensible as operational and performance work under this initiative, but the doc should say so.

### [CONCERN] Dependency direction: `review` layer imports from `providers/openai`

`TokenUsage`, `LoopTelemetry`, and the shared `_add` summing helper go into `providers/openai/usage.py`.

- D8 says `turn_capture` imports `_add` from that module.
- `ReviewResult` in `review/models.py` carries the same token fields.
- That makes provider-agnostic review code depend on one concrete provider's package. It also puts that dependency on the SDK and Codex paths, which use the same `ReviewResult`.
- The slice itself says SDK and Codex usage is a follow-up, so these types will need to be shared soon.

`TokenUsage` and the summing helper are provider-neutral. Place them in a neutral location such as `core/`, or in `providers/` above the openai subpackage. Keep only the chunk-usage reader in `providers/openai`.

### [CONCERN] Failure modes for the new I/O paths are only partly enumerated

The doc covers these cases explicitly:

- an empty final turn (`EmptyFinalTurnError.telemetry`)
- a backend that omits usage fields
- a backend that rejects the effort level (400 → `ProviderAPIError`)
- a per-file `read_file` failure
- a backend that rejects `stream_options` (Risk Assessment)

Two cases are missing:

1. **Stream failure mid-loop.** The stream can time out, or the peer can disconnect mid-turn. That raises an error other than `EmptyFinalTurnError`. The accumulated `LoopTelemetry` is then lost, and it is unclear whether the failed review artifact records partial turns, usage, or duration. `durationSeconds` is described as "always on a `review_client` result", but the error path is not covered.
2. **Observability.** The project's failure-mode rule requires each failure to be observable (a log at WARNING or above, or a metric) and to have a test that asserts the signal. The Technical Requirements test list does not include one for these paths. Examples are a missing usage chunk, a usage chunk that arrives with malformed detail objects, and a batch that hits the byte budget. Missing usage silently becomes `not reported`, and the doc does not say whether that is logged.

`read_file` batching keeps all reads in one `asyncio.to_thread` call. The doc does not say whether a hung read (a FIFO or a network mount) inside a batch is bounded. D5 rejects special files, so this may be covered, but it should be stated.

### [NOTE] Risk on `stream_options` is deferred to Phase 6 instead of being resolved in design

The risk is that every OpenAI-compatible request now sends `stream_options`. That could break Gemini or Ollama, which the doc says "need confirming". The mitigation is a live run per profile and, if needed, a profile-level opt-out field. That is a reasonable plan and it avoids dispatching on the profile name. It also means a regression could ship for backends not reachable during Phase 6. Consider stating what happens if a profile cannot be reached before merge.

### [NOTE] NFRs

The 900 architecture defines no NFRs, so there is nothing to restate. The slice's own event-loop constraint (under 1 ms) and its single worker hop per batch are stated.

### [PASS] Consistency with existing patterns and boundaries

The design follows the slice 924 pattern:

- an alias field with a single reader
- the value carried on `ResolvedModel` and `AgentConfig`
- gating by a capability flag
- recording only the value that was actually sent

It uses a closed enum, the same validate-warn-skip handling as `max_output_tokens`, and no string dispatch on profile names. D2 declines an extra CLI flag and pipeline key. That matches the project's rule to resist adding complexity. D6 keeps the batch output under the per-result floor and adds a test that ties the two constants together. Codex warns loudly instead of claiming an effort that was not sent.

### Run Digest

- Response length: 6177 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
