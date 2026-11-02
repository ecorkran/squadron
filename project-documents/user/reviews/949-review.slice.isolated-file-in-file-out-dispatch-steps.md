---
docType: review
layer: project
reviewType: slice
slice: isolated-file-in-file-out-dispatch-steps
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: 59bbabe5098846835fd871b107d521ad96349515
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 38
turns: 20
promptTokens: 1748954
cachedTokens: 1313536
completionTokens: 86638
reasoningTokens: 87376
durationSeconds: 481.3
costUsd: 0.106972
costBasis: alias_pricing
runId: run-20261102-p4-6acd47b2
squadronVersion: 0.24.13
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "`reply_from` run-time lookup does not match how nested and skipped steps are keyed"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Interfaces Required"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Undefined behavior when the named step's result exists but holds no reply text"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Technical Decisions"
  - id: F003
    severity: concern
    category: under-specification
    summary: "`metadata[\"written_files\"]` is introduced as state but appears in no decision, component change, or criterion"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#State Management"
  - id: F004
    severity: concern
    category: scope
    summary: "Plain `--validate` gains warning output the plan entry assigns as unchanged"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Technical Scope"
  - id: F005
    severity: note
    category: docs
    summary: "The isolation guarantee is dispatch-only while the Value section states it unconditionally"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Value"
  - id: F006
    severity: note
    category: dependency-direction
    summary: "A reporting module now depends on an actions module for a generic helper"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Component Structure"
---

# Review: slice — slice 949

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] `reply_from` run-time lookup does not match how nested and skipped steps are keyed

The design states the interface it needs is `prior_output_key(step_name, action_type, index)` "for finding an earlier step's dispatch result" (D3 repeats this: results "keys prefixed `{step}:dispatch-`"). That key scheme is created by exactly one place — the top-level walk in `execute_pipeline` (`src/squadron/pipeline/executor.py`, `prior_outputs[key] = action_result`). Three other accumulation sites in the same file use different schemes: a `loop:` body uses `f"{inner_step_index}-{action_type}-{action_index}"` in `running_prior`, `_run_each_item` uses the same inner-index form for `item_prior`, and `_execute_step_once` snapshots within a step as `f"{action_type}-{action_index}"`. Because D9's walker deliberately descends into `loop`/`each` bodies and `fan_out.inner`, a `reply_from` written on a step inside one of those is accepted at validation ("names a step earlier in the same list") and then finds nothing at run time. Either state the lookup in terms of the key scheme each container uses, or restrict `reply_from` to top-level steps at validation; leaving it implicit means a valid-looking pipeline fails at run time with a message about a missing reference the loader already approved.

### [CONCERN] Undefined behavior when the named step's result exists but holds no reply text

D3 covers only one absence: "At run time, a missing result fails the step with a message naming the reference." A result can be present and still carry no reply. `DispatchAction._dispatch` returns `ActionResult(success=True, outputs={SKIPPED_KEY: ..., "paths": [...]})` when a step has `existing: keep` and its artifact already exists, and the implement branch's kept-work path does the same — so a `reply_from` naming a kept step (a legitimate resume shape, and the design's own walkthrough exercises resumed runs) reaches `step_reply` and finds neither `reply` nor `response`. The same applies to a restored failed dispatch on a resumed run, since `_seed_resume_outputs` restores entries from `completed_steps` regardless of success. Specify which of these is a load-time error, a run-time failure kind, or a deliberate empty hand-off, and add it to Success Criteria — today "It never sends an empty reply" is asserted without a mechanism that covers these cases.

### [CONCERN] `metadata["written_files"]` is introduced as state but appears in no decision, component change, or criterion

State Management says the run "does not record them in state beyond `metadata['written_files']`, which lists the paths." No such key exists in the codebase (no match in `src/`), and the phrase "beyond ... which lists" reads as if it already did. The key also appears in no row of the Component Structure table, in none of D1–D9, and in no Success Criterion — so the sentence both claims a state-format addition and leaves it unowned. Either drop the reference (file writing already reports through `FailureKind.STEP_IO` and the step's own output files) or name it as a decision with the metadata key's shape and a criterion asserting it, since `ActionResult.metadata` is persisted and read back on resume.

### [CONCERN] Plain `--validate` gains warning output the plan entry assigns as unchanged

The plan entry (900-slices line 512, item 43) specifies "(5) `sq run <pipeline> --validate --strict` fails on any step key the step type does not know; plain `--validate` and `sq run` keep today's behavior." The design has plain `--validate` "lists them as warnings" — a new call to `unknown_key_errors` plus rendering in the `--validate` branch of `cli/commands/run.py`, beyond the unchanged exit code. The Value section presents this as a benefit ("Pipeline authors ... plain `--validate` lists it as a warning"), but no consumer asked for it and Amoeba's probe only uses `--validate --strict`. Cut it or fold it into the single strict path: D9's own `unknown_key_errors(steps)` already returns one error per key, so the non-strict rendering is the only extra code and it changes a behavior the plan froze.

### [NOTE] The isolation guarantee is dispatch-only while the Value section states it unconditionally

Value says "`allowed_tools: []` means what it says," but Excluded defers the guard for review and summary steps, both of which accept `allowed_tools`. Slot 4 of the plan entry is dispatch-scoped, so the deferral is right; the claim and the CHANGELOG bullet should be scoped the same way, or a reader will believe `allowed_tools: []` is a hard guarantee on a review step where it remains a no-op.

### [NOTE] A reporting module now depends on an actions module for a generic helper

D4 moves `batch_report._write_atomic` into `reply_io` and has `batch_report` import it. That satisfies DRY, but it inverts the natural direction: a run-report writer would import from `pipeline/actions/`, which holds action implementations and imports providers, resolvers, and the action registry. A neutral home (for example a small `pipeline/atomic_write.py` beside `batch_report`) keeps the shared helper out of the actions package without duplicating it; worth a line in the design either way, since the table only lists `reply_io` as new.

### Run Digest

- Response length: 6662 chars
- Response is newline-free: no
- Tool calls made: 38
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 345381
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / cache write / completion / reasoning: 1748954 / 1313536 / not computed / 86638 / 87376
- Duration: 481.3 s
- Cost: $0.11 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
