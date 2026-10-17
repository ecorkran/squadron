---
docType: review
layer: project
reviewType: slice
slice: artifact-usage-stamping
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/178-slice.artifact-usage-stamping.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261016
dateUpdated: 20261016
reviewedSha: 9277fa19d66feef7d73e0b21c256012e6e6022c5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 394678
cachedTokens: 309348
cacheWriteTokens: 85320
completionTokens: 3325
durationSeconds: 28.3
costUsd: 0.406149
costBasis: provider
runId: run-20261017-slices-plan-d9bcbe25
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Summary and compact dropped from the plan-assigned scope"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Overview"
  - id: F002
    severity: concern
    category: architecture-boundary
    summary: "Event-action authority rule is stretched, not honored"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#D1 — Eligibility"
  - id: F003
    severity: concern
    category: dependency-direction
    summary: "Pipeline layer depends on the stats reporting layer"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#D4 — One key table, one reader"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Proportionality: some mechanisms exceed what the slice needs"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Technical Scope"
  - id: F005
    severity: concern
    category: under-specification
    summary: "Heuristic file attribution and the multi-file task case"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#D1 — Eligibility"
  - id: F006
    severity: note
    category: error-handling
    summary: "Failure modes are well enumerated"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#D6 — Failure modes"
  - id: F007
    severity: pass
    category: integration
    summary: "Integration points and refactor safety"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Integration Points"
---

# Review: slice — slice 178

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Summary and compact dropped from the plan-assigned scope

Plan entry 34 assigns stamping of "every artifact with frontmatter that dispatch, summary and compact write". The slice narrows this to dispatch only. The reasoning is sound: compact writes no file, and the summary `file` emit has no frontmatter block. But it is still a deviation from the plan entry. The slice plan entry and the arch statement of what 175's usage capture covers should be amended in the same change, so 179 and later readers don't expect summary and compact stamps. Step 5 of the development approach only updates `140-arch`, not the plan entry.

### [CONCERN] Event-action authority rule is stretched, not honored

`140-arch` (Events section) says an event action "may not read `result.outputs`". D1 reads `result.outputs` for `SKIPPED_KEY`. The slice justifies this by precedent in `dispatch-artifact` and `revision-stamp`, but it never reconciles the precedent with the architecture text. Either the architecture rule needs an explicit carve-out for `SKIPPED_KEY`, or the keep-detection should move to an explicit field on the result. Its claim that missing outputs in prompt-only mode can't cause a wrong stamp holds only because usage is also absent there. That is an incidental coupling, not a guarantee. Resolve it in the arch doc update the slice already plans.

### [CONCERN] Pipeline layer depends on the stats reporting layer

`pipeline/artifact_usage.read_artifact_usage` is specified to use `stats/frontmatter_usage.record_from_frontmatter`. That makes the pipeline/domain layer import from a reporting module, and the stamp action (events → pipeline) would then transitively depend on `stats`. The key table is already shared via `review/run_cost.py`. The frontmatter-to-`UsageRecord` reader belongs beside it, in `review/` or `core/`, and `stats` and `pipeline` should both depend downward on it. Placing it there keeps dependencies pointing one way and costs nothing extra.

### [CONCERN] Proportionality: some mechanisms exceed what the slice needs

The slice must preserve cost by stage past pruning and feed 179. Several parts go beyond that:
- The `usagePartial` sticky flag and the `CostBasis.MIXED` enum member. Mixed-basis handling is a new enum value that touches every cost-basis renderer. The slice could omit `costBasis` once rounds disagree.
- The agent-rewrite detection, which needs a `revision_number` versus `usageRounds` heuristic and its own warning.
- `--json` on `artifacts`, with no named consumer; 179 reads `artifacts_usage_report` directly.
- The separate `ArtifactKindDir` enum alongside the existing `ArtifactKind`.
Cut or defer `--json`. Decide whether `MIXED` and `usagePartial` are required by 179 or can follow later.

### [CONCERN] Heuristic file attribution and the multi-file task case

For a tasks slice that writes several task files, the stamp is skipped with a WARNING. That means P5 spend is silently absent from `sq stats artifacts` for multi-file task breakdowns, while Success Criteria says "A P5 run stamps the task file". The slice doesn't say how common multi-file output is. It also doesn't say whether the stamp should go to a primary file or whether `sq stats slice` should surface "spend not attributed". Define the expected behavior for that case, or state that it is accepted as a known gap with a count visible in the report. Also, the mtime-since-`run_started_at` rule is shared with the post-condition. A resumed run, or an unrelated edit during the run, could stamp the wrong file. Acknowledge that in Risk.

### [NOTE] Failure modes are well enumerated

D6 lists each new I/O path (resolution, read, write, malformed prior keys, unreadable files in the report) with a handling strategy and an observable signal. Success Criteria requires a test for each. It matches the "never fails a run" convention. No NFR from the parent architecture applies to this path, and the slice states a bounded cost of one read and one write per dispatch.

### [PASS] Integration points and refactor safety

The stamp runs as a POST_ACTION built-in after `revision-stamp`, in registration order, and stops when `dispatch-artifact` fails. That is consistent with the events model and with the planned `140-arch` ordering update. Moving path resolution into one shared module, and keeping review output byte-identical, are both pinned by existing tests. The 179 consumer interface is clear and independent of run state.

### Run Digest

- Response length: 5335 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 394678 / 309348 / 85320 / 3325 / not computed
- Duration: 28.3 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
