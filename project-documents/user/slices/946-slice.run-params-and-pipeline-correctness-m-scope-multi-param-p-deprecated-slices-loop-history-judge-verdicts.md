---
docType: slice-design
slice: run-params-and-pipeline-correctness-m-scope-multi-param-p-deprecated-slices-loop-history-judge-verdicts
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261014
dateUpdated: 20261014
status: complete
---

# Slice Design: Run Params and Pipeline Correctness — `-m` Scope, Multi-Param `-p`, Deprecated Slices, Loop History, Judge Verdicts

## Overview

Seven small, independent fixes shipped together as one patch release. Each one is a place where `sq run` or `sq review` does something other than what the user asked for: `-m` overrides models it shouldn't (#215), `-p` needs repeating for every param (#207), deprecated slices get run (#208), summaries lose revise rounds (#170), cf is left on the wrong slice (#206), parser warnings cite the wrong finding id (#141), and judge JSON output reports the wrong verdict (#140).

## Value

- `sq run P4 946 -m luna` changes the design model and leaves `review-model` alone.
- `-p model=opus,review-model=sonnet` replaces two `-p` flags.
- A slice marked `deprecated` is never picked up by a plan pipeline.
- A summary after a three-round revise loop sees all three rounds.
- After `slices-plan`, cf points at the first slice, where the next work starts.
- Warnings and JSON output agree with the saved artifact.

## Technical Scope

Included, one fix per issue:

1. **#215 `-m` scope.** Move `cli_override` below the action and step models in `ModelResolver.cascade_candidates` (`pipeline/resolver.py`). New order: action, step, cli, pipeline, config. `-m` already writes `params["model"]` (`_assemble_params`), so any step whose model is `"{model}"` still gets the `-m` value; a step whose model is `"{review-model}"` or a literal alias keeps it. The classifier, `--explain` and the `-v` labels read the same tuple; `--explain` also writes `-m` into its `model` param, as a run does.
2. **#207 multi-param `-p`.** `_apply_param_overrides` (`cli/commands/run.py`) splits each `-p` entry on commas, then on the first `=`. An empty key or a pair without `=` raises `typer.BadParameter`, as a malformed single entry does today. `_extract_model_override` uses the same split so `-p a=1,model=x` sets the model. Repeated `-p` keeps working.
3. **#208 deprecated slices.** Add `DEPRECATED = "deprecated"` to `CfSliceStatus` and to `_EXCLUDED_STATUSES` (`pipeline/sources.py`). `_cf_unfinished_slices` filters on `_EXCLUDED_STATUSES` instead of `!= COMPLETE`, so all four sources share one set. This also drops `deferred` slices from `unfinished_slices`, which the issue asks for.
4. **#170 loop history.** A loop step result carries its earlier rounds in a new `StepResult.prior_rounds`; `action_results` stays the final round, so conditions and failure reporting are unchanged (D2). `prior_outputs` keys become unique per step (D3). `summary_context._format_review` renders each finding as `[SEVERITY] title (location)` text.
5. **#206 reset cf slice.** When an `each` step completes and is not an item rerun, set the cf slice to the first item the source yielded. If the source yielded nothing, leave cf alone. A paused or failed step leaves cf alone too: a paused item may resume past its own set-slice step. A failed `cf set slice` logs a WARNING and does not fail the run. Add `ContextForgeClient.set_slice(index)`; the `set_slice` cf-op uses it instead of calling `_run` directly.
6. **#141 parser ids.** In `review/parsers.py`, number findings by `len(findings) + 1` at the point of the warning, not by match index, so a skipped match no longer shifts the id.
7. **#140 judge verdict.** Extract the judge verdict computation from `ReviewAction._enforce_verdict` into one function in `pipeline/actions/judge.py`. The pipeline action and the `sq review` CLI both call it; the CLI passes the result to `to_dict(verdict_override=…)` for `--output json`/`file` and to `save_review_result` (D4).

Excluded: anything not listed in the seven issues.

## Technical Decisions

**D1 — `-m` is the run's default model, not a global override.** The cascade put `cli_override` first because there were no per-step model params when it was written. Pipelines now name per-step models through params (`review-model`, `summary-model`), and the user asked for those to be left alone. A user who wants everything on one model sets each param. No new flag.

**D2 — Loop results: earlier rounds in their own field.** Putting every round in `action_results` would change what `_flag_kind`, `_item_failure_reason` and `sq review --max` report, since they take the first failed action. So both loop shapes collect finished rounds into `StepResult.prior_rounds`, and only the `prior_outputs` build reads `[*prior_rounds, *action_results]`. `prior_rounds` is not persisted: a run resumed after the loop rebuilds `prior_outputs` from the final round, as before.

**D3 — Unique `prior_outputs` keys.** Today the key is `f"{action_type}-{idx}"`, so a later step's `dispatch-0` overwrites an earlier step's `dispatch-0` and keeps the earlier dict position, which breaks the "most recent first" readers in `dispatch.py` and `checkpoint.py`. The key becomes `f"{step_name}:{action_type}-{idx}"` in both `executor.py` and `StateManager.load_prior_outputs`. Readers only iterate in order; none looks up a key by name. The summary header shows the key, which now names the step.

**D4 — One judge verdict function.** `judge_verdict(template, step_override, result, logger) -> tuple[str, Provenance]` keeps today's behavior, including the WARNING and UNKNOWN fallback for a malformed threshold override. The CLI has no step override and passes `None`. A non-judge template returns `result.verdict.value`, so the CLI can call it unconditionally.

## Success Criteria

- `sq run P4 -m luna --explain` shows the design and revise steps on luna and the review steps on `review-model`'s alias.
- `-p a=1,b=2` sets both params; `-p a=1,b` and `-p =x` fail with an error naming the bad entry.
- A `deprecated` or `deferred` slice is excluded by all four `cf.*` sources.
- A loop that runs three rounds keeps the final round in `action_results` and the first two in `prior_rounds`; a later step's `prior_outputs` holds all three in order; findings render as text.
- After a completed `each` step over slices, cf's slice is the first yielded item; with no items, or a paused step, it is unchanged.
- A review response with an invalid-severity match before a placeholder-location finding logs the persisted F### id.
- `sq review` on a judge template with `--output json` emits the same verdict as the saved artifact.
- ruff format, ruff check, pyright (zero errors) and the full suite pass.

## Risk Assessment

Low. D1 changes resolution order: a user who relied on `-m` overriding a literal step model now gets the step's model. That is the requested behavior and goes in the CHANGELOG. D3 changes the stored `prior_outputs` key, which is rebuilt from the state file on resume, so old state files load with the new scheme.

## Implementation Notes

One commit per issue, each with its tests. Order: #141, #208, #207, #215, #140, #206, #170 (smallest first; #170 touches the executor most).
