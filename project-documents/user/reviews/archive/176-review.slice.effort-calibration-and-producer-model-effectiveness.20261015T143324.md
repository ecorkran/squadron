---
docType: review
layer: project
reviewType: slice
slice: effort-calibration-and-producer-model-effectiveness
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: f3d652e04ad1cd7fa1754737fc12613851c26444
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 363126
cachedTokens: 268114
cacheWriteTokens: 95002
completionTokens: 4883
durationSeconds: 43.5
costUsd: 0.456333
costBasis: provider
runId: run-20261015-p4-08d36a4f
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: hidden-dependency
    summary: "Hidden dependency on the 320 metrology config after the dependency was dropped"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D8 — Observed producer effectiveness"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`git cat-file --batch` has no enumerated failure handling"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D9 — Failure modes"
  - id: F003
    severity: concern
    category: integration
    summary: "Replay-slice integration promise has no defined interface"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#Integration Requirements"
  - id: F004
    severity: concern
    category: scope
    summary: "Proportionality: scope that nothing uses yet"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D7 — Report shapes"
  - id: F005
    severity: note
    category: dry
    summary: "Verdict-acceptance rule duplicated"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D6 — Review rounds come from git"
  - id: F006
    severity: note
    category: documentation
    summary: "Persisted state change should be reflected in the architecture document"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#State Management"
  - id: F007
    severity: pass
    category: architecture
    summary: "Layering and dependency direction"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#Component Structure"
  - id: F008
    severity: pass
    category: scope
    summary: "Plan alignment of the #210 split and stated honesty of reports"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D1 — #210 splits: observed report here, replay and judging in a follow-on"
---

# Review: slice — slice 176

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Hidden dependency on the 320 metrology config after the dependency was dropped

The plan entry now says "Dependencies now [175]", and the frontmatter lists only `[175]`. But D8 gates the producer report on `metrology.min_evidence_n`, "the existing key, default 5". That key belongs to the 320 metrology store. D4 also cites "the 320 reference rule" as the authority for `status: complete`. The slice therefore reads a 320-owned config key and relies on a 320 convention, and neither appears under Prerequisites or Interfaces Required.

Two things are unspecified:
- How the key is read.
- What happens if it is missing or invalid. The "default 5" is a magic default, and project rules require centralizing such defaults in config.

Either declare 320's config and reference rule as prerequisites and say how the key is loaded and validated, or give this slice its own centrally defined threshold.

### [CONCERN] `git cat-file --batch` has no enumerated failure handling

D6 introduces a long-lived `git cat-file --batch` subprocess as a new I/O path. D9 covers `run_git` returning `None` and an unreadable frontmatter version. It does not cover failures specific to a streaming child process:
- The process hangs.
- It dies mid-stream, giving a truncated read.
- A requested object is `missing`. This is plausible in shallow clones and with archive blobs.

`run_git` (`review/git_utils.py`) is a one-shot wrapper with a timeout, and the design never says how the batch process gets an equivalent. It also states that `stats/git_history.py` is "the only module that runs git", yet the batch process cannot go through `run_git`. Add D9 rows for hang or timeout, mid-stream exit, and `missing` objects. Each needs an explicit behavior (fail the report, never a partial one) and an observable signal.

### [CONCERN] Replay-slice integration promise has no defined interface

Integration Requirements say the replay follow-on can obtain "the commit that added the original artifact, plus its parent, from `git_history` alone". "Provides to Other Slices" repeats this. The API Contracts define only `WindowSource` and `ReviewRound` for `git_history`, and nothing that returns an artifact's introducing commit or its parent. As written, this is an acceptance criterion with no supporting design. Either specify the function and its failure modes, or drop the claim and let the follow-on slice define it. Dropping it also removes speculative scope (see the proportionality finding).

### [CONCERN] Proportionality: scope that nothing uses yet

The design is large for its effort rating of 3/5. It adds four subcommands, four new `stats/` modules, a state schema change, a four-way window resolver, and a fixed cross-project JSON contract. These items can be cut or deferred:
- **By-kind table and `Kind` parsing.** The tag format does not exist yet (ai-project-guide#42), and the design admits no file carries one. Every row would read `untagged`. Parsing and rendering are speculative until the format lands. Defer them to a patch once the tag exists. The plan entry only requires the "untagged" bucket.
- **The `markers` window fallback.** It is a third heuristic on top of `branch` and `merge`, and it is described as inferring a range from the first to the last matched marker. Show `none` and `unavailable` when neither a branch nor a merge exists.
- **Replay-oriented provisions in `git_history`.** See the previous finding.
- **A fixed JSON key contract justified by "pooling later".** Nothing consumes the pooled data. A versioned, minimal schema is enough, and the full key list can follow with the consumer.
- **`squadron_version`, `generated_at` and `project_root` on every report.** Keep only what pooling needs once pooling exists.

Cutting these keeps the work the plan entry actually assigns: #214 reports, the observed producer report, and `sq stats runs`.

### [NOTE] Verdict-acceptance rule duplicated

D6 and D8 each define "accepted" as PASS or CONCERNS. The loop's own `until` condition already encodes this in the executor (the condition grammar was deferred to 149). The design should reference one shared definition so the reports cannot drift from loop semantics. The Technical Requirements already forbid bare string comparisons.

### [NOTE] Persisted state change should be reflected in the architecture document

D3 adds `prior_round_results`, `accepted` and `exhausted` to `StepState` without a schema version bump. This is additive and consistent with 175's precedent. The state-file example in `140-arch.pipeline-foundation.md` and its resume semantics do not mention loop rounds. Add that to the architecture document when this slice lands.

### [PASS] Layering and dependency direction

The `stats/` cores take injected inputs (`StateManager`, `GitHistory`, project root) and return typed reports. They contain no Typer code, and the CLI layer only renders. Dependencies point from `stats` into `pipeline.state` and `review.git_utils`, never the reverse. The pipeline change is confined to persisting data the executor already produces (`StepResult.prior_rounds`, `accepted`, `exhausted`), so it stays within the architecture's state and resume responsibilities. The no-write requirement (Functional Requirement 9) holds. Old run files still load through defaults.

### [PASS] Plan alignment of the #210 split and stated honesty of reports

The plan entry explicitly leaves the decisions on splitting (b) and on adopting an eval tool to this design. D1 makes both, and the plan entry already records the outcome (the split, effort now 3/5, and the replay work moved to entry 33). Assigned scope is kept: `slice`, `slices`, `producers` (the observed form) and `runs` are all present. D2 (ordinal effort, distributions with n) and D8 (below-floor marking, observational caveat) are sound. The D9 failure table covers most new paths, apart from the gap noted above.

### Run Digest

- Response length: 7622 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 363126 / 268114 / 95002 / 4883 / not computed
- Duration: 43.5 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
