---
docType: tasks
slice: run-params-and-pipeline-correctness-m-scope-multi-param-p-deprecated-slices-loop-history-judge-verdicts
project: squadron
lld: user/slices/946-slice.run-params-and-pipeline-correctness-m-scope-multi-param-p-deprecated-slices-loop-history-judge-verdicts.md
dependencies: []
projectState: 0.21.8 released; slice 946 design complete
dateCreated: 20261014
dateUpdated: 20261014
status: not_started
---

# Tasks: Run Params and Pipeline Correctness

## #141 Parser warning ids
- [ ] Number findings in `review/parsers.py` by kept count, not match index
- [ ] Test: invalid-severity match before a placeholder-location finding logs the persisted F### id
- [ ] Commit

## #208 Deprecated slices
- [ ] Add `DEPRECATED` to `CfSliceStatus` and `_EXCLUDED_STATUSES`
- [ ] `_cf_unfinished_slices` filters on `_EXCLUDED_STATUSES`
- [ ] Tests: deprecated and deferred slices excluded by all four sources
- [ ] Commit

## #207 Multi-param `-p`
- [ ] Split each `-p` entry on commas in `_apply_param_overrides` and `_extract_model_override`
- [ ] Malformed pairs raise `typer.BadParameter` naming the entry
- [ ] Tests: `-p a=1,b=2`, mixed with repeated `-p`, `-p a=1,model=x`, `-p a=1,b`, `-p =x`
- [ ] Commit

## #215 `-m` scope
- [ ] Reorder `cascade_candidates`: action, step, cli, pipeline, config
- [ ] Update resolver and classification tests that assert the old order
- [ ] Test: `-m` with a step model `"{review-model}"` resolves the review alias; a `"{model}"` step resolves the `-m` value
- [ ] Commit

## #140 Judge verdict
- [ ] Extract `judge_verdict` into `pipeline/actions/judge.py`; `ReviewAction._enforce_verdict` calls it
- [ ] `sq review` uses it for `--output json`/`file` and for the saved artifact
- [ ] Test: judge template `--output json` verdict matches the artifact
- [ ] Commit

## #206 Reset cf slice after `each`
- [ ] Add `ContextForgeClient.set_slice`; `set_slice` cf-op uses it
- [ ] `_execute_each_step` sets cf slice to the first yielded item (not on item rerun, not when empty)
- [ ] Tests: reset to first item; no items leaves cf alone; item rerun leaves cf alone
- [ ] Commit

## #170 Loop history
- [ ] Loop step result carries all iterations' action results; conditions use the current iteration
- [ ] `prior_outputs` keys include the step name in `executor.py` and `StateManager.load_prior_outputs`
- [ ] `_format_review` renders findings as text
- [ ] Tests: three-round loop result, `until` on current round, summary context lists every round
- [ ] Commit

## Close-out
- [ ] ruff format, ruff check, pyright (zero errors), full suite
- [ ] CHANGELOG bullets under Unreleased
