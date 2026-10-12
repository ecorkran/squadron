---
docType: review
layer: project
reviewType: code
slice: proportionate-reviews-review-and-revise-loops-that-can-cut-scope
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261011
dateUpdated: 20261011
reviewedSha: 3634988e58fd8a3e43bb26ac8b17095a33034d61
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
diffTruncated: false
durationSeconds: 25.8
squadronVersion: 0.21.4
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Guidance asks for a GitHub issue but says nothing about what to do if the model can't create one"
    location: "src/squadron/pipeline/actions/dispatch.py:294-299"
  - id: F002
    severity: note
    category: design
    summary: "The scope-cutting guidance also applies to the generic fix loop, not just `feedback: review` revisions"
    location: "src/squadron/pipeline/actions/dispatch.py:586"
  - id: F003
    severity: pass
    category: dry
    summary: "Single source for the constant, and tests reference it instead of copying the text"
    location: "tests/pipeline/actions/test_dispatch.py:11"
  - id: F004
    severity: pass
    category: testing
    summary: "Edge cases are covered: the fallback path and the no-findings path"
    location: "tests/pipeline/actions/test_dispatch.py:760-778"
  - id: F005
    severity: pass
    category: error-handling
    summary: "No new I/O, error handling, or concurrency surface"
    location: "src/squadron/pipeline/actions/dispatch.py:586"
---

# Review: code — slice 943

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] Guidance asks for a GitHub issue but says nothing about what to do if the model can't create one

`REVISE_GUIDANCE` tells the revise model to "record each deferral as a GitHub issue named in the artifact." Nothing in `_findings_block` or `_resolve_feedback_prompt` (lines 559–620) checks that the dispatched model can actually create issues, for example through `gh` or a tool. If it can't, the instruction still requires an issue reference in the artifact. The most likely result is a made-up issue number that looks real.

This is the failure mode the project's "Hallucination traps in prompts" section warns about: an instruction to produce a value from a source that may not be available. It also breaks the "never use silent fallback values" principle, because a made-up issue number is a silent fallback.

Suggested fix: say what to do when an issue can't be filed, and say it explicitly. For example: "If you cannot create the issue, mark the deferral `DEFERRED (issue not yet filed)` and list it in your response." Either an issue gets filed or there is a visible placeholder, never an invented number.

### [NOTE] The scope-cutting guidance also applies to the generic fix loop, not just `feedback: review` revisions

`_findings_block` is shared with `_resolve_prompt_from_prior_review` (lines 590–594), which drives the judge-gated fix/review loop from slice 303. That loop can run against code as well as planning artifacts. So the "defer only scope the artifact's plan does not require" instruction now reaches those fix loops too, where "artifact's plan" may not mean anything clear.

The new test `test_fallback_path_appends_revise_guidance` shows this is intended, so this needs no action. It's worth confirming that the wording still reads correctly for code-fix pipelines.

### [PASS] Single source for the constant, and tests reference it instead of copying the text

The tests import `REVISE_GUIDANCE` rather than repeating the string, so editing the wording only touches one place. The existing full-prompt assertion was updated to the new layout.

### [PASS] Edge cases are covered: the fallback path and the no-findings path

`test_fallback_path_appends_revise_guidance` checks that the guidance is appended at the end of the non-feedback path. `test_no_findings_prompt_omits_revise_guidance` checks that the early return at lines 568–572 does not include it, which is correct because there are no findings to resolve.

### [PASS] No new I/O, error handling, or concurrency surface

The change only extends prompt text. It adds no new failure modes, exception paths, or shared state.

## Response

- **F001 (CONCERN): fixed.** `REVISE_GUIDANCE` now says that when the model cannot create the issue it writes `issue not filed` where the number would go and says so in its reply, and that it must never write an issue number GitHub did not return. The design's quoted paragraph was updated to match.
- **F002 (NOTE): no change.** Reaching the fallback fix loop is intended (design, F008 of the design review). For a code fix, the artifact's plan is its slice design and task file, so the deferral rule still reads correctly.

### Run Digest

- Response length: 3480 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 25.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
