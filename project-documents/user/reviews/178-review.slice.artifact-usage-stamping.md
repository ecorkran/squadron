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
reviewedSha: 22c305850d747adeb52d0ab4427a3b188817b7bd
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 392963
cachedTokens: 351090
cacheWriteTokens: 41863
completionTokens: 6167
durationSeconds: 49.8
costUsd: 0.264914
costBasis: provider
runId: run-20261017-slices-plan-d9bcbe25
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Stamp conforms to the events authority model and ordering rules"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#D1 — Eligibility"
  - id: F002
    severity: pass
    category: scope
    summary: "Scope narrowing is justified and reflected in the plan"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Overview"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Write safety of the second frontmatter write is not specified"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Risk Assessment"
  - id: F004
    severity: concern
    category: correctness
    summary: "\"Total equals sum of rounds\" criterion contradicts the D2 floor behaviour"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Functional Requirements"
  - id: F005
    severity: concern
    category: attribution
    summary: "Stamped file may not be the file the dispatch wrote"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#D1 — Eligibility"
  - id: F006
    severity: note
    category: dependency-direction
    summary: "Events package takes a dependency on pipeline-layer usage types"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Component Structure"
  - id: F007
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable; one candidate cut"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#D5"
---

# Review: slice — slice 178

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Stamp conforms to the events authority model and ordering rules

`usage-stamp` is a POST_ACTION mutate action registered after `revision-stamp`. It reads `result.metadata` and never `result.outputs`, which stays inside the 140-arch rule at line 124. The chain-stops-on-failure behaviour is used correctly: because `dispatch-artifact` runs first, the stamp runs only after the post-condition passed. The stamp never fails the step, which matches the 911 D4 precedent. `disable:` still works. The slice also plans to update the arch events tree and ordering note, so the architecture document will not drift.

### [PASS] Scope narrowing is justified and reflected in the plan

Slice plan entry 34 already says summary and compact stay in run state. The dependencies, `[175, 176]`, match the plan, and the interface to 179 is stated. The exclusions (back-fill, `--json`, `costBasis`, and the review-after-prune gap with its own issue) keep the slice small.

### [CONCERN] Write safety of the second frontmatter write is not specified

The plan rates this slice Med risk because every phase dispatch now rewrites a human-authored design document. D6 covers `OSError` as "no stamp" and the risk section says "a stamp bug could corrupt a design document". Neither says whether `update_frontmatter` writes atomically (temp file plus rename) or in place. A crash or kill during an in-place write would leave a truncated design or task file. That is the "peer dies mid-write" case, and the design does not address it. The stamp also runs after `revision-stamp`, so each revision round now has two such writes. Either confirm that `update_frontmatter` is atomic, or add an atomic-write requirement and a test for the failure.

### [CONCERN] "Total equals sum of rounds" criterion contradicts the D2 floor behaviour

A functional requirement says a loop-revised design's total equals the sum of its rounds in run state. D2 concedes that an agent rewrite which drops the keys restarts the total and `usageRounds`, making the stamp "a floor". The criterion therefore holds only when the agent preserves the keys. Two things follow:
- Nothing tells a reader the number is a floor. The `sq stats artifacts` output and the `artifact spend` line present it as authoritative. 179 is meant to read it as the durable source for estimate accuracy.
- A restart is indistinguishable from a first round. Dropped keys on a revision round produce no signal at all, even though D6 lists every other degraded case with a WARNING.

Qualify the criterion. Consider also warning when the stamp finds no prior keys on a dispatch that is not the file's first, if the context carries enough to tell. A short note in the 179 "Provides" section should say the total can undercount.

### [CONCERN] Stamped file may not be the file the dispatch wrote

D1 says the stamp runs once a candidate "was written this run". It then stamps the first candidate in suffix order, not the candidate that was written. For a split task breakdown, a round that rewrote only `-2` stamps `-1`, which changes a file the dispatch never touched. This is deliberate, and the design explains it. Two parts are unspecified:
- The design does not say whether `dispatch_artifact_paths` returns only existing files. If it can include nonexistent paths, the first candidate may be one that does not exist, and the failure falls under a generic WARNING.
- The extra diff on an untouched file goes into the per-round commit.

State the existence assumption, and add a test for a round that rewrites only the later part.

### [NOTE] Events package takes a dependency on pipeline-layer usage types

Arch lines 120-122 describe events as separate machinery that reuses only `ActionResult` and `ValidationError`. The stamp now imports `UsageRecord` and `pipeline/artifact_usage`. The direction (events → pipeline → review) has no cycle, and `dispatch-artifact` already depends on pipeline path helpers. Still, the arch sentence is no longer strictly true. Amend it when the arch events tree is updated in Development Approach step 5. `stats` importing `ArtifactKind` from `pipeline` follows the same pattern.

### [NOTE] Proportionality is acceptable; one candidate cut

The refactors (key table, reader move, path extraction) remove duplication that this slice would otherwise add, so they stay. The `artifact spend` line on `sq stats slice` duplicates `sq stats artifacts --slice N`. It falls under the plan's "extends `sq stats`" wording, so it is not scope creep. If effort runs over the 3/5 estimate, it is the first thing to defer.

### Run Digest

- Response length: 5687 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 392963 / 351090 / 41863 / 6167 / not computed
- Duration: 49.8 s
- Cost: $0.26 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
