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
reviewedSha: c8f0e2b64b721a17e1e4f7b2db4fe52bb8ef80fe
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 278547
cachedTokens: 183111
cacheWriteTokens: 95428
completionTokens: 5273
durationSeconds: 46.3
costUsd: 0.453433
costBasis: provider
runId: run-20261015-p4-08d36a4f
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Alignment with the slice plan entry and the architecture boundaries"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#Technical Decisions"
  - id: F002
    severity: concern
    category: error-handling
    summary: "D3 does not say what happens to rounds spent in a loop that never completes"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D3 — Persist every loop round"
  - id: F003
    severity: concern
    category: under-specification
    summary: "`--json` contract is promised in the criteria but deferred in the design"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md:244"
  - id: F004
    severity: concern
    category: hidden-dependency
    summary: "Prerequisites 321 and 941 are not declared in frontmatter or the plan entry"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md:6"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Weight to cut or defer"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D5 / #D2 / #Technical Scope"
  - id: F006
    severity: note
    category: architecture-alignment
    summary: "Commit-subject matching is a justified exception to the label-as-structure rule"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D5 — Task attribution through prescribed commit subjects"
  - id: F007
    severity: note
    category: failure-modes
    summary: "Git call count is bounded per report but grows with history"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D6 — Review rounds come from git, not run state"
  - id: F008
    severity: note
    category: scope
    summary: "Parent architecture does not yet describe effort or producer reporting"
    location: "project-documents/user/architecture/140-arch.pipeline-foundation.md"
  - id: F009
    severity: pass
    category: error-handling
    summary: "Failure modes, NFR restatement and testability"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D9 — Failure modes"
---

# Review: slice — slice 176

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with the slice plan entry and the architecture boundaries

- The design delivers (a), `sq stats runs`, and the observed half of (b) from plan entry 32.
- It moves the replay runner, pairwise judge and metrology record to entry 33, which the plan entry already records.
- It answers both questions the plan left open: whether (b) splits, and whether to adopt an eval tool. The rationale for borrowing only the method is concrete.
- Dependency direction is correct. The slice reads run state, git and planning docs, adds no executor, action or step-type machinery, and writes nothing (success criterion 9).
- The change to `StepState` follows the architecture's state model and uses the same additive, no-version-bump pattern as 175.

### [CONCERN] D3 does not say what happens to rounds spent in a loop that never completes

- D3 persists rounds in `_append_step`, so earlier rounds are saved only when the loop step is written to state.
- The Value section claims "Loop cost becomes correct". The doc does not say what is recorded for a loop that is interrupted, stalled, paused at a checkpoint, or resumed (`sq run --resume`) partway through its rounds.
- If `prior_rounds` lives only in the executor's memory, the rounds spent before the interruption are lost. Those are the runs most likely to have spent extra.
- D9 lists no row for this, so the undercount stays and no signal reports it.
- Fix: either state that the partial-loop case is out of scope and make the reports say `partial loop not recorded`, or persist per-round progress at round boundaries. Add a D9 row and a test either way.

### [CONCERN] `--json` contract is promised in the criteria but deferred in the design

- Success criterion 8 says `--json` "emits the D7 / API Contracts keys". D7 defines no JSON keys, and the API Contracts section gives only the planning-doc and git dataclasses.
- Line 244 says a fixed cross-project key contract waits until something consumes pooled data.
- The Value section sells "Data that can be pooled" as a benefit of this slice. Dataclass-field serialization with no stable keys does not deliver that.
- Fix: either specify the top-level keys per report (the verification walkthrough already assumes `levels[].measures`), or reword criterion 8 and the Value bullet to say the JSON mirrors the table and is unstable until a consumer exists.

### [CONCERN] Prerequisites 321 and 941 are not declared in frontmatter or the plan entry

- The frontmatter and plan entry say `dependencies: [175]`.
- The Prerequisites section also relies on 321, for the `metrology.min_evidence_n` config key, and on 941, for the committed-rounds guarantee that D6 depends on.
- Both are marked complete, so nothing is blocked. The declared dependency list is still incomplete, and the D1 change that dropped 320 removed only one of the related entries.
- Fix: add 321 and 941 to the frontmatter. Alternatively state that completed slices are listed as prerequisites only, and apply that rule consistently.

### [CONCERN] Weight to cut or defer

- **Per-task `Effort` parsing and summing (D2).** The doc says no task file from 160–175 has per-task effort. If the plan entry makes it mandatory, keep it, but record that it is exercised only by old `100`-band fixtures.
- **`--since`, `--pipeline`, and `sq stats runs`' separate renderer.** They add surface that nothing in the plan entry requires beyond `--slice` filtering. Consider deferring them.
- **Task groups and extra-commit counts (D5.2).** This is the heaviest mechanism: first-parent window walking, marker matching and group boundaries. It works only for the few slices since 174 that prescribe commit subjects (the doc cites 175 and 16 markers), while D5.3–D5.5 give slice-level numbers for everyone. The plan entry does assign per-task grouping, so keep it. Say plainly in Risk that the heavy path covers a small share of history.
- None of these is a blocker.

### [NOTE] Commit-subject matching is a justified exception to the label-as-structure rule

- D5 explains why exact subject text is the only task-to-commit link in existing history. A non-match surfaces as `marker not found` and is counted in the footer, never silently misattributed. That satisfies the intent of the rule.
- The same applies to review artifact names (D6) and to `status: complete` read from frontmatter (D4).

### [NOTE] Git call count is bounded per report but grows with history

- The "2 + V" bound is honest. `sq stats slices` covers every completed slice, so V (one `git show` per review artifact version) can reach hundreds of subprocess calls, each with its own timeout.
- The parent architecture states no latency NFR for reports, so this is not a violation. Consider either stating an expected V for this repo, or batching reads with `git cat-file --batch`, to keep a hang from stacking timeouts.
- The failure rows already say a skipped round is a WARNING plus a footer count.

### [NOTE] Parent architecture does not yet describe effort or producer reporting

- The architecture's out-of-scope section says cost and usage reporting are in scope as of slice 175. Nothing there mentions reading git history or planning documents, or reporting producer effectiveness.
- The slice commits to updating the run-state section with three `StepState` fields on landing. Add a one-line scope note about the 176 reports in the same edit, so the architecture and slice do not drift.

### [PASS] Failure modes, NFR restatement and testability

- D9 lists a handling strategy and an observable signal (WARNING, footer count, or exit 1) for each new git call and parser path.
- Hang, timeout and missing-object cases go through `run_git` rather than being implicit.
- Success criteria require a test for every row and a test of the call count.
- The parent architecture states no NFR for this path, so none needs restating.

### Run Digest

- Response length: 7576 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 278547 / 183111 / 95428 / 5273 / not computed
- Duration: 46.3 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
