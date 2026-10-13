---
docType: review
layer: project
reviewType: slice
slice: review-and-revise-loop-from-sq-review-max
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261012
dateUpdated: 20261012
reviewedSha: a93703d3c099b7a377a0ce01a69dfe344fed7688
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 29.3
runId: run-20261013-p4-55015267
squadronVersion: 0.21.6
findings:
  - id: F001
    severity: concern
    category: scope-creep
    summary: "Shared loop executor change is scope beyond the plan entry"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#Technical Scope (item 6) and D5"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Validation and guard mechanisms are heavier than the requirement needs"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#D6 and D2"
  - id: F003
    severity: concern
    category: under-specification
    summary: "Per-round progress output is not tied to a pipeline hook"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#Data Flow, API Contracts"
  - id: F004
    severity: note
    category: error-handling
    summary: "Failure modes are enumerated with observable signals"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#D5"
  - id: F005
    severity: note
    category: architecture
    summary: "Composition over extraction is well justified"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#D1, D4"
---

# Review: slice — slice 941

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Shared loop executor change is scope beyond the plan entry

Item 6 and the D5 table change `_execute_loop_body`, so a failed round commit ends the loop. This changes behavior for every P4, P5 and P6 pipeline run, not just `sq review --max`. The 941 plan entry says nothing about modifying shared executor semantics. The motivation is sound: a failed commit would otherwise let the next round sweep an uncommitted revision into a later commit. But it is a standalone bug fix that carries cross-pipeline blast radius.
- Either move it to the standing fixes slice 944 (the repo's bug-fix rule says fixes don't get their own slice) and make 941 depend on it.
- Or keep it here and amend the plan entry to name it, with a regression test showing the existing pipelines' behavior on commit failure.

### [CONCERN] Validation and guard mechanisms are heavier than the requirement needs

The slice adds several guard layers beyond the plan entry's `--max` and `--revise-model`, which makes it heavy for an effort of 3/5.
- **`MAX_SUPPORTED_OPTIONS` allowlist.** It uses Click `ParameterSource` inspection to reject every other option. A short explicit list of the options that conflict with the loop would meet the requirement without a generic refuse-by-default mechanism.
- **Dirty-tree refusal for `code`.** This adds a check, an error format and a test.
- **Slice-branch check for `code`.** This duplicates branch logic that P6 already owns.
- **Shape checks in D2.** Three separate override-shape checks cover hypothetical user overrides of P4/P5/P6. Keep the zero-or-multiple-loop check. The `until` and `skip_if_met` checks could collapse into one "loop shape unsupported" error.

Cut or defer the dirty-tree and branch guards if the PM accepts the sweep-in risk, and simplify the option allowlist. If any are kept, say which plan requirement each one protects.

### [CONCERN] Per-round progress output is not tied to a pipeline hook

The example stdout shows per-round verdicts, finding counts, short commit SHAs and the filename. The final step in the Data Flow diagram says it prints these from `execute_pipeline`'s result. The design never says what `execute_pipeline` returns or exposes for per-round data, and the Interfaces Required table lists no result or progress type. This is a hidden dependency. It is not yet clear that the information exists without either changing the executor or parsing logs. State the source (result type or callback) and what happens when a field is unavailable. Otherwise the output contract is a promise the implementation may not be able to keep.

### [NOTE] Failure modes are enumerated with observable signals

D5 covers the review or revise hang and timeout (inherited), the commit failure (WARNING log plus stderr), Ctrl-C, and the dirty tree. It also maps each to an exit code, with tests for the commit-failure and dirty-tree rows. The 900 architecture states no NFRs for this path, so nothing needs restating.

### [NOTE] Composition over extraction is well justified

D1 resolves the "run the loop only" versus "extract the loop" question the plan entry left open. It does this without duplicating loop YAML or restructuring shipped pipelines. D4 explains why run state is omitted and why `on_exhaust` becomes `fail`. Both decisions stay inside the pipeline package boundary and match the plan's requirement that loop changes propagate automatically.

### Run Digest

- Response length: 4585 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 29.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5

## Response (20261012)

- **F001 — fixed outside the slice.** The loop commit fix landed on main as a standalone fix (85a7f7aa) with its own regression test. Scope item 6 and the D5 row now treat it as inherited.
- **F002 — declined.** `MAX_SUPPORTED_OPTIONS` stays: refusing unknown options by default is the project's no-silent-fallback rule, and a deny-list would let new options be silently ignored. The `code` branch check stays because without it revisions commit to whatever branch is checked out, including `main`. The dirty-tree check stays because `code` round commits run `git add -A`. Merging the D2 shape checks into one error is cosmetic.
- **F003 — fixed.** New D7: `RunObserver.round_completed` is called after each round's commit, and the CLI's `RoundPrinter` builds the per-round lines from it, with defined output for a failed commit and for a round with no changes.
- **F004, F005 — notes, no action.**
