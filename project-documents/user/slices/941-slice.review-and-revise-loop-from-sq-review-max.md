---
docType: slice-design
slice: review-and-revise-loop-from-sq-review-max
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261012
dateUpdated: 20261012
status: not_started
---

# Slice Design: Review-and-Revise Loop from `sq review` — `--max`

## Overview

Today, revising an existing artifact until its review passes means running a whole pipeline (P4, P5 or P6), which first regenerates the design, tasks or code. `sq review slice|tasks|code <index> --max N` runs one review and then up to N revise-and-review rounds against the existing artifact. It uses the loop already defined in the built-in pipeline for that review kind. Nothing is regenerated.

## Value

- The PM can tighten an existing design, task file or implementation with one command. Today that takes a manual review → in-session revise → review cycle, or a full pipeline rerun that throws the artifact away.
- The loop is the one P4/P5/P6 already run. A change to a pipeline's loop (proportionality from 943, `accept_if`, commit behavior) reaches `sq review --max` without a second edit.

## Technical Scope

Included:

1. **`--max N`** on `sq review slice`, `sq review tasks` and `sq review code`. Typer accepts both `--max 3` and `--max=3`. N must be an integer ≥ 1, and the loop's own `max` validation enforces this.
2. **`--revise-model`** on the same three subcommands. It sets the reviser model and is only valid together with `--max`.
3. **Kind → pipeline table:** `REVISE_PIPELINE_BY_KIND: dict[BuiltinReviewTemplate, str]`, holding `SLICE → "P4"`, `TASKS → "P5"`, `CODE → "P6"`. `sq review arch --max` does not exist as an option. Any other kind missing from the table gets an explicit error.
4. **Loop runner:** builds a two-step pipeline definition from the mapped pipeline, `[review, <that pipeline's loop>]`, and runs it with `execute_pipeline`.
5. **`/sq:review` slash command:** documents `--max` and `--revise-model` and passes them through.
6. **Per-round progress:** `RunObserver` gains `round_completed`, which the executor calls after each loop round (D7). The CLI's per-round lines come from it.

Excluded:

- **MCP.** Squadron has no MCP review tool. Its only MCP code is a client (`tools/mcp_bridge.py`, `tools/cf_tools.py`), so the plan entry's MCP parity item has nothing to attach to. The 900 plan entry is amended to match. Interface parity here means CLI and slash command. If a later slice adds an MCP review tool, that tool exposes `--max` and `--revise-model` under the same parity rule.
- **Resume.** No resumable run state is written (D4).
- **`sq run --from loop-1`.** The pipeline YAML files are unchanged.

## Dependencies

### Prerequisites

None outstanding. A failed round commit already ends the loop (fix 85a7f7aa); D5 relies on it.

### Interfaces Required

| Interface | Location | Use |
|---|---|---|
| `load_pipeline(name)` | `pipeline/loader.py` | load P4/P5/P6, honoring project and user overrides |
| `execute_pipeline(definition, params, ...)` | `pipeline/executor.py` | run the composed definition |
| `StepConfig`, `PipelineDefinition` | `pipeline/models.py` | compose the two-step definition |
| `StepTypeName.LOOP`, `parse_loop_config`, `ExhaustBehavior` | `pipeline/loop_config.py` | find the loop and override `on_exhaust` |
| `BuiltinReviewTemplate` | `review/templates/__init__.py` | key the table |
| `save_review_result` / `archive_existing_review` | `review/persistence.py` | used unchanged by the pipeline review action |
| `RunObserver` | `pipeline/run_observer.py` | extended with `round_completed` (D7); passed to `execute_pipeline` as `observer` |

## Architecture

### Component Structure

- **`src/squadron/pipeline/review_revise.py`** (new). Holds `REVISE_PIPELINE_BY_KIND` and `build_review_revise_definition(kind) -> PipelineDefinition`. Pipeline knowledge stays in the pipeline package.
- **`src/squadron/cli/commands/review_revise.py`** (new). Holds `run_review_revise(kind, slice_index, reviewer, revise_model, max_rounds, cwd, verbosity) -> int`. It validates options, assembles params, calls `execute_pipeline` and reports the result. `review.py` is already about 1,300 lines, so it gets only the two option declarations per subcommand and a single early branch: `if max_rounds is not None: raise typer.Exit(run_review_revise(...))`.
- **`commands/sq/review.md`**: documents the options for `slice`, `tasks` and `code`.

### Data Flow

```
sq review slice 941 --model X --max 3 [--revise-model Y]
  → validate options (D6) → kind = BuiltinReviewTemplate.SLICE
  → build_review_revise_definition(SLICE):
       load_pipeline("P4") → the single step whose type is LOOP
       review step = copy of the loop body's review action config
       loop step   = P4's loop with on_exhaust = fail
       definition  = PipelineDefinition(name="review-revise-slice",
                       params=P4.params, steps=[review, loop])
  → params = {slice: 941, review-model: X, max-revisions: "3",
              model: Y if given (else P4's default `model`)}
  → execute_pipeline(definition, params, resolver, cf_client, cwd,
                     observer=RoundPrinter)
       review  → saves 941-review.slice.….md (archives any prior one)
       loop    → skip_if_met: PASS on the first review means 0 rounds
                 round: revise (dispatch, feedback: review, in place)
                        → review → commit (commit_each_iteration)
                 stops when `until` is met, or at max (accept_if / fail)
       RoundPrinter prints the review line on step_completed(review)
       and one line per round on round_completed (D7)
  → print the final verdict; exit code (D5)
```

### State Management

- **Artifacts and reviews** are on disk and in git. Each round's review goes through `save_review_result` with `revision_number=context.iteration`, which archives the previous review under `reviews/archive/` exactly as pipeline reviews already do. Each revision is committed.
- **Run state:** none is written (D4).
- **Summaries:** no summary step. The CLI prints per-round lines as rounds finish (D7) and the final verdict to stdout.

## Technical Decisions

### D1 — Compose `[review, loop]`, do not extract the loop

The loop's revise dispatch requires a prior review in `prior_outputs` (`_resolve_feedback_prompt` raises `DispatchFeedbackError` otherwise). In P4/P5 that review comes from the design or tasks step. A leading review step supplies it, and it is also the "one review" the slice promises.

Pulling the loop out into its own runnable unit would mean either duplicating loop YAML per kind, which violates DRY, or restructuring three shipped pipelines. Composition changes no pipeline file.

Rejected: `sq run P4 --from loop-1`. It starts with empty `prior_outputs`, so the first revise fails.

### D2 — The loop and review config come from the loaded pipeline

The loop is found as the single step whose `step_type` is `StepTypeName.LOOP`, not by step name. P4/P5 loops are unnamed (`loop-1`) and P6's is `revise-code`. A loaded pipeline with zero loop steps, or more than one, is an error that names the pipeline.

The leading review step copies the loop body's review action config (template, `{review-model}`, `{slice}`). The template is therefore never restated in this slice. Because the pipeline goes through `load_pipeline`, a project or user override of P4/P5/P6 changes `sq review --max` too.

Overrides can also change the shape the builder relies on, so the builder checks the loop and raises an error naming the pipeline when any of these fail:
- the loop body has exactly one `review` step;
- the loop sets `until`;
- the loop sets `skip_if_met: true`. Zero rounds after a passing first review (Success Criterion 2) depends on it.

All three shipped loops satisfy these checks.

### D3 — Model params

- **Reviewer:** `--model` is the reviewer. `review.py` resolves it with its existing `_resolve_model`, which also covers the omitted case through the config cascade, and passes the result to `run_review_revise` as `reviewer`. The runner passes it on as `review-model`. `review_revise.py` imports nothing from `review.py`, so there is no import cycle and no private-symbol reach.
- **Reviser:** `--revise-model` sets `model`, which the loop's revise dispatch reads. When it is omitted, the mapped pipeline's own `model` default applies. No reviser default is introduced here.
- **Rounds:** `--max` sets `max-revisions`.

Pool names in `--model` are handled by whatever the pipeline review action already resolves. A test asserts that a pool alias reaches the review action unchanged.

### D4 — No resumable run state; `on_exhaust` becomes `fail`

Run state is reloaded by pipeline name (`RunState.load_target`), and a composed in-memory definition cannot be reloaded. Recording it as `P4` would let `sq run --resume` replay the wrong steps.

Resume is unnecessary anyway. Every revision is committed and every review is saved, so after an interruption, rerunning the same command starts from the current artifact with a fresh review.

For the same reason, the pipelines' `on_exhaust: checkpoint` cannot be honored, since it pauses and offers `sq run --resume`. The composed loop sets `on_exhaust: fail`. `accept_if` still marks an exhausted loop accepted when the last verdict meets it.

### D5 — Outcomes, failure modes and exit codes

Exit codes 0, 1 and 2 mean what they mean for `sq review` without `--max` (`_exit_on`): 2 is a FAIL verdict, 1 is a failed run or save, and CONCERNS exits 0. An exhausted loop that is not accepted ends at FAIL, because `accept_if` is `concerns_or_better`.

| Outcome | Behavior | Signal | Exit |
|---|---|---|---|
| Final verdict PASS, or accepted by `accept_if` | normal finish | per-round lines | 0 |
| Final verdict FAIL, or loop exhausted and not accepted | normal finish | per-round lines | 2 |
| Revise dispatch or review fails, including a model call that hangs or times out | Inherited unchanged: the provider and dispatch timeouts apply, and this slice adds none. The loop ends. | The action error is printed | 1 |
| Round commit fails (hook failure, git timeout, planning commit off the target branch) | Inherited (fix 85a7f7aa): the loop stops after that round with the status a failed revise dispatch gets, `on_exhaust: fail` here. | `round N commit failed: <error>` on stderr from the run error; the executor logs it at ERROR | 1 |
| Ctrl-C mid-round | Inherited: `KeyboardInterrupt` propagates, and that round is not committed. `slice` and `tasks` commits stage only the artifact and review paths, so on a rerun a leftover artifact edit is reviewed and committed with round 1. | Python's interrupt | non-zero |
| `code` with a dirty working tree | Refused before any model call. `code` round commits stage everything (`git add -A`), so unrelated changes or a leftover interrupted edit would be swept into a revision commit. | Error listing the dirty paths | 1 |

### D6 — Option validation (fail fast, before any model call)

- The positional argument must be a slice index. Path inputs are refused with `--max requires a slice index`.
- `--revise-model` without `--max` is an error.
- With `--max`, the only options allowed are those in one constant, `MAX_SUPPORTED_OPTIONS`: `max`, `model`, `revise_model`, `cwd` and `verbose`. Any other parameter whose Click source is `ParameterSource.COMMANDLINE` is refused, and the error names it. The loop's review steps cannot honor other options, and silently ignoring them would be a fallback. Options added to `sq review` later are refused by default.
- For `code`, the current branch must be the slice branch, because revisions are committed to the checked-out branch. P6 enters the branch itself; this command does not switch branches. When the branch is wrong, the error names the expected branch.

### D7 — Per-round progress through `RunObserver`

`execute_pipeline` returns one `StepResult` per loop, holding only the last round's action results, so the per-round lines cannot be built from the result. `RunObserver` gains one method:

```python
def round_completed(self, step_name: str, iteration: int, results: list[ActionResult]) -> None: ...
```

`_execute_loop_body` receives the observer the same way the `each` body does and calls it after each round's commit, before the `until` check, so a round that ends the loop is still reported. `RunStateRecorder` implements it as a no-op, and so does the test double in `tests/pipeline/observer_support.py`.

The CLI's `RoundPrinter` observer reads the round's review verdict and finding count, and the commit's short SHA, from `results`. A round whose commit failed prints `commit failed` in place of the SHA. A round with no commit output (`committed: False`, nothing changed) prints `no changes`. A missing review result is a bug in the loop shape D2 already checks, so it raises.

### Patterns and Conventions

- The table is keyed by the `BuiltinReviewTemplate` enum. The CLI converts its literal kind to the enum once, at the boundary.
- The composed pipeline is named `review-revise-{kind}` for log and commit context only. It is never loaded by name.

## Implementation Details

### API Contracts

```
sq review slice <index> --max N [--model REVIEWER] [--revise-model REVISER] [--cwd DIR] [-v]
sq review tasks <index> --max N [...same...]
sq review code  <index> --max N [...same...]
```

Example stdout:

```
review-revise slice 941  reviewer=sol  reviser=opus  max=3
  review     CONCERNS (4)  941-review.slice.review-and-revise-….md
  round 1    CONCERNS (2)  committed a1b2c3d
  round 2    PASS          committed d4e5f6a
final: PASS after 2 rounds
```

## Integration Points

### Provides to Other Slices

None.

### Consumes from Other Slices

- **943 (proportionate reviews):** its revise guidance applies automatically, because the same dispatch action is used.
- **P4/P5/P6 loop definitions:** if one of them loses its loop, `--max` for that kind fails with the D2 error. It never silently runs only the single review.

## Success Criteria

### Functional Requirements

1. `sq review slice|tasks|code <index> --max N` runs one review and then at most N revise-and-review rounds, stopping early when the pipeline's `until` condition is met.
2. When the first review already meets `until`, zero rounds run.
3. Revisions edit the existing artifact in place, and each round is committed. Each new review archives the previous one under `reviews/archive/`.
4. `--model` sets the reviewer, `--revise-model` sets the reviser, and the default reviser is the mapped pipeline's `model` param.
5. `sq review arch --max` is rejected by the CLI, since the option does not exist there. A kind missing from `REVISE_PIPELINE_BY_KIND` raises an explicit error.
6. Without `--max`, `sq review` behaves identically: the existing review CLI tests pass unchanged.
7. The options refused in D6 produce an error naming the option, and no model call is made.
8. Exit codes follow D5.
9. `/sq:review slice 941 --max 2 --model X` behaves like the CLI command.

### Technical Requirements

- Unit tests for `build_review_revise_definition`:
  - each mapped kind yields `[review, loop]` with the pipeline's own loop config and `on_exhaust=fail`;
  - an error is raised for zero or two loops, for zero or two review steps in the loop body, and for a loop without `until` or `skip_if_met`;
  - a project override of P4 is picked up.
- CLI tests with the executor stubbed cover option validation, param assembly (`review-model`, `model`, `max-revisions`, `slice`) and the D5 exit-code mapping.
- A stubbed failed round commit produces the stderr line and exit 1.
- An executor test: `round_completed` is called once per round with that round's iteration and results, including a round whose commit failed.
- `RoundPrinter` tests: verdict and SHA line, `commit failed`, `no changes`, and a missing review raising.
- `code` with a dirty tree exits 1 before any executor call.
- One integration test runs the composed definition with fake review/dispatch actions through two rounds: CONCERNS → PASS.
- `ruff format`, `ruff check` and `pyright` with zero errors.
- A CHANGELOG bullet.

### Verification Walkthrough

1. Reviewer only, no revision, to see the baseline:
   `sq review slice 941 --model sol -v` → a single review, exactly as today.
2. Revise loop on a design:
   `sq review slice 941 --model sol --max 2 -v`
   - Expect: the review line plus up to 2 round lines, then `final: …`.
   - `git log --oneline -3` shows one commit per round.
   - `ls project-documents/user/reviews/archive/ | grep 941-review.slice` shows the archived earlier reviews.
   - The design file was edited in place, and no new design file exists.
3. Reviser override:
   `sq review tasks 941 --model sol --max 1 --revise-model sonnet -v` → the header shows `reviser=sonnet`.
4. Code loop:
   - On the slice branch: `sq review code 941 --model sol --max 1 -v` → revisions are committed on that branch.
   - On `main`, the same command exits 1 with an error naming the expected branch.
5. Refusals, each exiting non-zero with no model call:
   - `sq review arch 941 --max 1` → Typer reports an unknown option.
   - `sq review slice 941 --max 1 --json` → `--json is not supported with --max`.
   - `sq review slice path/to/file.md --against x --max 1` → `--max requires a slice index`.
   - `sq review slice 941 --revise-model opus` → `--revise-model requires --max`.
6. Parity: `/sq:review slice 941 --max 1 --model sol` in Claude Code produces the same output and commits as step 2.

## Implementation Notes

### Development Approach

1. `RunObserver.round_completed` and the executor call (D7), with tests.
2. `pipeline/review_revise.py`: the table, the builder and its unit tests.
3. `cli/commands/review_revise.py`: validation, params, `RoundPrinter`, execution and exit codes, with tests.
4. Wire `--max` / `--revise-model` into `review_slice`, `review_tasks` and `review_code`.
5. The integration test with fake actions.
6. The slash command doc, CHANGELOG and the walkthrough run.

Effort: 3/5.

### Special Considerations

- **Revise is not idempotent.** A rerun after an interruption starts a new review against the current artifact. Prior rounds are still in git and in the archive.
- **Code reviews have no `input` file,** so the revise dispatch gets no "revise in place" line for `code`. It works on the checked-out branch, the same as P6's `revise-code` loop. D6's branch check is what keeps those commits on the right branch.
