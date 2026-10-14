---
docType: review
layer: project
reviewType: code
slice: run-params-and-pipeline-correctness-m-scope-multi-param-p-deprecated-slices-loop-history-judge-verdicts
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/946-slice.run-params-and-pipeline-correctness-m-scope-multi-param-p-deprecated-slices-loop-history-judge-verdicts.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261014
dateUpdated: 20261014
reviewedSha: 1a9196019efaaf8b8cf1665ae9de37d13b44ed15
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 39
diffTruncated: false
turns: 19
promptTokens: 2849892
cachedTokens: 2137984
completionTokens: 116341
reasoningTokens: 111216
durationSeconds: 722.3
squadronVersion: 0.21.8
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "The judge-verdict fix is unreachable from every shipped CLI command"
    location: "src/squadron/cli/commands/review.py:825"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`_reset_cf_slice` claims a failed reset cannot fail the run, but one client failure mode escapes"
    location: "src/squadron/pipeline/executor.py:1805"
  - id: F003
    severity: concern
    category: api-design
    summary: "Comma-splitting `--param` values makes some values inexpressible and one case silently wrong"
    location: "src/squadron/cli/commands/run.py#_param_pairs"
  - id: F004
    severity: concern
    category: documentation
    summary: "Pipeline docs now contradict both the source filter and cf's post-batch state"
    location: "docs/PIPELINES.md:889"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "The extracted `judge_verdict` degradation contract has no direct test"
    location: "src/squadron/pipeline/actions/judge.py#judge_verdict"
  - id: F006
    severity: note
    category: observability
    summary: "`prior_outputs` keys are now used as display labels"
    location: "src/squadron/pipeline/summary_context.py#assemble_dispatch_context"
  - id: F007
    severity: note
    category: documentation
    summary: "Resolver module docstring still lists the old cascade order"
    location: "src/squadron/pipeline/resolver.py:1-8"
  - id: F008
    severity: pass
    category: correctness
    summary: "Parser finding IDs now agree with the persisted `F###` scheme"
    location: "src/squadron/review/parsers.py#_extract_findings"
  - id: F009
    severity: pass
    category: dry
    summary: "`prior_output_key` is correctly single-sourced across executor and state replay"
    location: "src/squadron/pipeline/models.py#prior_output_key"
---

# Review: code — slice 946

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] The judge-verdict fix is unreachable from every shipped CLI command

`test_review_judge_verdict.py` manufactures its subject by monkeypatching `squadron.cli.commands.review.get_template` to return a template with a `judge:` block, but no call site of `_run_review_command` passes a judge template name. I verified all five: `review.py:938` (`"slice"`), `review.py:1037` (`"arch"`), `review.py:1202` (`"tasks"`), `review.py:1377` (`"code"`), and `review_pr.py:419` (`"code"`). `JUDGE_TEMPLATE_NAME` is used only in `_resolve_judge_model` on the `review resolve` path, which never reaches `_run_review_command`, and `metrology/discovery.py:59` treats a persisted `reviewType` resolving to an `is_judge` template as the product of the *pipeline* review action. So the branch is reachable in practice only if a user drops a `~/.config/squadron/templates/{slice,arch,tasks,code}.yaml` carrying a `judge:` block. That is a real gap between "the test passes" and "#140 is fixed for invocations people actually run", and it is exactly the case the testing rules warn about — a test that only passes on a state production never reaches.

### [CONCERN] `_reset_cf_slice` claims a failed reset cannot fail the run, but one client failure mode escapes

The docstring states "a failed convenience reset must not fail the run", and the handler catches `ContextForgeError`. `ContextForgeNotAvailable` is a sibling, not a subclass — both derive directly from `Exception` in `integrations/context_forge.py` — and `ContextForgeClient._run` raises it when `cf` is not on PATH. `_check_cf` pre-flights cf at run start, so this is unlikely in a normal run, but the failure-mode enumeration rule applies precisely to the "already-unlikely" path: if it fires, it fires *after* `finally: _finish_each_report(...)` has written the batch report, so the whole batch's recorded work is discarded by an exception from a cosmetic reset. Either catch both, or state the single-mode assumption in the docstring. The test at `tests/pipeline/test_executor_each.py` covers only the `ContextForgeError` branch.

### [CONCERN] Comma-splitting `--param` values makes some values inexpressible and one case silently wrong

Splitting every entry on `,` means a value that legitimately contains a comma can no longer be passed at all — `-p "prompt=Fix X, then Y"` now raises `BadParameter` on the ` then Y` fragment. A loud failure is better than silent corruption, and `docs/PIPELINES.md` has been updated to document the new syntax ("A pair without `=` is an error"), but a value like `-p a=1,b=c` intended as `a="1,b=c"` parses as two pairs with no diagnostic. There is no escape mechanism (quoting, `\,`) and no test asserting the limitation, so the first person to hit it has no documented way out. Consider documenting the restriction explicitly alongside the new syntax, or accepting `,`-containing values via an escape.

### [CONCERN] Pipeline docs now contradict both the source filter and cf's post-batch state

Two documented contracts are now wrong. `docs/PIPELINES.md:889` says a batch leaves cf pointing at "the last slice"; `_reset_cf_slice` (executor.py:1784-1805) now deliberately points it at the *first* slice the source yielded (#206), and the accompanying test asserts `set_slice("180")` for items `180,181,182`. `docs/PIPELINES.md:448` still describes `cf.unfinished_slices` as "Slices in the plan whose status is not `complete`", but `sources.py:151` now filters on `_EXCLUDED_STATUSES`, which adds `deferred` and `deprecated` (#208). The second is the more consequential: an operator reading the table will expect a deferred slice to be selected by a plan batch, and it no longer will be.

### [CONCERN] The extracted `judge_verdict` degradation contract has no direct test

`judge_verdict` is the new single home for the slice-303-F003 contract ("a malformed threshold override degrades to UNKNOWN with a WARNING rather than raising, so an already-successful model call is never discarded"). I found no test that calls it: `tests/pipeline/actions/test_judge.py` imports `enforce_judge`, `JudgeThresholds`, `resolve_thresholds`, and `_DEFAULT_PASS_FLOOR` but not `judge_verdict`, and no other test module references the symbol. Extracting behaviour out of `ReviewAction._enforce_verdict` moved it one indirection away from whatever test guarded it; a direct test of the `except (TypeError, ValueError)` branch (including that the WARNING is emitted) would keep the contract pinned where it now lives. Flagging with the caveat that I checked imports and symbol references rather than the full body of every review-action test.

### [NOTE] `prior_outputs` keys are now used as display labels

The new key form `{step_name}:{action_type}-{idx}` (models.py#prior_output_key) reaches two places that render the key rather than a step name: `summary_context.py` emits `## Step: design:dispatch-0 (dispatch)` into the context block handed to non-SDK summary models, and `devlog.py:95` emits `- design:dispatch-0: PASS` into the committed DEVLOG entry. The design rationale states readers only iterate in order, which is true of `dispatch.py`, `checkpoint.py`, and `summary.py` — but these two iterate `items()` and use the key as a label, so the readable step name is now duplicated inside it. Worth a deliberate decision, since the DEVLOG line is committed to the repository.

### [NOTE] Resolver module docstring still lists the old cascade order

The module header still reads "1. CLI override (`--model` flag) 2. Action-level model 3. Step-level model …", but `cascade_candidates` now returns `(action_model, step_model, cli_override, pipeline_model, config_default)` (#215). `docs/PIPELINES.md:762-770` was updated to the new order; the docstring that the classifier (`classification.py:9`) names as the single source of truth was not. The `resolve()` Args docstring was corrected in this diff, so this is a partial update rather than an omission.

### [PASS] Parser finding IDs now agree with the persisted `F###` scheme

Changing `finding_id = f"F{index:03d}"` to `f"F{len(findings) + 1:03d}"` is the right fix: `ReviewResult.structured_findings` numbers kept findings only, so a severity-skipped match previously shifted every subsequent ID and made the soft-fail WARNING cite an ID no artifact contained (#141). The new test removes `NOTE` from `_SEVERITY_MAP` and asserts the warning names `F001`, which exercises the actual mismatch rather than a synthetic one.

### [PASS] `prior_output_key` is correctly single-sourced across executor and state replay

The key scheme is defined once and consumed by both `executor.py:641` and `state.py:650`, so the live path and the `load_prior_outputs` replay cannot drift — the failure mode that would make a resumed run's `prior_outputs` inconsistent with a fresh one. Ordering is also preserved for the order-sensitive readers: `[*prior_rounds, *action_results]` puts earlier loop rounds first, so `checkpoint._find_review_verdict`'s `reversed(...)` scan still sees the final round's verdict first, and the new loop test asserts both the ordering and that conditions still read only the final round.

### Run Digest

- Response length: 8390 chars
- Response is newline-free: no
- Tool calls made: 39
- Tool calls failed: 1
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 440082
- Effort: backend default
- Turns: 19
- Tokens — prompt / cached / completion / reasoning: 2849892 / 2137984 / 116341 / 111216
- Duration: 722.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Response

- **F001** accepted, no change: `sq review` has no subcommand that takes a judge template, so a judge reaches `_run_review_command` only through a user template that shadows `slice`, `arch`, `tasks` or `code`. That is the case #140 describes, and the fix covers it. The pipeline path was already correct.
- **F002** fixed: `_reset_cf_slice` also catches `ContextForgeNotAvailable`; the test covers both errors.
- **F003** fixed: `docs/PIPELINES.md` states that a `-p` value cannot contain a comma. No escape syntax: nothing passes comma values today, and an unmatched fragment fails loudly.
- **F004** fixed: the `cf.unfinished_slices` row and the batch cf-state note in `docs/PIPELINES.md` match the code.
- **F005** fixed: `TestJudgeVerdict` in `tests/pipeline/actions/test_judge.py` covers threshold merging and the malformed-override WARNING/UNKNOWN path.
- **F006** accepted as intended: `design:dispatch-0` names the step, which `dispatch-0` did not.
- **F007** fixed: the resolver module docstring lists the new cascade order.
