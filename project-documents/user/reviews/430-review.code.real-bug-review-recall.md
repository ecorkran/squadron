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
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/430-slice.real-bug-review-recall.md
aiModel: openai/gpt-6.1-sol
aiProfile: openrouter
status: complete
dateCreated: 20261118
dateUpdated: 20261118
reviewedSha: f6f1d6a845db4474c776447d87c1b2d016aa8d74
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
diffTruncated: false
turns: 8
promptTokens: 1339034
cachedTokens: 1144281
completionTokens: 2849
reasoningTokens: 1505
durationSeconds: 107.9
costUsd: 0.532424
costBasis: alias_pricing
squadronVersion: 0.24.33
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Unparseable review responses are recorded as successful reviews"
    location: "src/squadron/benchmark/recall/stage_ingest.py:98-112"
  - id: F002
    severity: concern
    category: correctness
    summary: "Parsing failures discard usage already read from the output"
    location: "src/squadron/benchmark/recall/stage_ingest.py:98-108"
  - id: F003
    severity: concern
    category: correctness
    summary: "No-call comb entries make otherwise known recipe costs unavailable"
    location: "src/squadron/benchmark/recall/stage_ingest.py:74-76"
  - id: F004
    severity: concern
    category: type-contract-debt
    summary: "Malformed import schemas can abort the import instead of being skipped"
    location: "src/squadron/benchmark/recall/hand_run_labels.py:159-161"
---

# Review: code — slice 430

**Verdict:** CONCERNS
**Model:** openai/gpt-6.1-sol
**Evidence:** 7 successful tool call(s) of 7 made; 431992 of 431992 diff characters reached the model

## Findings

### [CONCERN] Unparseable review responses are recorded as successful reviews

The review branch accepts any document containing a `findings` list and unconditionally records `StageOutcome.OK`. However, the production review parser can return `verdict: UNKNOWN` with an empty findings list when no review could be parsed; `ReviewResult.to_dict()` preserves that verdict.

Such an output is therefore stored as a successful zero-finding review instead of the documented `config_failure`, without the required stage-specific warning. Validate the review result’s semantic status, distinguishing a legitimate empty PASS from an unparseable response. Add a regression test using the production parser’s degraded output shape.

### [CONCERN] Parsing failures discard usage already read from the output

`call` collects usage and sent effort before findings are parsed, but the `ReviewOutputError` handler preserves only `raw_ref`. For example, a document with valid `cost_usd` and `effort` but malformed `findings` loses both fields.

The run loop subsequently charges the fallback figure rather than the reported cost, potentially allowing additional calls after actual spend has reached the cap. Preserve successfully validated telemetry when classifying malformed result content, and test that a config-failure entry retains its reported usage.

### [CONCERN] No-call comb entries make otherwise known recipe costs unavailable

`empty_comb_entry()` represents a stage where no model call occurred, but it inherits `StageUsage()` with `cost_usd=None`. In `scoring_metrics._cost()`, any entry with an unknown cost makes the entire recipe’s cost unavailable.

Consequently, a fully priced review that returns no scored findings causes every downstream comb to turn the recipe’s cost into “not recorded,” even though those stages cost exactly zero. Represent no-call stages explicitly as zero-cost, or exclude them from missing-cost detection. Add a report test covering a priced empty review followed by combs.

### [CONCERN] Malformed import schemas can abort the import instead of being skipped

The grading-file boundary validates only that JSON is an object. `_issue_list()` then unpacks `issues` and `new_issues` without validating their types: `{"issues": null}` raises `TypeError`. Likewise, `members: null` fails in `_assignments()`.

The review importer has a related gap: invalid `StageConfig` field types raise Pydantic `ValidationError`, which `_plan_one()` does not convert into a skipped-file record. These errors terminate planning rather than logging the offending file, continuing with valid files, and reporting skips as promised.

Validate imported document shapes with Pydantic boundary models and convert validation failures into `plan.skip(...)`. Add tests mixing malformed-schema files with valid files to verify continued import and WARNING observability.

### Run Digest

- Response length: 3610 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: stop
- Output budget: backend default
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 510
- Effort: backend default
- Turns: 8
- Tokens — prompt / cached / cache write / completion / reasoning: 1339034 / 1144281 / not computed / 2849 / 1505
- Duration: 107.9 s
- Cost: $0.53 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4

## Response (20261118)

- **Unparseable review responses recorded as successful:** fixed. A review output with verdict `UNKNOWN` is now a `config_failure` that keeps its usage.
- **No-call comb entries make recipe costs unavailable:** fixed. An empty-input comb records `cost_usd` 0.0.
- **Parsing failures discard usage:** not fixed. The loop then charges the bound's per-call figure (the largest observed cost or `--call-cost`), which errs high.
- **Malformed import schemas abort the import:** not fixed. The import reads the committed hand-run files, which import cleanly and are covered by tests on the real files.
- The previous round's FAIL (non-finite cost limits) and the empty-comb cap concern were fixed in f6f1d6a8.
