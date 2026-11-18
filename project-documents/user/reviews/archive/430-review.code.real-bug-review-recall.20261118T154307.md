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
reviewedSha: 6491303e8ed85b8e7a735b2e2a3f963102845b3a
revision_number: 1
diffTruncated: false
turns: 1
promptTokens: 201989
cachedTokens: 201728
completionTokens: 781
reasoningTokens: 365
durationSeconds: 170.1
costUsd: 0.028505
costBasis: alias_pricing
runId: run-20261118-p6-be6ab8d5
squadronVersion: 0.24.33
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Comb invalidation is lost when a retry stops midway"
    location: "src/squadron/benchmark/recall/run_plan.py:100-115"
  - id: F002
    severity: concern
    category: correctness
    summary: "Comb calls ignore the alias’s tool-use restriction"
    location: "src/squadron/benchmark/recall/stage_command.py:86-95"
  - id: F003
    severity: concern
    category: correctness
    summary: "A recorded zero cost prevents subsequent runs"
    location: "src/squadron/benchmark/recall/run_bound.py:130-134"
---

# Review: code — slice 430

**Verdict:** FAIL
**Model:** gpt-6.1-sol

## Findings

### [FAIL] Comb invalidation is lost when a retry stops midway

Staleness exists only in the invocation-local `pending_slots`. If a retry replaces a review, then hits a cap before replacing its stored comb, the next invocation considers both stages complete—even with `--retry-harness`. Reproduced: pending stages change from `['rev', 'c']` to `[]` after replacing only the review. Reports can consequently apply old positional decisions to new findings. Persist dependency invalidation and test interrupted retry/resume.

### [CONCERN] Comb calls ignore the alias’s tool-use restriction

The call passes the resolved model ID without `model_allows_tools`. `run_review_with_profile` therefore looks up tool capability using that ID, which defaults to allowing tools rather than honoring the alias’s `tool_use=false`. Meanwhile, `live_stage_config` records the restriction as false. This benchmarks tool-enabled calls under a no-tools identity. Forward the alias capability explicitly and test a restricted alias.

### [CONCERN] A recorded zero cost prevents subsequent runs

An observed `cost_usd=0.0` overrides even a positive `--call-cost`. When all pending priced configurations have zero observed costs, `bound.largest` becomes zero and `_dispatch` constructs `ReviewBudget(..., 0.0)`, which raises. Reproduced the resulting “per-review figure must be positive” error. Zero is explicitly a legitimate provider cost elsewhere in the project; handle it consistently and add a regression test.

### Run Digest

- Response length: 1895 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 201989 / 201728 / not computed / 781 / 365
- Duration: 170.1 s
- Cost: $0.03 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 3
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 3
- Finding-shaped matches — surviving validation: 3
- Answering model: not reported by provider (aiModel is the requested id)
