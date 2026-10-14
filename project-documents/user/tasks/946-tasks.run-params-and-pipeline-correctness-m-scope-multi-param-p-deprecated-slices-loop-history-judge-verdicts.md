---
docType: tasks
slice: run-params-and-pipeline-correctness-m-scope-multi-param-p-deprecated-slices-loop-history-judge-verdicts
project: squadron
lld: user/slices/946-slice.run-params-and-pipeline-correctness-m-scope-multi-param-p-deprecated-slices-loop-history-judge-verdicts.md
dependencies: []
projectState: 0.21.8 released; slice 946 design complete
dateCreated: 20261014
dateUpdated: 20261014
status: in_progress
---

# Tasks: Run Params and Pipeline Correctness

## #141 Parser warning ids
- [x] Number findings in `review/parsers.py` by kept count, not match index
- [x] Test: invalid-severity match before a placeholder-location finding logs the persisted F### id
- [x] Commit

## #208 Deprecated slices
- [x] Add `DEPRECATED` to `CfSliceStatus` and `_EXCLUDED_STATUSES`
- [x] `_cf_unfinished_slices` filters on `_EXCLUDED_STATUSES`
- [x] Tests: deprecated and deferred slices excluded by all four sources
- [x] Commit

## #207 Multi-param `-p`
- [x] Split each `-p` entry on commas in `_apply_param_overrides` and `_extract_model_override`
- [x] Malformed pairs raise `typer.BadParameter` naming the entry
- [x] Tests: `-p a=1,b=2`, mixed with repeated `-p`, `-p a=1,model=x`, `-p a=1,b`, `-p =x`
- [x] Commit

## #215 `-m` scope
- [x] Reorder `cascade_candidates`: action, step, cli, pipeline, config
- [x] Update resolver and classification tests that assert the old order
- [x] Test: `-m` with a step model `"{review-model}"` resolves the review alias; a `"{model}"` step resolves the `-m` value
- [x] Commit

## #140 Judge verdict
- [x] Extract `judge_verdict` into `pipeline/actions/judge.py`; `ReviewAction._enforce_verdict` calls it
- [x] `sq review` uses it for `--output json`/`file` and for the saved artifact
- [x] Test: judge template `--output json` verdict matches the artifact
- [x] Commit

## #206 Reset cf slice after `each`
- [x] Add `ContextForgeClient.set_slice`; `set_slice` cf-op uses it
- [x] `_execute_each_step` sets cf slice to the first yielded item (not on item rerun, not when empty)
- [x] Tests: reset to first item; no items leaves cf alone; item rerun leaves cf alone (as built: no item-rerun test; a paused step leaving cf alone and a failed `cf set slice` logging a WARNING are tested instead; the reset runs only when the each step completes)
- [x] Commit

## #170 Loop history
- [x] Loop step result carries all iterations' action results; conditions use the current iteration (as built: earlier rounds live in a new `StepResult.prior_rounds` field; `action_results` stays the final round)
- [x] `prior_outputs` keys include the step name in `executor.py` and `StateManager.load_prior_outputs`
- [x] `_format_review` renders findings as text
- [x] Tests: three-round loop result, `until` on current round, summary context lists every round
- [x] Commit

## Close-out
- [ ] ruff format, ruff check, pyright (zero errors), full suite
- [x] CHANGELOG bullets under Unreleased
