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
reviewedSha: 280ebf991ba3091537a733a4a54865ec41314f1c
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
turns: 8
promptTokens: 451317
cachedTokens: 354322
cacheWriteTokens: 96983
completionTokens: 4898
durationSeconds: 40.8
costUsd: 0.473031
costBasis: provider
runId: run-20261017-slices-plan-d9bcbe25
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Event-action authority rules are respected"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#D1 — Eligibility"
  - id: F002
    severity: pass
    category: scope
    summary: "Scope reduction is justified and the plan entry already reflects it"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Overview"
  - id: F003
    severity: concern
    category: dependency-direction
    summary: "Events layer gains a dependency on the pipeline layer, and the dependency graph is not stated"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Component Structure"
  - id: F004
    severity: concern
    category: scope-creep
    summary: "Atomic-write change to the shared `update_frontmatter` primitive is scope beyond the slice's deliverable"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Component Structure (Atomic frontmatter write)"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Design weight is high relative to a \"stamp usage into frontmatter\" requirement"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Technical Scope"
  - id: F006
    severity: concern
    category: under-specification
    summary: "Cross-run accumulation semantics are under-specified and conflict with the \"resumed run\" risk"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#D2 — Loop rounds / Risk Assessment"
  - id: F007
    severity: concern
    category: error-handling
    summary: "Failure modes for the new I/O paths are mostly covered but two gaps remain"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#D6 — Failure modes"
  - id: F008
    severity: note
    category: dry
    summary: "Positive: single key definition and reader consolidation"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#D4 — One key table, one reader"
  - id: F009
    severity: note
    category: integration
    summary: "Provides/consumes for 179 and 175/176 are consistent"
    location: "project-documents/user/slices/178-slice.artifact-usage-stamping.md#Integration Points"
---

# Review: slice — slice 178

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Event-action authority rules are respected

`usage-stamp` is a POST_ACTION built-in that mutates a file. It never reads `result.outputs` and never alters the `ActionResult`. It relies on the dispatcher's stop-at-first-failure ordering instead of re-checking the post-condition. This matches the 140-arch events section (observe / fail / mutate; "may not read `result.outputs`").

### [PASS] Scope reduction is justified and the plan entry already reflects it

The slice drops summary and compact stamping because neither writes a frontmatter artifact. Plan entry 34 already says "Summary and compact write no frontmatter artifact, so their usage stays in run state only (178 design)". Nothing assigned to the slice is lost.

### [CONCERN] Events layer gains a dependency on the pipeline layer, and the dependency graph is not stated

`events/builtin/usage_stamp.py` imports `pipeline/artifact_usage`, and `dispatch_artifact` imports pipeline-layer path helpers. Meanwhile the pipeline executor fires events. 140-arch presents events as separate machinery that reuses only `ActionResult` and `ValidationError`. The slice handles this by amending the arch doc (Development Approach step 5). That records the new edge but does not remove the cycle risk between `pipeline` and `events`.

`ArtifactUsage`, `fold` and the key constants are pure data and have no pipeline dependency. They could sit in `review/`, beside `RunCost` and `frontmatter_usage`, which the design already treats as the shared home for key definitions. `events` and `stats` would then both depend only on `review/` for this. The design should do that, or state the import graph and show it is acyclic.

### [CONCERN] Atomic-write change to the shared `update_frontmatter` primitive is scope beyond the slice's deliverable

Changing `documents/frontmatter.update_frontmatter` to temp-file-and-rename alters behavior for `revision-stamp` and the devlog action. Neither is part of this slice. It is justified as risk mitigation for corrupting a design doc, but `revision-stamp` has run that same primitive on every loop round without it. The slice does not say why atomicity is needed now, such as an observed failure or a new write-timing risk. Also, `update_frontmatter` appears to be where an in-place `path.write_text` would be kept, so a failed write there leaves the file untouched in most cases.

Either defer this to a separate fix (standing slice 944) and keep the stamp on the existing primitive, or state the concrete failure it prevents and keep it as step 1. As written, it is shared-infrastructure risk traded for a hypothetical.

### [CONCERN] Design weight is high relative to a "stamp usage into frontmatter" requirement

The slice touches about 12 modules and adds four new files. Several parts can be cut or deferred without losing the plan entry's deliverable (stamp artifacts, extend `sq stats` to read them):

- **Split-task handling.** It stamps the first part, so a round that rewrote only `-2` also dirties `-1` in that round's commit. This is the most intricate rule in D1 and exists for 13 historical files. Stamping whichever candidate was written, or only the sole file, would be lighter. Alternatively, defer split handling and log a WARNING when more than one part exists.
- **The `sq stats artifacts` subcommand, renderer and `fit_widths` table.** The `artifact spend` line on `sq stats slice` plus `artifacts_usage_report` for 179 already meet the requirement. The standalone command has no named consumer.
- **`pricedRounds` as well as `usageRounds`, the restart-detection WARNING, and per-key malformed-value handling.** These are three overlapping mechanisms for one "floor" caveat.
- **Wrapper doc updates for `/sq:stats` and `sq-stats`.** They only matter if the new subcommand stays.

The finding is to name what is cut or deferred. At minimum, the standalone `artifacts` subcommand and split-part special-casing should be justified against a named requirement or removed.

### [CONCERN] Cross-run accumulation semantics are under-specified and conflict with the "resumed run" risk

D2 says the stamp counts dispatches that wrote this file "from any run". The Risk section admits that on a resumed run or after a manual edit, a dispatch that wrote nothing still passes the post-condition and its spend is stamped on the existing artifact. Re-running a step with `existing: overwrite` (or a resume that re-dispatches) therefore double-counts or misattributes spend. The Functional Requirements assert totals "equal to the sum of its rounds' dispatch records in run state". That only holds for a single uninterrupted run, and the design does not say so.

The design should restrict the success criterion to that case, or add an idempotency guard such as recording the last-folded run and step in the stamp. Otherwise `artifacts_usage_report` is handed to 179 as a "floor" that can also overcount. It is described only as an undercount.

### [CONCERN] Failure modes for the new I/O paths are mostly covered but two gaps remain

D6 is thorough for the stamp: path resolution, parse, write and malformed keys each have a behavior and a log signal. Two gaps:

- **Cf client call that hangs.** D6 lists only "cf error" for path resolution. `dispatch_artifact_paths` calls `cf_client` on every eligible dispatch, which is a subprocess call. A hang or timeout has no stated bound or handling. The same call already exists in the post-condition, so say explicitly that the stamp inherits that call's timeout, or reuse its candidate list instead of resolving again.
- **Stats-side reads.** `sq stats artifacts` reads every top-level `*.md` in three directories. The design says nothing about volume (hundreds of slice files) or a concurrent write while a run is in progress. A half-written file is covered by the atomic write, but that depends on the contested `update_frontmatter` change above.

Neither is blocking, but each needs one line of explicit handling.

### [NOTE] Positive: single key definition and reader consolidation

Routing review persistence and the stamp through `RunCost.frontmatter_fields()`, and moving `_record` into a shared reader, removes duplicated key definitions. The byte-identical review output and unchanged `sq stats reviews` output are testable acceptance criteria. This matches the project's "define once" rule.

### [NOTE] Provides/consumes for 179 and 175/176 are consistent

`artifacts_usage_report` and `ArtifactUsage` are a clear contract for 179, and the dependencies on 175 and 176 are stated. There is no NFR in 140-arch that this slice touches, so no restatement is required.

### Run Digest

- Response length: 7936 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 8
- Tokens — prompt / cached / cache write / completion / reasoning: 451317 / 354322 / 96983 / 4898 / not computed
- Duration: 40.8 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
