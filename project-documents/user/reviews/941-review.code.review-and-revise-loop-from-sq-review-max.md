---
docType: review
layer: project
reviewType: code
slice: review-and-revise-loop-from-sq-review-max
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261013
dateUpdated: 20261013
reviewedSha: d85cb7a85723eeace8fd7bb6c3dd4d1e10c887ad
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 34
diffTruncated: false
turns: 20
promptTokens: 2492639
cachedTokens: 2164864
completionTokens: 87828
reasoningTokens: 83211
durationSeconds: 754.5
squadronVersion: 0.21.6
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "`sq review --max` runs a mutating pipeline without the project run lock"
    location: "src/squadron/cli/commands/review_revise.py:219"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Branch preconditions let `ValueError` subclasses escape as a traceback"
    location: "src/squadron/cli/commands/review_revise.py:275-295"
  - id: F003
    severity: concern
    category: design-principles
    summary: "`RoundPrinter` raises from `RunObserver` callbacks, violating the interface's stated contract"
    location: "src/squadron/cli/commands/review_revise.py:88"
  - id: F004
    severity: concern
    category: error-handling
    summary: "`params[\"model\"]` is an unguarded index read at the CLI boundary"
    location: "src/squadron/cli/commands/review_revise.py#_run"
  - id: F005
    severity: concern
    category: testing
    summary: "CLI tests read the ambient project pipeline override"
    location: "tests/cli/test_review_revise.py#_run_with"
  - id: F006
    severity: note
    category: design-principles
    summary: "`_configure_agent_logging` is invoked twice per `--max` run"
    location: "src/squadron/cli/commands/review.py:668"
  - id: F007
    severity: note
    category: design-principles
    summary: "A third copy of the resolver construction"
    location: "src/squadron/cli/commands/review_revise.py#_run"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Exit-code mapping is centralized, documented, and tested at its boundaries"
    location: "src/squadron/cli/commands/review_revise.py#outcome_of"
---

# Review: code — slice 941

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] `sq review --max` runs a mutating pipeline without the project run lock

`_run` calls `execute_pipeline` directly. The composed definition's second step is a loop carrying `commit_each_iteration: true` (copied from P4/P5/P6 by `build_review_revise_definition`), so `squadron.pipeline.run_lock.pipeline_mutates` would return `True` for it — the loop body commits on every round, and `_require_branch_preconditions` exists precisely because the run writes to the repository.

`sq run` takes that lock for exactly this shape: `run._locked` calls `_take_run_lock`, which enters `project_run_lock(os.getcwd())` when `pipeline_mutates(definition)` and exits 2 if the lock cannot be taken. `review_revise.py` imports neither `run_lock` nor `ExitStack`, so nothing equivalent happens here. Two `sq review --max` invocations (or one alongside an `sq run`) in the same checkout will interleave commits and archives on the same tree, which is the race `project_run_lock` was added for.

The check that *is* present (`_require_branch_preconditions`) guards the branch, not concurrency: it reads the branch once at startup and cannot stop a second process from committing into the same working tree mid-loop.

### [CONCERN] Branch preconditions let `ValueError` subclasses escape as a traceback

`_require_branch_preconditions` wraps the `code` path in `try: ... except GitEnvironmentError as exc: raise _refuse(str(exc)) from exc`. But `slice_facts` (verified in `src/squadron/pipeline/branch_ops.py`) raises three exception types, only one of which is caught:

- `GitEnvironmentError` — cf unreadable (caught)
- `SliceNotInPlanError` — the slice is not in the current plan (subclasses `ValueError`, **not caught**)
- `NoDesignFileError` — raised by `slice_branch_name` when the slice has no design file (subclasses `ValueError`, **not caught**)

So `sq review code 999 --max 2` for a slice outside the plan ends in an uncaught `ValueError` and a traceback, rather than the clean `Error: ...` refusal the rest of this module is careful to produce. `branches_ops` itself classifies both as *item* failures rather than environment faults, which is a third possible handling — but the current behaviour is neither, and it is the one path in this file that bypasses `_refuse`.

### [CONCERN] `RoundPrinter` raises from `RunObserver` callbacks, violating the interface's stated contract

`run_observer.py` documents the interface as: "it always runs, is synchronous, and never fails a step through a progress write." `RunStateRecorder` honours that (its `round_completed` is a documented no-op). `RoundPrinter.round_completed` and `RoundPrinter.step_completed` instead `raise ValueError` when a round lacks a review or commit result.

`round_completed` is invoked from inside `_execute_loop_body` (`executor._report_round`), i.e. mid-run, after the round's commit has already landed. A display-layer assumption that does not hold therefore aborts a run that has partially committed the repository — the opposite of the documented "never fails a step through a progress write" guarantee, and hard to distinguish from a genuine execution failure at the CLI. Raising is a defensible choice for an internal invariant, but then the Protocol's contract in `run_observer.py` is wrong and should say so, or the invariant should be asserted where the loop shape is known (build time) rather than in the display path.

### [CONCERN] `params["model"]` is an unguarded index read at the CLI boundary

`printer.header(str(kind), slice_index, reviewer, str(params["model"]), max_rounds)` indexes `params["model"]` directly. `params` is built as the mapped pipeline's own params minus `required` markers, merged with the overrides.

`build_review_revise_definition` explicitly supports project overrides of the shipped pipeline — `tests/pipeline/test_review_revise.py::test_project_override_of_the_pipeline_is_picked_up` exercises it — and a project pipeline that drops or renames its `model` param makes this a `KeyError` that propagates out of `asyncio.run`, out of `run_review_revise`, and out of `_run_revise_loop_if_requested` as a traceback. Every other user-facing failure in this module goes through `typer.echo(..., err=True)` plus an exit code; this one does not.

### [CONCERN] CLI tests read the ambient project pipeline override

`_run_with` patches `execute_pipeline`, `classify_for_run` and `ContextForgeClient`, but not `build_review_revise_definition`. So `_run` calls the real `load_pipeline("P4")`, which resolves through `project → user → built-in`. The assertion `assert params["model"] == "opus"  # P4's own default, untouched` in `test_params_carry_slice_reviewer_and_rounds_without_a_reviser` therefore depends on the state of `project-documents/user/pipelines/P4.yaml` in whichever checkout the suite runs in, and on `~/.config/squadron/pipelines/`.

The sibling test module `tests/pipeline/test_review_revise.py` avoids exactly this by pinning the loader (`_shipped = partial(load_pipeline, project_dir=_NONEXISTENT, user_dir=_NONEXISTENT)`), with a comment naming the hazard: "The shipped pipelines, not any project or user override on this machine." `tests/cli/test_review_max_cli.py` has the same exposure. The same pin belongs here.

### [NOTE] `_configure_agent_logging` is invoked twice per `--max` run

`_run_revise_loop_if_requested` calls `_configure_agent_logging(_resolve_verbosity(verbose))`, but `_resolve_verbosity` already ends with `_configure_agent_logging(resolved)` — its docstring says so explicitly ("Also attaches agent/tool log handlers for the resolved level"). The outer call is a no-op repetition of work the callee owns. Passing `_resolve_verbosity(verbose)` alone would express the intent.

### [NOTE] A third copy of the resolver construction

`_run` builds `DefaultPoolBackend()` and `ModelResolver(cli_override=..., pipeline_model=definition.model, pool_backend=..., profile_source=has_profile_param(params))`. That is the same four-argument construction as `run_session.classify_for_run` (which the same function calls immediately above) and as `run._run_pipeline`. Three copies of a four-keyword constructor will drift; `classify_for_run`'s docstring already claims to be the one place that "owns the policy, the classification pool backend and resolver".

### [PASS] Exit-code mapping is centralized, documented, and tested at its boundaries

`outcome_of` is the single place the composed pipeline's result is translated to the D5 exit code, and it reads `accepted`/`exhausted` before run status for the reason stated in the docstring (an exhausted, unaccepted loop has `FAILED` status but earns exit 2, not 1). The helpers `_saved` and `_failure_text` keep the "was the artifact written" and "what was the failing step's text" decisions out of the branch chain, and the module-level `EXIT_OK`/`EXIT_RUN_FAILED`/`EXIT_REVIEW_FAILED` constants avoid scattering literals. The ordering-sensitive cases — `exhausted and not accepted`, exhausted-and-accepted, a failed round commit, a failed leading review, and an unsaved final review for both PASS and FAIL — each carry a dedicated test in `tests/cli/test_review_revise.py`, so the precedence rule is pinned rather than incidental.

### Run Digest

- Response length: 8354 chars
- Response is newline-free: no
- Tool calls made: 34
- Tool calls failed: 1
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 322311
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 2492639 / 2164864 / 87828 / 83211
- Duration: 754.5 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response (20261013)

All fixed in `fix: address slice 941 code review findings`, except where noted.

- **F001 (run lock):** fixed. `run_review_revise` holds `project_run_lock(cwd)` when `pipeline_mutates` (always true for the composed loop); a held or unreadable lock exits 1 before anything runs.
- **F002 (`ValueError` subclasses escape):** fixed. `SliceNotInPlanError` and `NoDesignFileError` are refused like `GitEnvironmentError`. A builder shape error is now refused too, instead of a traceback.
- **F003 (`RoundPrinter` raises from observer callbacks):** fixed by honoring the contract, not changing it. The loop shape is already checked at build time, so an impossible round prints `<no review result>`, `<no commit result>` or `<no verdict>` instead of raising.
- **F004 (`params["model"]` unguarded):** fixed. A pipeline with no `model` param and no `--revise-model` exits 1 with an error naming the param.
- **F005 (tests read ambient overrides):** fixed. Both CLI test modules pin the shipped pipelines.
- **F006 (logging configured twice):** fixed.
- **F007 (third resolver copy):** partly fixed. `run_session.run_resolver` is shared by `classify_for_run` and the runner. `run._run_pipeline` keeps its own construction for now: about 60 `sq run` tests patch `ModelResolver` in `run.py`, and moving it would mean rewriting all of them in this slice.
