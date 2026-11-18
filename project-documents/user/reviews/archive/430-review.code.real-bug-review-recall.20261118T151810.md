---
docType: review
layer: project
reviewType: code
slice: real-bug-review-recall
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/430-slice.real-bug-review-recall.md
aiModel: gpt-6.1-sol
aiProfile: openai-oauth
status: complete
dateCreated: 20261118
dateUpdated: 20261118
reviewedSha: 7d9e99c9c79aff8a33b7bd6d7b9b7e3582e801c5
diffTruncated: false
turns: 1
promptTokens: 212280
cachedTokens: 209280
completionTokens: 994
reasoningTokens: 298
durationSeconds: 156.1
costUsd: 0.036868
costBasis: alias_pricing
runId: run-20261118-p6-be6ab8d5
squadronVersion: 0.24.33
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Failed and empty stages disappear from scoring"
    location: "src/squadron/benchmark/recall/scoring_select.py:49-55"
  - id: F002
    severity: fail
    category: correctness
    summary: "Retrying a parent leaves stale downstream combs"
    location: "src/squadron/benchmark/recall/run_plan.py:141-152"
  - id: F003
    severity: concern
    category: correctness
    summary: "Orphan recovery scans against the wrong sandbox"
    location: "src/squadron/benchmark/recall/stage_runner.py:170-177"
  - id: F004
    severity: concern
    category: correctness
    summary: "Recorded template identity can differ from the executed prompt"
    location: "src/squadron/benchmark/recall/stage_identity.py:44-53"
  - id: F005
    severity: concern
    category: correctness
    summary: "Distinct labelers can overwrite the same record"
    location: "src/squadron/metrology/recall_label_models.py:66-68"
---

# Review: code — slice 430

**Verdict:** FAIL
**Model:** gpt-6.1-sol

## Findings

### [FAIL] Failed and empty stages disappear from scoring

Live selection requires exact `effort_sent` equality, but failure and empty-comb entries default it to `None`. For aliases that apply effort, these entries become “incomplete stages” rather than scored misses or counted harness drops. Reproduced with a `haiku-xhigh` timeout: zero scored pairs, no dropped count. Preserve these entries’ eligibility without fabricating sent effort; test failures and empty combs through the production resolver.

### [FAIL] Retrying a parent leaves stale downstream combs

Pending selection evaluates each stage independently. A failed review produces successful empty comb entries; `--retry-harness` then reruns only the review. Reproduced with a review-plus-comb recipe. Those combs never evaluate the replacement findings, and existing positional decisions can also attach to different findings after a retry. Supersede and rerun dependent stages whenever their input changes.

### [CONCERN] Orphan recovery scans against the wrong sandbox

Recovery supplies the newly created sandbox to the old transcript’s leak scan. Production generates a different sandbox path each invocation. An absolute read inside the original sandbox therefore falls outside the allowed roots and, under the real home, is classified as leaked. Reproduced using the actual leak rules. Persist the original scan context and test recovery across distinct invocation paths.

### [CONCERN] Recorded template identity can differ from the executed prompt

`load_all_templates()` includes user overrides when computing the stage hash. However, `ScrubbedEnvironment` copies only configuration files—not the user templates directory—so child review and comb commands resolve built-in templates instead. With an override installed, results are attributed to a prompt that never ran. Resolve and transfer the exact template, or compute identity from the child’s actual template environment.

### [CONCERN] Distinct labelers can overwrite the same record

Replacing unsafe characters with underscores is not collision-resistant: `person:alice.smith` and `person:alice_smith` produce identical record IDs. `get_labels()` does not verify the requested labeler, so recording the second person’s decision can merge and overwrite the first person’s record, losing provenance and changing precedence. Use collision-resistant encoding and add a two-labeler round-trip test.

### Run Digest

- Response length: 3011 chars
- Response is newline-free: no
- Tool calls made: not offered
- Tool calls failed: not computed
- Stop reason: not computed
- Output budget: backend default
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: not computed
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 212280 / 209280 / not computed / 994 / 298
- Duration: 156.1 s
- Cost: $0.04 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
- Answering model: not reported by provider (aiModel is the requested id)
