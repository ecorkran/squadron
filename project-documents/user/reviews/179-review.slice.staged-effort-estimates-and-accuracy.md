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
reviewedSha: 8d6de0cf06227841582b8fb705522b4eecc922bb
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 365746
cachedTokens: 271235
cacheWriteTokens: 94501
completionTokens: 4411
durationSeconds: 40.1
costUsd: 0.449921
costBasis: provider
runId: run-20261017-slices-plan-d9bcbe25
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction match the architecture"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Architecture"
  - id: F002
    severity: concern
    category: under-specification
    summary: "Version selection and ordering across branches is under-specified"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#D3 — Reading the history within 176's git bound"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Accuracy section is heavier than the evidence it can produce"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#D6 — Accuracy is rank correlation, with n"
  - id: F004
    severity: note
    category: scope
    summary: "The slice drops 178 as a dependency and defers some scope, and says so"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Dependencies"
  - id: F005
    severity: note
    category: dependency
    summary: "External prerequisite gates integration, not build"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Prerequisites"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for each new I/O path"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#D7 — Failure modes"
  - id: F007
    severity: pass
    category: integration
    summary: "Contract with 176 and 941 is stated and consistent"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#D3 — Reading the history within 176's git bound"
---

# Review: slice — slice 179

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layering and dependency direction match the architecture

The new `effort` key sits in `documents/schema.py`, which the architecture's package structure lists as the home for document-level primitives. `stats/` cores contain no Typer code. `stats/git_history.py` remains the only module that runs git, and `reestimate_instruction` is a plain helper rather than an Action. The `dispatch` action keeps its listed responsibilities. The slice also states its link to the architecture's cost and usage reporting scope, and plans to amend the Non-goals line.

### [CONCERN] Version selection and ordering across branches is under-specified

D3 runs `git log --all -G '^effort:'`, so candidate commits can come from unmerged branches, rebased or cherry-picked duplicates, and other worktrees. D2 then defines an estimate as a version whose `effort` "differs from the previous committed value", and `EstimateHistory.estimates` is in "ancestry order".

The document never says three things:
- Which commit set forms the linear sequence: HEAD's first-parent line only, or every ref.
- How versions on divergent branches are ordered.
- How a duplicate of the same change is de-duplicated.

Collapsing consecutive equal values only helps once a linear order exists. Without one, `design`, `final` and `drift` can differ from run to run. They are the inputs to every accuracy row, so this is a correctness gap, not only a presentation one.

Fix: either restrict candidates to commits reachable from HEAD on the first-parent line, or state the tie-break and de-duplication rule. Add a test for a divergent-branch case.

### [CONCERN] Accuracy section is heavier than the evidence it can produce

The plan entry asks for per-stage estimates, history, and "an accuracy measure". The design delivers a separate `estimate_accuracy.py` core, four `AccuracyRow` values crossed with every `Measure`, two floor reasons (`below floor`, `no spread`), a shared-set rule for three rows, and a footer. By the design's own account, three of the four rows read `below floor` until designs carry `effort` (Consumes from Other Slices; Verification Walkthrough step 4). The remaining row, `plan (all)`, needs no design-stage data at all.

Cuts to consider:
- Ship `plan (all)` plus a single shared-set row group for `design` and `final`, and add the others when data exists. #232 already collects deferred work.
- Drop `final` as a separate row for now, since it equals `design` when there was no revision.
- Fold the "no spread" and "below floor" distinction into one placeholder, with the reason in JSON only.

Related: the five-value `EstimateStage` plus the full review-type to stage mapping serves a per-stage view that this slice itself defers to #232. Only `plan`, `design` and the latest value feed the reports. Keep the stage labels for the `sq stats slice` line, but check the mapping carries no more than that line needs.

### [NOTE] The slice drops 178 as a dependency and defers some scope, and says so

The plan entry lists `[176, 178]`. The design moves the `artifact_spend` measure, `--stage` grouping and the rollup drift line to #232, and amends the plan entry's dependencies to `[176]` (Implementation Notes step 6). The plan entry's wording ("per-stage estimates and an accuracy measure") is still met, and the deferral is explicit, so this is acceptable. Make sure the plan amendment and the #232 issue land in the same commit as the design, so the plan and design do not disagree.

### [NOTE] External prerequisite gates integration, not build

ai-project-guide#43 is open and outside this repo. The design handles it by saying the code builds and tests without it, and that Phase 7 integration waits for it (walkthrough step 3). That is a visible, bounded dependency. The slice's value (design-stage estimates) does not exist without that issue, which is worth tracking on the slice plan.

### [PASS] Failure modes are enumerated for each new I/O path

D7 covers a `git log -G` failure, a `git show` failure, a frontmatter parse failure, an invalid value, a removed key, a missing design, a non-integer `min_evidence_n`, and an unresolvable design at revise time. Each row names a behavior and an observable signal (WARNING, count, or exit 1), and Technical Requirements requires a test per row. No parent-architecture NFR applies to this path.

### [PASS] Contract with 176 and 941 is stated and consistent

The git-call budget is restated explicitly (3 + V + E) and the existing call-count test is updated to match. Reports stay read-only, and the only write is the revising agent's own one-line edit, constrained by the prompt and checked by the walkthrough.

### Run Digest

- Response length: 6086 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 365746 / 271235 / 94501 / 4411 / not computed
- Duration: 40.1 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
