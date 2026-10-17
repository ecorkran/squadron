---
docType: review
layer: project
reviewType: slice
slice: staged-effort-estimates-and-accuracy
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261016
dateUpdated: 20261016
reviewedSha: 0b37bbb061c4c90a20ac8571c80a2a202a1044c6
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 103899
cachedTokens: 11028
cacheWriteTokens: 92867
completionTokens: 4375
durationSeconds: 38.0
costUsd: 0.416993
costBasis: provider
runId: run-20261017-slices-plan-d9bcbe25
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Overweight: accuracy table, `--stage` grouping and drift line are built before any data exists"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Technical Scope (items 6, D5, D6)"
  - id: F002
    severity: concern
    category: dependency
    summary: "`artifact_spend` measure couples this slice to unimplemented slice 178"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Dependencies, #Integration Points"
  - id: F003
    severity: concern
    category: hidden-dependency
    summary: "Value depends on an external ai-project-guide change that is not a tracked prerequisite"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Dependencies (companion issue), D4"
  - id: F004
    severity: concern
    category: correctness
    summary: "Stage labelling relies on author-date ordering, which is fragile"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#D2"
  - id: F005
    severity: concern
    category: architecture-boundary
    summary: "Re-estimate helper placed under `pipeline/actions/` although it is not an Action"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Component Structure"
  - id: F006
    severity: concern
    category: scope
    summary: "Behavior change to all `feedback: review` revise prompts, with an unquantified side effect on agent edits"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#D4, #Risk Assessment"
  - id: F007
    severity: note
    category: scope
    summary: "Reporting is outside the 140 architecture's stated surface"
    location: "project-documents/user/architecture/140-arch.pipeline-foundation.md"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for every new I/O path"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#D7"
  - id: F009
    severity: pass
    category: conventions
    summary: "Code-structure conventions are honored"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Technical Requirements"
---

# Review: slice — slice 179

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Overweight: accuracy table, `--stage` grouping and drift line are built before any data exists

Verification step 4 says that after implementation the `plan`, `design` and `final` rows all read `below floor`. No completed design carries `effort`, and 14 of 149 designs mention it in prose, which the slice declines to read. For the foreseeable future the slice therefore ships machinery that renders no result:
- `--stage plan|design|final` grouping, with its `unestimated` row.
- A 4-row by 7-measure Spearman table with floor and no-spread handling.
- A drift line.
- A new `estimate_accuracy.py` module and a `stage` parameter on the rollup.

Only the first of the four accuracy rows, `plan (all)`, has data today. It correlates the plan estimate with outcomes, which 176 already supports.

Cut or defer to a follow-up slice that lands once the companion template change has produced real design-stage data:
- `--stage` and `estimate_accuracy.py`.
- The `plan`/`design`/`final` accuracy rows and the drift line.

The core value is the writing side (`effort` key, re-estimate prompt) plus the per-slice history in `sq stats slice`. That is enough to start collecting data. The accuracy rollup can wait until it has something to measure.

### [CONCERN] `artifact_spend` measure couples this slice to unimplemented slice 178

178 is "designed, not implemented". The slice adds `Measure.ARTIFACT_SPEND` and a new column in the default `sq stats slices` table. That column is not part of the estimate-accuracy goal, and it makes the "default output unchanged" guarantee conditional on 178. Integration Points says the column "waits for it", but the Success Criteria (7) and Verification (4) assume it exists. This is a hidden build ordering. Remove `artifact_spend` from this slice, since it belongs with 178 or a later slice. If it stays, make the 178 dependency an explicit gate on Success Criteria 7 and Verification 4.

### [CONCERN] Value depends on an external ai-project-guide change that is not a tracked prerequisite

The design says the companion issue "is not a build dependency", yet it is the only mechanism that makes designers write the first `effort`. D4 deliberately stops revise rounds from adding a first estimate. Until the companion issue lands, the design stage is empty for every pipeline-produced design, the history is plan-only, and the whole reader/report stack runs on nothing. Either treat the issue as a delivery gate for this slice (a task with an owner), or let P4's own prompt (squadron-owned) ask the designer for the first `effort`, so the slice is self-sufficient. Filing the issue in "implementation step 1" does not close the dependency.

### [CONCERN] Stage labelling relies on author-date ordering, which is fragile

A stage comes from "the latest review round committed strictly before it: earlier author date, and not in the same commit". Author dates are not monotonic along history. Rebases, cherry-picks, amends, merges of slice branches and equal-second timestamps all break this. A mislabel would silently move an estimate between `design` and `after-slice-review` and corrupt the accuracy comparison. The design neither states the mitigation nor lists the case in D7. Order by commit topology (position in the `git log` output, which the single whole-history pass already provides) rather than by date. Failing that, state the limitation and add a test with equal or out-of-order dates.

### [CONCERN] Re-estimate helper placed under `pipeline/actions/` although it is not an Action

140 defines `src/squadron/pipeline/actions/` as the home for implementations of the Action protocol, registered in the action registry. `reestimate.py` is a plain prompt-text helper that calls `resolve_slice_info` from the review package. It sits in that directory only because `dispatch.py` does. It blurs the layer definition, and it adds a `pipeline → review/persistence` dependency that the design does not call out. Put it beside the other prompt-building helpers, or inline it in `dispatch.py`. If it stays in `actions/`, say that it is deliberately a non-action helper.

### [CONCERN] Behavior change to all `feedback: review` revise prompts, with an unquantified side effect on agent edits

Appending a paragraph that invites frontmatter edits changes every revise prompt, including `sq review --max` and the judge and findings-addressed cycles. The design says this "does not bias a comparison". But the instruction gives a revising agent a reason to open and rewrite the design, which is exactly the case 178 D2 notes can drop frontmatter keys. The interaction with the 911 revision-stamp (a POST_ACTION that mutates design frontmatter) is not addressed, and neither is the 172/173 commit-time frontmatter gate. The design has no test for the stamp or the gate preserving or rejecting `effort`. Add a success criterion that a revise round followed by the stamp and gate keeps `effort` intact, and add that failure to D7.

### [NOTE] Reporting is outside the 140 architecture's stated surface

The 140 architecture defines no stats or metrology layer. The slice builds on 175/176, and its parent chain is the slice plan, so this is acceptable. The slice correctly excludes routing by effort, which the architecture lists as out of scope ("Automated complexity estimation for model selection"), and it leaves the executor and state model unchanged.

### [PASS] Failure modes are enumerated for every new I/O path

D7 covers the `git log -G` failure (WARNING, then exit 1), `git show` failure, unparseable frontmatter, invalid values, a removed key, and an unresolvable slice in the revise step. Each has an observable signal, and the Technical Requirements demand a test per row. Git calls are bounded as 3 + V + E and stay inside `GitHistory`, consistent with 176's rule that it is the only module that runs git. The design also states the rejection of silent fallbacks by skipping and counting bad values.

### [PASS] Code-structure conventions are honored

The key name is defined once as `EFFORT_ESTIMATE_KEY`. Stages, rows and measures are enums, and the review-type to stage mapping is a single dict. The prompt avoids an example value near the slot, so it does not create a hallucination trap. The parser rules are met by lenient reading plus a test on the real commit shape.

### Run Digest

- Response length: 7933 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 103899 / 11028 / 92867 / 4375 / not computed
- Duration: 38.0 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
