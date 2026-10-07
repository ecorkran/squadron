---
docType: slice-design
slice: pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [197]
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
pipeline/sources.py            CHANGED  merged slices excluded and count as closed   (#188)
pipeline/item_resume.py        CHANGED  dependency check and reconcile use the predicate (#188)
review/profile_resolution.py   NEW      resolve_review_profile(), review_profile_source() (#184)
cli/commands/review.py         CHANGED  _resolve_profile and _reject_unknown_alias delegate (#184)
pipeline/actions/review.py     CHANGED  profile from the shared helper; per-action profile source (#184)
pipeline/resolver.py           CHANGED  resolve_full(..., profile_source=) per-call override (#184)
pipeline/classification.py     CHANGED  review candidates use review_profile_source (#175/#184)
cli/commands/run.py            CHANGED  --dry-run runs the pre-run alias check (#175)
codehost/refs.py               CHANGED  head fallback, source-naming errors, adjustments (#186)
codehost/errors.py             CHANGED  PullRequestRefLaggingError; RefMoved message names sources (#186)
codehost/models.py             CHANGED  RefAdjustment; FetchedRange.adjustments (#186)
cli/commands/pr.py             CHANGED  no lastResort echo; adjustments printed once (#186)
```

### Data Flow

**#188 selection.** `cf.slices_ready_to_implement` reads the plan's slices from cf, then calls `merged_slice_branches(entries, target, cwd)` once. A slice in that set is treated as `complete`. It is skipped as an item and counts as closed for dependency flagging. Each one is logged at WARNING: `slice 108: branch 108-slice.x is merged into dev/erik but cf reports not_started; treating it as complete. Check off its tasks to close it in cf.`

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

**#186 fetch.**

```
fetch base + refs/pull/N/head ──► head sha == API head? ── yes ─► range
                                        │ no
                                        ▼
                     fetched is ancestor of API head? (PR ref lags)
                          │ yes                         │ no
                          ▼                             ▼
          fetch API head sha by sha;              RefMovedSinceResolutionError
          else refs/heads/<head_ref>;             (names both sources + hint)
          verify == API head
             │ ok                   │ fails
             ▼                      ▼
   range + RefAdjustment     PullRequestRefLaggingError
                             (names every source and sha + hint)
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

`sources.py` has no `cwd` today. Every `cf` call it makes runs in the process cwd, so the predicate gets that same directory (`os.getcwd()` at the call site). The executor's `effective_cwd` already defaults to it.

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

`ModelResolver` keeps the run-level `profile_source` for dispatch, summary and compact. `resolve_full` gains a keyword `profile_source: bool | None = None`. `None` uses the run's value, and the review action passes `review_profile_source(...)`. `resolve()` is unchanged. `classify_pipeline`'s `_collect_unknown_alias` takes a `profile_source: bool` from its caller. For `review` actions the caller loads the template named in the action config (after placeholder resolution) and calls `review_profile_source`. An unknown template is already a classification error, so no new failure path is added.

Result: a literal model id that `sq review` accepts because `default_review_profile` is set is accepted by a pipeline review step too, and it runs on that profile.

### D5: #175, `--dry-run` runs the pre-run alias check

The dry-run path calls `classify_pipeline` with the merged params and reports `UnknownModelAliasError` the same way a run does (exit 1, same message, same close matches). A preview is meant to select what a run would, and a dry run is the safe place to catch a typo.

### D6: #186, the head fallback

When the fetched `refs/pull/N/head` sha differs from the API head sha:

| fetched vs API head | Meaning | Action |
|---|---|---|
| fetched is an ancestor | PR ref lags | Fall back (below) |
| fetched descends from it | pushed after resolution | `RefMovedSinceResolutionError`, hint: rerun |
| unrelated | force-push or rewrite | `RefMovedSinceResolutionError`, hint: rerun |

Fallback order:
1. `git fetch <remote> +<api-head-sha>:<head_local>`. This works for same-repo and fork PRs when the commit is reachable on the host.
2. `git fetch <remote> +refs/heads/<head_ref>:<head_local>`.

After either fetch, `head_local` must equal the API head sha. On a fork PR the second fetch may pull a same-named branch from the base repo, and verification rejects it. When both fail, `PullRequestRefLaggingError` (a `CodeHostError`, role HEAD) is raised.

The guard against reviewing a stale commit is unchanged. Only the exact API head sha is ever reviewed.

The refspec strings are GitHub conventions. `fetch_pull_request_refs` passes them in as a `head_fallback_sources: tuple[str, ...]` argument to `fetch_and_range`, so `refs.py` stays host-neutral.

### D7: #186, error text names sources

- `RefMovedSinceResolutionError` gains `expected_source` and `actual_source` labels. Message: `head moved since resolution: host API reported ae1cbf2…, refs/pull/49/head fetched d3008a6…`. Fix hint: `Rerun to resolve the pull request again.`
- `PullRequestRefLaggingError` message: `refs/pull/49/head on origin is behind the pull request head: host API reports ae1cbf2…, refs/pull/49/head is d3008a6…; fetching ae1cbf2… by sha failed: <reason>; refs/heads/dev/jane is <sha | not fetchable: reason>`. Fix hint: `The host has not updated its pull-request ref yet. Rerun later, or push the head branch to a remote this checkout can fetch.`

### D8: #186, one line per failure

The adapter keeps logging every failure at WARNING (Failure-Mode Enumeration). The duplicate comes from `logging.lastResort`. The code-host commands (`sq pr show`, `sq review pr`, and the other `sq pr` commands that render `CodeHostError`) attach a `NullHandler` to `squadron.codehost` at default verbosity and `-v`. At `-vv` they route it to stderr with a `%(levelname)s %(name)s:` prefix, so a diagnostic record never looks like the operator error. The wiring is one helper next to `render_code_host_error`, called by every such command.

### D9: #186, adjustments are data, not log lines

`RefAdjustment(role: RefRole, reported_sha: str, used_sha: str, source: str, reason: str)` goes on `FetchedRange.adjustments: tuple[RefAdjustment, ...]`. It covers the #131 base fast-forward and the #186 head fallback. The command prints each adjustment once, dim, on stderr: `head: refs/pull/49/head lags; reviewed ae1cbf2… fetched by sha`. D8 hides codehost log records below `-vv`, so without this the #131 note would disappear at default verbosity.

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
- **#188:** A git failure in the predicate raises `GitStateUnknownError`. It never returns an empty set silently.
- **#184:** A pipeline `review:` step with no `profile` param, on a template that declares `profile:`, runs on that profile. With neither, it runs on `default_review_profile` when that is set. `sq review` and the pipeline choose the same profile for the same template, model and config (a parametrized parity test over every `ReviewProfileSource`).
- **#175/#184:** A literal non-alias model id with `default_review_profile` set is accepted by both `sq review` and a pipeline review step. With no profile source on either path, both reject it with the same message and close matches.
- **#175:** `sq run review 931 --model glm-flash-low. --dry-run` exits 1 with `unknown model alias 'glm-flash-low.'; did you mean: glm-flash-low?…`. A real run fails before step 1, and the slot's existing review artifact is byte-identical afterwards.
- **#186:** When `refs/pull/N/head` lags and the API head sha is fetchable, the review runs on the API head sha and prints one adjustment line.
- **#186:** When nothing yields the API head sha, `PullRequestRefLaggingError` names every source tried with its sha or failure, and gives the hint. A head that truly moved raises `RefMovedSinceResolutionError` naming both sources.
- **#186:** At default verbosity and `-v`, a `CodeHostError` appears on stderr exactly once. At `-vv` the WARNING record also appears, prefixed with level and logger name.

### Technical Requirements
- Tests for each item above. The #188 predicate is tested against real temporary git repositories (merged `--no-ff`, fast-forward, empty branch, missing branch, git failure). The #186 cases use a fake `ProcessRunner` with a lagging `refs/pull` fixture shaped like the issue (PR ref one commit behind, branch and API at head).
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
