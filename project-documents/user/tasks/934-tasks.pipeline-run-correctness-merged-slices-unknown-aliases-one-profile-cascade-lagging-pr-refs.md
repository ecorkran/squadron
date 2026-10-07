---
docType: tasks
slice: pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs
project: squadron
lld: user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md
dependencies: [196, 197]
projectState: >
  Slice design complete (20261006) and through two review rounds (both CONCERNS, all findings
  addressed). No code written. 196 and 197 are complete. `git.integration_branch` is set
  (`squadron-issues`), so the slice branch forks from it.
dateCreated: 20261007
dateUpdated: 20261007
status: not_started
---

## Context Summary

- Working on **934 pipeline-run-correctness**: four bugs where a run does the wrong thing
  instead of failing or finishing cleanly. #184 (one review-profile cascade) and #175 (unknown
  aliases, `--dry-run`), #188 (merged slice reads as open), #186 (lagging PR ref).
- Tasks reference the slice design by decision number (D1–D10). Its D-sections, the D10
  failure-mode tables, Success Criteria and Verification Walkthrough are the contract.
- Order follows the design's Development Approach: Part A (#184 + #175), Part B (#188),
  Part C (#186), Part D (docs, walkthrough, close-out). Each part is independent of the others.
- Every git test runs in a temporary repo the test creates, never the project checkout. Every
  D10 row has a test asserting both the outcome and the log record (level and message).
- Every task that changes code ends with `ruff format`, `ruff check`, `pyright` (zero errors),
  its tests, and a commit on the slice branch. Locate existing tests with `grep` before adding
  new files. Commit messages use the repo's semantic prefixes.
- Out of scope: `implement-plan` checking boxes or editing frontmatter (D1), changing cf's
  status derivation, the #131 base fast-forward rule (it only moves onto `adjustments`), GitLab
  and other hosts.
- Effort: 4/5. Closes #175, #184, #186, #188.

---

## Task 1 — Create the slice branch

- [ ] Run `cf config get git.integration_branch`; call its value the target. Confirm `git status` is clean and the current branch is the target
- [ ] `git checkout -b 934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs {target}`
  - [ ] Success: `git branch --show-current` prints the new branch name

---

## Part A — #184 / #175: one review-profile cascade, per-action profile source, dry-run check

## Task 2 — `review/profile_resolution.py` (D3)

- [ ] Create the module with `ReviewProfileSource` (StrEnum: `explicit`, `alias`, `template`, `config`, `default`) and `ReviewProfileChoice(name, source)`
- [ ] `resolve_review_profile(explicit, alias_profile, template)` returns the choice in this order: explicit → alias profile → `template.profile` → `default_review_profile` → `ProfileName.SDK`
  - [ ] The sdk fallback is `ProfileName.SDK`, never a `"sdk"` literal
- [ ] `review_profile_source(explicit_present, template) -> bool` is True when explicit, `template.profile`, or `default_review_profile` is set; never for the alias profile or the sdk default
- [ ] Both functions read `default_review_profile` through one private reader (find how `cli/commands/review.py:_resolve_profile` reads it today and move that read here)
- [ ] Tests (`tests/review/`): one case per `ReviewProfileSource`, order precedence (explicit beats all, alias beats template, and so on), template `None`, and `review_profile_source` agreeing with `resolve_review_profile` (source is never `alias`/`default` when it returns True; True exactly when the source is `explicit`, `template` or `config`)
  - [ ] Success: tests pass
- [ ] Commit: `feat: add shared review profile resolution module`

## Task 3 — `sq review` delegates to the module

- [ ] In `cli/commands/review.py`, delete `_resolve_profile` and make its call site use `resolve_review_profile`
- [ ] `_reject_unknown_alias` computes its profile-source test with `review_profile_source`; no second copy of the "is a profile set" logic remains in the file
- [ ] Tests: existing `tests/cli/test_review_profile.py` and `test_review_resolve.py` pass unchanged; add one case where `default_review_profile` makes a literal id acceptable
  - [ ] Success: tests pass; `grep -n "_resolve_profile" src/` finds no definition
- [ ] Commit: `refactor: route sq review profile cascade through shared module`

## Task 4 — `ModelResolver.resolve_full(profile_source=)` (D4)

- [ ] In `pipeline/resolver.py`, add keyword `profile_source: bool | None = None` to `resolve_full`; `None` uses the run's value; `resolve()` unchanged. The run-level `profile_source` still drives dispatch, summary and compact
- [ ] The backstop in `ModelResolver._resolved` uses the per-call value
- [ ] Tests (`tests/pipeline/test_resolver.py`): override True accepts a literal id the run-level False would reject; override False rejects one the run-level True would accept; `None` falls back to the run-level value; `resolve()` unaffected
  - [ ] Success: tests pass
- [ ] Commit: `feat: per-call profile source on resolve_full`

## Task 5 — Pipeline review action uses the shared helper (D3, D4)

- [ ] In `pipeline/actions/review.py`, replace the inline cascade with `resolve_review_profile(param, alias_profile, template)`, and pass `review_profile_source(param is not None, template)` to `resolver.resolve_full(..., profile_source=...)`
- [ ] No `"sdk"` review-profile literal remains in the file
- [ ] Tests (find the action's existing test file by grep): no `profile` param on a template declaring `profile:` runs on that profile; neither set and `default_review_profile` set runs on it; neither set and no config runs on sdk; explicit param still wins
  - [ ] Success: tests pass; `grep -rn '"sdk"' src/squadron/pipeline/actions/review.py src/squadron/cli/commands/review.py` finds nothing used as a profile default
- [ ] Commit: `fix: pipeline review step resolves profile like sq review (#184)`

## Task 6 — Parity test across both paths

- [ ] Add one parametrized test, over every `ReviewProfileSource`, that sets up the same template, model and config and asserts `sq review` and the pipeline review action select the same profile name
  - [ ] Success: test passes for all five sources
- [ ] Commit: `test: assert review profile parity between sq review and pipeline`

## Task 7 — One template lookup in classification (D4)

- [ ] In `pipeline/classification.py` add `_review_template(action_type, resolved_cfg) -> ReviewTemplate | None`. It **never raises**; an unknown name returns `None`
- [ ] `_review_template_model_fallback` uses it, so the labelling path (`action_model_candidate` → `action_model_label` → `_summarize_action_config`) behaves exactly as before
- [ ] Tests (`tests/pipeline/test_classification.py`): known template returned; unknown name returns `None` without raising; model fallback unchanged for known and unknown names
  - [ ] Success: tests pass; existing classification tests unchanged
- [ ] Commit: `refactor: single review template lookup in classification`

## Task 8 — Unknown review template fails before the run (D4)

- [ ] Add `UnknownReviewTemplateError(name, close_matches)` as a `ValueError` subclass (next to `UnknownModelAliasError`). Message: `unknown review template 'cod'; did you mean: code?`
- [ ] Add `_require_review_template(action_type, resolved_cfg) -> ReviewTemplate | None`: calls `_review_template`, raises the error when a fully resolved name returns `None`; skips a name still holding an unresolved placeholder
- [ ] `classify_pipeline` catches the error and collects it with the alias errors into the single `ClassificationError`; it never escapes classification
- [ ] Tests: unknown literal template fails before step 1; unknown template plus unknown alias reported in one message; placeholder name skipped; a review step whose template resolves only at run time to an unknown name fails through the review action's `KeyError` path with verbose labelling on, not from `action_model_label`; every built-in pipeline in `src/squadron/data/pipelines` classifies cleanly
  - [ ] Success: tests pass
- [ ] Commit: `feat: reject unknown review templates before the run`

## Task 9 — Review profile source in the alias check (D4, #175)

- [ ] `_collect_unknown_alias` takes `profile_source: bool` from its caller. For each `review` action the caller loads the template via `_require_review_template` and passes `review_profile_source(...)`; other action types keep `has_profile_param`
- [ ] Tests: a literal non-alias id with `default_review_profile` set passes classification for a review step; the same id with no profile source fails with the same message and close matches `sq review` gives; a template-declared `profile:` makes a literal id acceptable; non-review actions unchanged
  - [ ] Success: tests pass
- [ ] Commit: `fix: alias check uses the review step's real profile source (#175, #184)`

## Task 10 — `_classify_for_run` in `cli/commands/run.py` (D5)

- [ ] Add `_classify_for_run(definition, *, model_override, params, strict) -> PipelineClassification` owning policy (YAML `auth_policy` < `--strict`), `DefaultPoolBackend()`, the `ModelResolver(... profile_source=has_profile_param(params))`, and the `classify_pipeline` call; it raises `ClassificationError`
- [ ] `_run_pipeline_sdk` uses it in place of its inline block (its own pool backend for the authoritative resolver is unchanged); `--explain` uses it with `explain_params`; the second inline copy is deleted
  - [ ] Success: existing run and explain tests pass unchanged
- [ ] Commit: `refactor: share one classification helper between run and explain`

## Task 11 — `--dry-run` classifies (D5, #175)

- [ ] `--dry-run` calls `_classify_for_run` with params from `_assemble_params` and `_extract_model_override(model, param)`, and accepts `--strict` like the other paths
- [ ] On `ClassificationError` print the run path's message (`Error: Pipeline classification failed — …`) and exit 1 before rendering any step; on success render as today
- [ ] Tests: `review 931 --model glm-flash-low. --dry-run` exits 1 with `unknown model alias 'glm-flash-low.'; did you mean: glm-flash-low?`; a valid model renders the same step list as before; `--dry-run --strict` is accepted, raises the same errors as a strict run, otherwise renders the same step list; a real run with the bad alias fails before step 1 and the slot's existing review artifact is byte-identical afterwards (fixture file, compare bytes)
  - [ ] Success: tests pass
- [ ] Commit: `fix: sq run --dry-run runs the pre-run alias check (#175)`

## Task 12 — Part A validation

- [ ] Run the full test suite once, plus `ruff format`, `ruff check`, `pyright`
  - [ ] Success: all pass; zero pyright errors
- [ ] Commit any formatter changes: `style: format part A`  (skip if none)

---

## Part B — #188: git is the record of a merged slice

## Task 13 — `merged_slice_branches` predicate (D1, D10)

- [ ] In `pipeline/git_ops.py` add `merged_slice_branches(entries, target, cwd) -> set[int]`. Branch names come from the same helper the enter step uses (locate with grep; do not re-derive)
  - [ ] One `for-each-ref refs/heads` call for tips, one `rev-list --first-parent {target}` call, one `merge-base --is-ancestor` call per candidate
  - [ ] A slice is merged only when its tip is an ancestor of the target **and** not on the target's first-parent chain
  - [ ] A missing branch reads as not merged, with no log
  - [ ] Any timeout (`run_git` returns `None`) or unexpected exit (for `--is-ancestor`: not 0 or 1) logs ERROR via `logger.exception` naming the command and stderr, and raises `GitStateUnknownError`. Never returns an empty set on failure
- [ ] Docstring cites the `--no-ff` assertion at `tests/pipeline/test_branch_merge.py:88`
- [ ] Tests in `tests/pipeline/test_git_ops.py` (real temp repos): `--no-ff` merged → in the set; fast-forward merged → not; branch entered with no commits → not; missing branch → not; mixed set returns only merged. D10 rows with the fake/patched `run_git`: each of the three calls timing out and exiting non-zero raises `GitStateUnknownError` with the asserted ERROR record (target missing for `rev-list`)
  - [ ] Success: tests pass
- [ ] Commit: `feat: add merged_slice_branches predicate`

## Task 14 — Sources take `cwd` (D1)

- [ ] `SourceFn` gains keyword `cwd: str`; all four registered sources accept it (only `slices_ready_to_implement` uses it)
- [ ] `evaluate_each_source(source, params, cf_client, *, cwd)` passes it on
- [ ] Callers pass the cwd they already hold: executor `effective_cwd`, item resume `cwd`, the dry-run renderer (`run_dry_run.py`, from `run()`)
- [ ] Tests: each caller hands the source its cwd (fake source records it); existing source and executor tests updated for the new keyword
  - [ ] Success: tests pass; pyright clean
- [ ] Commit: `refactor: pass the run cwd to each-sources`

## Task 15 — `slices_ready_to_implement` treats merged slices as closed (D1)

- [ ] Call `merged_slice_branches(entries, target, cwd)` once. Target comes from `read_integration_target`
- [ ] Item loop skips `entry.index in merged`; `open_in_plan` excludes merged indexes; `in_plan` unchanged
- [ ] One WARNING per merged slice: `slice N: branch B is merged into T but cf reports S; treating it as complete. Check off its tasks to close it in cf.`
- [ ] A `GitStateUnknownError` from the predicate propagates, so the `each` step fails before any item runs, logged and reported as a cf failure in a source is today
- [ ] Tests (`tests/pipeline/test_sources.py`, temp repo + fake cf): merged unchecked slice A absent from items; dependent B carries no `flag_reason`; WARNING record asserted; open-per-cf, unmerged dependency still flagged exactly as before; source run with a `cwd` different from the process cwd gets that repo's answer; predicate failure fails the step before any item
  - [ ] Success: tests pass
- [ ] Commit: `fix: batch selection treats merged slices as complete (#188)`

## Task 16 — Item resume uses the predicate (D1)

- [ ] `_open_dependencies` counts a dependency complete if cf says so or the predicate reports it merged
- [ ] `_select_item` reconcile path: an item no longer selected reconciles to PASSED when the predicate reports it merged, whatever cf's status
- [ ] A predicate failure surfaces as the resume's error and changes no report record
- [ ] Tests (`tests/pipeline/test_item_resume_*.py`): resume of B runs with no `dependency A not complete`; resume of merged A reconciles to PASSED; unmerged open dependency still blocks; predicate failure leaves `report.json` unchanged
  - [ ] Success: tests pass
- [ ] Commit: `fix: item resume trusts git for merged slices (#188)`

## Task 17 — Part B validation

- [ ] Run the full test suite once, plus `ruff format`, `ruff check`, `pyright`
  - [ ] Success: all pass; zero pyright errors
- [ ] Commit any formatter changes: `style: format part B`  (skip if none)

---

## Part C — #186: lagging PR ref

## Task 18 — Models and errors (D7, D8, D9)

- [ ] `codehost/models.py`: add `RefAdjustment(role, reported_sha, used_sha, source, reason)` and `FetchedRange.adjustments: tuple[RefAdjustment, ...]` (default empty)
- [ ] `codehost/errors.py`: add `RENDERED_BY_CALLER` (the `extra` key constant); `RefMovedSinceResolutionError` gains `expected_source`/`actual_source` with the D7 message and hint `Rerun to resolve the pull request again.`; add `PullRequestHeadUnavailableError` (a `CodeHostError`, role HEAD) with the D7 message and hint
- [ ] Tests (`tests/codehost/`): message text names each source and sha; hints present; `adjustments` defaults to `()`
  - [ ] Success: tests pass
- [ ] Commit: `feat: add RefAdjustment and source-naming code host errors`

## Task 19 — Base fast-forward onto `adjustments` (D9)

- [ ] The #131 base fast-forward in `refs.py` records a `RefAdjustment` (role BASE) instead of a log-only note; its WARNING is tagged `extra={RENDERED_BY_CALLER: True}`
- [ ] Tests: existing #131 tests pass; the fast-forward case returns one adjustment with the reported and used shas
  - [ ] Success: tests pass
- [ ] Commit: `refactor: record base fast-forward as a ref adjustment`

## Task 20 — Primary fetch timeout (D10)

- [ ] In `refs.py`, convert `ProcessTimedOutError` on the primary `_fetch` into `HostCommandTimeoutError`, as `github_cli.py` does for `gh` calls
- [ ] Tests (fake `ProcessRunner`): primary fetch timeout raises `HostCommandTimeoutError`, not a traceback
  - [ ] Success: tests pass
- [ ] Commit: `fix: render primary PR fetch timeout as a code host error`

## Task 21 — Obtain the API head locally (D6 step 1)

- [ ] In `refs.py` add a helper that, given the API head sha, returns it as present locally: `cat-file -e <sha>^{commit}`; if absent, fetch `+<sha>:<api_local>` then `+<head_fallback_source>:<api_local>` (the second source is an argument, `head_fallback_sources: tuple[str, ...]`). `<api_local>` is a sibling of `head_local` in the per-PR namespace
- [ ] After each attempt `rev-parse <api_local>` must equal the API head sha; a mismatch rejects that attempt
- [ ] A fallback attempt catches `ProcessTimedOutError` and records `timed out after Ns`; non-zero exit records stderr. Each attempt logs DEBUG
- [ ] No attempt yields the sha: raise `PullRequestHeadUnavailableError` naming every source with its sha or reason (WARNING tagged `RENDERED_BY_CALLER`)
- [ ] Tests (fake runner; the API head sha **absent** locally before the fetch): sha already present → no fetch; fetch-by-sha succeeds; sha fetch `not our ref` then branch fetch succeeds; branch fetch returns a different sha → rejected; timeout on a fallback recorded as the reason; all fail → error naming each source
  - [ ] Success: tests pass
- [ ] Commit: `feat: fetch the API head by sha or head branch when the PR ref lags`

## Task 22 — Classify and use the API head (D6 step 2, D10)

- [ ] In `fetch_and_range`, when the PR-ref sha differs from the API head: call Task 21's helper first, then test whether the PR-ref sha is an ancestor of the API head (`merge-base --is-ancestor`). Ancestor → `update-ref head_local <api-sha>`, record a head `RefAdjustment`, build the range. Descends or unrelated → `RefMovedSinceResolutionError` naming both sources
- [ ] Only the exact API head sha is ever reviewed. `update-ref` failure or timeout renders `RefNotFetchableError`/`HostCommandTimeoutError`
- [ ] Tests, using the lagging fixture from the issue (PR ref one commit behind, branch and API at head, API sha absent locally until a fallback fetch): lag → range built on the API head with one adjustment; pushed after resolution → `RefMovedSinceResolutionError` hinting rerun; unrelated → same; ancestry timeout and non-0/1 exit answer "no" with the existing WARNING; `update-ref` failure and timeout
  - [ ] Success: tests pass; `uv run pytest tests/codehost -k lagging -v` selects the lag cases
- [ ] Commit: `fix: review the API head when refs/pull/N/head lags (#186)`

## Task 23 — GitHub adapter passes the head refspec (D6)

- [ ] `fetch_pull_request_refs` passes `refs/heads/<head_ref>` as `head_fallback_sources` to `fetch_and_range`; `refs.py` stays host-neutral (`test_import_boundaries.py` passes)
- [ ] Tests (`tests/codehost/test_github_cli.py`): the adapter passes the expected sources; a fork PR whose same-named base branch returns another sha is rejected by the sha check
  - [ ] Success: tests pass
- [ ] Commit: `feat: github adapter supplies head branch fallback refspec`

## Task 24 — `code_host_logging` context manager (D8)

- [ ] Add `code_host_logging(verbosity: int)` next to `render_code_host_error`. On entry: record the `squadron.codehost` logger level, add one stderr handler (format `%(levelname)s %(name)s: %(message)s`) with the tag filter, set level WARNING/INFO/DEBUG for verbosity 0/1/2+. On exit (`finally`): remove exactly that handler, restore the level. `propagate` untouched
- [ ] Filter drops `RENDERED_BY_CALLER` records below verbosity 2 and keeps them at 2+
- [ ] Nested entry is a no-op on entry and exit
- [ ] Tag the WARNINGs that precede a raised `CodeHostError` in the adapter and `refs.py` (and adjustment WARNINGs); tag nothing else
- [ ] Tests: tagged WARNING absent at verbosity 0 and 1, present at 2 with prefix; untagged WARNING reaches stderr at every verbosity; entering twice shows one handler inside and zero after, level restored; a raised `typer.Exit` inside still cleans up; records still reach `caplog`
  - [ ] Success: tests pass
- [ ] Commit: `feat: code host logging scope that prints each failure once`

## Task 25 — Wire the commands (D8, D9)

- [ ] `sq review pr`: wrap the body after `_resolve_verbosity(verbose)` in `with code_host_logging(verbosity):`. `sq pr show` and `sq pr create` use `code_host_logging(0)`; no new flags
- [ ] Print each `RefAdjustment` once, dim, on stderr: `head: refs/pull/49/head lags; reviewed ae1cbf2… fetched by sha`. The PR review artifact's provenance records the head sha actually reviewed
- [ ] Tests (`tests/cli/test_review_pr.py`, `test_pr_show.py`): a `CodeHostError` appears on stderr exactly once at default and `-v`; at `-vv` the tagged WARNING also appears; lag success prints one adjustment line and the artifact carries the API head sha; an untagged codehost WARNING still shows at default verbosity; a fetch timeout never produces a traceback
  - [ ] Success: tests pass
- [ ] Commit: `fix: print code host failures and ref adjustments once (#186)`

## Task 26 — Part C validation

- [ ] Run the full test suite once, plus `ruff format`, `ruff check`, `pyright`
  - [ ] Success: all pass; zero pyright errors
- [ ] Commit any formatter changes: `style: format part C`  (skip if none)

---

## Part D — Docs and verification

## Task 27 — Documentation

- [ ] `docs/PIPELINES.md`: merged slices count as complete in `implement-plan` and item resume (git is the record); review profile cascade shared with `sq review`; unknown review template and alias rejected pre-run, including `--dry-run`
- [ ] `CHANGELOG.md`: short user-facing bullets for the four fixes; technical detail stays in DEVLOG
  - [ ] Success: docs match behavior
- [ ] Commit: `docs: document pipeline run correctness fixes`

## Task 28 — Live walkthrough

- [ ] Run Verification Walkthrough steps 1, 3 and 4 from the slice design (step 4: the unit fixture via `uv run pytest tests/codehost -k lagging -v`) with `CLAUDECODE` unset and `uv run`; always pass `--model`
- [ ] Step 2: needs a non-SDK profile with credentials already configured. With one, run both commands and show `profile=…` in both headers; restore the config key afterwards. Without one, run only the unset half (both fail with the same message) and say so in the DEVLOG
- [ ] Record each step's command and key output line in the DEVLOG entry
  - [ ] Success: each step matches the design; any divergence is fixed (with a test) or filed as a GitHub issue linked from the DEVLOG
- [ ] Commit: `docs: add slice 934 implementation DEVLOG entry`

## Task 29 — Close out

- [ ] Set this file's `status: complete`; slice design `status: complete`; check off 934 in `900-slices.maintenance-and-refactoring.md`
- [ ] Commit: `docs: mark slice 934 complete`
  - [ ] Success: commit on the slice branch; tree clean

---

## Notes

- No merge task is listed: Phase 7 merges the slice branch into the target after the code review. The merge or a closing comment linking the slice closes #175, #184, #186, #188.
