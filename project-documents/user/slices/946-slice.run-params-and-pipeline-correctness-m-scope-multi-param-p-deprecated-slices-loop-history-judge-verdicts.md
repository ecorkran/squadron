---
docType: slice-design
slice: run-params-and-pipeline-correctness-m-scope-multi-param-p-deprecated-slices-loop-history-judge-verdicts
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261014
dateUpdated: 20261014
status: in_progress
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

1. **#215 `-m` scope.** Move `cli_override` below the action and step models in `ModelResolver.cascade_candidates` (`pipeline/resolver.py`). New order: action, step, cli, pipeline, config. `-m` already writes `params["model"]` (`_assemble_params`), so any step whose model is `"{model}"` still gets the `-m` value; a step whose model is `"{review-model}"` or a literal alias keeps it. `--dry-run`, the classifier and the `-v` labels read the same tuple, so they follow automatically.
2. **#207 multi-param `-p`.** `_apply_param_overrides` (`cli/commands/run.py`) splits each `-p` entry on commas, then on the first `=`. An empty key or a pair without `=` raises `typer.BadParameter`, as a malformed single entry does today. `_extract_model_override` uses the same split so `-p a=1,model=x` sets the model. Repeated `-p` keeps working.
3. **#208 deprecated slices.** Add `DEPRECATED = "deprecated"` to `CfSliceStatus` and to `_EXCLUDED_STATUSES` (`pipeline/sources.py`). `_cf_unfinished_slices` filters on `_EXCLUDED_STATUSES` instead of `!= COMPLETE`, so all four sources share one set. This also drops `deferred` slices from `unfinished_slices`, which the issue asks for.
4. **#170 loop history.** The loop step result carries every iteration's action results in order. Conditions (`until`, `accept_if`, exhaust handling) keep reading the current iteration only (D2). `prior_outputs` keys become unique per step (D3). `summary_context._format_review` renders each finding as `[SEVERITY] title (location)` text.
5. **#206 reset cf slice.** When an `each` step finishes without an exception and is not an item rerun, set the cf slice to the first item the source yielded. If the source yielded nothing, leave cf alone. Add `ContextForgeClient.set_slice(index)`; the `set_slice` cf-op uses it instead of calling `_run` directly.
6. **#141 parser ids.** In `review/parsers.py`, number findings by `len(findings) + 1` at the point of the warning, not by match index, so a skipped match no longer shifts the id.
7. **#140 judge verdict.** Extract the judge verdict computation from `ReviewAction._enforce_verdict` into one function in `pipeline/actions/judge.py`. The pipeline action and the `sq review` CLI both call it; the CLI passes the result to `to_dict(verdict_override=…)` for `--output json`/`file` and to `save_review_result` (D4).

Excluded: anything not listed in the seven issues.

## Technical Decisions

**D1 — `-m` is the run's default model, not a global override.** The cascade put `cli_override` first because there were no per-step model params when it was written. Pipelines now name per-step models through params (`review-model`, `summary-model`), and the user asked for those to be left alone. A user who wants everything on one model sets each param. No new flag.

**D2 — Loop results: two lists.** `_execute_loop_step` keeps `iteration_action_results` (reset each round, used for every condition) and adds `loop_action_results` (appended each round, used to build the step result). The step-result builders (`_loop_exhaust_result` and the success/accept/fail returns) get `loop_action_results` as `action_results`; any condition they evaluate gets the iteration list. `last_with_verdict` over the step result still finds the last round's review because results stay in order.

**D3 — Unique `prior_outputs` keys.** Today the key is `f"{action_type}-{idx}"`, so a later step's `dispatch-0` overwrites an earlier step's `dispatch-0` and keeps the earlier dict position, which breaks the "most recent first" readers in `dispatch.py` and `checkpoint.py`. The key becomes `f"{step_name}:{action_type}-{idx}"` in both `executor.py` and `StateManager.load_prior_outputs`. Readers only iterate in order; none looks up a key by name. The summary header shows the key, which now names the step.

**D4 — One judge verdict function.** `judge_verdict(template, step_override, result, logger) -> tuple[str, Provenance]` keeps today's behavior, including the WARNING and UNKNOWN fallback for a malformed threshold override. The CLI has no step override and passes `None`. A non-judge template returns `result.verdict.value`, so the CLI can call it unconditionally.

## Success Criteria

- `sq run P4 <slice> -m luna --dry-run` shows the design and revise steps on luna and the review steps on `review-model`'s alias.
- `-p a=1,b=2` sets both params; `-p a=1,b` and `-p =x` fail with an error naming the bad entry.
- A `deprecated` or `deferred` slice is excluded by all four `cf.*` sources.
- A loop that runs three rounds produces a step result with three rounds of action results; `until` still stops on the current round's verdict; the summary context lists all rounds, and findings render as text.
- After an `each` step over slices, cf's slice is the first yielded item; with no items, it is unchanged; an item rerun does not change it.
- A review response with an invalid-severity match before a placeholder-location finding logs the persisted F### id.
- `sq review` on a judge template with `--output json` emits the same verdict as the saved artifact.
- ruff format, ruff check, pyright (zero errors) and the full suite pass.

## Risk Assessment

Low. D1 changes resolution order: a user who relied on `-m` overriding a literal step model now gets the step's model. That is the requested behavior and goes in the CHANGELOG. D3 changes the stored `prior_outputs` key, which is rebuilt from the state file on resume, so old state files load with the new scheme.

## Implementation Notes

One commit per issue, each with its tests. Order: #141, #208, #207, #215, #140, #206, #170 (smallest first; #170 touches the executor most).
