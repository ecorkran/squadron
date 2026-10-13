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
reviewedSha: ede19d6a753c23a7c63f442b7763b2ba08ff1424
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 33.3
runId: run-20261013-p4-55015267
squadronVersion: 0.21.6
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "Review-step extraction from the loop body is under-specified"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#D2 — The loop and review config come from the loaded pipeline"
  - id: F002
    severity: concern
    category: hidden-dependency
    summary: "Zero-round behavior depends on an unverified `skip_if_met` in the shipped loops"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md:79-81"
  - id: F003
    severity: concern
    category: error-handling
    summary: "A failed round commit lets the loop keep revising"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md:132"
  - id: F004
    severity: note
    category: proportionality
    summary: "The option-allowlist mechanism is heavier than the plan requires"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#D6 — Option validation"
  - id: F005
    severity: note
    category: integration
    summary: "Exit code 2 and line-number references need confirming"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md:125-134"
  - id: F006
    severity: pass
    category: alignment
    summary: "Scope and boundaries match the plan entry"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#Technical Scope"
---

# Review: slice — slice 941

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Review-step extraction from the loop body is under-specified

D2 defines errors only for zero or multiple loop steps. The builder also copies "the loop body's review action config" into the leading review step, and that is a second hidden dependency on the shape of P4/P5/P6. The doc doesn't say what happens if the loop body has no review action, has more than one, or if the review has a different shape in one pipeline. Integration Points covers only the loss of the loop itself. Add an explicit error for 0 or more than 1 review actions in the loop body, and a unit test for it. Without that, a pipeline edit could silently produce a wrong review step.

### [CONCERN] Zero-round behavior depends on an unverified `skip_if_met` in the shipped loops

Success Criterion 2 (a PASS on the first review runs zero rounds) relies on the mapped pipeline's loop having `skip_if_met` and an `until` condition. The data flow presents this as inherited behavior. But D1 and D2 take the loop from whatever `load_pipeline` returns, including project and user overrides. If an override drops `skip_if_met`, a PASS design still gets a revise round. State the assumption and add a check or test that fails clearly when the loop lacks it. Alternatively, have the runner skip the loop itself when the first review already passes.

### [CONCERN] A failed round commit lets the loop keep revising

D5 accepts that the loop "records the failed commit result and continues". The runner only reports exit 1 after the loop finishes. For `code`, round commits use `git add -A`, so uncommitted edits from the failed round get swept into the next round's commit. The slice and tasks commits stage only the artifact and review paths, so they leave an unreviewed gap. The slice itself worries about this kind of contamination in the dirty-tree rule. Either stop the loop on the first failed commit, or explain why continuing is safe. The failure is observable (stderr plus a WARNING log), but its consequences aren't handled.

### [NOTE] The option-allowlist mechanism is heavier than the plan requires

The plan asks only that `--max` and `--revise-model` be declared options. The `MAX_SUPPORTED_OPTIONS` allowlist, which uses Click `ParameterSource`, is extra, and so are the dirty-tree and branch checks for `code`. These are defensible under the "no silent fallback" rule and are small. If effort runs over 3/5, the cheaper cut is to refuse a short explicit list of known-incompatible options and defer the default-deny allowlist.

### [NOTE] Exit code 2 and line-number references need confirming

Exit code 2 for FAIL or an unaccepted exhausted loop should match what the existing `sq review` verdict exit codes mean, so scripts see the same codes. The doc doesn't say whether it does. The interface table also cites line numbers such as `loader.py:148`, which will drift. Cite the symbol names only.

### [PASS] Scope and boundaries match the plan entry

The scope matches plan entry 35, including the explicit exclusions: MCP, resume, and `sq run --from`. Rejecting `sq run P4 --from loop-1` and the choice to compose `[review, loop]` rather than extract the loop respect DRY and leave the pipelines unchanged. The failure modes for hangs, timeouts, interrupts and commit failures are enumerated in D5 with exit codes. The doc names no NFR targets, and none appear to apply.

### Run Digest

- Response length: 4872 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 33.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
