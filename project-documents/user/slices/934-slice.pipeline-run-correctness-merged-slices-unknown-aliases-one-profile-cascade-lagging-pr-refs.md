---
docType: slice-design
slice: pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [196, 197]
interfaces: []
dateCreated: 20261006
dateUpdated: 20261006
status: not_started
---

# Slice Design: Pipeline Run Correctness — Merged Slices, Unknown Aliases, One Profile Cascade, Lagging PR Refs

## Overview

Four bugs where a run does the wrong thing instead of failing or finishing cleanly:

1. **A merged slice reads as open** ([#188](https://github.com/ecorkran/squadron/issues/188)). cf derives slice status from task checkboxes first. When the implement agent leaves the boxes unchecked, `implement-plan` merges the slice and cf still reports it `not_started`. Item resume then flags its dependents ([item_resume.py:327](../../../src/squadron/pipeline/item_resume.py#L327)), and a batch rerun selects it again ([sources.py:242](../../../src/squadron/pipeline/sources.py#L242)). The slice branch is now an ancestor of the target, so `existing: keep` finds no work and the slice is reimplemented.
2. **Unknown aliases** ([#175](https://github.com/ecorkran/squadron/issues/175)). Slice 196 (D13) added `require_known_model`, the pre-run check in `classify_pipeline`, and the backstop in `ModelResolver._resolved`. The issue stays open for two reasons. The check's "is there a profile source" test is the pipeline's own (`has_profile_param`), which #184 says is wrong for review steps. Also, `sq run review 931 --model glm-flash-low. --dry-run` exits 0 today (observed 20261006), because the dry-run path never classifies.
3. **Two profile cascades** ([#184](https://github.com/ecorkran/squadron/issues/184)). `sq review` resolves the profile as flag → alias profile → template `profile:` → `default_review_profile` → `sdk` ([cli/commands/review.py:531](../../../src/squadron/cli/commands/review.py#L531)). A pipeline `review:` step uses param → alias profile → `sdk` ([pipeline/actions/review.py:198](../../../src/squadron/pipeline/actions/review.py#L198)). The same template and model can run on different profiles depending on the path.
4. **Lagging PR ref** ([#186](https://github.com/ecorkran/squadron/issues/186)). `fetch_pull_request_refs` fetches `refs/pull/N/head` and requires it to equal the API's `headRefOid` ([refs.py:150](../../../src/squadron/codehost/refs.py#L150)). On GHE the PR ref stayed one commit behind the branch for over 30 minutes. The error then says "head moved since resolution", which sends the reader looking for a race. It does not say which source returned which sha, gives no fix hint, and prints twice. It prints twice because the CLI configures no handler for `squadron.codehost`, so Python's `logging.lastResort` echoes the adapter's WARNING record bare to stderr, and then `render_code_host_error` prints the same text.

## Value

- `implement-plan` reruns and item resumes trust git's record of what was merged. They stop reimplementing finished slices and stop blocking their dependents.
- A review template runs on the same profile whether it is started from `sq review` or from a pipeline step. The unknown-alias check accepts and rejects the same names on both paths (interface parity).
- `sq run --dry-run` catches a mistyped alias without spending a model call and without risking a slot's artifact.
- `sq review pr` works on hosts whose PR refs lag. When the head cannot be fetched, the error names each source and its sha, prints once, and says what to do.

## Technical Scope

**Included**
- A shared `merged_slice_branches` predicate in `pipeline/git_ops.py`, used by `cf.slices_ready_to_implement`, item resume's dependency check, and item resume's reconcile path (#188).
- A shared review-profile resolution module used by `sq review`, the pipeline review action, and the review-step alias check (#184, #175).
- `sq run --dry-run` runs the same pre-run alias check as a real run (#175).
- A head-ref fallback in `refs.fetch_and_range`, source-naming errors, `FetchedRange.adjustments`, and one stderr line per failure for code-host commands (#186).

**Excluded**
- `implement-plan` does not check off task boxes or edit design frontmatter (see D1).
- Changing cf's status derivation. That precedence belongs to context-forge.
- The base-side fast-forward rule (#131) is unchanged. It moves onto `adjustments` so it stays visible (D9).
- GitLab or other code hosts. Only the GitHub adapter implements `fetch_pull_request_refs` today.

**Effort and risk, restated.** The plan entry (Effort 3/5, Risk Low) covered four fixes. The design adds four pieces the fixes need:
- the `cwd` argument on each-sources (D1)
- unknown review templates failing before the run (D4)
- one classification helper shared by run, dry-run and explain (D5)
- `FetchedRange.adjustments` and the code-host log filter (D8, D9)

**Why one slice, not four.** The plan entry bundled the four fixes, and the design keeps them together, because #175 and #184 share one change (the profile-source helper and the classifier wiring). The other two pieces share nothing with them or each other:
- #188 (`git_ops`, `sources`, `item_resume`)
- #186 (`codehost`, `cli/commands/pr*`)

So each lands as its own task group with its own commits, in the order given under Implementation Notes, and none waits on another. If the PM prefers separate slices, the split falls along exactly these lines and the decisions carry over unchanged.

Revised: **Effort 4/5, Risk Low.** Each piece is local and has its own test, and every ambiguous case fails closed (D1, D6) or fails before the run (D4, D5). The plan entry is updated to match.

## Dependencies

### Prerequisites
- **197** (complete): `implement-plan`, `cf.slices_ready_to_implement`, item resume (D2, D8), `merge_slice_branch` with `--no-ff`.
- **196** (complete): `require_known_model`, the classification pre-run check, the resolver backstop (D13).

### Interfaces Required
- `git` with `merge-base --is-ancestor`, `rev-list --first-parent`, `for-each-ref`.
- The `cf` client's `list_slices` (status, design file, dependencies) and `get_config("git.integration_branch")` via `read_integration_target`.
- GitHub's support for fetching a reachable commit by sha.

## Architecture

### Component Structure

```
pipeline/git_ops.py            CHANGED  merged_slice_branches()                      (#188)
pipeline/sources.py            CHANGED  sources take cwd; merged slices count as closed (#188)
pipeline/executor.py           CHANGED  evaluate_each_source(..., cwd=) passes the run's cwd (#188)
cli/commands/run_dry_run.py    CHANGED  passes cwd to evaluate_each_source (#188)
pipeline/item_resume.py        CHANGED  dependency check and reconcile use the predicate (#188)
review/profile_resolution.py   NEW      resolve_review_profile(), review_profile_source() (#184)
cli/commands/review.py         CHANGED  _resolve_profile and _reject_unknown_alias delegate (#184)
pipeline/actions/review.py     CHANGED  profile from the shared helper; per-action profile source (#184)
pipeline/resolver.py           CHANGED  resolve_full(..., profile_source=) per-call override (#184)
pipeline/classification.py     CHANGED  one template lookup; review profile source; unknown template pre-run (#175/#184)
cli/commands/run.py            CHANGED  _classify_for_run shared by run, --explain, --dry-run (#175)
codehost/refs.py               CHANGED  head fallback, source-naming errors, adjustments (#186)
codehost/errors.py             CHANGED  PullRequestHeadUnavailableError; RefMoved message names sources (#186)
codehost/models.py             CHANGED  RefAdjustment; FetchedRange.adjustments (#186)
cli/commands/pr.py             CHANGED  configure_code_host_logging; adjustments printed once (#186)
```

### Data Flow

**#188 selection.** `cf.slices_ready_to_implement` reads the plan's slices from cf, then calls `merged_slice_branches(entries, target, cwd)` once. A slice in that set (`merged`) is treated as `complete` at the two places the source reads status ([sources.py:256-276](../../../src/squadron/pipeline/sources.py#L256)):
- **Item loop:** `if entry.status in _EXCLUDED_STATUSES or entry.index in merged: continue`. A merged slice is never returned as an item.
- **Dependency flag:** the source flags `dependency D not designed` only when `D in open_in_plan and D not in returned`. `open_in_plan` becomes `{e.index for e in entries if e.status not in _EXCLUDED_STATUSES and e.index not in merged}`. A merged dependency is therefore never flagged. A dependency that is open per cf, not merged, and not returned is flagged exactly as today.

`in_plan` (the "outside plan" warning) is unchanged. A test asserts both points: the merged slice is absent from the items, and its dependent carries no `flag_reason`.

Each merged slice is logged at WARNING: `slice 108: branch 108-slice.x is merged into dev/erik but cf reports not_started; treating it as complete. Check off its tasks to close it in cf.`

**#188 resume.** `_open_dependencies` asks cf for statuses and asks the predicate which in-plan dependencies are merged. A dependency counts as complete if either answer says so. `_select_item`'s reconcile path, for an item that is no longer selected, reconciles to PASSED when the predicate reports it merged, whatever cf's status is.

**#184 / #175 profile.**

```
sq review:     flag ─┐
pipeline step: param ┴─► resolve_review_profile(explicit, alias_profile, template)
                         explicit → alias profile → template.profile → default_review_profile → sdk
                         returns ReviewProfileChoice(name, source)

alias check:   review_profile_source(explicit_present, template)
               True when explicit, template.profile, or default_review_profile is set
               (never the alias profile, never the sdk default)
```

The pipeline review action computes `review_profile_source(...)` for its template and passes it to `resolver.resolve_full(..., profile_source=...)`. Classification does the same for every `review` action, after resolving its `template` placeholder. Other action types keep `has_profile_param`.

**#186 fetch.** The API head sha is usually not in the local clone when `refs/pull/N/head` lags: nothing has fetched it. Ancestry can only be tested once both commits are local, so the fetch comes first and the classification second.

```
fetch base + refs/pull/N/head ──► PR-ref sha == API head? ── yes ─► range
                                        │ no
                                        ▼
            API head present locally? (cat-file -e <sha>^{commit})
                 │ no                                   │ yes
                 ▼                                      │
   fetch <sha> by sha → <api_local>;                    │
   else refs/heads/<head_ref> → <api_local>;            │
   each verified == API head                            │
     │ none yields it        │ one does                 │
     ▼                       └──────────┬───────────────┘
 PullRequestHeadUnavailableError         ▼
 (names every source + reason)   PR-ref sha ancestor of API head?
                                   │ yes (lag)          │ no (descends or unrelated)
                                   ▼                    ▼
                         head_local := API head   RefMovedSinceResolutionError
                         range + RefAdjustment    (names both sources + hint)
```

### State Management

No new persisted state. `FetchedRange.adjustments` is in-memory, and the PR review artifact's existing provenance takes the head sha actually reviewed. The #188 predicate reads git each time and caches nothing.

## Technical Decisions

### D1: #188, git is the record of a merged slice; implement-plan does not close out slices

Option A (implement-plan checks every task box and marks the slice complete before merging) is rejected. It would record 149 items as done that nobody verified, which fabricates state. Marking only the design frontmatter does not help, because cf ranks task completion above frontmatter. Option B (a merged slice branch means complete) uses a fact squadron already relies on: `merge_slice_branch` returns `ALREADY` on the same ancestry test.

Ancestry alone is not enough. A branch that was entered but never committed to sits on the target's history too. The predicate therefore requires both of these:
- the branch tip is an ancestor of the target (`merge-base --is-ancestor`), and
- the tip is **not** on the target's first-parent chain (`rev-list --first-parent <target>`).

`merge_slice_branch` always merges with `--no-ff`, so a merged slice's tip is a second parent. An empty branch's tip lies on the first-parent chain. A hand merge that fast-forwarded reads as not merged, which falls back to today's behavior (cf decides) and never to wrongly closing a slice. A missing branch reads as not merged.

`merged_slice_branches(entries, target, cwd) -> set[int]` makes one `for-each-ref` call for branch tips, one `rev-list --first-parent` call, and one `--is-ancestor` call per candidate. A git failure is logged and raises `GitStateUnknownError`. Selection does not guess.

**The repository is the run's `cwd`, passed in, never read from the process.** Sources get no `cwd` today (`(args, cf_client, params)`). D1 widens the each-source contract instead of having a source call `os.getcwd()`, which would be a second definition of "the repository":
- `SourceFn` gains a keyword `cwd: str`, and `evaluate_each_source(source, params, cf_client, *, cwd)` passes it on. All four registered sources take it. Only `slices_ready_to_implement` uses it.
- Callers pass the `cwd` they already hold: the executor's `effective_cwd` ([executor.py:1535](../../../src/squadron/pipeline/executor.py#L1535)), item resume's `cwd` ([item_resume.py:289](../../../src/squadron/pipeline/item_resume.py#L289)), and the dry-run renderer ([run_dry_run.py:77](../../../src/squadron/cli/commands/run_dry_run.py#L77)), which gets it from `run()`, the same value `_run_pipeline` would use.
- `cf` subprocesses still run in the process cwd. `sq run` has no `--cwd` flag, so the two are equal in every CLI path today. The predicate does not check that equality. A future `--cwd` must point the cf client at the same directory, and that is that change's work, not this slice's.

### D2: #188, the D2 "all tasks checked" row stays

It covers a different case (tasks checked, slice not marked complete), and it does not overlap with D1.

### D3: #184, one review-profile module

`review/profile_resolution.py` owns:
- `ReviewProfileSource` (StrEnum: `explicit`, `alias`, `template`, `config`, `default`)
- `ReviewProfileChoice(name: str, source: ReviewProfileSource)`
- `resolve_review_profile(explicit: str | None, alias_profile: str | None, template: ReviewTemplate | None) -> ReviewProfileChoice`
- `review_profile_source(explicit_present: bool, template: ReviewTemplate | None) -> bool`

It keeps `sq review`'s order, alias profile included. That order is the published behavior, and the pipeline path is the one that changes. The `sdk` fallback is `ProfileName.SDK`, defined once. `cli/commands/review.py:_resolve_profile` and the inline cascade in `pipeline/actions/review.py` are deleted, and both call sites use the module.

`review_profile_source` and `resolve_review_profile` read `default_review_profile` through one private reader, so the guard and the cascade cannot disagree (this is the drift 196 D13 documented by hand).

### D4: #175/#184, the alias check's profile source is per action

`ModelResolver` keeps the run-level `profile_source` for dispatch, summary and compact. `resolve_full` gains a keyword `profile_source: bool | None = None`. `None` uses the run's value, and the review action passes `review_profile_source(...)`. `resolve()` is unchanged. `classify_pipeline`'s `_collect_unknown_alias` takes a `profile_source: bool` from its caller. For `review` actions the caller loads the template named in the action config (after placeholder resolution) and calls `review_profile_source`.

**An unknown review template becomes a pre-run error. That is a new failure path.** Today classification tolerates it: `_review_template_model_fallback` ([classification.py:77](../../../src/squadron/pipeline/classification.py#L77)) returns `None` for an unknown name, and the run fails later when the review action raises `KeyError` on template load. Once the profile source depends on the template, an unknown template would quietly mean "no template profile", and the alias check would report a misleading unknown alias. So:
- One template lookup in classification, `_review_template(action_type, resolved_cfg) -> ReviewTemplate | None`, serves both the model fallback and `review_profile_source`. It raises `UnknownReviewTemplateError(name, close_matches)` when the resolved name has no template.
- These errors are collected with the alias errors into the single pre-run `ClassificationError` (196 D13's shape), so one run reports every bad name. Message: `unknown review template 'cod'; did you mean: code?`
- A name that still holds an unresolved placeholder after merging params (filled per `each` item) is skipped before the run, as alias candidates already are. At run time the review action's existing `KeyError` path and the resolver backstop cover it.
- Any review pipeline that names an unknown template now fails before step 1 instead of at that step. That is the intended change. No built-in pipeline does this (`src/squadron/data/pipelines` names templates only literally). A test loads every built-in pipeline through classification to keep it that way.

Result: a literal model id that `sq review` accepts because `default_review_profile` is set is accepted by a pipeline review step too, and it runs on that profile.

### D5: #175, `--dry-run` runs the pre-run alias check

A preview is meant to select what a run would, and a dry run is the safe place to catch a typo. Today the run path builds its classifier inline ([run.py:322-347](../../../src/squadron/cli/commands/run.py#L322)), `--explain` builds a second copy ([run.py:531-545](../../../src/squadron/cli/commands/run.py#L531)), and `--dry-run` ([run.py:1175](../../../src/squadron/cli/commands/run.py#L1175)) never classifies.

`run.py` gains one helper:

```python
def _classify_for_run(definition, *, model_override, params, strict) -> PipelineClassification
```

It owns everything the three paths must agree on:
- **Policy:** YAML `auth_policy` < `--strict`.
- **Pool backend:** `DefaultPoolBackend()`. Classification needs it to recognise `pool:` candidates and check pool membership, and it never calls `select()`.
- **Resolver:** `ModelResolver(cli_override=model_override, pipeline_model=definition.model, pool_backend=…, profile_source=has_profile_param(params))`.
- **Call:** `classify_pipeline(definition, resolver, pool_backend, policy=…, params=params)`.

It returns the classification or raises `ClassificationError`. Callers:
- `_run_pipeline_sdk` uses it in place of its inline block, and its own pool backend for the authoritative resolver is unchanged.
- `--explain` uses it with `explain_params`.
- `--dry-run` uses it with the params from `_assemble_params` and `_extract_model_override(model, param)`, the same inputs a run gets.

On `ClassificationError`, dry-run prints the run path's message (`Error: Pipeline classification failed — …`) and exits 1 before rendering any step. On success it renders as today. Dry-run gains the `--strict` handling the other two paths already have.

### D6: #186, the head fallback

When the fetched `refs/pull/N/head` sha (the PR-ref sha) differs from the API head sha:

1. **Obtain the API head locally.** If `git cat-file -e <api-sha>^{commit}` succeeds, it is already present. Otherwise try, in order, each fetching into `<api_local>`, a sibling of `head_local` in the same per-PR namespace:
   1. `git fetch <remote> +<api-sha>:<api_local>`. This works for same-repo and fork PRs when the host serves the commit by sha.
   2. `git fetch <remote> +refs/heads/<head_ref>:<api_local>`.

   After each attempt, `rev-parse <api_local>` must equal the API head sha. On a fork PR, attempt 2 may fetch a same-named branch of the base repo, and this check rejects it. If no attempt yields the sha, raise `PullRequestHeadUnavailableError` (a `CodeHostError`, role HEAD). It cannot say "lags", because without the commit the relationship is unknown.
2. **Classify, now that both commits are local.** `refs._is_ancestor` answers "no" when a commit is absent (it fails closed). That is why this step must come after step 1 and never before.

| PR-ref sha vs API head | Meaning | Action |
|---|---|---|
| PR-ref sha is an ancestor | PR ref lags | `update-ref head_local <api-sha>`, record a `RefAdjustment`, build the range |
| PR-ref sha descends from it | pushed after resolution | `RefMovedSinceResolutionError`, hint: rerun |
| unrelated | force-push or rewrite | `RefMovedSinceResolutionError`, hint: rerun |

The guard against reviewing a stale commit is unchanged. Only the exact API head sha is ever reviewed.

The refspec strings are GitHub conventions. `fetch_pull_request_refs` passes the attempt-2 refspec in as a `head_fallback_sources: tuple[str, ...]` argument (attempt 1 uses the sha, which is host-neutral) to `fetch_and_range`, so `refs.py` stays host-neutral.

### D7: #186, error text names sources

- `RefMovedSinceResolutionError` gains `expected_source` and `actual_source` labels. Message: `head moved since resolution: host API reported ae1cbf2…, refs/pull/49/head fetched d3008a6…`. Fix hint: `Rerun to resolve the pull request again.`
- `PullRequestHeadUnavailableError` message: `pull request head ae1cbf2… (host API) could not be fetched; refs/pull/49/head on origin is d3008a6…; fetch by sha: <reason>; refs/heads/dev/jane: <sha that did not match | reason>`. Fix hint: `The host's pull-request ref and its API disagree, and the API head is not fetchable from origin yet. Rerun later, or push the head branch to a remote this checkout can fetch.`

### D8: #186, one line per failure

The adapter keeps logging every failure at WARNING (Failure-Mode Enumeration). The duplicate comes from `logging.lastResort`. The fix suppresses only the records the command itself prints. Every other `squadron.codehost` diagnostic stays visible at every verbosity.

- **Tag.** `codehost/errors.py` defines `RENDERED_BY_CALLER` (one constant, the `extra` key). A codehost log call sets `extra={RENDERED_BY_CALLER: True}` only when the command is guaranteed to print the same fact:
  - a WARNING logged right before raising a `CodeHostError` (printed by `render_code_host_error`)
  - a WARNING describing a `RefAdjustment` (printed by D9's adjustment line)

  Nothing else is tagged: other WARNINGs from `remotes`, `worktree`, `metadata_lock`, and so on.
- **Handler, scoped to the command.** `code_host_logging(verbosity: int)` is a context manager next to `render_code_host_error`. The `squadron.codehost` logger is process-global, so the helper must not leave anything behind for tests or other commands in the same process.
  - **On entry** it records the logger's current level, then adds one stderr handler with the format `%(levelname)s %(name)s: %(message)s` and the filter below. It sets the logger's level to WARNING at verbosity 0, INFO at 1, DEBUG at 2 or more.
  - **On exit** (`finally`, so a raised `typer.Exit` also cleans up) it removes exactly that handler and restores the level.
  - `propagate` is not touched. Records still reach root handlers such as pytest's `caplog`. `lastResort` is not used, because Python falls back to it only when no handler is found anywhere in the logger's hierarchy, and this handler is one.
  - **Nesting:** an inner call that finds its handler already attached is a no-op on entry and on exit. It adds no second handler and does not remove the outer one. A test enters the helper twice and asserts one handler while inside and zero after.
- **Filter.** Below verbosity 2 it drops tagged records. At 2 or more it keeps them, so the full diagnostic trail is there when asked for.
- **Callers and their verbosity source.** Only two commands render `CodeHostError` today (`grep render_code_host_error`):
  - `sq review pr` already resolves verbosity (`_resolve_verbosity(verbose)`, [review_pr.py:378](../../../src/squadron/cli/commands/review_pr.py#L378)). It wraps its body after that line in `with code_host_logging(verbosity):`.
  - `sq pr show` and `sq pr create` have no `-v` option. They call `code_host_logging(0)`: render-once, with untagged warnings shown. This slice adds no flag to them. The `-vv` diagnostic trail for a failing fetch is reachable through `sq review pr -vv`, which shares the fetch path (`resolve_and_fetch_pull_request`).

Effect: at default and `-v`, a failure prints exactly once (the render). An untagged codehost warning prints once with its level and logger prefix, as it already does via `lastResort` but now prefixed. Nothing that is visible today disappears. A test asserts that an untagged WARNING still reaches stderr at default verbosity, and that a tagged one does not.

### D9: #186, adjustments are data, not log lines

`RefAdjustment(role: RefRole, reported_sha: str, used_sha: str, source: str, reason: str)` goes on `FetchedRange.adjustments: tuple[RefAdjustment, ...]`. It covers the #131 base fast-forward and the #186 head fallback. The command prints each adjustment once, dim, on stderr: `head: refs/pull/49/head lags; reviewed ae1cbf2… fetched by sha`. The matching WARNING is tagged under D8, so each adjustment prints once at default verbosity. The PR review artifact gets the head sha that was actually reviewed.

### D10: Failure modes of the new I/O paths

Every new git or network call has a bound, an observable signal, and a test asserting that signal. Bounds:
- `run_git` (pipeline): `GIT_COMMAND_TIMEOUT_SECONDS`; it returns `None` on a timeout or a spawn failure.
- `refs.py` fetches: `GIT_FETCH_TIMEOUT_SECONDS`.
- `refs.py` queries: `GIT_QUERY_TIMEOUT_SECONDS`.

**#188 predicate** (`merged_slice_branches`, local git):

| Call | Hangs / times out | Git refuses (non-zero) | Observable signal | Result |
|---|---|---|---|---|
| `for-each-ref refs/heads` (tips) | `None` | non-zero exit | ERROR via `logger.exception`, naming the command and stderr | raises `GitStateUnknownError` |
| `rev-list --first-parent <target>` | `None` | non-zero (e.g. target missing) | same | raises `GitStateUnknownError` |
| `merge-base --is-ancestor` per candidate | `None` | exit not in (0, 1) | same | raises `GitStateUnknownError` |
| branch absent from `for-each-ref` | — | — | none (a normal answer) | not merged; cf decides |
| branch merged, cf says open | — | — | WARNING naming slice, branch, target, cf status | treated as complete |

When the source raises, the `each` step fails before any item runs. That failure is logged and reported the way a cf failure in a source is today. Item resume surfaces it as the resume's error and changes no report record.

**#186 head fallback** (network):

| Call | Hangs / times out | Peer disconnects or host refuses | Observable signal | Result |
|---|---|---|---|---|
| `cat-file -e <api-sha>^{commit}` | `ProcessTimedOutError` → `HostCommandTimeoutError` | exit non-zero = absent (a normal answer) | DEBUG | go to the fetch attempts |
| `fetch <remote> +<sha>:<api_local>` | `ProcessTimedOutError` caught for this attempt; recorded as `timed out after Ns` | non-zero exit (e.g. `not our ref`, `upload-pack: not our ref`); stderr recorded | DEBUG per attempt; reason carried into the next step | next fallback |
| `fetch <remote> +refs/heads/<head_ref>:<api_local>` | same | same | same | verify, or raise |
| `<api_local>` after a partial or failed fetch | — | ref absent or at another sha | verification against the API head sha | that attempt fails; the stale PR-ref sha is never reviewed |
| `merge-base --is-ancestor` (classification) | `ProcessTimedOutError` → `HostCommandTimeoutError` | exit not in (0, 1) → answered no (existing fail-closed) | WARNING (existing) | `RefMovedSinceResolutionError` |
| `update-ref head_local <api-sha>` | `ProcessTimedOutError` → `HostCommandTimeoutError` | non-zero | WARNING (tagged) + rendered `RefNotFetchableError` | exit 1 |
| all attempts fail | — | — | WARNING (tagged, D8) plus a single rendered `PullRequestHeadUnavailableError` naming each attempt and its reason | exit 1 |
| fallback succeeds | — | — | dim adjustment line (D9) plus a tagged WARNING | review proceeds |

`ProcessRunner.run` raises `ProcessTimedOutError` on timeout. `refs.py` catches it nowhere today, so even the primary `_fetch` timing out escapes `sq review pr` as a traceback instead of a rendered `CodeHostError`. The slice handles both cases:
- The primary fetch converts the timeout to the existing `HostCommandTimeoutError`, as `github_cli.py:504` does for `gh` calls.
- A fallback attempt catches it and records it as that attempt's reason.

The fallback adds no new runner method. Tests drive each row through the fake `ProcessRunner`: timeout, `not our ref`, a branch whose fetched sha disagrees, and success.

## Integration Points

### Provides to Other Slices
- `merged_slice_branches()` for any later source or resume path that needs "is this slice done" with git as the record.
- `review/profile_resolution.py` as the single review-profile cascade. Slice 935 (rules injection) and any new review entry point resolve profiles through it.
- `FetchedRange.adjustments` for PR review provenance.

### Consumes from Other Slices
- 197's `merge_slice_branch` `--no-ff` guarantee. D1's first-parent test depends on it. A future change to fast-forward merges would turn D1 off silently, so the predicate's docstring cites the existing `--no-ff` assertion (`tests/pipeline/test_branch_merge.py:88`).
- 196's `require_known_model` and `UnknownModelAliasError`, unchanged.

## Success Criteria

### Functional Requirements
- **#188:** In a plan where slice A's branch is merged into the target with `--no-ff` and its tasks are unchecked, `cf.slices_ready_to_implement` does not return A, does not flag A's dependents for A, and logs one WARNING naming A, its branch, the target and cf's status.
- **#188:** Item resume of a dependent of A runs (no `dependency A not complete`). Item resume of A itself reconciles to PASSED.
- **#188:** A slice branch entered but with no commits, a missing branch, or a fast-forward-merged branch is not treated as merged.
- **#188:** A git failure or timeout in the predicate logs at ERROR and raises `GitStateUnknownError`; it never returns an empty set silently (D10 rows, one test each).
- **#188:** The predicate reads the `cwd` handed to the source; a test runs the source with a `cwd` different from the process cwd and gets that repository's answer.
- **#184:** A pipeline `review:` step with no `profile` param, on a template that declares `profile:`, runs on that profile. With neither, it runs on `default_review_profile` when that is set. `sq review` and the pipeline choose the same profile for the same template, model and config (a parametrized parity test over every `ReviewProfileSource`).
- **#175/#184:** A literal non-alias model id with `default_review_profile` set is accepted by both `sq review` and a pipeline review step. With no profile source on either path, both reject it with the same message and close matches.
- **#175/#184:** A pipeline review step naming an unknown template fails before step 1 with `unknown review template '…'; did you mean: …?`, collected with any alias errors into one message. Every built-in pipeline still classifies cleanly.
- **#175:** `--dry-run`, `--explain` and a real run all classify through `_classify_for_run`; `--dry-run --strict` applies the strict policy.
- **#175:** `sq run review 931 --model glm-flash-low. --dry-run` exits 1 with `unknown model alias 'glm-flash-low.'; did you mean: glm-flash-low?…`. A real run fails before step 1, and the slot's existing review artifact is byte-identical afterwards.
- **#186:** When `refs/pull/N/head` lags and the API head sha is fetchable, the review runs on the API head sha and prints one adjustment line.
- **#186:** The fixture for the lag case has the API head sha **absent** from the local clone before the fetch, as in the issue. A fixture where it is already present does not count as covering the case.
- **#186:** When nothing yields the API head sha, `PullRequestHeadUnavailableError` names every source tried with its sha or failure, and gives the hint. A head that truly moved raises `RefMovedSinceResolutionError` naming both sources.
- **#186:** At default verbosity and `-v`, a `CodeHostError` appears on stderr exactly once. At `-vv` the tagged WARNING record also appears, prefixed with level and logger name. An untagged codehost WARNING appears at every verbosity.
- **#186:** A fetch timeout, primary or fallback, never escapes as a traceback: the primary raises `HostCommandTimeoutError`; a fallback timeout is a recorded attempt reason (D10).

### Technical Requirements
- Tests for each item above. The #188 predicate is tested against real temporary git repositories (merged `--no-ff`, fast-forward, empty branch, missing branch, git failure). The #186 cases use a fake `ProcessRunner` with a lagging `refs/pull` fixture shaped like the issue: PR ref one commit behind, branch and API at head, and the API head sha absent locally until a fallback fetch brings it in.
- No remaining copy of the review profile cascade: `_resolve_profile` and the inline cascade in `pipeline/actions/review.py` are gone, and `"sdk"` as a review-profile literal is gone.
- `ruff format`, `ruff check`, and `pyright` all clean.
- Issues #175, #184, #186, #188 are closed by the merge commit or by a closing comment that links the slice.

### Integration Requirements
- `implement-plan` reruns over a plan with a merged, unchecked slice proceed to the next open slice.
- `sq pr show` and `sq review pr` share the fetch path, so both get D6 to D9.

### Verification Walkthrough

Draft. Refined after Phase 6.

1. **#175 dry run (safe):**
   ```bash
   uv run sq run review 931 --model glm-flash-low. --dry-run; echo "exit=$?"
   ```
   Expected: `unknown model alias 'glm-flash-low.'; did you mean: glm-flash-low? If this is a literal model ID, set a profile.` and `exit=1`. (Today: the step list and `exit=0`.)

2. **#184 parity:** set `default_review_profile` to a non-SDK profile with credentials (e.g. `uv run sq config set default_review_profile openrouter`). Then:
   ```bash
   uv run sq review slice 934 --model <literal-openrouter-model-id> -v --no-save
   uv run sq run review 934 --model <literal-openrouter-model-id> -v
   ```
   Both run, and both verbose headers show `profile=openrouter`. Unset the config key, rerun either one, and both fail with the same unknown-alias message.

3. **#188 (scratch project):** in a scratch cf project with a two-slice plan where B depends on A, run `sq run implement-plan <plan>` so that A merges. Then uncheck all of A's tasks, so cf reports A `not_started`.
   ```bash
   uv run sq run implement-plan <plan> --dry-run
   ```
   Expected: A is absent from the item list, B is not flagged `dependency A not designed`, and stderr shows the WARNING naming A's branch and the target. Then `uv run sq run --resume <run-id> --item <B>` runs B without `dependency A not complete`.

4. **#186:** a lagging PR ref cannot be produced on demand on github.com, so the live check uses the unit fixture. Run:
   ```bash
   uv run pytest tests/codehost -k lagging -v
   ```
   For a live confirmation on a host that lags (GHE, per the issue), run `uv run sq review pr <n> --model sonnet`. Expected: one dim adjustment line naming `refs/pull/<n>/head` and the sha reviewed, and no "head moved" error. Force the failure case by pointing at a PR whose head sha the remote cannot serve. Expected: the error appears once, with every source named, followed by the hint.

## Implementation Notes

### Development Approach
1. **#184 + #175** (profile module, call-site deletion, per-action profile source, classification, dry-run). Do these first: they are small, and they make later live tests safe from typos.
2. **#188** (predicate with temp-repo tests, then sources, then item resume).
3. **#186** (errors and adjustments model, fallback in `fetch_and_range`, GitHub refspecs, CLI logging helper).

### Special Considerations
- D1 is conservative on purpose. Every ambiguous git shape falls back to cf's answer, never to "complete".
- D6 never reviews a sha other than the API head. The fallback only changes where that sha is fetched from.
