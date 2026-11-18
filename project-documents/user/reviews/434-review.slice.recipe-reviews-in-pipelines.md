---
docType: review
layer: project
reviewType: slice
slice: recipe-reviews-in-pipelines
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md
aiModel: openai/gpt-6.1-sol
aiProfile: openrouter
status: complete
dateCreated: 20261118
dateUpdated: 20261118
reviewedSha: 4cbe0d20a04a45c2010a0a9dbcc78e5a8e6f057f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 244495
cachedTokens: 191934
completionTokens: 1888
reasoningTokens: 1062
durationSeconds: 71.6
costUsd: 0.143195
costBasis: alias_pricing
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Shared recipe boundary and production cost rules match the architecture"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md#Architecture"
  - id: F002
    severity: concern
    category: integration
    summary: "CLI-backed pipeline reviews lose the promised run linkage"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:329-340"
  - id: F003
    severity: concern
    category: data-model
    summary: "Report identity is not defined consistently for skipped and aborted stages"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:260-274"
---

# Review: slice — slice 434

**Verdict:** CONCERNS
**Model:** openai/gpt-6.1-sol

## Findings

### [PASS] Shared recipe boundary and production cost rules match the architecture

The dependency direction matches the architecture’s 20261118 amendment: shared recipe machinery imports review and metrology services, while production and benchmark callers import recipes. The design reuses existing review dispatch, persistence and comb machinery rather than duplicating them. Sequential execution, production cost-cap accounting, coarse metrology records and sidecar storage also align with the amended architecture.

### [CONCERN] CLI-backed pipeline reviews lose the promised run linkage

The design routes slash commands and prompt-only pipeline reviews through `sq review`, but the storage contract assigns `null` to `run_id`, `step_name` and `iteration` for every `sq review` invocation. No distinction or context-propagation contract is specified for a CLI review invoked on behalf of a pipeline.

This leaves the plan’s requirement for pipeline recipe records keyed by run id unmet for that route, and prevents 431 from joining those reviews using the advertised integration keys. Specify how pipeline context reaches CLI-backed reviews when a run exists; reserve null linkage for genuinely standalone reviews. If prompt-only renderings have no run identity, explicitly delimit that exception instead of promising run-keyed records for them.

### [CONCERN] Report identity is not defined consistently for skipped and aborted stages

D10 groups reviews by the ordered stage identities, including effort actually sent. However, the record contains stages in execution order, reviewer failures skip their comb chains, aborted records contain only finished stages, and empty-input combs make no call. The design does not specify how these records obtain a comparable recipe identity.

Consequently, the same configured recipe can appear to have different configurations solely because a reviewer failed or a comb had no input. Conversely, an aborted record cannot identify the resolved settings of stages it never reached. This undermines the architecture’s comparability principle and D10’s intended incomplete counts and “config differs” flags.

Persist the resolved planned stage configurations separately from execution results, and define grouping for skipped stages and unknown effort without substituting configured effort for effort sent. Add report tests covering a complete review, an empty-input comb, a skipped comb chain and an aborted review of the same configuration.

### Run Digest

- Response length: 2871 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: stop
- Output budget: backend default
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 1115
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 244495 / 191934 / not computed / 1888 / 1062
- Duration: 71.6 s
- Cost: $0.14 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 3
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 3
- Finding-shaped matches — surviving validation: 3

## Response (20261118, PM session)

- F002 (run linkage): fixed by stating the exception. Prompt-only pipelines run `sq review` as a shell command, so their recipe records have null `run_id`, `step_name` and `iteration`, and 431 cannot join them; only executor-run pipelines get run-keyed records. Passing run context into `sq review` is not built here.
- F003 (report identity): fixed. The record carries `planned`, every stage's `StageConfig` resolved before the first call, and D10 keys rows on recipe name, recipe hash and `planned`. A failed reviewer, skipped comb chain, empty-input comb or aborted review shares the complete review's row and counts as Incomplete. `effort_sent` leaves the key; differing efforts among stages that ran flag the row "effort differs". Report tests cover all four cases.
