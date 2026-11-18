---
docType: review
layer: project
reviewType: code
slice: real-bug-review-recall
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/430-slice.real-bug-review-recall.md
aiModel: openai/gpt-6.1-sol
aiProfile: openrouter
status: complete
dateCreated: 20261118
dateUpdated: 20261118
reviewedSha: fd7e6b0892b7674201c513221bcad2de96557efb
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
diffTruncated: false
turns: 10
promptTokens: 1634962
cachedTokens: 1444545
completionTokens: 3430
reasoningTokens: 1918
durationSeconds: 125.4
costUsd: 0.559589
costBasis: alias_pricing
squadronVersion: 0.24.33
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Reject non-finite cost limits before dispatch"
    location: "src/squadron/benchmark/recall/run_bound.py:119-120"
  - id: F002
    severity: concern
    category: correctness
    summary: "Empty comb stages consume budget despite making no call"
    location: "src/squadron/benchmark/recall/run_loop.py:160-165"
  - id: F003
    severity: concern
    category: type-contract-debt
    summary: "Malformed grading fields abort the entire import"
    location: "src/squadron/benchmark/recall/hand_run_labels.py:159-161"
  - id: F004
    severity: concern
    category: correctness
    summary: "Unparseable findings discard already-read cost telemetry"
    location: "src/squadron/benchmark/recall/stage_ingest.py:104-108"
---

# Review: code — slice 430

**Verdict:** FAIL
**Model:** openai/gpt-6.1-sol
**Evidence:** 9 successful tool call(s) of 9 made; 429474 of 429474 diff characters reached the model

## Findings

### [FAIL] Reject non-finite cost limits before dispatch

`--max-cost nan` passes this validation because `NaN <= 0` is false. `ReviewBudget` also accepts it, and its subsequent `spent >= cap` checks are always false, disabling the dollar cap. Infinity is accepted too. Additionally, the `call_cost` branch at lines 137–138 accepts non-finite or non-positive figures.

Validate cost inputs with `math.isfinite()` and explicit positivity checks before auth preflight or dispatch. Add tests proving NaN, infinity, zero, and negative figures are refused without making calls.

### [CONCERN] Empty comb stages consume budget despite making no call

`run_stage()` returns `empty_comb_entry()` without invoking a subprocess when its input is empty. The loop nevertheless increments `plan_calls` for a plan-billed comb, or charges the fallback review figure because the empty entry has `cost_usd=None`.

For example, an empty review followed by two plan-billed combs with a cap of one records the first no-op as a call and stops before the second, although neither requires a model request. Priced no-ops similarly consume the dollar budget.

Represent whether a call occurred explicitly and avoid charging or applying call caps to no-op stages. Cover both billing modes in loop-level tests.

### [CONCERN] Malformed grading fields abort the entire import

The loader verifies only that each grading document is a JSON object. `_issue_list()` then unpacks `issues` and `new_issues` without validating their shapes; valid JSON such as `{"issues": null}` raises an uncaught `TypeError`. Likewise, an issue with `"members": null` crashes `_assignments()` at line 188.

These errors bypass `plan.skip()`, preventing other valid files from importing and violating the documented bad-file handling behavior. Validate grading documents through a Pydantic boundary schema and report invalid files with the existing WARNING/skip mechanism. Add malformed-shape tests alongside the existing bad-reference tests.

### [CONCERN] Unparseable findings discard already-read cost telemetry

`ingest_output()` reads usage and effort into `call` before parsing findings. If findings parsing raises `ReviewOutputError`, the exception branch returns a failure entry retaining only `raw_ref`, discarding valid usage already extracted from the document.

A response with a recorded cost but malformed findings therefore gets charged at the fallback figure in `run_loop`, potentially undercounting actual spend and allowing more calls than the dollar cap permits. It also removes that observed cost from future estimates.

Preserve successfully parsed usage on configuration-failure entries, as the no-decision-line branch already does. Add a regression test with valid cost telemetry and invalid findings that checks both the stored usage and budget accounting.

### Run Digest

- Response length: 3462 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: stop
- Output budget: backend default
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 992
- Effort: backend default
- Turns: 10
- Tokens — prompt / cached / cache write / completion / reasoning: 1634962 / 1444545 / not computed / 3430 / 1918
- Duration: 125.4 s
- Cost: $0.56 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4
